from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any]:
    if a is None:
        return b or {}
    if b is None:
        return a
    merged = dict(a)
    for key, val in b.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = {**merged[key], **val}
        else:
            merged[key] = val
    return merged


class FlightState(TypedDict):
    user_query: str
    extracted_params: dict[str, Any] | None
    flights: list[dict[str, Any]]
    total_results: int
    error: str | None
    follow_up_question: str | None
    search_complete: bool
    progress_steps: Annotated[list[str], operator.add]


class HotelState(TypedDict):
    user_query: str
    extracted_params: dict[str, Any] | None
    hotels: list[dict[str, Any]]
    total_results: int
    error: str | None
    follow_up_question: str | None
    search_complete: bool
    progress_steps: Annotated[list[str], operator.add]


class TripState(TypedDict):
    user_query: str
    session_id: str | None
    trip_session: Annotated[dict[str, Any] | None, _merge_dicts]
    extracted_params: dict[str, Any] | None
    impact_analysis: dict[str, Any] | None
    clarifying_questions: list[dict[str, Any]]
    flight_results: Annotated[list[dict[str, Any]], operator.add]
    hotel_results: Annotated[list[dict[str, Any]], operator.add]
    destination_research: dict[str, Any] | None
    itinerary: list[dict[str, Any]]
    message: str
    error: str | None
    progress_steps: Annotated[list[str], operator.add]
