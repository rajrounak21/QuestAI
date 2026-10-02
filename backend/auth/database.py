from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection

from backend.auth import config

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not config.MONGODB_URI:
            raise RuntimeError("MONGODB_URI missing in .env")
        # tz_aware=True: BSON datetimes are always UTC, but pymongo returns them
        # naive by default. A naive value serialises to "2026-10-02T07:15:00"
        # with no offset, and the browser then parses that as *local* time — a
        # 12:45 IST alert rendered as "7:15 am". Returning UTC-aware datetimes
        # makes isoformat() emit "+00:00" so the frontend converts correctly.
        #
        # Safe: every reader already guards with `if X.tzinfo is None`, which
        # simply becomes a no-op once the values arrive aware.
        _client = MongoClient(config.MONGODB_URI, tz_aware=True)
    return _client


def get_users_collection() -> Collection:
    client = get_client()
    # Use default DB from URI, fallback to questai
    try:
        db = client.get_default_database()
    except Exception:
        db = client["questai"]
    users = db["users"]
    # Ensure unique email index (safe to call repeatedly)
    try:
        users.create_index("email", unique=True)
    except Exception:
        pass
    return users
