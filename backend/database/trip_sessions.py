from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STALE_RUN_MINUTES = 10

MAX_TRIP_SEARCHES = 20
CONTINUE_BUMP = 10
SEARCH_COSTS = {"flights": 1, "hotels": 1, "research": 5}

# History cards need only these fields.
HISTORY_PROJECTION = {
    "session_id": 1,
    "title": 1,
    "query": 1,
    "origin": 1,
    "destination": 1,
    "departure_date": 1,
    "return_date": 1,
    "status": 1,
    "updated_at": 1,
    "trip.origin": 1,
    "trip.destination": 1,
    "trip.departure_date": 1,
    "trip.return_date": 1,
    "trip.duration_days": 1,
    "trip.travelers": 1,
    "trip.budget.max_total": 1,
    "trip.budget.currency": 1,
}

# Terminal states — polling stops.
TERMINAL = ("ready", "awaiting_input", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_title(query: str, origin: str = "", destination: str = "") -> str:
    """A trip's label.

    The route, not just the destination: two saved trips to the same city are
    indistinguishable otherwise ("Mumbai", "Mumbai"), which is exactly the
    confusion in the Recent list. Falls back to the destination alone, then to
    the raw query.
    """
    o = (origin or "").strip()
    d = (destination or "").strip()
    if o and d:
        base = f"{o} to {d}"
    else:
        base = d or o or (query or "").strip()
    q = base[:70] if len(base) <= 70 else base[:67] + "..."
    return q or "Trip"


def new_trip_doc(
    user_id: str,
    session_id: str,
    query: str,
    parent_session_id: str | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    return {
        "user_id": user_id,
        "session_id": session_id,
        "title": make_title(query),
        "query": query,
        "parent_session_id": parent_session_id,
        "status": "running",
        "trip": {},
        "clarifying_questions": [],
        "conversation": [],
        "pending_preview": None,
        "awaiting_kind": None,
        "searches_spent": 0,
        "cap_extra": 0,
        "progress": {"stage": "planning", "detail": "Starting trip planner", "at": now},
        "error": "",
        "created_at": now,
        "updated_at": now,
    }


def insert_new_trip(
    user_id: str,
    session_id: str,
    query: str,
    parent_session_id: str | None = None,
) -> None:
    from backend.database.collections import get_trip_sessions_collection

    get_trip_sessions_collection().insert_one(
        new_trip_doc(user_id, session_id, query, parent_session_id)
    )


def mark_running(user_id: str, session_id: str, detail: str = "Working on your trip") -> None:
    from backend.database.collections import get_trip_sessions_collection

    now = _utcnow()
    get_trip_sessions_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {
                "status": "running",
                "error": "",
                "progress": {"stage": "planning", "detail": detail, "at": now},
                "updated_at": now,
            }
        },
    )


def set_progress(user_id: str, session_id: str, stage: str, detail: str) -> None:
    from backend.database.collections import get_trip_sessions_collection

    now = _utcnow()
    get_trip_sessions_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {
                "progress": {"stage": stage, "detail": detail, "at": now},
                "updated_at": now,
            }
        },
    )


def complete_trip(
    user_id: str,
    session_id: str,
    *,
    status: str,
    trip: dict[str, Any] | None = None,
    clarifying_questions: list[dict[str, Any]] | None = None,
    message: str = "",
    user_text: str = "",
    pending_preview: dict[str, Any] | None = None,
    awaiting_kind: str | None = None,
) -> None:
    """Terminal write. Appends one conversation turn when user_text given."""
    from backend.database.collections import get_trip_sessions_collection

    now = _utcnow()
    update: dict[str, Any] = {
        "status": status,
        "trip": trip or {},
        "clarifying_questions": clarifying_questions or [],
        "progress": {"stage": "done", "detail": message[:200], "at": now},
        "error": "",
        "updated_at": now,
    }
    if status in ("ready", "failed"):
        # Terminal: preview consumed, kind resolved.
        update["pending_preview"] = None
        update["awaiting_kind"] = None
    else:
        if pending_preview is not None:
            update["pending_preview"] = pending_preview
        if awaiting_kind is not None:
            update["awaiting_kind"] = awaiting_kind
    if trip and (trip.get("destination") or trip.get("trip_id")):
        update["title"] = make_title(
            "", trip.get("origin", ""), trip.get("destination", "")
        )
        # origin was never mirrored to the top level, so history had no way to
        # show the route without reading into the trip doc.
        update["origin"] = trip.get("origin", "")
        update["destination"] = trip.get("destination", "")
        update["departure_date"] = trip.get("departure_date", "")
        update["return_date"] = trip.get("return_date")
    col = get_trip_sessions_collection()
    col.update_one({"user_id": user_id, "session_id": session_id}, {"$set": update})
    if user_text:
        col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$push": {
                    "conversation": {
                        "user": user_text,
                        "assistant": message,
                        "at": now,
                    }
                }
            },
        )


