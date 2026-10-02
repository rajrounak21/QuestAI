from __future__ import annotations

import logging
import os
from typing import Any

import serpapi

from backend.agents.shopping.schemas.shopping import ShoppingSearchRequest

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            raise ValueError("SERP_API_KEY not found in environment")
        _client = serpapi.Client(api_key=api_key)
    return _client


def amazon_search(request: ShoppingSearchRequest) -> dict[str, Any]:
    client = _get_client()
    params: dict[str, Any] = {
        "engine": "amazon",
        "k": request.query,
        "amazon_domain": request.amazon_domain,
    }

    logger.info(f"SerpAPI Amazon: k='{request.query}' domain={request.amazon_domain}")

    try:
        results = client.search(params)
        data = results.data
        # amazon returns organic_results or search_results depending on version
        count = len(data.get("organic_results", []) or data.get("search_results", []))
        logger.info(f"SerpAPI Amazon response: {count} organic_results")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Amazon search failed: {e}")
        raise
