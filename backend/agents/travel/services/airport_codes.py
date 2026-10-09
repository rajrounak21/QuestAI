"""Resolve trip origin/destination into IATA airport codes for google_flights.

Order:
  1. Already an IATA code -> pass through.
  2. Static city table (airports.py) -> instant, no LLM.
  3. A single narrow LLM call -> covers the long tail of cities the table
     does not know.

Step 3 is not optional. google_flights rejects anything that is not a 3-letter
airport code with a 400, and the trip stores what the user typed ("Mumbai",
"Bali"). Resolving that is information the session does not contain, so it was
never the redundant sentence-parsing round-trip that could simply be deleted -
which is why removing that LLM broke every city-named flight search.

Hotels need none of this: google_hotels accepts a city name.
"""

from __future__ import annotations

import logging

from backend.agents.travel.services.airports import resolve_iata

logger = logging.getLogger(__name__)

_IATA_PROMPT = """You map places to the IATA airport code a traveller would fly into.

Return ONLY a JSON object:
{{
  "origin_code": "3-letter IATA code or null",
  "destination_code": "3-letter IATA code or null"
}}

Rules:
- Use the MAIN airport that serves the city.
- If a place is ALREADY a 3-letter code, echo it back unchanged.
- If you genuinely do not know the code, use null. Never guess.

Origin: {origin}
Destination: {destination}"""


def _via_llm(origin: str, destination: str) -> tuple[str | None, str | None]:
    """One narrow call, only for places the table missed."""
    try:
        from backend.agents.shared.json_llm import JsonCallFailed, invoke_json

        prompt = _IATA_PROMPT.format(origin=origin, destination=destination)
        data, _ = invoke_json(prompt, max_tokens=200, agent="trip-iata")
        got_origin = str(data.get("origin_code") or "").strip().upper()
        got_dest = str(data.get("destination_code") or "").strip().upper()

        def _clean(code: str) -> str | None:
            return code if len(code) == 3 and code.isalpha() else None

        return _clean(got_origin), _clean(got_dest)
    except Exception as e:  # a resolution failure must not kill the run
        logger.warning(f"IATA fallback failed for {origin!r} -> {destination!r}: {e}")
        return None, None


def resolve_airports(origin: str, destination: str) -> tuple[str | None, str | None]:
    """(origin_code, destination_code); either may be None if unresolvable."""
    from_table_o = resolve_iata(origin)
    from_table_d = resolve_iata(destination)

    if from_table_o and from_table_d:
        return from_table_o, from_table_d

    llm_o, llm_d = _via_llm(origin, destination)
    final_o = from_table_o or llm_o
    final_d = from_table_d or llm_d

    if from_table_o or llm_o:
        logger.info(f"IATA: table={origin!r}->{from_table_o} llm={llm_o}")
    if from_table_d or llm_d:
        logger.info(f"IATA: table={destination!r}->{from_table_d} llm={llm_d}")

    return final_o, final_d
