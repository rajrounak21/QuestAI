from __future__ import annotations

import json
import logging
import re
from typing import Any

from datetime import date

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.services.llm import init_llm

logger = logging.getLogger(__name__)


PLANNER_PROMPT = """You are a research planner. Today's date is {today}. Given a user's research goal, create a structured research plan.

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "goal": "the research goal",
  "sub_questions": [
    {{"question": "sub question 1", "importance": "high"}},
    {{"question": "sub question 2", "importance": "medium"}}
  ],
  "source_types_needed": ["google", "scholar", "news"],
  "search_queries": [
    {{"query": "search query text", "source_type": "google", "purpose": "why this query"}}
  ]
}}

Rules:
- 3-5 sub-questions
- 4-8 search queries across source types
- Search queries MUST focus on {year} and {prev_year} developments only
- Do NOT use year ranges like "2022..2026" — focus on the latest work
- For scholar queries, target recent papers from {prev_year}-{year}
- For news queries, target latest announcements and releases
- For google queries, target current overviews and comparisons
- Queries should find the NEWEST methods, not historical reviews

User research goal: {goal}"""


def planner_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running planner node")

    user_query = state["user_query"]
    today = date.today()
    prompt = PLANNER_PROMPT.format(
        goal=user_query,
        today=today.strftime("%B %d, %Y"),
        year=today.year,
        prev_year=today.year - 1,
    )

    try:
        llm = init_llm(temperature=0.1, max_tokens=2048)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        plan = _parse_json(text)
    except Exception as e:
        logger.error(f"Planner LLM failed: {e}, using fallback")
        plan = _fallback_plan(user_query)

    return {
        "research_plan": plan,
        "current_round": 1,
        "research_complete": False,
        "search_queries": plan.get("search_queries", []),
    }


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _fallback_plan(goal: str) -> dict[str, Any]:
    return {
        "goal": goal,
        "sub_questions": [
            {"question": f"What is known about {goal}?", "importance": "high"},
            {"question": f"What are the latest developments regarding {goal}?", "importance": "high"},
            {"question": f"What are the limitations or challenges related to {goal}?", "importance": "medium"},
        ],
        "source_types_needed": ["google", "scholar"],
        "search_queries": [
            {"query": goal, "source_type": "google", "purpose": "general overview"},
            {"query": f"{goal} research paper", "source_type": "scholar", "purpose": "academic evidence"},
        ],
    }
