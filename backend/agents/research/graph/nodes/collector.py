from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.schemas.sources import SourceType
from backend.agents.research.services.progress import check_cancellation, report as report_progress
from backend.agents.research.tools.search import search

logger = logging.getLogger(__name__)

SOURCE_TYPE_MAP = {
    "google": SourceType.GOOGLE,
    "scholar": SourceType.SCHOLAR,
    "news": SourceType.NEWS,
}

SEARCH_TIMEOUT_S = 12


def _execute_single_search(query_dict: dict, already_done: set) -> tuple[dict, list]:
    check_cancellation()
    query_text = query_dict.get("query", "").replace("‑", "-").strip()
    source_type_str = query_dict.get("source_type", "google")

    if not query_text or query_text in already_done:
        return ({"query": query_text, "source_type": source_type_str, "results_count": 0, "skipped": True}, [])

    source_type = SOURCE_TYPE_MAP.get(source_type_str, SourceType.GOOGLE)
    logger.info(f"Searching [{source_type_str}]: {query_text}")

    try:
        results = search(query_text, source_type, 8)
        res_dicts = [r.to_dict() for r in results]
        record = {
            "query": query_text,
            "source_type": source_type_str,
            "results_count": len(res_dicts),
        }
        return (record, res_dicts)
    except Exception as e:
        logger.warning(f"Search failed for '{query_text}': {e}")
        return ({"query": query_text, "source_type": source_type_str, "results_count": 0}, [])


def collector_node(state: ResearchState) -> dict[str, Any]:
    check_cancellation()
    logger.info("Running parallel collector node")

    queries = state.get("search_queries", [])
    if not queries:
        return {"raw_results": [], "searches_performed": []}

    report_progress("searching", f"Searching {len(queries)} sources in parallel")
    already_done = {
        s.get("query", "") for s in state.get("searches_performed", [])
    }

    all_results: list[dict[str, Any]] = []
    searches_done: list[dict[str, Any]] = []

    # Execute all searches in parallel with max 5 worker threads
    with ThreadPoolExecutor(max_workers=min(5, len(queries))) as pool:
        futures = [pool.submit(_execute_single_search, q, already_done) for q in queries]
        for fut in as_completed(futures):
            try:
                record, res_dicts = fut.result(timeout=SEARCH_TIMEOUT_S + 2)
                if not record.get("skipped"):
                    record["round"] = state.get("current_round", 1)
                    searches_done.append(record)
                    all_results.extend(res_dicts)
            except Exception as e:
                logger.warning(f"Parallel search worker error: {e}")

    logger.info(f"Collector: {len(all_results)} total results from {len(searches_done)} searches")
    return {
        "raw_results": all_results,
        "searches_performed": searches_done,
    }

