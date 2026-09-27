from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from travel_agent.schemas.hotel import (
    HotelResult,
    HotelSearchResponse,
)

logger = logging.getLogger(__name__)


def _make_hotel_id(name: str, property_token: str) -> str:
    raw = f"{name}-{property_token}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _parse_price(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def _extract_star_rating(hotel_class: str | None, extracted: int | None) -> int | None:
    if extracted is not None:
        return extracted
    if hotel_class:
        match = re.search(r"(\d)", hotel_class)
        if match:
            return int(match.group(1))
    return None


def normalize_hotels(raw: dict[str, Any]) -> list[HotelResult]:
    properties = raw.get("properties", [])
    results: list[HotelResult] = []

    for prop in properties:
        name = prop.get("name", "")
        if not name:
            continue

        rate = prop.get("rate_per_night", {})
        price_per_night = _parse_price(rate.get("extracted_lowest"))
        if price_per_night <= 0:
            logger.debug(f"Skipping hotel with no price: {name}")
            continue

        total_rate = prop.get("total_rate", {})
        total_price = _parse_price(total_rate.get("extracted_lowest"))

        images = prop.get("images", [])
        image_urls = [img.get("thumbnail", "") for img in images if img.get("thumbnail")]
        primary_image = image_urls[0] if image_urls else ""

        property_token = prop.get("property_token", "")
        hotel_id = _make_hotel_id(name, property_token)

        result = HotelResult(
            id=hotel_id,
            name=name,
            image=primary_image,
            images=image_urls,
            rating=prop.get("overall_rating"),
            reviews=prop.get("reviews"),
            address="",
            price_per_night=price_per_night,
            total_price=total_price,
            currency="USD",
            hotel_class=_extract_star_rating(
                prop.get("hotel_class"), prop.get("extracted_hotel_class")
            ),
            amenities=prop.get("amenities", []),
            check_in_time=prop.get("check_in_time", ""),
            check_out_time=prop.get("check_out_time", ""),
            free_cancellation=bool(prop.get("free_cancellation")),
            deal=prop.get("deal"),
            booking_link=prop.get("link", ""),
            source="google_hotels",
        )

        results.append(result)

    logger.info(f"Normalized {len(results)} hotels from {len(properties)} properties")
    return results


def build_hotel_search_response(
    request_dict: dict[str, Any],
    raw: dict[str, Any],
) -> HotelSearchResponse:
    hotels = normalize_hotels(raw)

    from travel_agent.schemas.hotel import HotelSearchRequest

    request = HotelSearchRequest(**request_dict)

    return HotelSearchResponse(
        request=request,
        hotels=hotels,
        total_results=len(hotels),
    )
