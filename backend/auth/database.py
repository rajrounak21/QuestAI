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
        _client = MongoClient(config.MONGODB_URI)
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
