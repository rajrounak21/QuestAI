from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from job_agent.models.job_models import JobSearchRequest

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


def google_jobs_search(request: JobSearchRequest) -> dict[str, Any]:
    client = _get_client()
    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": request.query,
        "location": request.location,
        "google_domain": request.google_domain,
        "gl": request.gl,
        "hl": request.hl,
    }
    # remove empty location to avoid SerpApi error - but location is useful
    if not params["location"]:
        params.pop("location")
    logger.info(f"SerpAPI Google Jobs: q='{request.query}' location='{request.location}' gl={request.gl}")
    try:
        results = client.search(params)
        data = results.data
        count = len(data.get("jobs_results", []))
        logger.info(f"SerpAPI response: {count} jobs_results for q='{request.query}'")
        return data
    except Exception as e:
        logger.error(f"SerpAPI Google Jobs search failed: {e}")
        raise


def google_jobs_search_multi(requests: list[JobSearchRequest]) -> list[dict[str, Any]]:
    """Execute up to 3 searches, return list of raw responses."""
    raws = []
    for req in requests[:3]:
        try:
            raw = google_jobs_search(req)
            raws.append(raw)
        except Exception as e:
            logger.warning(f"Skipping failed job search q='{req.query}': {e}")
            raws.append({"jobs_results": [], "error": str(e), "search_metadata": {}})
    return raws
