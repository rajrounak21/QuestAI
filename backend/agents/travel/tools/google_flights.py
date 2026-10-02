from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from backend.agents.travel.schemas.flight import CabinClass, FlightSearchRequest, TripType

load_dotenv(override=True)

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


def google_flights_return_options(
    departure_token: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
    currency: str = "USD",
    travelers: int = 1,
) -> dict[str, Any]:
    """Step 2 of the round-trip chain: return-leg options for a selected
    outbound flight. Entries carry booking_token for step 3."""
    client = _get_client()
    params: dict[str, Any] = {
        "engine": "google_flights",
        "departure_token": departure_token,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "type": "1",
        "currency": currency,
        "hl": "en",
    }

    if travelers > 1:
        params["adults"] = str(travelers)
    logger.info("SerpAPI Google Flights: return-leg options lookup")
    try:
        results = client.search(params)
        data = results.data
        logger.info("SerpAPI response: return-leg options received")
        return data
    except Exception as e:
        logger.error(f"SerpAPI return-leg lookup failed: {e}")
        raise


def google_flights_booking_options(
    booking_token: str,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str | None = None,
    trip_type: str = "one_way",
    currency: str = "USD",
    travelers: int = 1,
) -> dict[str, Any]:
    """Follow-up lookup: booking options (book with airline/OTA) for one flight.

    Costs 1 extra SerpApi search — call on demand (selected flight), never bulk.
    SerpApi needs the original search context alongside the token.
    """
    client = _get_client()
    is_round = trip_type == "round_trip" and bool(return_date)
    params: dict[str, Any] = {
        "engine": "google_flights",
        "booking_token": booking_token,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "type": "1" if is_round else "2",
        "currency": currency,
        "hl": "en",
    }
    if is_round:
        params["return_date"] = return_date
    if travelers > 1:
        params["adults"] = str(travelers)
    logger.info("SerpAPI Google Flights: booking options lookup")
    try:
        results = client.search(params)
        data = results.data
        logger.info(f"SerpAPI response: {len(data.get('booking_options', []))} booking options")
        return data
    except Exception as e:
        logger.error(f"SerpAPI booking options lookup failed: {e}")
        raise
