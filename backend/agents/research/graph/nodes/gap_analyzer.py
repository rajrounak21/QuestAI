# NOTE: RECONSTRUCTED FILE (original lost in folder move accident).
# Contract rebuilt from graph.py (route_after_gap reads research_complete),
# main.py (session.gaps = identified_gaps), and validator/synthesizer shapes:
#   returns {"identified_gaps": [...], "follow_up_queries": [...], "research_complete": bool,
#            "search_queries": [...] (only when looping)}
# Uses init_llm_qwen like the original. REVIEW before production use.
from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.services.llm import init_llm_qwen
from backend.agents.research.services.progress import report as report_progress

logger = logging.getLogger(__name__)

GAP_PROMPT = """You are a research gap analyzer. Compare the collected evidence against the research sub-questions.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "gaps": [
    {{"question": "unanswered question", "status": "missing/weak/covered", "reason": "why", "follow_up_queries": ["search query"]}}
  ],
  "research_complete": true/false
}}

Rules:
- status "covered": evidence answers it well — no follow-up needed
- status "weak": partially answered — suggest 1-2 follow-up search queries
- status "missing": no evidence — suggest 1-2 follow-up search queries
- research_complete true ONLY if every sub-question is covered
- follow-up queries must be specific search strings, not questions

Research goal: {goal}

Sub-questions:
{sub_questions}

Evidence collected (count: {evidence_count}):
{evidence_text}"""


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def gap_analyzer_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running gap_analyzer node")
    report_progress(
        "searching",
        f"Round {state.get('current_round', 1)}/{state.get('max_rounds', 3)}: checking gaps",
    )

    plan = state.get("research_plan", {})
    evidence = state.get("evidence", [])
    sub_questions = [sq.get("question", "") for sq in plan.get("sub_questions", [])]
    goal = state.get("user_query", "")

    if not evidence:
        logger.info("No evidence collected, requesting another round")
        return {
            "identified_gaps": [{
                "question": "No evidence collected yet",
                "status": "missing",
                "reason": "Searches returned no usable results",
                "follow_up_queries": [goal],
            }],
            "follow_up_queries": [goal],
            "search_queries": [{"query": goal, "source_type": "google", "purpose": "retry"}],
            "research_complete": False,
        }

    sub_q_text = "\n".join(f"- {q}" for q in sub_questions) or "- (none)"
    ev_text = "\n".join(
        f"- [{ev.get('id', '')}] {ev.get('claim', '')[:150]}"
        for ev in evidence[:20]
    )

    try:
        llm = init_llm_qwen(temperature=0.0, max_tokens=2048)
        raw = llm.invoke(GAP_PROMPT.format(
            goal=goal,
            sub_questions=sub_q_text,
            evidence_count=len(evidence),
            evidence_text=ev_text or "No evidence",
        ))
        text = raw.content if hasattr(raw, "content") else str(raw)
        result = _parse_json(text)

        gaps = result.get("gaps", [])
        complete = bool(result.get("research_complete", False))

        follow_ups: list[str] = []
        next_queries: list[dict[str, Any]] = []
        for g in gaps:
            if g.get("status") in ("missing", "weak"):
                for fq in g.get("follow_up_queries", [])[:2]:
                    follow_ups.append(fq)
                    next_queries.append({
                        "query": fq,
                        "source_type": "google",
                        "purpose": f"fill gap: {g.get('question', '')[:80]}",
                    })

        logger.info(f"Gap analysis: {len(gaps)} gaps, complete={complete}")
        out: dict[str, Any] = {
            "identified_gaps": gaps,
            "follow_up_queries": follow_ups,
            "research_complete": complete,
        }
        if not complete and next_queries:
            out["search_queries"] = next_queries
        return out

    except Exception as e:
        logger.error(f"Gap analysis failed: {e}, using fallback")
        complete = len(evidence) >= 3
        return {
            "identified_gaps": [] if complete else [{
                "question": "Evidence coverage unclear (analyzer unavailable)",
                "status": "weak",
                "reason": str(e)[:200],
                "follow_up_queries": [],
            }],
            "follow_up_queries": [],
            "research_complete": complete,
        }
