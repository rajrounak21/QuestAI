from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import date, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from travel_agent.agent.state import TripState
from travel_agent.agent.nodes import (
    extract_trip_params_node,
    detect_impact_node,
    validate_trip_params_node,
    _parse_json,
)
from travel_agent.services.trip_memory import trip_memory
from travel_agent.schemas.trip import (
    TripSession, TripBudget, DayPlan, Activity,
    compute_flight_hash, compute_hotel_hash, compute_research_hash,
)

logger = logging.getLogger(__name__)

DEPENDENCY_MAP = {
    "origin":               ["flights"],
    "destination":          ["flights", "hotels", "research", "itinerary"],
    "departure_date":       ["flights", "hotels", "itinerary"],
    "return_date":          ["flights", "hotels", "itinerary"],
    "duration_days":        ["flights", "hotels", "itinerary"],
    "travelers":            ["flights", "hotels"],
    "budget.max_total":     ["flights", "hotels"],
    "hotel_preferences":    ["hotels", "itinerary"],
    "flight_preferences":   ["flights"],
    "interests":            ["research", "itinerary"],
}


def load_session(state: TripState) -> dict[str, Any]:
    logger.info("Loading trip session")

    session_id = state.get("session_id")
    extracted = state.get("extracted_params") or {}
    intent = extracted.get("intent", "new_trip")

    if intent == "new_trip" and not session_id:
        session = trip_memory.get_or_create()
        return {
            "trip_session": session.to_dict(),
            "progress_steps": [f"Created new trip: {session.trip_id}"],
        }

    if session_id:
        session = trip_memory.get(session_id)
        if session:
            return {
                "trip_session": session.to_dict(),
                "progress_steps": [f"Loaded trip: {session.trip_id}"],
            }

    session = trip_memory.get_or_create()
    return {
        "trip_session": session.to_dict(),
        "progress_steps": [f"Created new trip: {session.trip_id}"],
    }


