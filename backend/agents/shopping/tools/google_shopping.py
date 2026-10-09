from __future__ import annotations

import logging
from typing import Any

from backend.agents.shared.serpapi_client import search as serpapi_search
from backend.agents.shopping.schemas.shopping import ShoppingSearchRequest

logger = logging.getLogger(__name__)


def google_shopping_search(request: ShoppingSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google_shopping",
        "q": request.query,
        "location": request.location,
        "gl": request.gl,
        "hl": request.hl,
        "google_domain": request.google_domain,
    }

    logger.info(f"SerpAPI Google Shopping: q='{request.query}' location='{request.location}' gl={request.gl}")

    try:
        results = serpapi_search(params)
        data = results.data
        count = len(data.get("shopping_results", []))
        logger.info(f"SerpAPI response: {count} shopping_results")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Google Shopping search failed: {e}")
        raise
