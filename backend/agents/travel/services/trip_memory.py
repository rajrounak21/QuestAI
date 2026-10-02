from __future__ import annotations

import contextvars
import logging
import uuid
from datetime import datetime
from typing import Any

from backend.agents.travel.schemas.trip import TripSession

logger = logging.getLogger(__name__)

# User scope for the Mongo store. The trips router sets this per request /
# worker thread (asyncio.to_thread propagates context), so the LangGraph
# nodes keep calling the same trip_memory interface with zero changes.
_current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trip_user_id", default=None
)


def use_user(user_id: str):
    """Set the user scope for the current context. Returns a reset token."""
    return _current_user.set(user_id)


def reset_user(token) -> None:
    _current_user.reset(token)


def current_user_id() -> str | None:
    """Read-only peek at the user scope (for spend accounting)."""
    return _current_user.get()


class MongoTripStore:
    """Drop-in replacement for the old in-memory dict. Same method shapes,
    keyed by (user_id, session_id) in the trip_sessions collection."""

    def _uid(self) -> str:
        uid = _current_user.get()
        if not uid:
            raise RuntimeError("trip store used without user scope (use_user)")
        return uid

    def get_or_create(self, session_id: str | None = None) -> TripSession:
        from backend.database.collections import get_trip_sessions_collection

        uid = self._uid()
        if session_id:
            doc = get_trip_sessions_collection().find_one(
                {"user_id": uid, "session_id": session_id}
            )
            if doc and doc.get("trip"):
                try:
                    return TripSession(**doc["trip"])
                except Exception as e:
                    logger.warning(f"Stored trip unreadable session={session_id}: {e}")
            return TripSession(
                trip_id=session_id, last_updated=datetime.now().isoformat()
            )
        trip_id = f"trip_{uuid.uuid4().hex[:8]}"
        return TripSession(trip_id=trip_id, last_updated=datetime.now().isoformat())

    def get(self, session_id: str) -> TripSession | None:
        from backend.database.collections import get_trip_sessions_collection

        uid = self._uid()
        doc = get_trip_sessions_collection().find_one(
            {"user_id": uid, "session_id": session_id}
        )
        if not doc or not doc.get("trip"):
            return None
        try:
            return TripSession(**doc["trip"])
        except Exception as e:
            logger.warning(f"Stored trip unreadable session={session_id}: {e}")
            return None

    def save(self, session: TripSession) -> None:
        from backend.database.collections import get_trip_sessions_collection

        uid = self._uid()
        session.last_updated = datetime.now().isoformat()
        get_trip_sessions_collection().update_one(
            {"user_id": uid, "session_id": session.trip_id},
            {
                "$set": {
                    "trip": session.to_dict(),
                    "updated_at": datetime.now(),
                },
                "$setOnInsert": {
                    "user_id": uid,
                    "session_id": session.trip_id,
                    "status": "running",
                    "created_at": datetime.now(),
                },
            },
            upsert=True,
        )

    def exists(self, session_id: str) -> bool:
        from backend.database.collections import get_trip_sessions_collection

        uid = self._uid()
        doc = get_trip_sessions_collection().find_one(
            {"user_id": uid, "session_id": session_id},
            {"_id": 1, "trip": 1},
        )
        return bool(doc and doc.get("trip"))

    def delete(self, session_id: str) -> None:
        from backend.database.collections import (
            get_trip_sessions_collection,
        )
        from backend.database.trip_sessions import delete_trip_doc

        delete_trip_doc(self._uid(), session_id)

    def list_sessions(self) -> list[str]:
        from backend.database.collections import get_trip_sessions_collection

        uid = self._uid()
        cur = get_trip_sessions_collection().find(
            {"user_id": uid}, {"session_id": 1}
        )
        return [d["session_id"] for d in cur]


def build_trip_context(session: TripSession, current_query: str) -> str:
    parts: list[str] = []

    if session.destination:
        parts.append(f"Trip to: {session.destination}")
    if session.origin:
        parts.append(f"From: {session.origin}")
    if session.departure_date:
        parts.append(f"Dates: {session.departure_date} to {session.return_date or 'TBD'}")
    if session.travelers:
        parts.append(f"Travelers: {session.travelers}")
    if session.budget.max_total:
        parts.append(f"Budget: {session.budget.currency} {session.budget.max_total}")
    if session.budget.flight_actual:
        parts.append(f"Flight cost: {session.budget.currency} {session.budget.flight_actual}")
    if session.budget.hotel_actual:
        parts.append(f"Hotel cost: {session.budget.currency} {session.budget.hotel_actual}")
    if session.selected_flight:
        parts.append(f"Selected flight: {session.selected_flight.get('airline', '')} {session.selected_flight.get('flight_number', '')}")
    if session.selected_hotel:
        parts.append(f"Selected hotel: {session.selected_hotel.get('name', '')}")
    if session.interests:
        parts.append(f"Interests: {', '.join(session.interests)}")
    if session.itinerary:
        parts.append(f"Itinerary: {len(session.itinerary)} days planned")

    is_followup = len(session.conversation) > 0
    if is_followup:
        last_exchange = session.conversation[-1]
        parts.append(f"Previous question: {last_exchange.get('user', '')}")

    parts.append(f"Current question: {current_query}")

    return "\n\n".join(parts)


trip_memory = MongoTripStore()
