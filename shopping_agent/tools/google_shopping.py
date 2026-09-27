from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from shopping_agent.models.shopping_models import ShoppingSearchRequest

load_dotenv()

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


def google_shopping_search(request: ShoppingSearchRequest) -> dict[str, Any]:
    client = _get_client()

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
        results = client.search(params)
        data = results.data
        count = len(data.get("shopping_results", []))
        logger.info(f"SerpAPI response: {count} shopping_results")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Google Shopping search failed: {e}")
        raise
