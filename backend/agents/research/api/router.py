from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth.security import get_current_user
from backend.database.collections import get_research_collection
from backend.database.research_sessions import (
    complete_session,
    doc_to_session_data,
    insert_new_session,
    list_history,
)
from backend.agents.research.memory.session import build_context_for_question
from backend.agents.research.services.progress import clear_target, report, set_target
from backend.agents.research.services.topic_check import route_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


class RunIn(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None
    force_new: bool = False
    force_continue: bool = False
    max_rounds: int = 3


class RunAccepted(BaseModel):
    session_id: str
    status: str = "running"


class ConfirmOut(BaseModel):
    needs_confirm: bool = True
    session_id: str
    proposed_new_goal: str


def _run_and_persist(
    user_id: str,
    session_id: str,
    raw_query: str,
    effective_query: str,
    max_rounds: int,
) -> None:
    """Blocking graph run in a worker thread. Never raises to the client."""
    from backend.agents.research.main import run_research
    from backend.database.research_sessions import set_progress

    col = get_research_collection()
    token = set_target(user_id, session_id)
    try:
        report("planning", "Starting research")
        # Scratch uuid: keeps server's in-memory SessionMemory out of the
        # persistence path (Mongo doc is the source of truth, no double context).
        result = run_research(effective_query, session_id=str(uuid.uuid4()), max_rounds=max_rounds)
        complete_session(
            user_id=user_id,
            session_id=session_id,
            report=result.get("report"),
            evidence=result.get("evidence", []),
            searches=result.get("searches_performed", []),
            user_text=raw_query,
            assistant_answer=result.get("formatted", ""),
        )
        set_progress(user_id, session_id, "done", "Report ready")
    except Exception as e:
        logger.exception(f"Research run failed session={session_id}: {e}")
        col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"status": "failed", "error": str(e)[:500]}},
        )
        set_progress(user_id, session_id, "failed", str(e)[:200])
    finally:
        clear_target(token)


@router.post("/run", status_code=202)
async def run(body: RunIn, tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    col = get_research_collection()

    session_id = body.session_id or str(uuid.uuid4())
    doc = col.find_one({"user_id": user_id, "session_id": session_id})

    if doc and doc.get("status") == "running" and not (body.force_new or body.force_continue):
        raise HTTPException(status_code=409, detail={"message": "research already running", "session_id": session_id})

    session = doc_to_session_data(doc, session_id)
    route = route_session(session, body.query, force_new=body.force_new, force_continue=body.force_continue)
    action = route["action"]

    if action == "confirm":
        return ConfirmOut(session_id=session_id, proposed_new_goal=body.query)

    if action == "new":
        new_id = route["session_id"]
        insert_new_session(user_id, new_id, route.get("new_goal", body.query), parent_session_id=session_id)
        tasks.add_task(asyncio.to_thread, _run_and_persist, user_id, new_id, body.query, body.query, body.max_rounds)
        return RunAccepted(session_id=new_id)

    # fresh / continue
    if action == "fresh":
        insert_new_session(user_id, session_id, body.query)
        effective = body.query
    else:
        effective = build_context_for_question(session, body.query)
        col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"status": "running"}},
        )
    tasks.add_task(asyncio.to_thread, _run_and_persist, user_id, session_id, body.query, effective, body.max_rounds)
    return RunAccepted(session_id=session_id)


@router.get("/history")
async def history(limit: int = 5, user: dict = Depends(get_current_user)):
    items = list_history(user["id"], limit=min(limit, 50))
    for it in items:
        it["_id"] = str(it["_id"])
    return {"items": items}


@router.get("/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    col = get_research_collection()
    doc = col.find_one({"user_id": user["id"], "session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="session not found")
    doc["_id"] = str(doc["_id"])
    return doc
