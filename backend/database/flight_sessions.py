from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_PERSIST_FLIGHTS = 50

SESSION_HISTORY_PROJECTION = {
    "session_id": 1,
    "title": 1,
    "query": 1,
    "flight_count": 1,
    "origin": 1,
    "destination": 1,
    "departure_date": 1,
    "last_search_at": 1,
    "updated_at": 1,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_title(query: str) -> str:
    q = (query or "").strip()
    return q[:70] if len(q) <= 70 else q[:67] + "..."


def _params_summary(params: dict[str, Any] | None) -> dict[str, Any]:
    p = params or {}
    return {
        "origin": p.get("origin", ""),
        "destination": p.get("destination", ""),
        "departure_date": p.get("departure_date", ""),
    }


def upsert_session_on_search(
    user_id: str,
    session_id: str,
    query: str,
    flight_count: int,
    params: dict[str, Any] | None = None,
) -> None:
    """One session, many searches. First search creates the session doc."""
    from backend.database.collections import get_flight_sessions_collection

    now = _utcnow()
    summary = _params_summary(params)
    get_flight_sessions_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {
                "flight_count": flight_count,
                "last_search_at": now,
                "updated_at": now,
                **summary,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "session_id": session_id,
                "title": make_title(query),
                "query": query,
                "created_at": now,
            },
        },
        upsert=True,
    )


def insert_search(
    user_id: str,
    session_id: str,
    query: str,
    flights: list[dict[str, Any]],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.database.collections import get_flight_searches_collection

    doc: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "params": params or {},
        "flights": (flights or [])[:MAX_PERSIST_FLIGHTS],
        "flight_count": len(flights or []),
        "created_at": _utcnow(),
    }
    get_flight_searches_collection().insert_one(doc)
    return doc


def list_session_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    from backend.database.collections import get_flight_sessions_collection

    cur = (
        get_flight_sessions_collection()
        .find({"user_id": user_id}, SESSION_HISTORY_PROJECTION)
        .sort("updated_at", -1)
        .limit(max(1, min(limit, 50)))
    )
    return list(cur)


def get_session_with_latest_search(
    user_id: str, session_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """History open = Mongo only, zero SerpApi cost."""
    from backend.database.collections import (
        get_flight_searches_collection,
        get_flight_sessions_collection,
    )

    session = get_flight_sessions_collection().find_one(
        {"user_id": user_id, "session_id": session_id}
    )
    if not session:
        return None, None
    latest = get_flight_searches_collection().find_one(
        {"user_id": user_id, "session_id": session_id},
        sort=[("created_at", -1)],
    )
    return session, latest


def delete_session(user_id: str, session_id: str) -> bool:
    from backend.database.collections import (
        get_flight_searches_collection,
        get_flight_sessions_collection,
    )

    get_flight_searches_collection().delete_many(
        {"user_id": user_id, "session_id": session_id}
    )
    res = get_flight_sessions_collection().delete_one(
        {"user_id": user_id, "session_id": session_id}
    )
    return res.deleted_count > 0
