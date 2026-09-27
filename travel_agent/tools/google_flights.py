from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from travel_agent.schemas.flight import CabinClass, FlightSearchRequest, TripType

load_dotenv()

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None

CABIN_CLASS_MAP = {
    CabinClass.ECONOMY: "1",
    CabinClass.PREMIUM_ECONOMY: "2",
    CabinClass.BUSINESS: "3",
    CabinClass.FIRST: "4",
}

TRIP_TYPE_MAP = {
    TripType.ONE_WAY: "2",
    TripType.ROUND_TRIP: "1",
}


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            raise ValueError("SERP_API_KEY not found in environment")
        _client = serpapi.Client(api_key=api_key)
    return _client


def google_flights_search(request: FlightSearchRequest) -> dict[str, Any]:
    client = _get_client()

    params: dict[str, Any] = {
        "engine": "google_flights",
        "departure_id": request.origin,
        "arrival_id": request.destination,
        "outbound_date": request.departure_date,
        "currency": request.currency,
        "hl": "en",
        "type": TRIP_TYPE_MAP.get(request.trip_type, "2"),
        "travel_class": CABIN_CLASS_MAP.get(request.cabin_class, "1"),
    }

    if request.trip_type == TripType.ROUND_TRIP and request.return_date:
        params["return_date"] = request.return_date

    if request.passengers > 1:
        params["adults"] = str(request.passengers)

    logger.info(
        f"SerpAPI Google Flights: {request.origin} → {request.destination} "
        f"on {request.departure_date} (type={params['type']})"
    )

    try:
        results = client.search(params)
        data = results.data
        logger.info(
            f"SerpAPI response: {len(data.get('best_flights', []))} best, "
            f"{len(data.get('other_flights', []))} other flights"
        )
        return data
    except Exception as e:
        logger.error(f"SerpAPI Google Flights search failed: {e}")
        raise
