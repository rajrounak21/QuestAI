from __future__ import annotations

import logging
from typing import Any

from travel_agent.agent.trip_graph import get_trip_graph
from travel_agent.services.trip_memory import trip_memory

logger = logging.getLogger(__name__)


def run_trip_planner(query: str, session_id: str | None = None) -> dict[str, Any]:
    logger.info(f"Running trip planner: {query}")

    graph = get_trip_graph()

    initial_state = {
        "user_query": query,
        "session_id": session_id,
        "trip_session": None,
        "extracted_params": None,
        "impact_analysis": None,
        "clarifying_questions": [],
        "flight_results": [],
        "hotel_results": [],
        "destination_research": None,
        "itinerary": [],
        "message": "",
        "error": None,
        "progress_steps": [],
    }

    try:
        result = graph.invoke(initial_state)

        trip_data = result.get("trip_session") or {}
        error = result.get("error")
        message = result.get("message", "")
        clarifying = result.get("clarifying_questions") or []

        if clarifying:
            return {
                "trip": trip_data,
                "message": message or "I need a few more details:",
                "error": None,
                "clarifying_questions": clarifying,
                "progress_steps": result.get("progress_steps", []),
            }

        if error:
            return {
                "trip": trip_data,
                "message": error,
                "error": error,
                "clarifying_questions": [],
                "progress_steps": result.get("progress_steps", []),
            }

        return {
            "trip": trip_data,
            "message": message or f"Trip to {trip_data.get('destination', 'unknown')} is ready!",
            "error": None,
            "clarifying_questions": [],
            "progress_steps": result.get("progress_steps", []),
        }

    except Exception as e:
        logger.error(f"Trip planner failed: {e}")
        return {
            "trip": {},
            "message": "Trip planning failed. Please try again.",
            "error": str(e),
            "clarifying_questions": [],
            "progress_steps": [],
        }


def run_trip_chat(session_id: str, message: str) -> dict[str, Any]:
    logger.info(f"Trip chat: session={session_id}, message={message}")

    session = trip_memory.get(session_id)
    if not session:
        return {
            "trip": {},
            "message": "Trip not found. Please create a new trip.",
            "error": "Trip not found",
        }

    return run_trip_planner(message, session_id=session_id)


def get_trip(session_id: str) -> dict[str, Any] | None:
    session = trip_memory.get(session_id)
    if session:
        return session.to_dict()
    return None


def delete_trip(session_id: str) -> bool:
    if trip_memory.exists(session_id):
        trip_memory.delete(session_id)
        return True
    return False