def update_trip_state(state: TripState) -> dict[str, Any]:
    logger.info("Updating trip state")

    extracted = state.get("extracted_params") or {}
    trip_data = state.get("trip_session") or {}
    intent = extracted.get("intent", "new_trip")

    if intent == "new_trip":
        departure_date = extracted.get("departure_date")
        return_date = extracted.get("return_date")
        duration = extracted.get("duration_days") or 5

        if not departure_date:
            from datetime import timedelta
            dep = date.today() + timedelta(days=30)
            departure_date = dep.isoformat()
        if not return_date:
            from datetime import timedelta
            dep = date.fromisoformat(departure_date)
            ret = dep + timedelta(days=duration)
            return_date = ret.isoformat()

        budget_data = extracted.get("budget") or {}
        new_trip = TripSession(
            trip_id=trip_data.get("trip_id", ""),
            origin=extracted.get("origin") or "",
            destination=extracted.get("destination") or "",
            departure_date=departure_date,
            return_date=return_date,
            duration_days=duration,
            travelers=extracted.get("travelers") or 2,
            budget=TripBudget(
                currency=budget_data.get("currency") or "USD",
                max_total=budget_data.get("max_total"),
            ),
            hotel_preferences=extracted.get("hotel_preferences") or {},
            flight_preferences=extracted.get("flight_preferences") or {},
            interests=extracted.get("interests") or [],
            last_updated=datetime.now().isoformat(),
        )
        new_trip.flight_input_hash = compute_flight_hash(
            new_trip.origin, new_trip.destination, new_trip.departure_date,
            new_trip.return_date, new_trip.travelers, new_trip.flight_preferences,
        )
        new_trip.hotel_input_hash = compute_hotel_hash(
            new_trip.destination, new_trip.departure_date, new_trip.return_date,
            new_trip.travelers, new_trip.budget.max_total, new_trip.hotel_preferences,
        )
        new_trip.research_input_hash = compute_research_hash(
            new_trip.destination, new_trip.interests,
        )
        trip_memory.save(new_trip)
        return {
            "trip_session": new_trip.to_dict(),
            "progress_steps": ["Trip parameters extracted"],
        }

    from datetime import timedelta

    session = TripSession(**trip_data)

    follow_up_type = extracted.get("follow_up_type")
    follow_up_target = extracted.get("follow_up_target")

    if follow_up_type == "cost_check":
        flight_cost = session.budget.flight_actual or 0
        hotel_cost = session.budget.hotel_actual or 0
        activities = session.budget.activities_estimated or 0
        total = flight_cost + hotel_cost + activities
        budget_max = session.budget.max_total or 0
        remaining = budget_max - total if budget_max else None
        msg = f"Your {session.destination} trip cost breakdown:\n"
        msg += f"Flights: ${flight_cost:.0f}\n" if flight_cost else ""
        msg += f"Hotel: ${hotel_cost:.0f}\n" if hotel_cost else ""
        msg += f"Activities: ${activities:.0f}\n" if activities else ""
        msg += f"Total: ${total:.0f}\n"
        if budget_max:
            msg += f"Budget: ${budget_max:.0f}\n"
            msg += f"{'Under budget' if remaining and remaining >= 0 else 'Over budget'} by ${abs(remaining or 0):.0f}"
        return {
            "trip_session": session.to_dict(),
            "message": msg,
            "progress_steps": ["Cost check complete"],
        }

    if follow_up_type == "update_dates":
        if extracted.get("departure_date"):
            session.departure_date = extracted["departure_date"]
        if extracted.get("duration_days"):
            session.duration_days = extracted["duration_days"]
        dep = date.fromisoformat(session.departure_date)
        session.return_date = (dep + timedelta(days=session.duration_days)).isoformat()

    elif follow_up_type == "make_cheaper" or follow_up_type == "update_budget":
        if extracted.get("budget", {}).get("max_total"):
            session.budget.max_total = extracted["budget"]["max_total"]
        else:
            current_max = session.budget.max_total or 2000
            session.budget.max_total = current_max * 0.7

    elif follow_up_type == "update_hotel":
        if follow_up_target:
            session.hotel_preferences["class"] = follow_up_target

    elif follow_up_type == "update_flight":
        if follow_up_target:
            session.flight_preferences["stops"] = follow_up_target

    elif follow_up_type == "extend_trip":
        if extracted.get("duration_days"):
            session.duration_days = extracted["duration_days"]
        if extracted.get("departure_date"):
            session.departure_date = extracted["departure_date"]
        dep = date.fromisoformat(session.departure_date)
        session.return_date = (dep + timedelta(days=session.duration_days)).isoformat()

    session.last_updated = datetime.now().isoformat()
    session.flight_input_hash = compute_flight_hash(
        session.origin, session.destination, session.departure_date,
        session.return_date, session.travelers, session.flight_preferences,
    )
    session.hotel_input_hash = compute_hotel_hash(
        session.destination, session.departure_date, session.return_date,
        session.travelers, session.budget.max_total, session.hotel_preferences,
    )
    session.research_input_hash = compute_research_hash(
        session.destination, session.interests,
    )
    trip_memory.save(session)

    return {
        "trip_session": session.to_dict(),
        "progress_steps": ["Trip state updated"],
    }


def route_after_extract(state: TripState) -> str:
    if state.get("error"):
        return "error"
    extracted = state.get("extracted_params") or {}
    if not extracted:
        return "error"
    return "validate"


def route_after_validate(state: TripState) -> str:
    questions = state.get("clarifying_questions") or []
    if questions:
        return "ask_user"
    return "continue"


