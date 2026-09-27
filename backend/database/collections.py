from __future__ import annotations

from pymongo.collection import Collection

from backend.database.mongodb import get_db

RESEARCH_COLLECTION = "research_sessions"


def get_research_collection() -> Collection:
    return get_db()[RESEARCH_COLLECTION]


def ensure_research_indexes() -> None:
    col = get_research_collection()
    col.create_index([("user_id", 1), ("updated_at", -1)])
    col.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    col.create_index([("user_id", 1), ("created_at", -1)])
