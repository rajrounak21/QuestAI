from __future__ import annotations

import logging
from typing import Any

from backend.agents.travel.agent.graph import get_hotel_graph

logger = logging.getLogger(__name__)


def run_hotel_search(query: str) -> dict[str, Any]:
    graph = get_hotel_graph()

    initial_state = {
        "user_query": query,
        "extracted_params": None,
        "hotels": [],
        "total_results": 0,
        "error": None,
        "follow_up_question": None,
        "search_complete": False,
        "progress_steps": [],
    }

    logger.info(f"Starting hotel search: {query}")
    result = graph.invoke(initial_state)

    return {
        "hotels": result.get("hotels", []),
        "total_results": result.get("total_results", 0),
        "error": result.get("error"),
        "follow_up_question": result.get("follow_up_question"),
        "extracted_params": result.get("extracted_params"),
        "progress_steps": result.get("progress_steps", []),
    }