def merge_user_answers(state: TripState) -> dict[str, Any]:
    logger.info("Merging user answers into trip params")

    extracted = state.get("extracted_params") or {}
    user_query = state.get("user_query", "")
    questions = state.get("clarifying_questions") or []

    if not questions:
        return {"extracted_params": extracted}

    query_lower = user_query.lower()

    for q in questions:
        field = q.get("field", "")
        options = q.get("options") or []

        if field == "budget":
            if "custom budget" in query_lower:
                import re
                nums = re.findall(r'[\d,]+', user_query.replace(",", ""))
                for n in nums:
                    val = float(n)
                    if 100 <= val <= 100000:
                        extracted["budget"] = {"max_total": val, "currency": "USD"}
                        break
            elif any(w in query_lower for w in ["cheap", "budget", "low"]):
                extracted["budget"] = {"max_total": 1000, "currency": "USD"}
            elif any(w in query_lower for w in ["mid", "moderate", "medium", "average"]):
                extracted["budget"] = {"max_total": 2500, "currency": "USD"}
            elif any(w in query_lower for w in ["luxury", "high", "expensive", "premium"]):
                extracted["budget"] = {"max_total": 5000, "currency": "USD"}
            else:
                import re
                nums = re.findall(r'[\d,]+', user_query.replace(",", ""))
                for n in nums:
                    val = float(n)
                    if 100 <= val <= 100000:
                        extracted["budget"] = {"max_total": val, "currency": "USD"}
                        break

        elif field == "origin":
            words = user_query.split()
            for i, w in enumerate(words):
                if w.lower() in ["from", "origin", "starting"]:
                    if i + 1 < len(words):
                        origin_word = words[i + 1].strip(".,!?")
                        extracted["origin"] = origin_word
                        break

        elif field == "departure_date":
            import re
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', user_query)
            if date_match:
                extracted["departure_date"] = date_match.group(1)
            elif any(w in query_lower for w in ["tomorrow"]):
                from datetime import timedelta
                extracted["departure_date"] = (date.today() + timedelta(days=1)).isoformat()
            elif any(w in query_lower for w in ["next week"]):
                from datetime import timedelta
                extracted["departure_date"] = (date.today() + timedelta(weeks=1)).isoformat()
            elif any(w in query_lower for w in ["next month"]):
                from datetime import timedelta
                extracted["departure_date"] = (date.today() + timedelta(days=30)).isoformat()

        elif field == "return_date":
            if extracted.get("departure_date") and extracted.get("duration_days"):
                from datetime import timedelta
                dep = date.fromisoformat(extracted["departure_date"])
                ret = dep + timedelta(days=extracted["duration_days"])
                extracted["return_date"] = ret.isoformat()

        elif field == "travelers":
            import re
            nums = re.findall(r'\d+', user_query)
            for n in nums:
                val = int(n)
                if 1 <= val <= 20:
                    extracted["travelers"] = val
                    break

    if extracted.get("departure_date") and not extracted.get("return_date"):
        duration = extracted.get("duration_days", 5)
        from datetime import timedelta
        dep = date.fromisoformat(extracted["departure_date"])
        extracted["return_date"] = (dep + timedelta(days=duration)).isoformat()

    return {
        "extracted_params": extracted,
        "clarifying_questions": [],
    }


def route_after_impact(state: TripState) -> str:
    impact = state.get("impact_analysis") or {}
    agents = impact.get("affected_agents", [])

    if not agents:
        return "synthesize"

    if "flights" in agents or "hotels" in agents or "research" in agents:
        return "run_agents"

    return "synthesize"


