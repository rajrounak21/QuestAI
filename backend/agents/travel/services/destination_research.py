from __future__ import annotations

import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agents.research.tools.search import google_search, google_news
from backend.agents.research.services.source_processor import process_sources
from backend.agents.research.services.llm import init_llm, init_llm_light

logger = logging.getLogger(__name__)

SEARCH_QUERIES_PROMPT = """Generate 3-4 Google Search queries to research a trip to a SPECIFIC destination.

Destination: {destination}
Duration: {duration_days} days
Travelers: {travelers} people
Interests: {interests}

IMPORTANT: Every query MUST include the destination name "{destination}" to get relevant results.

Generate queries to find:
1. Top attractions and things to do in {destination}
2. Opening hours and ticket prices in {destination}
3. Best restaurants and food in {destination}
4. Any recent news about {destination} travel

Return ONLY a JSON object:
{{"queries": ["query1 with destination name", "query2 with destination name", "query3 with destination name", "query4 with destination name"]}}"""

ITINERARY_PROMPT = """You are an expert travel planner. Create a detailed day-by-day itinerary for a trip.

Destination: {destination}
Duration: {duration_days} days
Dates: {departure_date} to {return_date}
Travelers: {travelers} people
Budget for activities: {currency} {activity_budget}

Evidence from research (use as reference, but also use your knowledge of {destination}):
{evidence}

CRITICAL RULES:
- You MUST return a complete itinerary with ALL {duration_days} days
- Each day MUST have 3-5 activities (morning, afternoon, evening)
- Use your knowledge of {destination} attractions, restaurants, and landmarks
- Include famous places in {destination} even if not in the evidence
- Estimate realistic costs for each activity
- Keep total activity cost within {currency} {activity_budget}
- Include a mix: sightseeing, food, culture, relaxation
- EVERY day MUST include inner-city transport as its own activity lines: airport-hotel transfers on first/last day, plus metro/taxi/tuk-tuk/bus rides between activities using {destination}'s real local transport (e.g. Dubai Metro/taxi fares, Delhi Metro fares) with realistic per-ride costs — the user moves between these places, so transport is a real cost, not zero
- Transport lines look like: {{"time": "09:30", "name": "Metro: hotel to Old Dubai", "description": "Red Line, ~25 min", "estimated_cost": 2.0, "location": "Dubai Metro"}}

Return ONLY a valid JSON object (no markdown, no explanation):
{{"days": [{{"day": 1, "title": "Arrival and Exploration", "activities": [{{"time": "10:00", "name": "Activity Name", "description": "Brief description", "estimated_cost": 25.0, "location": "Location name", "source_url": ""}}]}}]}}"""

FALLBACK_ITINERARY_PROMPT = """Create a {duration_days}-day itinerary for {destination}.

Dates: {departure_date} to {return_date}
Travelers: {travelers} people
Budget: {currency} {activity_budget} for activities

Use your knowledge of {destination} to create a realistic day-by-day plan.
Include 3-5 activities per day with times, costs, and locations.
Every day MUST also include inner-city transport lines (airport-hotel transfers, metro/taxi rides between spots with realistic local fares) as activities with estimated_cost, inside the {currency} {activity_budget} activity budget.

Return ONLY valid JSON:
{{"days": [{{"day": 1, "title": "Day Title", "activities": [{{"time": "10:00", "name": "Name", "description": "Description", "estimated_cost": 25.0, "location": "Location", "source_url": ""}}]}}]}}"""


def generate_search_queries(
    destination: str,
    duration_days: int,
    travelers: int,
    interests: list[str],
) -> list[str]:
    prompt = SEARCH_QUERIES_PROMPT.format(
        destination=destination,
        duration_days=duration_days,
        travelers=travelers,
        interests=", ".join(interests) if interests else "general sightseeing",
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=512)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)
        return result.get("queries", [])
    except Exception as e:
        logger.error(f"Failed to generate search queries: {e}")
        return [
            f"top things to do in {destination} attractions",
            f"{destination} opening hours ticket prices",
            f"best restaurants in {destination} food",
            f"{destination} travel news events",
        ]


def _run_single_search(query: str) -> list:
    try:
        return google_search(query, num_results=5)
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return []


