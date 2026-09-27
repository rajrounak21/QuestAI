from __future__ import annotations

from typing import Any

from shopping_agent.agent.shopping_graph import get_shopping_graph


def run_shopping_search(user_query: str) -> dict[str, Any]:
    initial_state: dict[str, Any] = {
        "user_query": user_query,
        "products": [],
        "total_results": 0,
        "error": None,
        "follow_up_question": None,
        "search_complete": False,
        "progress_steps": [],
    }

    graph = get_shopping_graph()
    result = graph.invoke(initial_state)

    return {
        "products": result.get("products", []),
        "total_results": result.get("total_results", 0),
        "error": result.get("error"),
        "follow_up_question": result.get("follow_up_question"),
        "extracted_params": result.get("extracted_params"),
        "progress_steps": result.get("progress_steps", []),
        "search_complete": result.get("search_complete", False),
    }