def fail_trip(
    user_id: str,
    session_id: str,
    error: str,
    *,
    user_text: str = "",
    assistant_text: str = "",
) -> None:
    """Terminal failure write.

    `user_text` appends the turn that failed. Without it the user's message was
    never persisted, so the thread kept rendering the PREVIOUS turn as "last"
    and the optimistic "sending..." bubble could never be cleared - the client
    waits for its own text to appear in the conversation.
    """
    from backend.database.collections import get_trip_sessions_collection

    now = _utcnow()
    message = (error or "Trip planning failed")[:500]
    col = get_trip_sessions_collection()
    col.update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$set": {
                "status": "failed",
                "error": message,
                "progress": {"stage": "failed", "detail": message[:200], "at": now},
                "updated_at": now,
                # The retry affordance lives on the failed turn, so a failed
                # run must not leave a stale pending preview behind.
                "pending_preview": None,
                "awaiting_kind": None,
            }
        },
    )
    if user_text:
        col.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$push": {
                    "conversation": {
                        "user": user_text,
                        "assistant": assistant_text or message,
                        "at": now,
                    }
                }
            },
        )


def is_stale(doc: dict[str, Any]) -> bool:
    if doc.get("status") != "running":
        return False
    at = doc.get("updated_at") or doc.get("created_at")
    if not at:
        return True
    if isinstance(at, str):
        try:
            at = datetime.fromisoformat(at)
        except ValueError:
            return True
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return (_utcnow() - at).total_seconds() > STALE_RUN_MINUTES * 60


def heal_stale(user_id: str, session_id: str) -> bool:
    """Mark a dead worker's doc failed. Returns True if healed."""
    from backend.database.collections import get_trip_sessions_collection

    col = get_trip_sessions_collection()
    doc = col.find_one({"user_id": user_id, "session_id": session_id})
    if doc and is_stale(doc):
        fail_trip(user_id, session_id, "Trip run stopped unexpectedly. Please try again.")
        return True
    return False


def get_trip_doc(user_id: str, session_id: str) -> dict[str, Any] | None:
    from backend.database.collections import get_trip_sessions_collection

    return get_trip_sessions_collection().find_one(
        {"user_id": user_id, "session_id": session_id}
    )


def list_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    from backend.database.collections import get_trip_sessions_collection

    cur = (
        get_trip_sessions_collection()
        .find({"user_id": user_id}, HISTORY_PROJECTION)
        .sort("updated_at", -1)
        .limit(max(1, min(limit, 50)))
    )

    items = list(cur)
    for it in items:
        trip = it.get("trip") or {}
        origin = (it.get("origin") or trip.get("origin") or "").strip()
        destination = (it.get("destination") or trip.get("destination") or "").strip()
        it["origin"] = origin
        it["destination"] = destination
        it["duration_days"] = trip.get("duration_days")
        it["travelers"] = trip.get("travelers")
        it["budget"] = trip.get("budget") or {}
        from backend.agents.travel.services.airports import resolve_iata

        it["origin_iata"] = resolve_iata(origin) if origin else None
        it["destination_iata"] = resolve_iata(destination) if destination else None
        if not it.get("departure_date"):
            it["departure_date"] = trip.get("departure_date") or ""
        if not it.get("return_date"):
            it["return_date"] = trip.get("return_date") or ""
        if origin or destination:
            it["title"] = make_title(it.get("query") or "", origin, destination)
    return items


def delete_trip_doc(user_id: str, session_id: str) -> bool:
    from backend.database.collections import get_trip_sessions_collection

    res = get_trip_sessions_collection().delete_one(
        {"user_id": user_id, "session_id": session_id}
    )
    return res.deleted_count > 0


# Keys that must NEVER reach an LLM prompt (bulk, tokens, internals).
_BANNED_CONTEXT_KEYS = {
    "images", "image", "airline_logo", "booking_token", "departure_token",
    "booking_link", "property_token", "evidence", "sources", "research",
    "flight_input_hash", "hotel_input_hash", "research_input_hash",
    "last_updated", "status", "trip_id", "conversation",
}


