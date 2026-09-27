from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_PERSIST_EVIDENCE = 15
MAX_RELOAD_EVIDENCE = 50
MAX_RELOAD_SEARCHES = 30
MAX_RELOAD_CONVERSATION = 10

# Dashboard card needs only these fields.
HISTORY_PROJECTION = {
    "query": 1,
    "executive_summary": 1,
    "updated_at": 1,
    "session_id": 1,
    "status": 1,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_research_doc(
    user_id: str,
    session_id: str,
    query: str,
    parent_session_id: str | None = None,
) -> dict[str, Any]:
    """Fresh topic = fresh doc. query/research_goal frozen from #1."""
    now = _utcnow()
    return {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "research_goal": query,
        "status": "running",
        "parent_session_id": parent_session_id,
        "answer": "",
        "executive_summary": "",
        "report": None,
        "evidence": [],
        "searches": [],
        "conversation": [],
        "created_at": now,
        "updated_at": now,
    }


def clean_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip validator internals. Keep quality/issues_count only."""
    if not report:
        return None
    notes = report.get("validation_notes") or {}
    return {
        "goal": report.get("goal", ""),
        "executive_summary": report.get("executive_summary", ""),
        "findings": report.get("findings", []),
        "comparison": report.get("comparison", ""),
        "recent_developments": report.get("recent_developments", ""),
        "limitations": report.get("limitations", ""),
        "sources": report.get("sources", []),
        "validation_notes": {
            "overall_quality": notes.get("overall_quality", "unknown"),
            "issues_count": notes.get("issues_count", 0),
        },
    }


def build_completion_update(
    report: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    searches: list[dict[str, Any]],
    user_text: str,
    assistant_answer: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns ($set, $push) payloads for completing one research run."""
    cleaned = clean_report(report)
    set_doc: dict[str, Any] = {
        "status": "completed",
        "answer": assistant_answer,
        "executive_summary": (report or {}).get("executive_summary", ""),
        "report": cleaned,
        "evidence": (evidence or [])[:MAX_PERSIST_EVIDENCE],
        "searches": searches or [],
        "updated_at": _utcnow(),
    }
    push_doc: dict[str, Any] = {
        "conversation": {
            "user": user_text,
            "assistant": assistant_answer,
            "at": _utcnow(),
        }
    }
    return set_doc, push_doc


def doc_to_session_data(doc: dict[str, Any] | None, fallback_session_id: str):
    """Rebuild in-memory SessionData from a Mongo doc.

    This is the topic_check connection point: route_session() takes a
    SessionData, so the API layer loads it via this helper first
    (capped: evidence[-50], searches[-30], conversation[-10]).
    Fresh session (no doc) -> empty conversation -> route_session skips check.
    """
    from backend.agents.research.memory.session import SessionData

    if not doc:
        return SessionData(session_id=fallback_session_id)
    return SessionData(
        session_id=doc.get("session_id", fallback_session_id),
        research_goal=doc.get("research_goal", ""),
        research_plan=None,  # v1: full plan not persisted, replanned per run
        searches=(doc.get("searches") or [])[-MAX_RELOAD_SEARCHES:],
        sources=[],
        evidence=(doc.get("evidence") or [])[-MAX_RELOAD_EVIDENCE:],
        gaps=[],
        conversation=(doc.get("conversation") or [])[-MAX_RELOAD_CONVERSATION:],
    )


# ---- Thin DB ops (called by API layer later, not by the agent) ----

def insert_new_session(
    user_id: str,
    session_id: str,
    query: str,
    parent_session_id: str | None = None,
) -> dict[str, Any]:
    from backend.database.collections import get_research_collection

    doc = new_research_doc(user_id, session_id, query, parent_session_id)
    get_research_collection().insert_one(doc)
    return doc


def get_session_doc(user_id: str, session_id: str) -> dict[str, Any] | None:
    from backend.database.collections import get_research_collection

    return get_research_collection().find_one(
        {"user_id": user_id, "session_id": session_id}
    )


def list_history(user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    from backend.database.collections import get_research_collection

    cur = (
        get_research_collection()
        .find({"user_id": user_id}, HISTORY_PROJECTION)
        .sort("updated_at", -1)
        .limit(limit)
    )
    return list(cur)


def complete_session(
    user_id: str,
    session_id: str,
    report: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    searches: list[dict[str, Any]],
    user_text: str,
    assistant_answer: str,
) -> None:
    from backend.database.collections import get_research_collection

    set_doc, push_doc = build_completion_update(
        report, evidence, searches, user_text, assistant_answer
    )
    get_research_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {"$set": set_doc, "$push": push_doc},
    )
