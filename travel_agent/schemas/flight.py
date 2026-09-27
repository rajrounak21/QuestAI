from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TripType(str, Enum):
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    trip_type: TripType = TripType.ONE_WAY
    passengers: int = 1
    cabin_class: CabinClass = CabinClass.ECONOMY
    currency: str = "USD"


class AirportInfo(BaseModel):
    airport: str = ""
    time: str = ""
    terminal: str | None = None


class StopDetail(BaseModel):
    airport: str = ""
    duration: str = ""
    arrival: str = ""
    departure: str = ""


class FlightSegment(BaseModel):
    airline: str = ""
    airline_logo: str = ""
    flight_number: str = ""
    departure: AirportInfo = Field(default_factory=AirportInfo)
    arrival: AirportInfo = Field(default_factory=AirportInfo)
    duration: int = 0
    aircraft: str | None = None
    travel_class: str = ""


class FlightResult(BaseModel):
    id: str = ""
    airline: str = ""
    airline_logo: str = ""
    flight_number: str = ""
    departure: AirportInfo = Field(default_factory=AirportInfo)
    arrival: AirportInfo = Field(default_factory=AirportInfo)
    duration: int = 0
    duration_display: str = ""
    stops: int = 0
    stop_details: list[StopDetail] = Field(default_factory=list)
    price: float = 0.0
    currency: str = "USD"
    booking_link: str = ""
    segments: list[FlightSegment] = Field(default_factory=list)
    source: str = "google_flights"


class FlightSearchResponse(BaseModel):
    request: FlightSearchRequest
    flights: list[FlightResult] = Field(default_factory=list)
    total_results: int = 0
    error: str | None = None
