from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from backend.agents.travel.schemas.hotel import (
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


def _extract_area(nearby_places: list[dict[str, Any]]) -> str:
    """Best-effort location label — Google gives nearby places, not addresses."""
    if not nearby_places:
        return ""
    names = [str(n.get("name", "")).strip() for n in nearby_places]
    names = [n for n in names if n]
    if not names:
        return ""
    # Prefer a neighbourhood/landmark over the airport.
    for n in names:
        if "airport" not in n.lower():
            return n
    return names[0]


def _maps_link(gps: dict[str, Any], name: str) -> str:
    lat = gps.get("latitude") if isinstance(gps, dict) else None
    lon = gps.get("longitude") if isinstance(gps, dict) else None
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    if name:
        from urllib.parse import quote_plus

        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name)}"
    return ""


def normalize_hotels(raw: dict[str, Any], currency: str = "USD") -> list[HotelResult]:
    properties = raw.get("properties", [])
    results: list[HotelResult] = []
    dropped_no_link = 0

    for prop in properties:
        name = prop.get("name", "")
        if not name:
            continue

        booking_link = (prop.get("link", "") or "").strip()
        if not booking_link:
            # No bookable URL — not actionable, filter out.
            dropped_no_link += 1
            continue

        rate = prop.get("rate_per_night", {})
        price_per_night = _parse_price(rate.get("extracted_lowest"))
        # NOTE: no price does NOT drop the hotel (long stays like 30+ nights
        # often return no rates). Price shows as "unavailable", booking link stays.

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
            address=_extract_area(prop.get("nearby_places", [])),
            price_per_night=price_per_night,
            total_price=total_price,
            currency=currency,
            hotel_class=_extract_star_rating(
                prop.get("hotel_class"), prop.get("extracted_hotel_class")
            ),
            amenities=prop.get("amenities", []),
            check_in_time=prop.get("check_in_time", ""),
            check_out_time=prop.get("check_out_time", ""),
            free_cancellation=bool(prop.get("free_cancellation")),
            deal=prop.get("deal"),
            booking_link=booking_link,
            maps_link=_maps_link(prop.get("gps_coordinates", {}), name),
            source="google_hotels",
        )

        results.append(result)

    logger.info(f"Normalized {len(results)} hotels from {len(properties)} properties (dropped {dropped_no_link} without booking link)")
    return results


def build_hotel_search_response(
    request_dict: dict[str, Any],
    raw: dict[str, Any],
) -> HotelSearchResponse:
    from backend.agents.travel.schemas.hotel import HotelSearchRequest

    request = HotelSearchRequest(**request_dict)

    # google_hotels returns native_currency as {} and formatted_price as None, so
    # the only place the currency exists is search_parameters. Hardcoding "USD"
    # relabelled every result whenever a non-USD currency was requested.
    hotels = normalize_hotels(raw, currency=request.currency)

    return HotelSearchResponse(
        request=request,
        hotels=hotels,
        total_results=len(hotels),
    )
