"""Cache for research evidence (web, scholar, news).

Deliberately NOT used for prices. Flight, hotel and shopping results must never
be served stale - showing yesterday's fare while the page says "live" is a lie
the PriceDisclaimer cannot undo. Evidence is different: a paper or a news
article stays true, so a short-lived cache is safe as long as the UI says when
the data was collected.

Entries live in Mongo with a TTL so they expire on their own rather than
depending on a process staying up.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from backend.agents.research.schemas.sources import SearchResult

logger = logging.getLogger(__name__)

RESEARCH_CACHE_COLLECTION = "research_cache"

# Evidence does not go stale in minutes, but a research answer that cites a
# three-day-old article set should not claim to be this morning's.
CACHE_TTL_SECONDS = 3600  # 1 hour


def get_cache_collection():
    from backend.database.mongodb import get_db

    return get_db()[RESEARCH_CACHE_COLLECTION]


def ensure_research_cache_indexes() -> None:
    col = get_cache_collection()
    col.create_index([("created_at", -1)])
    # Mongo expires these itself, so nothing has to sweep them.
    col.create_index("created_at", expireAfterSeconds=CACHE_TTL_SECONDS)


def cache_key(engine: str, query: str, num_results: int) -> str:
    raw = json.dumps(
        {"engine": engine, "query": (query or "").strip().lower(), "num": num_results},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def restore(items: list[dict[str, Any]]) -> list[SearchResult]:
    """Rebuild SearchResult objects from cached dicts.

    SearchResult is a dataclass, not a BaseModel, and to_dict() deliberately
    omits raw_data - the untrimmed SerpApi payload - so the cached form is the
    smaller one and raw_data comes back empty. That is the intended trade: the
    raw blob is only read during parsing.
    """
    from backend.agents.research.schemas.sources import SourceType

    out: list[SearchResult] = []
    for i in items:
        try:
            out.append(
                SearchResult(
                    title=i.get("title", ""),
                    url=i.get("url", ""),
                    snippet=i.get("snippet", ""),
                    source_type=SourceType(i.get("source_type") or SourceType.GOOGLE.value),
                    date=i.get("date", ""),
                    raw_data=i.get("raw_data") or {},
                )
            )
        except Exception:
            continue
    return out


def get_cached(engine: str, query: str, num_results: int) -> tuple[list[dict[str, Any]], float] | None:
    """Return (items, cached_at_epoch) or None."""
    try:
        doc = get_cache_collection().find_one({"_id": cache_key(engine, query, num_results)})
        if not doc:
            return None
        created = doc.get("created_at_epoch")
        if not isinstance(created, (int, float)) or time.time() - created > CACHE_TTL_SECONDS:
            return None
        return list(doc.get("items") or []), float(created)
    except Exception as e:
        # A cache read must never fail a search.
        logger.warning(f"Research cache read failed: {e}")
        return None


def serialise(results: list[SearchResult]) -> list[dict[str, Any]]:
    """Cached shape for a list of results.

    raw_data is kept: some downstream steps read it (evidence extraction looks
    for provider fields there), so dropping it would change research output
    depending on whether the cache was warm.
    """
    out: list[dict[str, Any]] = []
    for s in results:
        try:
            out.append(
                {
                    "title": s.title,
                    "url": s.url,
                    "snippet": s.snippet,
                    "source_type": s.source_type.value,
                    "date": s.date,
                    "raw_data": s.raw_data or {},
                }
            )
        except Exception:
            continue
    return out


def set_cached(engine: str, query: str, num_results: int, items: list[dict[str, Any]]) -> None:
    try:
        get_cache_collection().update_one(
            {"_id": cache_key(engine, query, num_results)},
            {
                "$set": {
                    "items": items,
                    "created_at_epoch": time.time(),
                },
                "$setOnInsert": {"engine": engine, "query": (query or "")[:200]},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Research cache write failed: {e}")


def describe_age(cached_at_epoch: float) -> str:
    secs = max(0, int(time.time() - cached_at_epoch))
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    return f"{hours}h ago"