def run_flight_search(state: TripState) -> dict[str, Any]:
    logger.info("Running flight search for trip")

    trip_data = state.get("trip_session") or {}
    origin = trip_data.get("origin", "")
    destination = trip_data.get("destination", "")
    departure_date = trip_data.get("departure_date", "")
    return_date = trip_data.get("return_date")
    travelers = trip_data.get("travelers", 2)
    flight_prefs = trip_data.get("flight_preferences", {})

    new_hash = compute_flight_hash(origin, destination, departure_date, return_date, travelers, flight_prefs)
    if trip_data.get("flight_input_hash") == new_hash and trip_data.get("flight_results"):
        logger.info("Flight inputs unchanged, reusing cached results")
        return {
            "flight_results": trip_data.get("flight_results", []),
            "progress_steps": ["Reusing cached flight results"],
        }

    query_parts = [f"Flights from {origin} to {destination} on {departure_date}"]
    if return_date:
        query_parts.append(f"returning {return_date}")
    query_parts.append(f"for {travelers} people")
    if flight_prefs.get("stops"):
        query_parts.append(f"{flight_prefs['stops']} flights")

    query = " ".join(query_parts)

    try:
        from travel_agent.agent.flight_agent import run_flight_search as search_flights
        result = search_flights(query)

        flights = result.get("flights", [])

        return {
            "flight_results": flights[:10],
            "progress_steps": [f"Found {len(flights)} flight options"],
        }
    except Exception as e:
        logger.error(f"Flight search failed: {e}")
        return {
            "flight_results": [],
            "progress_steps": ["Flight search failed, continuing"],
        }


def run_hotel_search(state: TripState) -> dict[str, Any]:
    logger.info("Running hotel search for trip")

    trip_data = state.get("trip_session") or {}
    destination = trip_data.get("destination", "")
    departure_date = trip_data.get("departure_date", "")
    return_date = trip_data.get("return_date")
    travelers = trip_data.get("travelers", 2)
    hotel_prefs = trip_data.get("hotel_preferences", {})
    budget = trip_data.get("budget", {})

    new_hash = compute_hotel_hash(destination, departure_date, return_date, travelers, budget.get("max_total"), hotel_prefs)
    if trip_data.get("hotel_input_hash") == new_hash and trip_data.get("hotel_results"):
        logger.info("Hotel inputs unchanged, reusing cached results")
        return {
            "hotel_results": trip_data.get("hotel_results", []),
            "progress_steps": ["Reusing cached hotel results"],
        }

    query_parts = [f"Hotels in {destination}"]
    if departure_date and return_date:
        query_parts.append(f"from {departure_date} to {return_date}")
    elif departure_date:
        query_parts.append(f"check-in {departure_date}")
    query_parts.append(f"for {travelers} people")
    if hotel_prefs.get("class"):
        query_parts.append(f"{hotel_prefs['class']}-star hotel")

    max_total = budget.get("max_total")
    if max_total and return_date and departure_date:
        dep = date.fromisoformat(departure_date)
        ret = date.fromisoformat(return_date)
        nights = max(1, (ret - dep).days)
        max_hotel_per_night = (max_total * 0.4) / nights
        query_parts.append(f"under ${int(max_hotel_per_night)} per night")

    query = " ".join(query_parts)

    try:
        from travel_agent.agent.hotel_agent import run_hotel_search as search_hotels
        result = search_hotels(query)

        hotels = result.get("hotels", [])

        if max_total and return_date and departure_date:
            dep = date.fromisoformat(departure_date)
            ret = date.fromisoformat(return_date)
            nights = max(1, (ret - dep).days)
            max_per_night = (max_total * 0.4) / nights
            budget_hotels = [h for h in hotels if h.get("price_per_night", 0) <= max_per_night * 1.2]
            if len(budget_hotels) >= 3:
                hotels = budget_hotels
                logger.info(f"Filtered to {len(hotels)} hotels within budget (${max_per_night:.0f}/night)")

        return {
            "hotel_results": hotels[:10],
            "progress_steps": [f"Found {len(hotels)} hotel options"],
        }
    except Exception as e:
        logger.error(f"Hotel search failed: {e}")
        return {
            "hotel_results": [],
            "progress_steps": ["Hotel search failed, continuing"],
        }


