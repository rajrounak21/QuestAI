from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from travel_agent.agent.state import FlightState, HotelState
from travel_agent.agent.nodes import extract_params_node, extract_hotel_params_node

logger = logging.getLogger(__name__)


def validate_params(state: FlightState) -> dict[str, Any]:
    params = state.get("extracted_params")
    if not params:
        return {
            "error": "Could not extract flight parameters.",
            "search_complete": True,
            "progress_steps": ["Error: extraction failed"],
        }

    origin = params.get("origin", "")
    destination = params.get("destination", "")
    departure_date = params.get("departure_date", "")

    if not origin or not destination:
        return {
            "follow_up_question": "I need both a departure location and a destination to search for flights. Where are you flying from and to?",
            "search_complete": True,
            "progress_steps": ["Missing origin or destination"],
        }

    if not departure_date:
        return {
            "follow_up_question": "What date would you like to travel?",
            "search_complete": True,
            "progress_steps": ["Missing departure date"],
        }

    return {
        "progress_steps": [
            f"Found airports: {origin} → {destination}",
            f"Departure: {departure_date}",
        ],
    }


def search_flights(state: FlightState) -> dict[str, Any]:
    logger.info("Running search_flights node")

    params = state.get("extracted_params")
    if not params:
        return {
            "error": "No search parameters available.",
            "search_complete": True,
            "progress_steps": ["Error: no parameters"],
        }

    try:
        from travel_agent.schemas.flight import FlightSearchRequest, TripType, CabinClass
        from travel_agent.tools.google_flights import google_flights_search
        from travel_agent.services.flight_normalizer import build_search_response

        trip_type = TripType.ROUND_TRIP if params.get("trip_type") == "round_trip" else TripType.ONE_WAY

        cabin_map = {
            "economy": CabinClass.ECONOMY,
            "premium_economy": CabinClass.PREMIUM_ECONOMY,
            "business": CabinClass.BUSINESS,
            "first": CabinClass.FIRST,
        }
        cabin_class = cabin_map.get(params.get("cabin_class", "economy"), CabinClass.ECONOMY)

        request_dict = {
            "origin": params["origin"],
            "destination": params["destination"],
            "departure_date": params["departure_date"],
            "return_date": params.get("return_date"),
            "trip_type": trip_type,
            "passengers": params.get("passengers", 1),
            "cabin_class": cabin_class,
            "currency": params.get("currency", "USD"),
        }

        raw = google_flights_search(FlightSearchRequest(**request_dict))

        response = build_search_response(request_dict, raw)

        flights_data = [f.model_dump() for f in response.flights]

        return {
            "flights": flights_data,
            "total_results": response.total_results,
            "search_complete": True,
            "progress_steps": [
                f"Searched Google Flights",
                f"Found {response.total_results} flight options",
            ],
        }

    except Exception as e:
        logger.error(f"Flight search failed: {e}")
        return {
            "error": "Flight search is temporarily unavailable. Please try again.",
            "search_complete": True,
            "progress_steps": ["Error: search failed"],
        }


def route_after_validate(state: FlightState) -> Literal["search_flights", "END"]:
    if state.get("error") or state.get("follow_up_question"):
        return "END"
    return "search_flights"


def build_graph() -> StateGraph:
    builder = StateGraph(FlightState)

    builder.add_node("extract_params", extract_params_node)
    builder.add_node("validate_params", validate_params)
    builder.add_node("search_flights", search_flights)

    builder.add_edge(START, "extract_params")
    builder.add_edge("extract_params", "validate_params")

    builder.add_conditional_edges(
        "validate_params",
        route_after_validate,
        {
            "search_flights": "search_flights",
            "END": END,
        },
    )

    builder.add_edge("search_flights", END)

    return builder.compile()


_compiled_graph = None


def get_flight_graph() -> StateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def validate_hotel_params(state: HotelState) -> dict[str, Any]:
    params = state.get("extracted_params")
    if not params:
        return {
            "error": "Could not extract hotel parameters.",
            "search_complete": True,
            "progress_steps": ["Error: extraction failed"],
        }

    location = params.get("location", "")
    check_in = params.get("check_in", "")
    check_out = params.get("check_out", "")

    if not location:
        return {
            "follow_up_question": "Where would you like to stay? Please provide a city or hotel location.",
            "search_complete": True,
            "progress_steps": ["Missing location"],
        }

    if not check_in or not check_out:
        return {
            "follow_up_question": "What dates will you be staying? I need check-in and check-out dates.",
            "search_complete": True,
            "progress_steps": ["Missing dates"],
        }

    return {
        "progress_steps": [
            f"Finding hotels in {location}",
            f"Check-in: {check_in}, Check-out: {check_out}",
        ],
    }


def search_hotels(state: HotelState) -> dict[str, Any]:
    logger.info("Running search_hotels node")

    params = state.get("extracted_params")
    if not params:
        return {
            "error": "No search parameters available.",
            "search_complete": True,
            "progress_steps": ["Error: no parameters"],
        }

    try:
        from travel_agent.schemas.hotel import HotelSearchRequest, SortBy
        from travel_agent.tools.google_hotels import google_hotels_search
        from travel_agent.services.hotel_normalizer import build_hotel_search_response

        sort_map = {
            "price": SortBy.PRICE,
            "rating": SortBy.RATING,
            "reviews": SortBy.REVIEWS,
        }
        sort_by = sort_map.get(params.get("sort_by", "relevance"), SortBy.RELEVANCE)

        request_dict = {
            "location": params["location"],
            "check_in": params["check_in"],
            "check_out": params["check_out"],
            "guests": params.get("guests", 2),
            "rooms": params.get("rooms", 1),
            "currency": params.get("currency", "USD"),
            "max_price": params.get("max_price"),
            "min_rating": params.get("min_rating"),
            "hotel_class": params.get("hotel_class"),
            "sort_by": sort_by,
        }

        raw = google_hotels_search(HotelSearchRequest(**request_dict))

        response = build_hotel_search_response(request_dict, raw)

        hotels_data = [h.model_dump() for h in response.hotels]

        return {
            "hotels": hotels_data,
            "total_results": response.total_results,
            "search_complete": True,
            "progress_steps": [
                "Searched Google Hotels",
                f"Found {response.total_results} hotel options",
            ],
        }

    except Exception as e:
        logger.error(f"Hotel search failed: {e}")
        return {
            "error": "Hotel search is temporarily unavailable. Please try again.",
            "search_complete": True,
            "progress_steps": ["Error: search failed"],
        }


def route_after_hotel_validate(state: HotelState) -> Literal["search_hotels", "END"]:
    if state.get("error") or state.get("follow_up_question"):
        return "END"
    return "search_hotels"


def build_hotel_graph() -> StateGraph:
    builder = StateGraph(HotelState)

    builder.add_node("extract_params", extract_hotel_params_node)
    builder.add_node("validate_params", validate_hotel_params)
    builder.add_node("search_hotels", search_hotels)

    builder.add_edge(START, "extract_params")
    builder.add_edge("extract_params", "validate_params")

    builder.add_conditional_edges(
        "validate_params",
        route_after_hotel_validate,
        {
            "search_hotels": "search_hotels",
            "END": END,
        },
    )

    builder.add_edge("search_hotels", END)

    return builder.compile()


_compiled_hotel_graph = None


def get_hotel_graph() -> StateGraph:
    global _compiled_hotel_graph
    if _compiled_hotel_graph is None:
        _compiled_hotel_graph = build_hotel_graph()
    return _compiled_hotel_graph
