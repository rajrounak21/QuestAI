from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from backend.agents.shopping.schemas.shopping import (
    ProductSource,
    ShoppingProduct,
    ShoppingSearchRequest,
    ShoppingSearchResponse,
)

logger = logging.getLogger(__name__)


def _parse_price(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _make_product_id(title: str, product_url: str) -> str:
    raw = f"{title}-{product_url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def normalize_products(raw: dict[str, Any]) -> list[ShoppingProduct]:
    results: list[ShoppingProduct] = []
    shopping_results = raw.get("shopping_results", [])
    search_metadata = raw.get("search_metadata", {})
    search_url = search_metadata.get("google_shopping_url", "") or search_metadata.get("google_url", "")

    for item in shopping_results:
        title = item.get("title", "") or item.get("product_title", "")
        if not title:
            continue

        product_url = item.get("product_link", "") or item.get("serpapi_product_api", "")
        if not product_url:
            logger.debug(f"Skipping product with no link: {title[:60]}")
            continue

        # price handling: extracted_price preferred, fallback to price string
        extracted = item.get("extracted_price")
        price_str = item.get("price", "")
        price = _parse_price(extracted if extracted is not None else price_str)
        if price <= 0:
            logger.debug(f"Skipping product with no price: {title[:60]}")
            continue

        image_url = item.get("product_thumbnail", "") or item.get("thumbnail", "") or item.get("serpapi_thumbnail", "")
        if not image_url:
            logger.debug(f"Skipping product with no image: {title[:60]}")
            continue

        store = item.get("source", "") or item.get("seller", "") or ""
        # normalize Amazon.in variants to "Amazon" for unified Store filter
        if store.strip().lower() in ("amazon.in", "amazon.com", "amazon"):
            store = "Amazon"
        rating = item.get("rating")
        if rating is not None:
            try:
                rating = float(rating)
            except (ValueError, TypeError):
                rating = None

        reviews = item.get("reviews")
        if reviews is not None:
            try:
                reviews = int(reviews)
            except (ValueError, TypeError):
                reviews = None

        tag = item.get("tag")
        delivery = item.get("delivery")
        extensions = item.get("extensions", []) or []

        product_id = _make_product_id(title, product_url)

        product = ShoppingProduct(
            id=product_id,
            title=title,
            price=price,
            currency="INR",
            store=store,
            rating=rating,
            reviews=reviews,
            image_url=image_url,
            product_url=product_url,
            tag=tag,
            delivery=delivery,
            extensions=extensions,
            source=ProductSource(
                product_link=product_url,
                serpapi_product_api=item.get("serpapi_product_api", ""),
                search_url=search_url,
            ),
        )
        results.append(product)

    logger.info(f"Normalized {len(results)} products from {len(shopping_results)} raw results")
    return results


def normalize_amazon_products(raw: dict[str, Any]) -> list[ShoppingProduct]:
    results: list[ShoppingProduct] = []
    # SerpApi amazon uses organic_results (or search_results)
    items = raw.get("organic_results") or raw.get("search_results") or []
    search_metadata = raw.get("search_metadata", {})
    search_url = search_metadata.get("amazon_url", "") or search_metadata.get("google_url", "")

    for item in items:
        title = item.get("title", "") or item.get("product_title", "")
        if not title:
            continue

        product_url = item.get("product_link", "") or item.get("link", "") or item.get("serpapi_product_api", "")
        if not product_url:
            logger.debug(f"Skipping amazon product with no link: {title[:60]}")
            continue

        # Amazon price handling: various shapes
        #  - prices: {raw, extracted_price}
        #  - price: string
        #  - extracted_price directly
        price_val: Any = None
        if isinstance(item.get("prices"), dict):
            price_val = item["prices"].get("extracted_price") or item["prices"].get("raw")
        if price_val is None:
            price_val = item.get("extracted_price") if item.get("extracted_price") is not None else item.get("price", "")
        price = _parse_price(price_val)
        if price <= 0:
            logger.debug(f"Skipping amazon product with no price: {title[:60]}")
            continue

        image_url = (
            item.get("product_photo", "")
            or item.get("thumbnail", "")
            or item.get("serpapi_thumbnail", "")
            or item.get("image", "")
        )
        if not image_url:
            logger.debug(f"Skipping amazon product with no image: {title[:60]}")
            continue

        # store is always Amazon for this source
        store = "Amazon"

        rating = item.get("rating") or item.get("product_star_rating")
        if rating is not None:
            try:
                rating = float(str(rating).strip())
            except (ValueError, TypeError):
                rating = None

        reviews = item.get("reviews") or item.get("product_num_ratings") or item.get("product_num_reviews")
        if reviews is not None:
            try:
                # reviews may be "1,234" or "(1234)"
                reviews = int(re.sub(r"[^\d]", "", str(reviews)) or "0")
                if reviews == 0:
                    reviews = None
            except (ValueError, TypeError):
                reviews = None

        tag = item.get("tag")
        if isinstance(tag, list):
            tag = tag[0] if tag else None
        # amazon often has coupon/price savings in extensions
        delivery = item.get("delivery") or item.get("delivery_info")
        if isinstance(delivery, list):
            delivery = delivery[0] if delivery else None
        extensions = item.get("extensions", []) or []
        if isinstance(extensions, str):
            extensions = [extensions]

        product_id = _make_product_id(title, product_url)

        product = ShoppingProduct(
            id=product_id,
            title=title,
            price=price,
            currency="INR",
            store=store,
            rating=rating,
            reviews=reviews,
            image_url=image_url,
            product_url=product_url,
            tag=tag,
            delivery=delivery,
            extensions=extensions,
            source=ProductSource(
                product_link=product_url,
                serpapi_product_api=item.get("serpapi_product_api", ""),
                search_url=search_url,
            ),
        )
        product.source.engine = "amazon"
        results.append(product)

    logger.info(f"Normalized {len(results)} amazon products from {len(items)} raw results")
    return results


def _dedupe_key(title: str, price: float) -> str:
    slug = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    slug = re.sub(r"\s+", " ", slug)
    # price bucket ±1% so ₹28,999 vs ₹29,000 still dedupes
    bucket = round(price / 100) if price > 0 else 0
    return f"{slug}|{bucket}"


def dedupe_products(products: list[ShoppingProduct]) -> list[ShoppingProduct]:
    """Merge Google Shopping + Amazon duplicates. Deterministic, no LLM.

    Prefer the record with a rating; otherwise keep first seen.
    """
    seen: dict[str, ShoppingProduct] = {}
    for p in products:
        key = _dedupe_key(p.title, p.price)
        existing = seen.get(key)
        if existing is None:
            seen[key] = p
            continue
        # prefer rated over unrated; on tie keep first (stable order)
        if existing.rating is None and p.rating is not None:
            seen[key] = p
    return list(seen.values())


def flatten_product(p: ShoppingProduct) -> dict[str, Any]:
    """Mongo-safe product: flat `source` string so the frontend never
    needs to know the API difference (google_shopping vs amazon)."""
    data = p.model_dump()
    engine = (data.get("source") or {}).get("engine", "google_shopping")
    data["source"] = engine
    return data


def build_shopping_response(
    request_dict: dict[str, Any],
    raw: dict[str, Any],
) -> ShoppingSearchResponse:
    request = ShoppingSearchRequest(**request_dict)
    products = normalize_products(raw)
    return ShoppingSearchResponse(
        request=request,
        products=products,
        total_results=len(products),
    )


def build_combined_response(
    request_dict: dict[str, Any],
    all_products: list[ShoppingProduct],
) -> ShoppingSearchResponse:
    request = ShoppingSearchRequest(**request_dict)
    # Every product carries the request currency (INR/USD/...) so the
    # frontend can format prices per location.
    for p in all_products:
        p.currency = request.currency or "INR"
    return ShoppingSearchResponse(
        request=request,
        products=all_products,
        total_results=len(all_products),
    )