def run_destination_research(state: TripState) -> dict[str, Any]:
    logger.info("Running destination research")

    trip_data = state.get("trip_session") or {}
    destination = trip_data.get("destination", "")
    duration = trip_data.get("duration_days", 5)
    travelers = trip_data.get("travelers", 2)
    departure_date = trip_data.get("departure_date", "")
    return_date = trip_data.get("return_date", "")
    interests = trip_data.get("interests", [])
    budget = trip_data.get("budget", {})

    new_hash = compute_research_hash(destination, interests)
    if trip_data.get("research_input_hash") == new_hash and trip_data.get("research"):
        logger.info("Research inputs unchanged, reusing cached results")
        return {
            "destination_research": trip_data.get("research", {}),
            "progress_steps": ["Reusing cached destination research"],
        }

    activity_budget = 300.0
    if budget.get("max_total"):
        flight = budget.get("flight_actual") or 0
        hotel = budget.get("hotel_actual") or 0
        remaining = budget["max_total"] - flight - hotel
        activity_budget = max(remaining * 0.4, 100.0)

    try:
        from travel_agent.services.destination_research import research_destination
        result = research_destination(
            destination=destination,
            duration_days=duration,
            travelers=travelers,
            departure_date=departure_date,
            return_date=return_date,
            interests=interests,
            activity_budget=activity_budget,
            currency=budget.get("currency", "USD"),
        )

        return {
            "destination_research": result,
            "progress_steps": ["Researched destination attractions"],
        }
    except Exception as e:
        logger.error(f"Destination research failed: {e}")
        return {
            "destination_research": {},
            "progress_steps": ["Destination research failed, continuing"],
        }


def synthesize_itinerary(state: TripState) -> dict[str, Any]:
    logger.info("Synthesizing itinerary")

    extracted = state.get("extracted_params") or {}
    follow_up_type = extracted.get("follow_up_type")

    if follow_up_type == "cost_check":
        trip_data = state.get("trip_session") or {}
        existing_message = state.get("message", "")
        if trip_data and existing_message:
            return {
                "trip_session": trip_data,
                "message": existing_message,
                "clarifying_questions": [],
                "progress_steps": ["Cost check complete"],
            }

    clarifying = state.get("clarifying_questions") or []
    if clarifying:
        greeting = state.get("message", "")
        question_texts = []
        for q in clarifying:
            q_obj = {
                "field": q.get("field", ""),
                "question": q.get("question", ""),
                "why": q.get("why", ""),
            }
            if q.get("options"):
                q_obj["options"] = q["options"]
            question_texts.append(q_obj)

        return {
            "trip_session": {},
            "message": greeting or "I need a few more details to plan your trip:",
            "clarifying_questions": question_texts,
            "progress_steps": ["Asking clarifying questions"],
        }

    error = state.get("error")
    if error:
        return {
            "trip_session": {},
            "message": error,
            "progress_steps": [f"Error: {error}"],
        }

    trip_data = state.get("trip_session") or {}
    if not trip_data:
        return {
            "trip_session": {},
            "message": "No trip data available.",
            "progress_steps": ["Error: no trip data"],
        }

    flight_results = state.get("flight_results") or trip_data.get("flight_results") or []
    hotel_results = state.get("hotel_results") or trip_data.get("hotel_results") or []
    destination_research = state.get("destination_research") or trip_data.get("research") or {}
    logger.info(f"Synthesize: trip_session keys={list(trip_data.keys())[:10]}, flights={len(flight_results)}, hotels={len(hotel_results)}, research={bool(destination_research)}")
    itinerary_suggestions = destination_research.get("itinerary_suggestions", {})
    days_data = itinerary_suggestions.get("days", [])

    try:
        trip_session = TripSession(**trip_data)
    except Exception as e:
        logger.error(f"Failed to create TripSession from data: {e}")
        trip_session = TripSession(
            trip_id=trip_data.get("trip_id", ""),
            origin=trip_data.get("origin", ""),
            destination=trip_data.get("destination", ""),
            departure_date=trip_data.get("departure_date") or "",
            return_date=trip_data.get("return_date"),
            duration_days=trip_data.get("duration_days", 5),
            travelers=trip_data.get("travelers", 2),
        )

    if flight_results:
        trip_session.flight_results = flight_results[:10]
        cheapest = min(flight_results, key=lambda f: f.get("price", float("inf")))
        trip_session.selected_flight = cheapest
        trip_session.budget.flight_actual = cheapest.get("price")

    if hotel_results:
        trip_session.hotel_results = hotel_results[:10]
        valid = [h for h in hotel_results if h.get("price_per_night", 0) > 0]
        if valid:
            best = min(valid, key=lambda h: h.get("price_per_night", float("inf")))
            trip_session.selected_hotel = best
            trip_session.budget.hotel_actual = best.get("total_price", 0)

    if destination_research:
        trip_session.research = itinerary_suggestions
        trip_session.sources = destination_research.get("sources", [])
        evidence_list = destination_research.get("evidence", [])
        if evidence_list:
            from travel_agent.schemas.trip import DestinationEvidence
            trip_session.evidence = [DestinationEvidence(**e) for e in evidence_list[:20]]

    if days_data:
        try:
            trip_session.itinerary = [DayPlan(**d) for d in days_data]
        except Exception as e:
            logger.error(f"Failed to parse itinerary days: {e}")
            trip_session.itinerary = []

    trip_session.status = "ready"
    trip_memory.save(trip_session)

    trip_dict = trip_session.to_dict()

    return {
        "trip_session": trip_dict,
        "message": f"Your {trip_session.destination} trip is ready!",
        "clarifying_questions": [],
        "progress_steps": ["Trip plan complete"],
    }


