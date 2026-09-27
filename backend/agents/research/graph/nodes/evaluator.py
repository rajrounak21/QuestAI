from __future__ import annotations

import logging
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.schemas.sources import ProcessedSource, SearchResult, SourceType
from backend.agents.research.services.source_processor import extract_evidence, process_sources

logger = logging.getLogger(__name__)


def evaluator_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running evaluator node")

    raw = state.get("raw_results", [])
    searches_this_round = state.get("searches_performed", [])
    current_round = state.get("current_round", 1)

    round_searches = [s for s in searches_this_round if s.get("round") == current_round]
    has_new_data = any(s.get("results_count", 0) > 0 for s in round_searches)

    if not has_new_data:
        logger.info("No new results this round, keeping existing evidence")
        return {
            "processed_sources": state.get("processed_sources", []),
            "evidence": [],
        }

    search_results = []
    for r in raw:
        st_str = r.get("source_type", "google")
        try:
            st = SourceType(st_str)
        except ValueError:
            st = SourceType.GOOGLE
        search_results.append(SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("snippet", ""),
            source_type=st,
            date=r.get("date", ""),
            raw_data=r.get("raw_data", {}),
        ))

    processed = process_sources(search_results)
    logger.info(f"Evaluator: {len(processed)} sources after dedup/filter")

    plan = state.get("research_plan", {})
    sub_questions = [
        sq.get("question", "") for sq in plan.get("sub_questions", [])
    ]
    if not sub_questions:
        sub_questions = [plan.get("goal", "research question")]

    new_evidence = extract_evidence(processed, sub_questions)

    existing_urls = {
        e.get("source", {}).get("url", "") for e in state.get("evidence", [])
    }
    deduped = []
    for e in new_evidence:
        url = e.get("source", {}).get("url", "")
        if url not in existing_urls:
            deduped.append(e)
            existing_urls.add(url)

    logger.info(f"Evaluator: {len(deduped)} new evidence items (deduped from {len(new_evidence)})")

    processed_dicts = [s.to_dict() for s in processed]

    return {
        "processed_sources": processed_dicts,
        "evidence": deduped,
    }
