from __future__ import annotations

from pymongo.database import Database

from backend.auth.database import get_client


def get_db() -> Database:
    """Shared DB handle. Reuses the auth singleton client — no new connection."""
    client = get_client()
    try:
        return client.get_default_database()
    except Exception:
        return client["questai"]
