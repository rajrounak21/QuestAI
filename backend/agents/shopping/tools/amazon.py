from __future__ import annotations

import logging
from typing import Any

from backend.agents.shared.serpapi_client import search as serpapi_search
from backend.agents.shopping.schemas.shopping import ShoppingSearchRequest

logger = logging.getLogger(__name__)


def amazon_search(request: ShoppingSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "amazon",
        "k": request.query,
        "amazon_domain": request.amazon_domain,
    }

    logger.info(f"SerpAPI Amazon: k='{request.query}' domain={request.amazon_domain}")

    try:
        results = serpapi_search(params)
        data = results.data
        # amazon returns organic_results or search_results depending on version
        count = len(data.get("organic_results", []) or data.get("search_results", []))
        logger.info(f"SerpAPI Amazon response: {count} organic_results")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Amazon search failed: {e}")
        raise
