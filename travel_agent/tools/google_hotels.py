from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from travel_agent.schemas.hotel import HotelSearchRequest, SortBy

load_dotenv()

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None

SORT_BY_MAP = {
    SortBy.RELEVANCE: None,
    SortBy.PRICE: "3",
    SortBy.RATING: "8",
    SortBy.REVIEWS: "13",
}

RATING_MAP = {
    3.5: "7",
    4.0: "8",
    4.5: "9",
}


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            raise ValueError("SERP_API_KEY not found in environment")
        _client = serpapi.Client(api_key=api_key)
    return _client


def google_hotels_search(request: HotelSearchRequest) -> dict[str, Any]:
    client = _get_client()

    params: dict[str, Any] = {
        "engine": "google_hotels",
        "q": request.location,
        "check_in_date": request.check_in,
        "check_out_date": request.check_out,
        "adults": str(request.guests),
        "currency": request.currency,
        "hl": "en",
        "gl": "us",
    }

    sort_val = SORT_BY_MAP.get(request.sort_by)
    if sort_val:
        params["sort_by"] = sort_val

    if request.max_price is not None:
        params["max_price"] = str(int(request.max_price))

    if request.min_rating is not None:
        rating_key = min(RATING_MAP.keys(), key=lambda k: abs(k - request.min_rating))
        params["rating"] = RATING_MAP[rating_key]

    if request.hotel_class is not None:
        params["hotel_class"] = str(request.hotel_class)

    if request.amenities:
        params["amenities"] = ",".join(request.amenities)

    logger.info(
        f"SerpAPI Google Hotels: {request.location} "
        f"({request.check_in} to {request.check_out}, {request.guests} guests)"
    )

    try:
        results = client.search(params)
        data = results.data
        properties = data.get("properties", [])
        logger.info(f"SerpAPI response: {len(properties)} properties")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Google Hotels search failed: {e}")
        raise
