from __future__ import annotations

import logging
from typing import Any

from backend.agents.travel.agent.trip_graph import get_trip_graph
from backend.agents.travel.services.trip_memory import (
    reset_user,
    trip_memory,
    use_user,
)

logger = logging.getLogger(__name__)


def run_trip_planner(
    query: str,
    session_id: str | None = None,
    user_id: str | None = None,
    pending_questions: list[dict[str, Any]] | None = None,
    confirmed_scope: str | None = None,
) -> dict[str, Any]:
    logger.info(f"Running trip planner: {query}")

    token = use_user(user_id) if user_id else None
    try:
        graph = get_trip_graph()

        initial_state = {
            "user_query": query,
            "session_id": session_id,
            "trip_session": None,
            "extracted_params": None,
            "impact_analysis": None,
            # Preload unresolved clarifying questions so merge_answers can
            # fold the user's reply into params instead of re-asking.
            "clarifying_questions": pending_questions or [],
            "flight_results": [],
            "hotel_results": [],
            "destination_research": None,
            "itinerary": [],
            "message": "",
            "error": None,
            "warnings": [],
            "progress_steps": [],
            # "overwrite": modal-approved replan of an existing session.
            # Anything else (or missing) on an existing trip -> confirm gate.
            "confirmed_scope": confirmed_scope,
            "preview_trip": None,
        }

        try:
            result = graph.invoke(initial_state)

            trip_data = result.get("trip_session") or {}
            error = result.get("error")
            message = result.get("message", "")
            clarifying = result.get("clarifying_questions") or []
            cap_paused = bool(result.get("cap_hit", False))

            if clarifying:
                return {
                    "trip": trip_data,
                    "message": message or "I need a few more details:",
                    "error": None,
                    "clarifying_questions": clarifying,
                    "preview_trip": result.get("preview_trip"),
                    "cap_paused": cap_paused,
                    "progress_steps": result.get("progress_steps", []),
                    "warnings": result.get("warnings", []),
                }

            if error:
                return {
                    "trip": trip_data,
                    "message": error,
                    "error": error,
                    "clarifying_questions": [],
                    "cap_paused": cap_paused,
                    "progress_steps": result.get("progress_steps", []),
                    "warnings": result.get("warnings", []),
                }

            return {
                "trip": trip_data,
                "message": message or f"Trip to {trip_data.get('destination', 'unknown')} is ready!",
                "error": None,
                "clarifying_questions": [],
                "cap_paused": cap_paused,
                "progress_steps": result.get("progress_steps", []),
                    "warnings": result.get("warnings", []),
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
    finally:
        if token is not None:
            reset_user(token)


def run_trip_chat(session_id: str, message: str, user_id: str) -> dict[str, Any]:
    logger.info(f"Trip chat: session={session_id}, message={message}")

    token = use_user(user_id)
    try:
        session = trip_memory.get(session_id)
        if not session:
            return {
                "trip": {},
                "message": "Trip not found. Please create a new trip.",
                "error": "Trip not found",
            }
    finally:
        reset_user(token)

    return run_trip_planner(message, session_id=session_id, user_id=user_id)


def get_trip(session_id: str, user_id: str) -> dict[str, Any] | None:
    token = use_user(user_id)
    try:
        session = trip_memory.get(session_id)
        if session:
            return session.to_dict()
        return None
    finally:
        reset_user(token)


def delete_trip(session_id: str, user_id: str) -> bool:
    token = use_user(user_id)
    try:
        if trip_memory.exists(session_id):
            trip_memory.delete(session_id)
            return True
        return False
    finally:
        reset_user(token)
