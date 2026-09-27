from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.graph.nodes.planner import planner_node
from backend.agents.research.graph.nodes.router import router_node
from backend.agents.research.graph.nodes.collector import collector_node
from backend.agents.research.graph.nodes.evaluator import evaluator_node
from backend.agents.research.graph.nodes.gap_analyzer import gap_analyzer_node
from backend.agents.research.graph.nodes.synthesizer import synthesizer_node
from backend.agents.research.graph.nodes.validator import validator_node

logger = logging.getLogger(__name__)


def route_after_gap(state: ResearchState) -> Literal["collector", "synthesizer"]:
    if state.get("research_complete", False):
        logger.info("Research complete, routing to synthesizer")
        return "synthesizer"
    if state.get("current_round", 1) >= state.get("max_rounds", 3):
        logger.info("Budget exhausted, routing to synthesizer")
        return "synthesizer"
    logger.info("More research needed, routing back to collector")
    return "collector"


def route_after_validator(state: ResearchState) -> Literal["synthesizer", "END"]:
    issues = state.get("validation_issues", [])
    resynth_count = state.get("resynthesis_count", 0)

    has_real_issues = (
        issues
        and resynth_count < 1
    )

    if has_real_issues:
        logger.info(f"Validator found issues, re-synthesizing (attempt {resynth_count + 1})")
        return "synthesizer"

    logger.info("Report validated, done")
    return "END"


def increment_round(state: ResearchState) -> dict:
    return {"current_round": state.get("current_round", 1) + 1}


def increment_resynthesis(state: ResearchState) -> dict:
    return {"resynthesis_count": state.get("resynthesis_count", 0) + 1}


def build_graph() -> StateGraph:
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("router", router_node)
    builder.add_node("collector", collector_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("gap_analyzer", gap_analyzer_node)
    builder.add_node("increment_round", increment_round)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("validator", validator_node)
    builder.add_node("increment_resynthesis", increment_resynthesis)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "router")
    builder.add_edge("router", "collector")
    builder.add_edge("collector", "evaluator")
    builder.add_edge("evaluator", "gap_analyzer")

    builder.add_conditional_edges(
        "gap_analyzer",
        route_after_gap,
        {
            "collector": "increment_round",
            "synthesizer": "synthesizer",
        },
    )

    builder.add_edge("increment_round", "collector")
    builder.add_edge("synthesizer", "validator")

    builder.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "synthesizer": "increment_resynthesis",
            "END": END,
        },
    )

    builder.add_edge("increment_resynthesis", "synthesizer")

    return builder.compile()


compiled_graph = None


def get_graph() -> StateGraph:
    global compiled_graph
    if compiled_graph is None:
        compiled_graph = build_graph()
    return compiled_graph
