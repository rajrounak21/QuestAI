from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionData:
    session_id: str
    research_goal: str = ""
    research_plan: dict[str, Any] | None = None
    searches: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 3


class SessionMemory:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def get_or_create(self, session_id: str) -> SessionData:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData(session_id=session_id)
        return self._sessions[session_id]

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


def build_context_for_question(session: SessionData, current_question: str) -> str:
    parts: list[str] = []

    if session.research_goal:
        parts.append(f"Research goal: {session.research_goal}")

    is_followup = len(session.conversation) > 0
    if is_followup:
        last_exchange = session.conversation[-1]
        parts.append(f"Previous question: {last_exchange.get('user', '')}")
        prev_answer = last_exchange.get("assistant", "")
        if prev_answer:
            short_answer = prev_answer[:500] + "..." if len(prev_answer) > 500 else prev_answer
            parts.append(f"Previous answer (summary): {short_answer}")

    lower_q = current_question.lower()
    is_continue = any(kw in lower_q for kw in ["continue", "more", "further", "next", "what else"])
    is_source_ref = any(kw in lower_q for kw in ["source", "paper", "article", "cite", "compare"])
    is_summary = any(kw in lower_q for kw in ["summary", "summarize", "what did we find", "overall"])

    if is_continue or is_source_ref or is_summary:
        if session.evidence:
            recent_evidence = session.evidence[-5:]
            evidence_text = "\n".join(
                f"- {e.get('claim', '')[:100]} ({e.get('source', {}).get('url', '')})"
                for e in recent_evidence
            )
            parts.append(f"Evidence collected:\n{evidence_text}")
        if session.gaps:
            gaps_text = "\n".join(
                f"- [{g.get('status', '')}] {g.get('question', '')}"
                for g in session.gaps
            )
            parts.append(f"Identified gaps:\n{gaps_text}")
        if session.searches:
            searches_text = "\n".join(
                f"- [{s.get('source_type', '')}] {s.get('query', '')}"
                for s in session.searches[-6:]
            )
            parts.append(f"Searches already performed:\n{searches_text}")

    parts.append(f"Current question: {current_question}")

    return "\n\n".join(parts)


# Global instance
memory = SessionMemory()
