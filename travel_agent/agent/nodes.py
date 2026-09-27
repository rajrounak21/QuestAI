from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import date
from typing import Any

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from travel_agent.agent.state import FlightState, HotelState, TripState
from backend.agents.research.services.llm import init_llm, init_llm_light

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are a flight search assistant. Extract flight search parameters from the user's natural language query.

Today's date is {today}.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "origin": "IATA airport code (e.g., DEL for Delhi, DXB for Dubai, JFK for New York)",
  "destination": "IATA airport code",
  "departure_date": "YYYY-MM-DD",
  "return_date": "YYYY-MM-DD or null if one-way",
  "trip_type": "one_way or round_trip",
  "passengers": 1,
  "cabin_class": "economy, premium_economy, business, or first",
  "currency": "USD"
}}

Rules:
- Convert city names to IATA airport codes (e.g., Delhi → DEL, Dubai → DXB, London → LHR, New York → JFK)
- If the user says "next Friday" or "tomorrow", calculate the actual date from today ({today})
- If no return date is mentioned, set return_date to null and trip_type to "one_way"
- If a return date is mentioned, set trip_type to "round_trip"
- Default passengers to 1 if not specified
- Default cabin_class to "economy" if not specified
- Default currency to "USD"
- If the query is not about flights (e.g., hotels, restaurants), return {{"error": "This query is not about flights."}}

User query: {query}"""


def extract_params_node(state: FlightState) -> dict[str, Any]:
    logger.info("Running extract_params node")

    user_query = state["user_query"]
    today = date.today()

    prompt = EXTRACT_PROMPT.format(
        query=user_query,
        today=today.strftime("%Y-%m-%d"),
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=1024)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        params = _parse_json(text)

        if "error" in params:
            return {
                "error": params["error"],
                "search_complete": True,
                "progress_steps": ["Error: not a flight query"],
            }

        return {
            "extracted_params": params,
            "progress_steps": ["Extracted flight parameters from your request"],
        }

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {
            "error": "I couldn't understand your flight request. Please try rephrasing.",
            "search_complete": True,
            "progress_steps": ["Error: could not understand request"],
        }


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


HOTEL_EXTRACT_PROMPT = """You are a hotel search assistant. Extract hotel search parameters from the user's natural language query.

Today's date is {today}.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "location": "city or hotel location (e.g., Dubai, New York, Bali)",
  "check_in": "YYYY-MM-DD",
  "check_out": "YYYY-MM-DD",
  "guests": 2,
  "rooms": 1,
  "max_price": null,
  "min_rating": null,
  "hotel_class": null,
  "sort_by": "relevance"
}}

Rules:
- If the user says "next Friday" or "tomorrow", calculate the actual date from today ({today})
- If check_out is not mentioned, default to check_in + 1 night
- Default guests to 2 if not specified
- Default rooms to 1 if not specified
- Default sort_by to "relevance" unless specified (options: relevance, price, rating, reviews)
- If the user says "cheap" or "budget", set sort_by to "price"
- If the user says "best" or "top rated", set sort_by to "rating"
- If max_price is mentioned as a number, use it; otherwise null
- If min_rating is mentioned (e.g., "4 star", "4.5 plus"), use the number; otherwise null
- If hotel_class is mentioned (e.g., "5 star hotel"), use the number; otherwise null
- If the query is not about hotels (e.g., flights, restaurants), return {{"error": "This query is not about hotels."}}

User query: {query}"""


def extract_hotel_params_node(state: HotelState) -> dict[str, Any]:
    logger.info("Running extract_hotel_params node")

    user_query = state["user_query"]
    today = date.today()

    prompt = HOTEL_EXTRACT_PROMPT.format(
        query=user_query,
        today=today.strftime("%Y-%m-%d"),
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=1024)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        params = _parse_json(text)

        if "error" in params:
            return {
                "error": params["error"],
                "search_complete": True,
                "progress_steps": ["Error: not a hotel query"],
            }

        return {
            "extracted_params": params,
            "progress_steps": ["Extracted hotel parameters from your request"],
        }

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {
            "error": "I couldn't understand your hotel request. Please try rephrasing.",
            "search_complete": True,
            "progress_steps": ["Error: could not understand request"],
        }


TRIP_EXTRACT_PROMPT = """You are a trip planning assistant. Extract trip parameters from the user's natural language query.

Today's date is {today}.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "intent": "new_trip or follow_up",
  "origin": "city name or IATA code",
  "destination": "city name",
  "departure_date": "YYYY-MM-DD",
  "return_date": "YYYY-MM-DD or null",
  "duration_days": 5,
  "travelers": 2,
  "budget": {{"max_total": null, "currency": "USD"}},
  "hotel_preferences": {{"class": null, "sort_by": "relevance"}},
  "flight_preferences": {{"stops": null, "cabin_class": "economy"}},
  "interests": [],
  "follow_up_type": null,
  "follow_up_target": null
}}

