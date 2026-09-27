# NOTE: RECONSTRUCTED FILE (original lost in folder move accident).
# Minimal pass-through: planner already sets search_queries; router forwards
# the pending queries for the current round to the collector.
# REVIEW: if the original router filtered/limited queries per round, restore that logic.
from __future__ import annotations

import logging
from typing import Any

from backend.agents.research.graph.state import ResearchState

logger = logging.getLogger(__name__)


def router_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running router node")
    queries = state.get("search_queries", [])
    logger.info(f"Router: forwarding {len(queries)} queries (round {state.get('current_round', 1)})")
    return {"search_queries": queries}
