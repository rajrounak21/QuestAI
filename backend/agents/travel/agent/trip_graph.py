from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agents.travel.agent.state import TripState
from backend.agents.travel.agent.nodes import (
    extract_trip_params_node,
    detect_impact_node,
    validate_trip_params_node,
    _parse_json,
)
from backend.agents.travel.services.trip_memory import current_user_id, trip_memory
from backend.agents.travel.schemas.trip import (
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

    # Keep the router's session id so saves land on the Mongo doc created
    # up front (a random id here would orphan it).
    session = trip_memory.get_or_create(session_id=session_id)
    return {
        "trip_session": session.to_dict(),
        "progress_steps": [f"Created new trip: {session.trip_id}"],
    }


def _clean_budget_number(value: Any) -> float | None:
    try:
        num = float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
    if num is None or not (100 <= num <= 100000):
        return None
    return num


def _apply_trip_change(session: TripSession, path: str, value: Any) -> bool:
    """Apply one dot-notation change from impact analysis. Returns True if applied."""
    if value is None or value == "":
        return False
    try:
        if path in ("origin", "destination"):
            setattr(session, path, str(value).strip())
            return True
        if path in ("departure_date", "return_date"):
            date.fromisoformat(str(value))  # validate
            setattr(session, path, str(value))
            return True
        if path == "duration_days":
            v = int(value)
            if 1 <= v <= 60:
                session.duration_days = v
                return True
            return False
        if path == "travelers":
            v = int(value)
            if 1 <= v <= 20:
                session.travelers = v
                return True
            return False
        if path == "interests" and isinstance(value, list):
            session.interests = [str(x) for x in value]
            return True
        if path == "budget.max_total":
            v = float(value)
            if 100 <= v <= 100000:
                session.budget.max_total = v
                return True
            return False
        if path.startswith("hotel_preferences.") or path.startswith("flight_preferences."):
            group, _, key = path.partition(".")
            prefs = getattr(session, group, None)
            if isinstance(prefs, dict) and key:
                prefs[key] = value
                return True
            return False
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Ignoring bad trip change {path}={value!r}: {e}")
        return False
    return False


def _need_input(
    session: TripSession,
    field: str,
    question: str,
    why: str = "",
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Ask the user instead of assuming. Returns early so no agent runs and
    the stored trip is left untouched."""
    q: dict[str, Any] = {"field": field, "question": question}
    if why:
        q["why"] = why
    if options:
        q["options"] = options
    return {
        "trip_session": session.to_dict(),
        "clarifying_questions": [q],
        "impact_analysis": {"affected_agents": [], "changes": {}, "response": ""},
        "message": question,
        "progress_steps": ["Asking for missing details"],
    }


def _merge_for_preview(
    extracted: dict[str, Any],
    stored: dict[str, Any],
    impact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview merge for the confirm gate: extracted wins where present,
    then impact-detected values, then stored trip fills every gap.
    Only quotes message + stored values, never invents."""
    stored = stored or {}
    impact = impact or {}
    s_bud = stored.get("budget") or {}
    e_bud = extracted.get("budget") or {}

    def _pick(*vals: Any, default: Any = "") -> Any:
        for v in vals:
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return v
        return default

    def _pick_num(*vals: Any, default: Any = None) -> Any:
        for v in vals:
            if v is None:
                continue
            return v
        return default

    max_total = _pick_num(
        e_bud.get("max_total"), impact.get("budget.max_total"), s_bud.get("max_total")
    )
    return {
        "origin": _pick(extracted.get("origin"), impact.get("origin"), stored.get("origin", "")),
        "destination": _pick(
            extracted.get("destination"), impact.get("destination"), stored.get("destination", "")
        ),
        "departure_date": _pick(
            extracted.get("departure_date"),
            impact.get("departure_date"),
            stored.get("departure_date", ""),
        ),
        "return_date": _pick(
            extracted.get("return_date"), impact.get("return_date"), stored.get("return_date")
        ),
        "duration_days": _pick_num(
            extracted.get("duration_days"),
            impact.get("duration_days"),
            stored.get("duration_days", 5),
        ),
        "travelers": _pick_num(
            extracted.get("travelers"), stored.get("travelers", 2)
        ),
        "budget": {
            "currency": e_bud.get("currency") or s_bud.get("currency", "USD"),
            "max_total": max_total,
        },
        "hotel_preferences": extracted.get("hotel_preferences")
        or stored.get("hotel_preferences")
        or {},
        "flight_preferences": extracted.get("flight_preferences")
        or stored.get("flight_preferences")
        or {},
        "interests": extracted.get("interests") or stored.get("interests") or [],
    }


def _preview_summary(preview: dict[str, Any]) -> str:
    """One honest line built ONLY from preview values (message + stored)."""
    route = (
        f"{preview.get('origin') or '?'} → {preview.get('destination') or '?'}"
    )
    bits = [route]
    dep = preview.get("departure_date") or ""
    ret = preview.get("return_date") or ""
    if dep:
        bits.append(f"{dep}{(' → ' + ret) if ret else ''}")
    if preview.get("duration_days"):
        bits.append(f"{preview['duration_days']} days")
    if preview.get("travelers"):
        bits.append(f"{preview['travelers']} travelers")
    max_total = (preview.get("budget") or {}).get("max_total")
    if max_total is not None:
        bits.append(f"${max_total:g}")
    return (
        "Got it — "
        + ", ".join(bits)
        + ". Review below: create a new session, or overwrite this trip?"
    )


def update_trip_state(state: TripState) -> dict[str, Any]:
    logger.info("Updating trip state")

    extracted = state.get("extracted_params") or {}
    trip_data = state.get("trip_session") or {}
    intent = extracted.get("intent", "new_trip")
    impact = state.get("impact_analysis") or {}
    impact_changes = impact.get("changes") or {}

    stored_dest = ((trip_data or {}).get("destination") or "").strip()
    stored_orig = ((trip_data or {}).get("origin") or "").strip()

    def _differs(new_val: Any, stored_val: str) -> bool:
        if not isinstance(new_val, str) or not new_val.strip():
            return False
        return new_val.strip().lower() != stored_val.lower()

    # Location gate: ANY location change on an existing trip — whether the
    # message was classified new_trip or follow_up, whether the value came
    # from extract or impact — opens the form modal. Never apply silently,
    # never rebuild silently.
    loc_changed = (
        _differs(extracted.get("destination"), stored_dest)
        or _differs(extracted.get("origin"), stored_orig)
        or _differs(impact_changes.get("destination"), stored_dest)
        or _differs(impact_changes.get("origin"), stored_orig)
    )

    if stored_dest and (intent == "new_trip" or loc_changed):
        # Existing trip + new location (or new-trip message): NEVER apply or
        # rebuild silently. Show the merged preview in a form modal; the user
        # picks create-new-session vs overwrite there.
        if state.get("confirmed_scope") != "overwrite":
            preview = _merge_for_preview(extracted, trip_data, impact_changes)
            question = _preview_summary(preview)
            return {
                "trip_session": trip_data,
                "preview_trip": preview,
                "clarifying_questions": [
                    {"field": "confirm_details", "question": question}
                ],
                "impact_analysis": {"affected_agents": [], "changes": {}, "response": ""},
                "message": question,
                "progress_steps": ["Confirming trip details"],
            }
        # else: modal-approved overwrite — fall through to the rebuild below.

    if intent == "new_trip":
        # Merge rule: extracted wins where present, stored trip fills gaps.
        # (Modal submits are usually complete; this is the safety net.)
        stored = trip_data or {}
        s_bud = stored.get("budget") or {}
        departure_date = extracted.get("departure_date") or stored.get("departure_date")
        return_date = extracted.get("return_date") or stored.get("return_date")
        duration = extracted.get("duration_days") or stored.get("duration_days") or 5

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
        if budget_data.get("max_total") is None:
            budget_data = {**budget_data, "max_total": s_bud.get("max_total")}
        new_trip = TripSession(
            trip_id=trip_data.get("trip_id", ""),
            origin=extracted.get("origin") or stored.get("origin", ""),
            destination=extracted.get("destination") or stored.get("destination", ""),
            departure_date=departure_date,
            return_date=return_date,
            duration_days=duration,
            travelers=extracted.get("travelers") or stored.get("travelers", 2),
            budget=TripBudget(
                currency=budget_data.get("currency") or s_bud.get("currency", "USD"),
                max_total=budget_data.get("max_total"),
            ),
            hotel_preferences=extracted.get("hotel_preferences")
            or stored.get("hotel_preferences")
            or {},
            flight_preferences=extracted.get("flight_preferences")
            or stored.get("flight_preferences")
            or {},
            interests=extracted.get("interests") or stored.get("interests") or [],
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
    # impact / impact_changes already defined above (used by the gate).
    handled: set[str] = set()

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
        dep = extracted.get("departure_date") or impact_changes.get("departure_date")
        dur = extracted.get("duration_days") or impact_changes.get("duration_days")
        if not dep and not dur:
            # No usable date anywhere — ask, never assume.
            return _need_input(
                session,
                "departure_date",
                "Which date should your trip start?",
                "I need an exact date to search flights and hotels — I won't guess one.",
            )
        if dep:
            session.departure_date = dep
            handled.add("departure_date")
        if dur:
            try:
                dur_int = int(dur)
                if 1 <= dur_int <= 60:
                    session.duration_days = dur_int
                    handled.add("duration_days")
            except (ValueError, TypeError):
                pass
        dep = date.fromisoformat(session.departure_date)
        session.return_date = (dep + timedelta(days=session.duration_days)).isoformat()
        handled.add("return_date")

    elif follow_up_type == "make_cheaper" or follow_up_type == "update_budget":
        # Priority: explicit number from extract LLM > impact LLM's value (it
        # sees the current budget in the snapshot) > documented default.
        # No raw-message scanning here — the query belongs to the LLMs.
        new_max = _clean_budget_number((extracted.get("budget") or {}).get("max_total"))
        if new_max is None:
            new_max = _clean_budget_number(impact_changes.get("budget.max_total"))
        current_max = session.budget.max_total
        if new_max is None:
            if follow_up_type == "make_cheaper":
                new_max = round((current_max or 2000) * 0.7, 2)
            else:
                new_max = current_max  # update with no number: don't invent shrinkage
        elif follow_up_type == "make_cheaper" and current_max and new_max >= current_max:
            # LLM invented a number in the wrong direction — enforce cheaper.
            new_max = round(current_max * 0.7, 2)
        session.budget.max_total = new_max
        handled.add("budget.max_total")

    elif follow_up_type == "update_hotel":
        if follow_up_target:
            session.hotel_preferences["class"] = follow_up_target
            handled.add("hotel_preferences.class")
        else:
            return _need_input(
                session,
                "hotel_class",
                "Which hotel class should I book?",
                "So I only show hotels in the category you want.",
                ["3-star", "4-star", "5-star"],
            )

    elif follow_up_type == "update_flight":
        if follow_up_target:
            session.flight_preferences["stops"] = follow_up_target
            handled.add("flight_preferences.stops")
        else:
            return _need_input(
                session,
                "flight_stops",
                "Nonstop only, or are stops OK?",
                "So I only show flights you would actually take.",
                ["nonstop", "1 stop"],
            )

    elif follow_up_type == "extend_trip":
        dur = impact_changes.get("duration_days") or extracted.get("duration_days")
        if dur is None:
            return _need_input(
                session,
                "duration_days",
                "How many days should the trip be now?",
                "I need the total length to rebuild flights, hotels and the itinerary.",
            )
        try:
            dur_int = int(dur)
            if 1 <= dur_int <= 60:
                session.duration_days = dur_int
                handled.add("duration_days")
        except (ValueError, TypeError):
            return _need_input(
                session,
                "duration_days",
                "How many days should the trip be now?",
                "I need the total length to rebuild flights, hotels and the itinerary.",
            )
        if extracted.get("departure_date"):
            session.departure_date = extracted["departure_date"]
            handled.add("departure_date")
        dep = date.fromisoformat(session.departure_date)
        session.return_date = (dep + timedelta(days=session.duration_days)).isoformat()
        handled.add("return_date")

    # Generic fallback: apply anything the impact step detected (e.g.
    # destination/origin/travelers changes) that no branch above consumed.
    # Hashes below then re-run exactly the affected agents.
    for path, value in impact_changes.items():
        if path in handled:
            continue
        if path in ("departure_date", "return_date"):
            # Corroboration rule: an impact-proposed date applies only if the
            # extractor saw the SAME date (it parses the message with today's
            # context). An uncorroborated date is an LLM invention — drop it
            # instead of corrupting stored dates.
            if not value or str(value) != str(extracted.get(path) or ""):
                logger.warning(
                    f"Dropping uncorroborated LLM date {path}={value!r}"
                )
                continue
        _apply_trip_change(session, path, value)

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
    # Pass-through: the router already feeds the extract LLM the original
    # request plus the user's answers, so it returns complete params.
    # No regex parsing of the user message happens here anymore.
    logger.info("Merging user answers into trip params")
    return {
        "extracted_params": state.get("extracted_params") or {},
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
        from backend.agents.travel.agent.flight_agent import run_flight_search as search_flights
        _bump_searches(state, "flights")
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
        from backend.agents.travel.agent.hotel_agent import run_hotel_search as search_hotels
        _bump_searches(state, "hotels")
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
        from backend.agents.travel.services.destination_research import research_destination
        _bump_searches(state, "research")
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

    if state.get("cap_hit"):
        # Search budget exhausted: keep the stored trip untouched and let
        # the router pause with a CONTINUE affordance.
        return {
            "trip_session": state.get("trip_session") or {},
            "message": "Search budget paused.",
            "clarifying_questions": [],
            "cap_hit": True,
            "progress_steps": ["Search budget paused"],
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
            "preview_trip": state.get("preview_trip"),
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
            from backend.agents.travel.schemas.trip import DestinationEvidence
            trip_session.evidence = [DestinationEvidence(**e) for e in evidence_list[:20]]

    if days_data:
        try:
            trip_session.itinerary = [DayPlan(**d) for d in days_data]
        except Exception as e:
            logger.error(f"Failed to parse itinerary days: {e}")
            trip_session.itinerary = []

    # Sum per-activity estimates into the budget (was always 0 before).
    try:
        trip_session.budget.activities_estimated = round(
            sum(
                float(getattr(a, "estimated_cost", 0) or 0)
                for d in (trip_session.itinerary or [])
                for a in (getattr(d, "activities", None) or [])
            ),
            2,
        )
    except Exception as e:
        logger.warning(f"Could not sum activity costs: {e}")

    trip_session.status = "ready"
    trip_memory.save(trip_session)

    trip_dict = trip_session.to_dict()

    return {
        "trip_session": trip_dict,
        "message": f"Your {trip_session.destination} trip is ready!",
        "clarifying_questions": [],
        "progress_steps": ["Trip plan complete"],
    }


def _bump_searches(state: TripState, agent: str) -> None:
    """Count real provider calls for the per-trip cap. Skips silently
    outside a user-scoped run (direct unit tests)."""
    from backend.database.trip_sessions import SEARCH_COSTS, bump_searches

    uid = current_user_id()
    sid = state.get("session_id")
    if not uid or not sid:
        return
    try:
        bump_searches(uid, sid, SEARCH_COSTS.get(agent, 1))
    except Exception as e:
        logger.warning(f"Spend accounting failed: {e}")


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

    uid = current_user_id()
    sid = state.get("session_id")
    if uid and sid:
        from backend.database.trip_sessions import MAX_TRIP_SEARCHES, get_spent

        spent, extra = get_spent(uid, sid)
        if spent >= MAX_TRIP_SEARCHES + extra:
            logger.warning(f"Trip {sid} hit search cap ({spent}/{MAX_TRIP_SEARCHES + extra}) — pausing")
            results["cap_hit"] = True
            results["progress_steps"] = ["Search budget paused"]
            return results

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