Rules:
- If the user says "next Friday" or "tomorrow", calculate the actual date from today ({today})
- If the user explicitly mentions a date (e.g., "October 24", "next Monday"), convert to YYYY-MM-DD
- If NO dates are mentioned at all, set departure_date to null and return_date to null
- If no return date but duration is mentioned, calculate return_date from departure_date + duration
- If return date mentioned, calculate duration_days from departure to return
- Default duration_days to 5 if not specified
- Default travelers to 2 if not specified
- Default currency to "USD"
- Default budget.max_total to null if not specified (user has no budget constraint)
- interests = list of things they want to do (e.g., ["adventure", "food", "culture"])

FOLLOW-UP DETECTION (very important):
- If the message is a short follow-up like "make it cheaper", "change dates", "upgrade hotel", "nonstop flights", etc., set intent to "follow_up"
- follow_up_type mappings:
  - "make it cheaper", "reduce cost", "lower price", "save money" → follow_up_type: "make_cheaper"
  - "change dates", "different dates", "move to next month" → follow_up_type: "update_dates"
  - "upgrade hotel", "better hotel", "5 star" → follow_up_type: "update_hotel"
  - "nonstop", "direct flights", "no layovers" → follow_up_type: "update_flight"
  - "add more days", "extend trip", "longer trip" → follow_up_type: "extend_trip"
  - "what's the total", "total cost", "how much" → follow_up_type: "cost_check"
- follow_up_target = the specific change (e.g., "5-star", "nonstop", "make_cheaper")
- If the query is not about trip planning at all, return {{"error": "This query is not about trip planning."}}

User query: {query}"""


def extract_trip_params_node(state: TripState) -> dict[str, Any]:
    logger.info("Running extract_trip_params node")

    user_query = state["user_query"]
    today = date.today()

    prompt = TRIP_EXTRACT_PROMPT.format(
        query=user_query,
        today=today.strftime("%Y-%m-%d"),
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=1024)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        params = _parse_json(text)

        if "error" in params:
            return {
                "error": params["error"],
                "progress_steps": ["Error: not a trip planning query"],
            }

        return {
            "extracted_params": params,
            "progress_steps": ["Extracted trip parameters from your request"],
        }

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {
            "error": "I couldn't understand your trip request. Please try rephrasing.",
            "progress_steps": ["Error: could not understand request"],
        }


VALIDATE_TRIP_PROMPT = """You are a trip planning assistant. Check if the user provided enough information to plan a trip.

Extracted parameters:
{extracted_params}

Today's date: {today}

Determine which CRITICAL fields are missing or unclear. A trip CANNOT be planned without these:
1. **destination** — Where are they going? (REQUIRED)
2. **origin** — Where are they traveling from? (REQUIRED for flights)
3. **departure_date** — When do they leave? (REQUIRED)
4. **return_date** or **duration_days** — When do they return / how long? (REQUIRED)
5. **budget** — What is their total budget? (REQUIRED for filtering options)
6. **travelers** — How many people? (has default: 2)

Optional but helpful:
- hotel_preferences (star class, amenities)
- flight_preferences (nonstop, cabin class)
- interests (adventure, food, culture, etc.)

Return ONLY a JSON object:
{{
  "is_complete": true/false,
  "missing_fields": [
    {{"field": "field_name", "question": "natural human-like question to ask", "why": "why this is needed", "options": ["option1", "option2"] or null}}
  ],
  "greeting": "A friendly 1-sentence greeting acknowledging what they DID provide"
}}

Rules:
- If destination is missing or null, that's the #1 question
- If origin is missing or null, ask where they're flying from
- If departure_date is missing or null, ask when they want to travel — the frontend will show a date picker for this
- If budget is missing or null, ask about budget (give range options like "Budget ($500-1000)", "Mid-range ($1000-2500)", "Luxury ($2500+)")
- null or empty values mean the field is MISSING — treat them the same as not provided
- Keep questions conversational and friendly, like a travel agent would ask
- Group related questions together (max 4 questions at once)
- If everything is complete, set is_complete to true and missing_fields to []
- If user provided budget as a word like "cheap" or "luxury", map it to a range
- "greeting" should mention what they already told you (e.g., "Great, a trip to Dubai!")
- IMPORTANT: Always add "Other" as the last option in any options list so users can type their own value


User query: {user_query}"""


def validate_trip_params_node(state: TripState) -> dict[str, Any]:
    logger.info("Running validate_trip_params node")

    extracted = state.get("extracted_params") or {}
    intent = extracted.get("intent", "new_trip")

    if intent == "follow_up":
        logger.info("Follow-up detected, skipping validation")
        return {
            "clarifying_questions": [],
            "progress_steps": ["Follow-up detected, proceeding"],
        }

    user_query = state.get("user_query", "")
    today = date.today()

    prompt = VALIDATE_TRIP_PROMPT.format(
        extracted_params=json.dumps(extracted, indent=2),
        today=today.strftime("%Y-%m-%d"),
        user_query=user_query,
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=1024)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        result = _parse_json(text)

        if result.get("is_complete"):
            logger.info("Trip parameters are complete")
            return {
                "clarifying_questions": [],
                "progress_steps": ["All trip parameters collected"],
            }

        questions = result.get("missing_fields", [])
        greeting = result.get("greeting", "")
        logger.info(f"Missing {len(questions)} fields: {[q.get('field') for q in questions]}")

        return {
            "clarifying_questions": questions,
            "message": greeting,
            "progress_steps": [f"Need more info: {', '.join(q.get('field', '?') for q in questions)}"],
        }

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return {
            "clarifying_questions": [],
            "progress_steps": ["Validation check failed, proceeding with available info"],
        }


IMPACT_PROMPT = """Analyze what changed in a trip request and return ONLY the changed fields as structured JSON.

