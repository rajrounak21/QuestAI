from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.travel.hotels.main import run_hotel_search
from backend.auth.security import get_current_user
from backend.database.hotel_sessions import (
    delete_session,
    get_session_with_latest_search,
    insert_search,
    list_session_history,
    upsert_session_on_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hotels", tags=["hotels"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None


class SearchAgainIn(BaseModel):
    query: str | None = None


def _run_and_shape(query: str) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    """Sync SerpApi call (5-8s). Raises HTTPException on agent-level failure."""
    result = run_hotel_search(query)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    if result.get("follow_up_question"):
        raise HTTPException(status_code=422, detail=result["follow_up_question"])
    hotels = result.get("hotels") or []
    return hotels, result.get("total_results", len(hotels)), result.get("extracted_params")


def _persist(
    user_id: str,
    session_id: str,
    query: str,
    hotels: list[dict[str, Any]],
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    upsert_session_on_search(user_id, session_id, query, len(hotels), params)
    insert_search(user_id, session_id, query, hotels, params)
    return {
        "session_id": session_id,
        "query": query,
        "hotels": hotels,
        "hotel_count": len(hotels),
        "params": params,
    }


@router.post("/search")
def search(body: SearchIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    session_id = body.session_id or str(uuid.uuid4())
    logger.info(f"Hotel search user={user['id']} session={session_id} q={query[:80]}")
    hotels, _, params = _run_and_shape(query)
    return _persist(user["id"], session_id, query, hotels, params)


@router.get("/history")
def history(limit: int = 20, user: dict = Depends(get_current_user)):
    items = list_session_history(user["id"], limit=limit)
    for it in items:
        it["_id"] = str(it["_id"])
    return {"items": items}


@router.get("/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    session, latest = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="hotel session not found")
    session["_id"] = str(session["_id"])
    if latest:
        latest["_id"] = str(latest["_id"])
    return {"session": session, "latest": latest}


@router.post("/{session_id}/search")
def search_again(
    session_id: str, body: SearchAgainIn, user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Fresh SerpApi call for stale prices. Appends a new search doc."""
    session, _ = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="hotel session not found")
    query = (body.query or session.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    hotels, _, params = _run_and_shape(query)
    return _persist(user["id"], session_id, query, hotels, params)


@router.delete("/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    deleted = delete_session(user["id"], session_id)
    return {"deleted": deleted, "session_id": session_id}