def dispatch_agents(state: TripState) -> dict[str, Any]:
    logger.info("Conditional dispatch: running only affected agents")
    impact = state.get("impact_analysis") or {}
    affected = set(impact.get("affected_agents", []))

    results: dict[str, Any] = {
        "flight_results": [],
        "hotel_results": [],
        "destination_research": None,
        "progress_steps": [],
    }

    if "flights" in affected:
        logger.info("Dispatch: running flight search")
        results.update(run_flight_search(state))
    else:
        logger.info("Dispatch: skipping flights (not affected)")

    if "hotels" in affected:
        logger.info("Dispatch: running hotel search")
        results.update(run_hotel_search(state))
    else:
        logger.info("Dispatch: skipping hotels (not affected)")

    if "research" in affected:
        logger.info("Dispatch: running destination research")
        results.update(run_destination_research(state))
    else:
        logger.info("Dispatch: skipping research (not affected)")

    return results


def build_trip_graph() -> StateGraph:
    graph = StateGraph(TripState)

    graph.add_node("extract_params", extract_trip_params_node)
    graph.add_node("validate_params", validate_trip_params_node)
    graph.add_node("merge_answers", merge_user_answers)
    graph.add_node("detect_impact", detect_impact_node)
    graph.add_node("load_session", load_session)
    graph.add_node("update_state", update_trip_state)
    graph.add_node("dispatch", dispatch_agents)
    graph.add_node("synthesize", synthesize_itinerary)

    graph.add_edge(START, "extract_params")
    graph.add_conditional_edges(
        "extract_params",
        route_after_extract,
        {
            "validate": "validate_params",
            "error": "synthesize",
        },
    )
    graph.add_conditional_edges(
        "validate_params",
        route_after_validate,
        {
            "ask_user": "synthesize",
            "continue": "merge_answers",
        },
    )
    graph.add_edge("merge_answers", "detect_impact")
    graph.add_edge("detect_impact", "load_session")
    graph.add_edge("load_session", "update_state")

    graph.add_conditional_edges(
        "update_state",
        route_after_impact,
        {
            "run_agents": "dispatch",
            "synthesize": "synthesize",
        },
    )

    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


_compiled_graph: StateGraph | None = None


def get_trip_graph() -> StateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_trip_graph().compile()
    return _compiled_graph


def reset_trip_graph() -> None:
    global _compiled_graph
    _compiled_graph = None
