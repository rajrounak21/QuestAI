from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    GOOGLE = "google"
    SCHOLAR = "scholar"
    NEWS = "news"


class Relevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DISCARD = "discard"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_type: SourceType
    date: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_type": self.source_type.value,
            "date": self.date,
        }


@dataclass
class ProcessedSource:
    title: str
    url: str
    source_type: SourceType
    date: str
    snippet: str
    relevance: Relevance = Relevance.MEDIUM
    key_claims: list[str] = field(default_factory=list)
    evidence_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type.value,
            "date": self.date,
            "snippet": self.snippet,
            "relevance": self.relevance.value,
            "key_claims": self.key_claims,
            "evidence_text": self.evidence_text,
        }
