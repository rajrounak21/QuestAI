from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.agents.research.schemas.sources import ProcessedSource, SourceType


class GapStatus(str, Enum):
    COVERED = "covered"
    MISSING = "missing"
    WEAK = "weak"


@dataclass
class ResearchSubQuestion:
    question: str
    importance: str = "high"


@dataclass
class SearchQuery:
    query: str
    source_type: SourceType
    purpose: str = ""


@dataclass
class ResearchPlan:
    goal: str
    sub_questions: list[ResearchSubQuestion] = field(default_factory=list)
    search_queries: list[SearchQuery] = field(default_factory=list)
    source_types_needed: list[SourceType] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "sub_questions": [
                {"question": sq.question, "importance": sq.importance}
                for sq in self.sub_questions
            ],
            "search_queries": [
                {"query": q.query, "source_type": q.source_type.value, "purpose": q.purpose}
                for q in self.search_queries
            ],
            "source_types_needed": [st.value for st in self.source_types_needed],
        }


@dataclass
class Evidence:
    source: ProcessedSource
    claim: str
    supporting_text: str
    sub_question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "claim": self.claim,
            "supporting_text": self.supporting_text,
            "sub_question": self.sub_question,
        }


@dataclass
class ResearchGap:
    question: str
    status: GapStatus
    reason: str = ""
    follow_up_queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "status": self.status.value,
            "reason": self.reason,
            "follow_up_queries": self.follow_up_queries,
        }


@dataclass
class Finding:
    title: str
    explanation: str
    sources: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ResearchReport:
    goal: str
    executive_summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    comparison: str = ""
    recent_developments: str = ""
    limitations: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "executive_summary": self.executive_summary,
            "findings": [
                {
                    "title": f.title,
                    "explanation": f.explanation,
                    "sources": f.sources,
                }
                for f in self.findings
            ],
            "comparison": self.comparison,
            "recent_developments": self.recent_developments,
            "limitations": self.limitations,
            "sources": self.sources,
        }


@dataclass
class MemoryEntry:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
