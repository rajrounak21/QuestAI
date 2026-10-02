from __future__ import annotations

from typing import Any


def run_flight_search(query: str) -> dict[str, Any]:
    """Attach wrapper — travel core now lives in backend.agents.travel (LLM kept).

    Keeps typo handling (dehli -> DEL) inside the existing LLM extract node,
    so the backend route stays identical in shape to shopping's run_shopping_search.
    """
    from backend.agents.travel.agent.flight_agent import run_flight_search as _run

    return _run(query)