def _resolved_currency(trip: dict[str, Any]) -> str:
    """The currency the searches actually used.

    Delegates to the travel agent's resolver so the context handed to the LLM
    can never disagree with the prices on screen.
    """
    from backend.agents.travel.agent.trip_graph import trip_currency

    try:
        return trip_currency(trip or {})
    except Exception:
        return str((trip or {}).get("budget", {}).get("currency") or "USD")


def build_trip_context(
    trip: dict[str, Any] | None, recent: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Curated LLM context: every byte earns its place (~2KB, not ~46KB).

    Keeps decision inputs (params, budget actuals, picks, day titles+costs,
    recent turns). Drops images/logos/tokens/hashes/evidence/sources and the
    research dict (itinerary duplicate). Raises nothing on ragged input.
    """
    trip = trip or {}
    budget = trip.get("budget") or {}

    days: list[dict[str, Any]] = []
    for d in trip.get("itinerary") or []:
        if not isinstance(d, dict):
            continue
        acts = d.get("activities") or []
        day_cost = 0.0
        for a in acts:
            try:
                day_cost += float((a or {}).get("estimated_cost") or 0)
            except (ValueError, TypeError):
                continue
        days.append(
            {
                "day": d.get("day"),
                "date": d.get("date", ""),
                "title": d.get("title", ""),
                "stops": len(acts),
                "day_cost": round(day_cost, 2),
            }
        )

    picked_flight = trip.get("selected_flight") or {}
    picked_hotel = trip.get("selected_hotel") or {}
    recent_chat = [
        {"user": str(t.get("user", "")), "assistant": str(t.get("assistant", ""))}
        for t in (recent or [])[-2:]
        if isinstance(t, dict)
    ]

    ctx: dict[str, Any] = {
        "origin": trip.get("origin", ""),
        "destination": trip.get("destination", ""),
        "departure_date": trip.get("departure_date", ""),
        "return_date": trip.get("return_date"),
        "duration_days": trip.get("duration_days"),
        "travelers": trip.get("travelers"),
        "budget": {
            # Resolved once so the LLM sees the same currency the searches
            # actually quoted, not the schema's "USD" default.
            "currency": _resolved_currency(trip),
            "max_total": budget.get("max_total"),
            "flight_actual": budget.get("flight_actual"),
            "hotel_actual": budget.get("hotel_actual"),
            "activities": budget.get("activities_estimated"),
        },
        "hotel_preferences": trip.get("hotel_preferences") or {},
        "flight_preferences": trip.get("flight_preferences") or {},
        "interests": trip.get("interests") or [],
        "picked_flight": {
            "airline": picked_flight.get("airline", ""),
            "flight_number": picked_flight.get("flight_number", ""),
            "price": picked_flight.get("price"),
        }
        if picked_flight
        else None,
        "picked_hotel": {
            "name": picked_hotel.get("name", ""),
            "price_per_night": picked_hotel.get("price_per_night"),
            "area": picked_hotel.get("address", ""),
        }
        if picked_hotel
        else None,
        "itinerary_days": days,
        "recent_chat": recent_chat,
    }
    return ctx


def bump_searches(user_id: str, session_id: str, n: int) -> int:
    """Add n provider searches to the trip counter. Returns the new total."""
    from backend.database.collections import get_trip_sessions_collection

    col = get_trip_sessions_collection()
    col.update_one(
        {"user_id": user_id, "session_id": session_id},
        {"$inc": {"searches_spent": max(0, int(n))}},
    )
    doc = col.find_one(
        {"user_id": user_id, "session_id": session_id},
        {"searches_spent": 1},
    )
    return int((doc or {}).get("searches_spent", 0))


def get_spent(user_id: str, session_id: str) -> tuple[int, int]:
    """(searches_spent, cap_extra) for the trip."""
    from backend.database.collections import get_trip_sessions_collection

    doc = get_trip_sessions_collection().find_one(
        {"user_id": user_id, "session_id": session_id},
        {"searches_spent": 1, "cap_extra": 1},
    )
    doc = doc or {}
    return int(doc.get("searches_spent", 0)), int(doc.get("cap_extra", 0))


def add_cap_extra(user_id: str, session_id: str, n: int = CONTINUE_BUMP) -> None:
    from backend.database.collections import get_trip_sessions_collection

    get_trip_sessions_collection().update_one(
        {"user_id": user_id, "session_id": session_id},
        {"$inc": {"cap_extra": max(0, int(n))}},
    )
