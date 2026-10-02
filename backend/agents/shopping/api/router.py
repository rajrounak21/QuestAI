from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.shopping.main import run_shopping_search
from backend.agents.shopping.services.location import resolve_location
from backend.auth.security import get_current_user
from backend.database.shopping_sessions import (
    delete_session,
    get_session_with_latest_search,
    insert_search,
    list_session_history,
    upsert_session_on_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

SOURCES = ["google_shopping", "amazon"]


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None
    location: str = "in"


class SearchAgainIn(BaseModel):
    query: str | None = None
    location: str | None = None


def _run_and_shape(
    query: str, location: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Sync API call (5-7s). Raises HTTPException on agent-level failure."""
    result = run_shopping_search(query, location=location)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    if result.get("follow_up_question"):
        raise HTTPException(status_code=422, detail=result["follow_up_question"])
    products = result.get("products") or []
    return products, result.get("total_results", len(products))


def _persist(
    user_id: str,
    session_id: str,
    query: str,
    products: list[dict[str, Any]],
    location_code: str,
    location_label: str,
) -> dict[str, Any]:
    flat = [flatten_product_dict(p) for p in products]
    upsert_session_on_search(
        user_id, session_id, query, SOURCES, len(flat), location_code, location_label
    )
    insert_search(
        user_id, session_id, query, SOURCES, flat, location_code, location_label
    )
    return {
        "session_id": session_id,
        "query": query,
        "products": flat,
        "product_count": len(flat),
        "sources": SOURCES,
        "location": location_code,
        "location_label": location_label,
    }


def flatten_product_dict(p: dict[str, Any]) -> dict[str, Any]:
    # Graph returns model_dump() dicts with nested source.engine â€” flatten it.
    src = p.get("source")
    if isinstance(src, dict):
        p = {**p, "source": src.get("engine", "google_shopping")}
    elif not src:
        p = {**p, "source": "google_shopping"}
    return p


@router.post("/search")
def search(body: SearchIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    session_id = body.session_id or str(uuid.uuid4())
    loc_code, loc = resolve_location(body.location)
    logger.info(f"Shopping search user={user['id']} session={session_id} loc={loc_code} q={query[:60]}")
    products, _ = _run_and_shape(query, loc)
    return _persist(user["id"], session_id, query, products, loc_code, loc["label"])


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
        raise HTTPException(status_code=404, detail="shopping session not found")
    session["_id"] = str(session["_id"])
    if latest:
        latest["_id"] = str(latest["_id"])
    return {"session": session, "latest": latest}


@router.post("/{session_id}/search")
def search_again(
    session_id: str, body: SearchAgainIn, user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Fresh API call for stale prices. Appends a new search doc, touches session."""
    session, latest = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="shopping session not found")
    query = (body.query or session.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")
    # Search-again reuses the session location unless the user picked a new one.
    loc_code, loc = resolve_location(
        body.location or session.get("location") or (latest or {}).get("location")
    )
    products, _ = _run_and_shape(query, loc)
    return _persist(user["id"], session_id, query, products, loc_code, loc["label"])


@router.delete("/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    deleted = delete_session(user["id"], session_id)
    return {"deleted": deleted, "session_id": session_id}
