from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SortBy(str, Enum):
    RELEVANCE = "relevance"
    PRICE = "price"
    RATING = "rating"
    REVIEWS = "reviews"


class HotelSearchRequest(BaseModel):
    location: str
    check_in: str
    check_out: str
    guests: int = 2
    rooms: int = 1
    currency: str = "USD"
    max_price: float | None = None
    min_rating: float | None = None
    hotel_class: int | None = None
    amenities: list[str] = Field(default_factory=list)
    sort_by: SortBy = SortBy.RELEVANCE


class HotelResult(BaseModel):
    id: str = ""
    name: str = ""
    image: str = ""
    images: list[str] = Field(default_factory=list)
    rating: float | None = None
    reviews: int | None = None
    address: str = ""
    price_per_night: float = 0.0
    total_price: float = 0.0
    currency: str = "USD"
    hotel_class: int | None = None
    amenities: list[str] = Field(default_factory=list)
    check_in_time: str = ""
    check_out_time: str = ""
    free_cancellation: bool = False
    deal: str | None = None
    booking_link: str = ""
    source: str = "google_hotels"


class HotelSearchResponse(BaseModel):
    request: HotelSearchRequest
    hotels: list[HotelResult] = Field(default_factory=list)
    total_results: int = 0
    error: str | None = None