Current trip state:
{current_state}

User requested change:
{change_request}

Return ONLY a JSON object with two keys:
{{
  "changes": {{
    "field_path": "new_value"
  }},
  "response": "brief conversational response acknowledging the change"
}}

Rules:
- Only include fields that ACTUALLY CHANGED
- Valid field paths: origin, destination, departure_date, return_date, duration_days, travelers, budget.max_total, hotel_preferences, flight_preferences, interests
- For nested fields like hotel_preferences, use dot notation: "hotel_preferences.class"
- For flight preferences: "flight_preferences.stops"
- For budget: "budget.max_total"
- "response" should be a short conversational message like "Got it! I've updated your hotel to 5-star."

Examples:
- "Make hotel 5-star" → {{"changes": {{"hotel_preferences.class": "5-star"}}, "response": "Got it! Upgrading your hotel to 5-star."}}
- "Change dates to Oct 20" → {{"changes": {{"departure_date": "2026-10-20"}}, "response": "Updating your dates to October 20th."}}
- "Nonstop flights" → {{"changes": {{"flight_preferences.stops": "nonstop"}}, "response": "I'll search for nonstop flights."}}
- "What's the total?" → {{"changes": {{}}, "response": "Let me check your trip total."}}
- "Make it cheaper" → {{"changes": {{"budget.max_total": 1500}}, "response": "I'll look for cheaper options within your new budget."}}

User query: {query}"""


def detect_impact_node(state: TripState) -> dict[str, Any]:
    logger.info("Running detect_impact node")

    extracted = state.get("extracted_params") or {}
    trip_session = state.get("trip_session") or {}
    user_query = state.get("user_query", "")

    intent = extracted.get("intent", "new_trip")
    follow_up_type = extracted.get("follow_up_type")

    if intent == "new_trip":
        return {
            "impact_analysis": {
                "affected_agents": ["flights", "hotels", "research", "itinerary"],
                "changes": {},
                "response": "",
            },
            "progress_steps": ["Planning your new trip"],
        }

    if follow_up_type == "cost_check":
        return {
            "impact_analysis": {
                "affected_agents": [],
                "changes": {},
                "response": "",
            },
            "progress_steps": ["Checking trip cost"],
        }

    if follow_up_type in ("view_flight", "view_hotel"):
        return {
            "impact_analysis": {
                "affected_agents": [],
                "changes": {},
                "response": "",
            },
            "progress_steps": ["Viewing trip details"],
        }

    current_state_text = ""
    if trip_session:
        current_state_text = f"""
Destination: {trip_session.get('destination', 'TBD')}
Origin: {trip_session.get('origin', 'TBD')}
Dates: {trip_session.get('departure_date', 'TBD')} to {trip_session.get('return_date', 'TBD')}
Duration: {trip_session.get('duration_days', 'TBD')} days
Travelers: {trip_session.get('travelers', 'TBD')}
Budget: ${trip_session.get('budget', {}).get('max_total', 'not set')}
Hotel class: {trip_session.get('hotel_preferences', {}).get('class', 'not set')}
Flight stops: {trip_session.get('flight_preferences', {}).get('stops', 'not set')}
"""

    prompt = IMPACT_PROMPT.format(
        current_state=current_state_text or "No existing trip",
        change_request=user_query,
        query=user_query,
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=512)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        impact = _parse_json(text)

        changes = impact.get("changes", {})
        response = impact.get("response", "")

        from travel_agent.agent.trip_graph import DEPENDENCY_MAP
        affected = set()
        for field_path in changes:
            agents = DEPENDENCY_MAP.get(field_path, [])
            affected.update(agents)

        steps = []
        if "flights" in affected:
            steps.append("Updating flights")
        if "hotels" in affected:
            steps.append("Updating hotels")
        if "research" in affected:
            steps.append("Researching destination")
        if "itinerary" in affected:
            steps.append("Rebuilding itinerary")

        return {
            "impact_analysis": {
                "affected_agents": list(affected),
                "changes": changes,
                "response": response,
            },
            "progress_steps": steps or ["No changes needed"],
        }

    except Exception as e:
        logger.error(f"Impact detection failed: {e}")
        return {
            "impact_analysis": {
                "affected_agents": ["flights", "hotels", "research", "itinerary"],
                "changes": {},
                "response": "",
            },
            "progress_steps": ["Re-running all searches"],
        }
