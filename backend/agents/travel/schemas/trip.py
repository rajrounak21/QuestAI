from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TripStatus(str, Enum):
    PLANNING = "planning"
    READY = "ready"
    BOOKED = "booked"


class TripBudget(BaseModel):
    currency: str = ""
    max_total: float | None = None
    flight_budget: float | None = None
    hotel_budget: float | None = None
    flight_actual: float | None = None
    hotel_actual: float | None = None
    activities_estimated: float = 0.0

    @property
    def total_estimated(self) -> float:
        total = 0.0
        if self.flight_actual is not None:
            total += self.flight_actual
        if self.hotel_actual is not None:
            total += self.hotel_actual
        total += self.activities_estimated
        return total

    @property
    def remaining(self) -> float | None:
        if self.max_total is None:
            return None
        return self.max_total - self.total_estimated


class Activity(BaseModel):
    time: str = ""
    name: str = ""
    description: str = ""
    estimated_cost: float = 0.0
    location: str = ""
    source_url: str | None = None


class DayPlan(BaseModel):
    day: int = 0
    date: str = ""
    title: str = ""
    activities: list[Activity] = Field(default_factory=list)


class DestinationEvidence(BaseModel):
    attraction: str = ""
    claim: str = ""
    source_url: str = ""
    source_type: str = ""
    confidence: str = "medium"


class TripSession(BaseModel):
    trip_id: str = ""
    status: TripStatus = TripStatus.PLANNING
    origin: str = ""
    destination: str = ""
    departure_date: str = ""
    return_date: str | None = None
    duration_days: int = 5
    travelers: int = 1
    budget: TripBudget = Field(default_factory=TripBudget)
    hotel_preferences: dict[str, Any] = Field(default_factory=dict)
    flight_preferences: dict[str, Any] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    selected_flight: dict[str, Any] | None = None
    selected_hotel: dict[str, Any] | None = None
    flight_results: list[dict[str, Any]] = Field(default_factory=list)
    hotel_results: list[dict[str, Any]] = Field(default_factory=list)
    research: dict[str, Any] = Field(default_factory=dict)
    itinerary: list[DayPlan] = Field(default_factory=list)
    evidence: list[DestinationEvidence] = Field(default_factory=list)
    sources: list[dict[str, str]] = Field(default_factory=list)
    conversation: list[dict[str, str]] = Field(default_factory=list)
    flight_input_hash: str | None = None
    hotel_input_hash: str | None = None
    research_input_hash: str | None = None
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        status_val = self.status.value if hasattr(self.status, 'value') else str(self.status)

        itinerary_list = []
        for d in self.itinerary:
            if hasattr(d, 'model_dump'):
                itinerary_list.append(d.model_dump())
            elif isinstance(d, dict):
                itinerary_list.append(d)

        evidence_list = []
        for e in self.evidence[:20]:
            if hasattr(e, 'model_dump'):
                evidence_list.append(e.model_dump())
            elif isinstance(e, dict):
                evidence_list.append(e)

        return {
            "trip_id": self.trip_id,
            "status": status_val,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "duration_days": self.duration_days,
            "travelers": self.travelers,
            "budget": self.budget.model_dump() if hasattr(self.budget, 'model_dump') else self.budget,
            "hotel_preferences": self.hotel_preferences,
            "flight_preferences": self.flight_preferences,
            "interests": self.interests,
            "selected_flight": self.selected_flight,
            "selected_hotel": self.selected_hotel,
            "flight_results": self.flight_results[:5],
            "hotel_results": self.hotel_results[:5],
            "research": self.research,
            "itinerary": itinerary_list,
            "evidence": evidence_list,
            "sources": self.sources[:10],
            "conversation": self.conversation,
            "flight_input_hash": self.flight_input_hash,
            "hotel_input_hash": self.hotel_input_hash,
            "research_input_hash": self.research_input_hash,
            "last_updated": self.last_updated,
        }


class TripRequest(BaseModel):
    query: str
    session_id: str | None = None


class TripChatRequest(BaseModel):
    message: str


class TripResponse(BaseModel):
    trip: dict[str, Any]
    message: str = ""
    error: str | None = None


def compute_flight_hash(origin: str, destination: str, departure_date: str, return_date: str | None, travelers: int, preferences: dict[str, Any]) -> str:
    key = f"{origin}|{destination}|{departure_date}|{return_date}|{travelers}|{json.dumps(preferences, sort_keys=True)}"
    return hashlib.md5(key.encode()).hexdigest()


def compute_hotel_hash(destination: str, departure_date: str, return_date: str | None, travelers: int, budget_per_night: float | None, preferences: dict[str, Any]) -> str:
    key = f"{destination}|{departure_date}|{return_date}|{travelers}|{budget_per_night}|{json.dumps(preferences, sort_keys=True)}"
    return hashlib.md5(key.encode()).hexdigest()


def compute_research_hash(destination: str, interests: list[str]) -> str:
    key = f"{destination}|{json.dumps(sorted(interests))}"
    return hashlib.md5(key.encode()).hexdigest()
