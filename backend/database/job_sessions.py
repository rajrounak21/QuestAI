from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_PERSIST_JOBS = 60

SOURCES = ["google_jobs"]

SESSION_HISTORY_PROJECTION = {
    "session_id": 1,
    "title": 1,
    "query": 1,
    "sources": 1,
    "job_count": 1,
    "target_roles": 1,
    "locations": 1,
    "work_mode": 1,
    "last_search_at": 1,
    "updated_at": 1,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_title(query: str) -> str:
    q = (query or "").strip()
    return q[:60] if len(q) <= 60 else q[:57] + "..."


def upsert_session_on_search(
    user_id: str,
    session_id: str,
    query: str,
    job_count: int,
    target_roles: list[str] | None = None,
    locations: list[str] | None = None,
    work_mode: list[str] | None = None,
) -> None:
    """One session, many searches. First search creates the session doc."""
    from backend.database.collections import get_job_sessions_collection

    now = _utcnow()
    get_job_sessions_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {
                "sources": SOURCES,
                "job_count": job_count,
                "target_roles": list(target_roles or []),
                "locations": list(locations or []),
                "work_mode": list(work_mode or []),
                "last_search_at": now,
                "updated_at": now,
                # Follows the most recent search, not the first - see the note
                # in hotel_sessions.py.
                "title": make_title(query),
                "query": query,
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
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    from backend.database.collections import get_job_searches_collection

    doc: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "sources": SOURCES,
        "jobs": (jobs or [])[:MAX_PERSIST_JOBS],
        "job_count": len(jobs or []),
        "created_at": _utcnow(),
    }
    get_job_searches_collection().insert_one(doc)
    return doc


def list_session_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    from backend.database.collections import get_job_sessions_collection

    cur = (
        get_job_sessions_collection()
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
        get_job_searches_collection,
        get_job_sessions_collection,
    )

    session = get_job_sessions_collection().find_one(
        {"user_id": user_id, "session_id": session_id}
    )
    if not session:
        return None, None
    latest = get_job_searches_collection().find_one(
        {"user_id": user_id, "session_id": session_id},
        sort=[("created_at", -1)],
    )
    return session, latest


def delete_session(user_id: str, session_id: str) -> bool:
    from backend.database.collections import (
        get_job_searches_collection,
        get_job_sessions_collection,
    )

    get_job_searches_collection().delete_many(
        {"user_id": user_id, "session_id": session_id}
    )
    res = get_job_sessions_collection().delete_one(
        {"user_id": user_id, "session_id": session_id}
    )
    return res.deleted_count > 0
