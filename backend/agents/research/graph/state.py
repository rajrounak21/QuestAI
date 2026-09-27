from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ResearchState(TypedDict):
    session_id: str
    user_query: str
    research_plan: dict[str, Any] | None
    current_round: int
    max_rounds: int
    search_queries: list[dict[str, Any]]
    raw_results: Annotated[list[dict[str, Any]], operator.add]
    processed_sources: list[dict[str, Any]]
    evidence: Annotated[list[dict[str, Any]], operator.add]
    identified_gaps: list[dict[str, Any]]
    follow_up_queries: list[str]
    research_complete: bool
    final_report: dict[str, Any] | None
    searches_performed: Annotated[list[dict[str, Any]], operator.add]
    validation_issues: list[dict[str, Any]]
    resynthesis_count: int
