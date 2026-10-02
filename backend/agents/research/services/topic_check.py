from __future__ import annotations

import json
import logging
import re
import uuid

logger = logging.getLogger(__name__)

TOPIC_CHECK_PROMPT = """You are a research-topic continuity classifier.

Determine whether the current question belongs to the same research topic
as the existing research goal.

Return ONLY JSON, no markdown, no explanation:
{{"decision": "same" | "new" | "uncertain"}}

Rules:
- "same": current question is a follow-up, sub-question, or aspect of the goal
- "new": current question is a clearly different research topic
- "uncertain": related but could be a new direction, ambiguous

Research goal:
{research_goal}

Recent context:
{recent_context}

Current question:
{current_question}"""

_VALID = ("same", "new", "uncertain")


def build_recent_context(session, max_exchanges: int = 2) -> str:
    """Last N exchanges as tiny text. No evidence, no searches."""
    conv = (session.conversation or [])[-max_exchanges:]
    if not conv:
        return "No previous exchanges."
    lines: list[str] = []
    for ex in conv:
        lines.append(f"User: {ex.get('user', '')[:300]}")
        prev = ex.get("assistant", "")
        if prev:
            short = prev[:300] + "..." if len(prev) > 300 else prev
            lines.append(f"Assistant: {short}")
    return "\n".join(lines)


def _parse_decision(text: str) -> str | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        d = str(data.get("decision", "")).lower().strip()
        return d if d in _VALID else None
    except Exception:
        return None


def check_topic_continuity(
    research_goal: str,
    current_question: str,
    recent_context: str = "",
) -> dict:
    """One tiny LLM call. Returns {"decision": same|new|uncertain}."""
    from backend.agents.research.services.llm import init_llm_light

    prompt = TOPIC_CHECK_PROMPT.format(
        research_goal=research_goal or "(none)",
        recent_context=recent_context or "No previous exchanges.",
        current_question=current_question,
    )
    try:
        llm = init_llm_light(temperature=0.0, max_tokens=300)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        decision = _parse_decision(text)
        if decision:
            return {"decision": decision}
        logger.warning(f"Topic check unparseable: {text[:120]}")
    except Exception as e:
        logger.warning(f"Topic check LLM failed: {e}")
    return {"decision": "uncertain"}


def route_session(
    session,
    current_question: str,
    force_new: bool = False,
    force_continue: bool = False,
) -> dict:
    """Session Router. Pure Python decides session_id. LLM only proposes.

    Returns:
      fresh query (no conversation yet) -> {"action": "fresh", "session_id": ...}
      same  -> {"action": "continue", "session_id": <existing>}
      new   -> {"action": "new", "session_id": <new uuid>, "new_goal": current}
      uncertain -> {"action": "confirm", "session_id": <existing>,
                    "proposed_new_goal": current}
    """
    # Fresh query: skip topic check entirely.
    if not session.conversation:
        return {"action": "fresh", "session_id": session.session_id}

    if force_new:
        new_id = str(uuid.uuid4())
        return {"action": "new", "session_id": new_id, "new_goal": current_question}

    # In active session, preserve conversation thread continuity
    return {"action": "continue", "session_id": session.session_id}
