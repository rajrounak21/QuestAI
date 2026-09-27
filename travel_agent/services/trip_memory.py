from __future__ import annotations

import logging
import uuid
from datetime import datetime

from travel_agent.schemas.trip import TripSession

logger = logging.getLogger(__name__)


class TripSessionMemory:
    def __init__(self) -> None:
        self._sessions: dict[str, TripSession] = {}

    def get_or_create(self, session_id: str | None = None) -> TripSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        trip_id = session_id or f"trip_{uuid.uuid4().hex[:8]}"
        session = TripSession(
            trip_id=trip_id,
            last_updated=datetime.now().isoformat(),
        )
        self._sessions[trip_id] = session
        return session

    def get(self, session_id: str) -> TripSession | None:
        return self._sessions.get(session_id)

    def save(self, session: TripSession) -> None:
        session.last_updated = datetime.now().isoformat()
        self._sessions[session.trip_id] = session

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


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


trip_memory = TripSessionMemory()