def _run_news_search(query: str) -> list:
    try:
        return google_news(query, num_results=5)
    except Exception as e:
        logger.error(f"News search failed for '{query}': {e}")
        return []


def _parse_itinerary_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not data.get("days"):
        raise ValueError("Empty days array")
    return data


def research_destination(
    destination: str,
    duration_days: int,
    travelers: int,
    departure_date: str,
    return_date: str,
    interests: list[str],
    activity_budget: float = 300.0,
    currency: str = "USD",
) -> dict[str, Any]:
    logger.info(f"Researching destination: {destination}")

    queries = generate_search_queries(destination, duration_days, travelers, interests)
    logger.info(f"Search queries: {queries}")

    valid_queries = [q for q in queries if destination.lower() in q.lower()]
    if not valid_queries:
        valid_queries = [
            f"top things to do in {destination} attractions",
            f"{destination} opening hours ticket prices",
            f"best restaurants in {destination} food",
            f"{destination} travel news events",
        ]
    queries = valid_queries

    all_results = []
    news_query = f"{destination} travel news events"

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for q in queries:
            futures[executor.submit(_run_single_search, q)] = q
        futures[executor.submit(_run_news_search, news_query)] = "news"

        for future in as_completed(futures):
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Search task failed: {e}")

    processed = process_sources(all_results)

    dest_lower = destination.lower()
    relevant = [
        s for s in processed
        if dest_lower in s.title.lower() or dest_lower in s.snippet.lower()
    ]
    if len(relevant) >= 3:
        processed = relevant
        logger.info(f"Filtered to {len(processed)} destination-relevant sources")
    else:
        logger.info(f"Kept all {len(processed)} sources (only {len(relevant)} matched destination)")

    evidence_text = format_evidence(processed)

    itinerary_data = {"days": []}

    try:
        llm = init_llm(temperature=0.0, max_tokens=4096)
        itinerary_prompt = ITINERARY_PROMPT.format(
            destination=destination,
            duration_days=duration_days,
            departure_date=departure_date,
            return_date=return_date,
            travelers=travelers,
            currency=currency,
            activity_budget=activity_budget,
            evidence=evidence_text,
        )
        raw = llm.invoke(itinerary_prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        logger.info(f"LLM itinerary response length: {len(text)}")
        itinerary_data = _parse_itinerary_json(text)
        logger.info(f"Generated {len(itinerary_data.get('days', []))} days from evidence")
    except Exception as e:
        logger.warning(f"Itinerary from evidence failed ({e}), trying fallback...")
        try:
            fallback_prompt = FALLBACK_ITINERARY_PROMPT.format(
                destination=destination,
                duration_days=duration_days,
                departure_date=departure_date,
                return_date=return_date,
                travelers=travelers,
                currency=currency,
                activity_budget=activity_budget,
            )
            llm2 = init_llm(temperature=0.0, max_tokens=4096)
            raw2 = llm2.invoke(fallback_prompt)
            text2 = raw2.content if hasattr(raw2, "content") else str(raw2)
            itinerary_data = _parse_itinerary_json(text2)
            logger.info(f"Fallback generated {len(itinerary_data.get('days', []))} days")
        except Exception as e2:
            logger.error(f"Fallback itinerary also failed: {e2}")
            itinerary_data = {"days": []}

    evidence_list = []
    for s in processed:
        evidence_list.append({
            "attraction": s.title[:80],
            "claim": s.snippet[:200],
            "source_url": s.url,
            "source_type": s.source_type.value,
            "confidence": "medium",
        })

    sources_list = [{"url": s.url, "title": s.title} for s in processed[:15]]

    return {
        "evidence": evidence_list,
        "sources": sources_list,
        "itinerary_suggestions": itinerary_data,
    }


def format_evidence(processed_sources: list) -> str:
    lines = []
    for i, s in enumerate(processed_sources[:10]):
        source_type = s.source_type.value if hasattr(s.source_type, 'value') else str(s.source_type)
        lines.append(f"[{i+1}] {s.title[:80]} ({source_type})")
        lines.append(f"    {s.snippet[:150]}")
    return "\n".join(lines)
