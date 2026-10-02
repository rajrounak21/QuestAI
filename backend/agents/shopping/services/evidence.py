from __future__ import annotations

from typing import Any

from backend.agents.shopping.schemas.shopping import ShoppingProduct


def build_evidence(products: list[ShoppingProduct], raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Evidence preservation: every product keeps its source references.

    LLM can organize but cannot create facts — evidence is always verbatim from raw.
    """
    evidence: list[dict[str, Any]] = []
    search_url = raw.get("search_metadata", {}).get("google_shopping_url", "")

    for p in products:
        evidence.append(
            {
                "product_id": p.id,
                "title": p.title,
                "source_type": "google_shopping",
                "product_url": p.product_url,
                "image_url": p.image_url,
                "store": p.store,
                "price": p.price,
                "search_url": p.source.search_url or search_url,
                "serpapi_product_api": p.source.serpapi_product_api,
            }
        )
    return evidence


def attach_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    """Return metadata about source preservation for debugging."""
    meta = raw.get("search_metadata", {})
    return {
        "engine": "google_shopping",
        "google_shopping_url": meta.get("google_shopping_url", ""),
        "total_raw": len(raw.get("shopping_results", [])),
    }
