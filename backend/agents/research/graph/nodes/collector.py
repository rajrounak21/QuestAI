from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.schemas.sources import SourceType
from backend.agents.research.services.progress import report as report_progress
from backend.agents.research.tools.search import search

logger = logging.getLogger(__name__)

SOURCE_TYPE_MAP = {
    "google": SourceType.GOOGLE,
    "scholar": SourceType.SCHOLAR,
    "news": SourceType.NEWS,
}

# No single search may hang the whole run. SerpAPI/LLM clients have no
# reliable built-in timeout, so each query is bounded here. Worst case for a
# round is now ~len(queries) x SEARCH_TIMEOUT_S instead of forever.
SEARCH_TIMEOUT_S = 60
PROGRESS_EVERY_N = 3


def _bounded_search(query_text: str, source_type: SourceType) -> list:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(search, query_text, source_type, 10)
        try:
            return fut.result(timeout=SEARCH_TIMEOUT_S)
        except FuturesTimeout:
            logger.warning(f"Search timed out after {SEARCH_TIMEOUT_S}s: {query_text[:80]}")
            return []
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []


def collector_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running collector node")

    queries = state.get("search_queries", [])
    if not queries:
        return {"raw_results": [], "searches_performed": []}

    report_progress("searching", f"Searching {len(queries)} queries")
    already_done = {
        s.get("query", "") for s in state.get("searches_performed", [])
    }

    all_results: list[dict[str, Any]] = []
    searches_done: list[dict[str, Any]] = []

    for q in queries:
        query_text = q.get("query", "").replace("‑", "-")
        source_type_str = q.get("source_type", "google")

        if not query_text:
            continue

        if query_text in already_done:
            logger.info(f"Skipping duplicate query: {query_text}")
            continue

        source_type = SOURCE_TYPE_MAP.get(source_type_str, SourceType.GOOGLE)
        logger.info(f"Searching [{source_type_str}]: {query_text}")

        if len(searches_done) % PROGRESS_EVERY_N == 0:
            report_progress("searching", f"Searching ({len(searches_done) + 1}/{len(queries)} queries)")

        results = _bounded_search(query_text, source_type)

        for r in results:
            all_results.append(r.to_dict())

        searches_done.append({
            "query": query_text,
            "source_type": source_type_str,
            "results_count": len(results),
            "round": state.get("current_round", 1),
        })

    logger.info(f"Collector: {len(all_results)} total results from {len(searches_done)} searches")
    return {
        "raw_results": all_results,
        "searches_performed": searches_done,
    }
