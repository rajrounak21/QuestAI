from __future__ import annotations

import hashlib
import logging
from typing import Any

from travel_agent.schemas.flight import (
    AirportInfo,
    FlightResult,
    FlightSearchResponse,
    FlightSegment,
    StopDetail,
)

logger = logging.getLogger(__name__)


def _format_duration(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    if hours > 0:
        return f"{hours}h"
    return f"{mins}m"


def _make_flight_id(airline: str, flight_number: str, departure_time: str) -> str:
    raw = f"{airline}-{flight_number}-{departure_time}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _parse_segment(segment: dict[str, Any]) -> FlightSegment:
    dep = segment.get("departure_airport", {})
    arr = segment.get("arrival_airport", {})

    return FlightSegment(
        airline=segment.get("airline", ""),
        airline_logo=segment.get("airline_logo", ""),
        flight_number=segment.get("flight_number", ""),
        departure=AirportInfo(
            airport=dep.get("id", ""),
            time=dep.get("time", ""),
            terminal=dep.get("terminal"),
        ),
        arrival=AirportInfo(
            airport=arr.get("id", ""),
            time=arr.get("time", ""),
            terminal=arr.get("terminal"),
        ),
        duration=segment.get("duration", 0),
        aircraft=segment.get("airplane"),
        travel_class=segment.get("travel_class", ""),
    )


def _parse_stop(layover: dict[str, Any]) -> StopDetail:
    duration_min = layover.get("duration", 0)
    return StopDetail(
        airport=layover.get("id", ""),
        duration=_format_duration(duration_min),
        arrival="",
        departure="",
    )


def normalize_flights(
    raw: dict[str, Any],
    booking_link: str = "",
) -> list[FlightResult]:
    all_entries: list[dict[str, Any]] = []

    for entry in raw.get("best_flights", []):
        all_entries.append(entry)

    for entry in raw.get("other_flights", []):
        all_entries.append(entry)

    results: list[FlightResult] = []

    for entry in all_entries:
        flights = entry.get("flights", [])
        if not flights:
            continue

        price = entry.get("price", 0)
        if not price or price <= 0:
            logger.debug(f"Skipping flight with no price: {flights[0].get('flight_number', '?')}")
            continue

        first_seg = flights[0]
        last_seg = flights[-1]

        dep = first_seg.get("departure_airport", {})
        arr = last_seg.get("arrival_airport", {})

        segments = [_parse_segment(s) for s in flights]

        layovers = entry.get("layovers", [])
        stop_details = [_parse_stop(l) for l in layovers]

        total_duration = entry.get("total_duration", 0)
        price = entry.get("price", 0)
        airline = first_seg.get("airline", "")
        airline_logo = entry.get("airline_logo", "") or first_seg.get("airline_logo", "")
        flight_number = first_seg.get("flight_number", "")

        flight_id = _make_flight_id(
            airline, flight_number, dep.get("time", "")
        )

        result = FlightResult(
            id=flight_id,
            airline=airline,
            airline_logo=airline_logo,
            flight_number=flight_number,
            departure=AirportInfo(
                airport=dep.get("id", ""),
                time=dep.get("time", ""),
            ),
            arrival=AirportInfo(
                airport=arr.get("id", ""),
                time=arr.get("time", ""),
            ),
            duration=total_duration,
            duration_display=_format_duration(total_duration),
            stops=len(flights) - 1,
            stop_details=stop_details,
            price=float(price),
            currency="USD",
            booking_link=booking_link,
            segments=segments,
            source="google_flights",
        )

        results.append(result)

    logger.info(f"Normalized {len(results)} flights from {len(all_entries)} raw entries")
    return results


def build_search_response(
    request_dict: dict[str, Any],
    raw: dict[str, Any],
) -> FlightSearchResponse:
    booking_link = raw.get("search_metadata", {}).get("google_flights_url", "")

    flights = normalize_flights(raw, booking_link=booking_link)

    from travel_agent.schemas.flight import FlightSearchRequest, TripType

    request = FlightSearchRequest(**request_dict)

    return FlightSearchResponse(
        request=request,
        flights=flights,
        total_results=len(flights),
    )
