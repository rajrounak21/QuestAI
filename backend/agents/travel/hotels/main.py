from __future__ import annotations

from typing import Any


def run_hotel_search(query: str) -> dict[str, Any]:
    """Attach wrapper — travel core now lives in backend.agents.travel (LLM kept)."""
    from backend.agents.travel.agent.hotel_agent import run_hotel_search as _run

    return _run(query)
