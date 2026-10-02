from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from backend.agents.research.services.llm import init_llm_light

logger = logging.getLogger(__name__)

RouteType = Literal["direct", "evidence", "full"]

CLASSIFIER_PROMPT = """You are an intent complexity classifier for a research assistant.
Analyze the user's question relative to the current research session and decide the fastest, most appropriate route.

Routes:
1. "direct": Simple general knowledge questions, definitions (e.g. "what is RAG"), greetings, conversational replies, or questions that can be answered immediately without looking up web evidence.
2. "evidence": Questions specifically asking to summarize, compare, analyze, or explain evidence/findings already gathered in this session (e.g. "summarize finding 1", "compare these two frameworks from above"). Only valid if evidence has already been collected.
3. "full": Brand new research topics, complex questions requiring fresh web searches, academic papers, or latest current news/updates.

Rules:
- Return ONLY valid JSON: {{"route": "direct" | "evidence" | "full", "reason": "brief explanation"}}
- If there is any ambiguity, ALWAYS choose "full".
- If no evidence has been collected yet in this session, DO NOT choose "evidence".

Research Goal: {goal}
Evidence Count: {evidence_count}
User Question: {query}"""


def classify_complexity(query: str, session: Any) -> RouteType:
    evidence = getattr(session, "evidence", []) or []
    goal = getattr(session, "research_goal", "") or query
    q_lower = query.strip().lower()

    # Fast heuristics for direct conversational & basic definitions
    if q_lower in ("hi", "hello", "hey", "thanks", "thank you", "help"):
        logger.info(f"Fast heuristic classified query '{query}' as 'direct'")
        return "direct"

    if (q_lower.startswith(("what is ", "what are ", "define ", "explain ", "meaning of ", "who is ", "where is "))
        and len(q_lower.split()) <= 7
        and not any(k in q_lower for k in ("2025", "2026", "paper", "dataset", "benchmarks", "methods", "latest", "recent", "trend"))):
        logger.info(f"Fast heuristic classified query '{query}' as 'direct'")
        return "direct"

    prompt = CLASSIFIER_PROMPT.format(
        goal=goal[:200],
        evidence_count=len(evidence),
        query=query[:300],
    )

    try:
        llm = init_llm_light(temperature=0.0, max_tokens=150)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        route = data.get("route", "full").lower().strip()
        if route in ("direct", "evidence", "full"):
            # Don't allow 'evidence' route if no evidence exists
            if route == "evidence" and len(evidence) == 0:
                logger.info("Classifier suggested 'evidence' but no evidence exists -> fallback to 'full'")
                return "full"
            logger.info(f"Complexity Classifier: route='{route}' (reason: {data.get('reason', '')})")
            return route  # type: ignore
    except Exception as e:
        logger.warning(f"Complexity classification failed: {e} -> fallback to 'full'")

    return "full"
