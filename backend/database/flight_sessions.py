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
                "title": make_title(query),
                "query": query,
                **summary,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "session_id": session_id,
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

    stored = (flights or [])[:MAX_PERSIST_FLIGHTS]
    doc: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "params": params or {},
        "flights": stored,
        "flight_count": len(stored),
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


def list_session_searches(user_id: str, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Every search run inside one session, newest first.

    Each search is its own row. Flights are left out here - this backs a compact
    list, and a chosen search is loaded on its own via get_session_search() so
    opening one never pulls every search's results at once.
    """
    from backend.database.collections import get_flight_searches_collection

    cur = get_flight_searches_collection().aggregate([
        {"$match": {"user_id": user_id, "session_id": session_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": max(1, min(limit, 50))},
        {"$project": {
            "_id": 1,
            "query": 1,
            "created_at": 1,
            "flight_count": {"$size": {"$ifNull": ["$flights", []]}},
        }},
    ])
    items = []
    for doc in cur:
        items.append({
            "search_id": str(doc["_id"]),
            "query": doc.get("query", ""),
            "flight_count": doc.get("flight_count", 0),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
        })
    return items


def get_session_search(
    user_id: str, session_id: str, search_id: str
) -> dict[str, Any] | None:
    """One search from a session, with its flights.

    Scoped by session_id as well as _id so a search id from another session
    cannot be read by guessing it.
    """
    from bson import ObjectId
    from bson.errors import InvalidId

    from backend.database.collections import get_flight_searches_collection

    try:
        oid = ObjectId(search_id)
    except (InvalidId, TypeError):
        return None
    return get_flight_searches_collection().find_one(
        {"_id": oid, "user_id": user_id, "session_id": session_id}
    )


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
