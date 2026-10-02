from __future__ import annotations

from pydantic import BaseModel, Field


class ShoppingSearchRequest(BaseModel):
    query: str
    location: str = "India"
    gl: str = "in"
    hl: str = "en"
    google_domain: str = "google.co.in"
    amazon_domain: str = "amazon.in"
    currency: str = "INR"


class ProductSource(BaseModel):
    engine: str = "google_shopping"
    product_link: str = ""
    serpapi_product_api: str = ""
    search_url: str = ""


class ShoppingProduct(BaseModel):
    id: str = ""
    title: str = ""
    price: float = 0.0
    currency: str = "INR"
    store: str = ""
    rating: float | None = None
    reviews: int | None = None
    image_url: str = ""
    product_url: str = ""
    tag: str | None = None
    delivery: str | None = None
    extensions: list[str] = Field(default_factory=list)
    source: ProductSource = Field(default_factory=ProductSource)


class ShoppingSearchResponse(BaseModel):
    request: ShoppingSearchRequest
    products: list[ShoppingProduct] = Field(default_factory=list)
    total_results: int = 0
    error: str | None = None
