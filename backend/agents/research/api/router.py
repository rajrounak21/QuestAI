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
    heal_stale,
    insert_new_session,
    is_stale,
    list_history,
    mark_running,
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
    max_rounds: int = 1


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
    from backend.agents.research.main import run_research, _format_report
    from backend.database.research_sessions import set_progress, doc_to_session_data
    from backend.agents.research.services.progress import ResearchCancelledError, check_cancellation
    from backend.agents.research.services.complexity import classify_complexity
    from backend.agents.research.services.llm import init_llm
    from backend.agents.research.graph.nodes.synthesizer import synthesizer_node
    from backend.agents.research.graph.nodes.validator import validator_node

    col = get_research_collection()
    token = set_target(user_id, session_id)
    try:
        check_cancellation()
        doc = col.find_one({"user_id": user_id, "session_id": session_id})
        session = doc_to_session_data(doc, session_id)

        # 1. Classify complexity route
        route = classify_complexity(raw_query, session)
        logger.info(f"Executing research route: '{route}' for query: {raw_query[:60]}")

        if route == "direct":
            report("synthesizing", "Answering directly")
            llm = init_llm(temperature=0.2, max_tokens=2048)
            prompt = f"User Question: {raw_query}\n\nGoal: {session.research_goal or raw_query}\n\nProvide a concise, direct, helpful answer in 2-4 structured paragraphs."
            raw_resp = llm.invoke(prompt)
            answer_text = raw_resp.content if hasattr(raw_resp, "content") else str(raw_resp)
            direct_report = {
                "goal": session.research_goal or raw_query,
                "executive_summary": answer_text,
                "findings": [],
                "comparison": "",
                "recent_developments": "",
                "limitations": "",
                "sources": [],
            }
            formatted = _format_report(direct_report)
            result = {
                "report": direct_report,
                "evidence": session.evidence,
                "searches_performed": session.searches,
                "formatted": formatted,
            }
        elif route == "evidence":
            report("synthesizing", "Synthesizing from gathered evidence")
            synth_state = {
                "user_query": session.research_goal or raw_query,
                "research_plan": session.research_plan or {"goal": session.research_goal, "sub_questions": []},
                "evidence": session.evidence,
                "identified_gaps": [],
                "resynthesis_count": 0,
            }
            synth_res = synthesizer_node(synth_state)
            val_res = validator_node({**synth_state, **synth_res})
            report_dict = val_res.get("final_report") or synth_res.get("final_report")
            formatted = _format_report(report_dict) if report_dict else ""
            result = {
                "report": report_dict,
                "evidence": session.evidence,
                "searches_performed": session.searches,
                "formatted": formatted,
            }
        else:
            # Full deep research graph
            report("planning", "Starting deep research")
            result = run_research(effective_query, session_id=str(uuid.uuid4()), max_rounds=max_rounds)

        cur = col.find_one({"user_id": user_id, "session_id": session_id}, {"status": 1})
        if not cur or cur.get("status") == "cancelled":
            logger.info(f"Research run cancelled or deleted by user session={session_id}, dropping result")
            return

        complete_session(
            user_id=user_id,
            session_id=session_id,
            report=result.get("report"),
            evidence=result.get("evidence", []),
            searches=result.get("searches_performed", []),
            user_text=raw_query,
            assistant_answer=result.get("formatted", ""),
            route=route,
        )
        set_progress(user_id, session_id, "done", "Report ready")
    except ResearchCancelledError:
        logger.info(f"Research run immediately stopped due to cancellation or deletion session={session_id}")
        cur = col.find_one({"user_id": user_id, "session_id": session_id}, {"status": 1})
        if cur:
            col.update_one(
                {"user_id": user_id, "session_id": session_id},
                {"$set": {"status": "cancelled"}},
            )
            set_progress(user_id, session_id, "cancelled", "Cancelled by user")
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

    if doc and doc.get("status") == "running":
        if is_stale(doc) or heal_stale(user_id, session_id):
            doc = col.find_one({"user_id": user_id, "session_id": session_id})
        elif not (body.force_new or body.force_continue):
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
        mark_running(user_id, session_id)
    tasks.add_task(asyncio.to_thread, _run_and_persist, user_id, session_id, body.query, effective, body.max_rounds)
    return RunAccepted(session_id=session_id)


@router.get("/history")
async def history(limit: int = 5, user: dict = Depends(get_current_user)):
    items = list_history(user["id"], limit=min(limit, 50))
    for it in items:
        it["_id"] = str(it["_id"])
    return {"items": items}


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str, user: dict = Depends(get_current_user)):
    col = get_research_collection()
    res = col.update_one(
        {"user_id": user["id"], "session_id": session_id, "status": "running"},
        {"$set": {"status": "cancelled"}},
    )
    return {"cancelled": res.modified_count > 0, "session_id": session_id}


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    col = get_research_collection()
    res = col.delete_one({"user_id": user["id"], "session_id": session_id})
    return {"deleted": res.deleted_count > 0, "session_id": session_id}


@router.get("/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    col = get_research_collection()
    heal_stale(user["id"], session_id)
    doc = col.find_one({"user_id": user["id"], "session_id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="session not found")
    doc["_id"] = str(doc["_id"])
    return doc
