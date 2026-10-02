from __future__ import annotations

from pymongo.collection import Collection

from backend.database.mongodb import get_db

RESEARCH_COLLECTION = "research_sessions"
SHOPPING_SESSIONS_COLLECTION = "shopping_sessions"
SHOPPING_SEARCHES_COLLECTION = "shopping_searches"
FLIGHT_SESSIONS_COLLECTION = "flight_sessions"
FLIGHT_SEARCHES_COLLECTION = "flight_searches"
HOTEL_SESSIONS_COLLECTION = "hotel_sessions"
HOTEL_SEARCHES_COLLECTION = "hotel_searches"
TRIP_SESSIONS_COLLECTION = "trip_sessions"
JOB_PROFILES_COLLECTION = "job_profiles"
JOB_SESSIONS_COLLECTION = "job_sessions"
JOB_SEARCHES_COLLECTION = "job_searches"
JOB_ALERTS_COLLECTION = "job_alerts"


def get_research_collection() -> Collection:
    return get_db()[RESEARCH_COLLECTION]


def ensure_research_indexes() -> None:
    col = get_research_collection()
    col.create_index([("user_id", 1), ("updated_at", -1)])
    col.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    col.create_index([("user_id", 1), ("created_at", -1)])


def get_shopping_sessions_collection() -> Collection:
    return get_db()[SHOPPING_SESSIONS_COLLECTION]


def get_shopping_searches_collection() -> Collection:
    return get_db()[SHOPPING_SEARCHES_COLLECTION]


def ensure_shopping_indexes() -> None:
    sessions = get_shopping_sessions_collection()
    sessions.create_index([("user_id", 1), ("updated_at", -1)])
    sessions.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    searches = get_shopping_searches_collection()
    searches.create_index([("user_id", 1), ("session_id", 1), ("created_at", -1)])
    searches.create_index([("session_id", 1), ("created_at", -1)])


def get_flight_sessions_collection() -> Collection:
    return get_db()[FLIGHT_SESSIONS_COLLECTION]


def get_flight_searches_collection() -> Collection:
    return get_db()[FLIGHT_SEARCHES_COLLECTION]


def ensure_flight_indexes() -> None:
    sessions = get_flight_sessions_collection()
    sessions.create_index([("user_id", 1), ("updated_at", -1)])
    sessions.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    searches = get_flight_searches_collection()
    searches.create_index([("user_id", 1), ("session_id", 1), ("created_at", -1)])
    searches.create_index([("session_id", 1), ("created_at", -1)])


def get_hotel_sessions_collection() -> Collection:
    return get_db()[HOTEL_SESSIONS_COLLECTION]


def get_hotel_searches_collection() -> Collection:
    return get_db()[HOTEL_SEARCHES_COLLECTION]


def ensure_hotel_indexes() -> None:
    sessions = get_hotel_sessions_collection()
    sessions.create_index([("user_id", 1), ("updated_at", -1)])
    sessions.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    searches = get_hotel_searches_collection()
    searches.create_index([("user_id", 1), ("session_id", 1), ("created_at", -1)])
    searches.create_index([("session_id", 1), ("created_at", -1)])


def get_trip_sessions_collection() -> Collection:
    return get_db()[TRIP_SESSIONS_COLLECTION]


def ensure_trip_indexes() -> None:
    col = get_trip_sessions_collection()
    col.create_index([("user_id", 1), ("updated_at", -1)])
    col.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    col.create_index([("user_id", 1), ("status", 1)])


def get_job_profiles_collection() -> Collection:
    return get_db()[JOB_PROFILES_COLLECTION]


def get_job_sessions_collection() -> Collection:
    return get_db()[JOB_SESSIONS_COLLECTION]


def get_job_searches_collection() -> Collection:
    return get_db()[JOB_SEARCHES_COLLECTION]


def get_job_alerts_collection() -> Collection:
    return get_db()[JOB_ALERTS_COLLECTION]


def ensure_job_indexes() -> None:
    # One profile doc per user — no session_id, this is the onboarding store.
    profiles = get_job_profiles_collection()
    profiles.create_index([("user_id", 1)], unique=True)
    sessions = get_job_sessions_collection()
    sessions.create_index([("user_id", 1), ("updated_at", -1)])
    sessions.create_index([("user_id", 1), ("session_id", 1)], unique=True)
    searches = get_job_searches_collection()
    searches.create_index([("user_id", 1), ("session_id", 1), ("created_at", -1)])
    searches.create_index([("session_id", 1), ("created_at", -1)])
    alerts = get_job_alerts_collection()
    # Exactly one alert per user. The unique index enforces the product rule at
    # the storage layer, so a race can't leave two behind.
    alerts.create_index([("user_id", 1)], unique=True)
    # n8n polls /due constantly; without this it is a full collection scan.
    alerts.create_index([("next_run_at", 1), ("is_active", 1)])
    # /run addresses an alert by its public id, which never changes on edit.
    alerts.create_index([("alert_id", 1)], unique=True)
