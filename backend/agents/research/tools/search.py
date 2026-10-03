# Shapes verified against live responses - see verify_parsers.py.
#  - google_news returns no snippet key; _news_snippet builds provenance instead,
#    because process_sources() drops sources with an empty snippet.
#  - google_scholar has no year key in publication_info; see _year_from_citation.
from __future__ import annotations

import logging
import os
import re
from typing import Any

import serpapi
from dotenv import load_dotenv

from backend.agents.research.schemas.sources import SearchResult, SourceType

load_dotenv(override=True)

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None

# "..., 2020 - proceedings.neurips.cc" inside publication_info.summary.
_YEAR_IN_CITATION = re.compile(r",\s*((?:19|20)\d{2})\s*[-–]")
_YEAR_ANYWHERE = re.compile(r"\b((?:19|20)\d{2})\b")


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            raise ValueError("SERP_API_KEY not found in environment")
        _client = serpapi.Client(api_key=api_key)
    return _client


def _parse_organic(results: list[dict[str, Any]], source_type: SourceType) -> list[SearchResult]:
    out: list[SearchResult] = []
    for r in results:
        title = r.get("title", "")
        url = r.get("link", "")
        snippet = r.get("snippet", "")
        if not title.strip() or not url:
            continue
        out.append(SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source_type=source_type,
            date=r.get("date", ""),
            raw_data=r,
        ))
    return out


def google_search(query: str, num_results: int = 10) -> list[SearchResult]:
    try:
        client = _get_client()
        data = client.search({"engine": "google", "q": query, "num": num_results}).data
        results = data.get("organic_results", [])
        logger.info(f"SerpAPI google: {len(results)} organic_results for '{query[:60]}'")
        return _parse_organic(results, SourceType.GOOGLE)[:num_results]
    except Exception as e:
        logger.error(f"SerpAPI google search failed: {e}")
        return []


def _year_from_citation(pub: dict[str, Any]) -> str:
    """publication_info is only {authors, summary}; the year is inside summary
    as "..., 2020 - publisher"."""
    m = _YEAR_IN_CITATION.search(pub.get("summary", "") or "")
    if m:
        return m.group(1)
    m = _YEAR_ANYWHERE.search(pub.get("summary", "") or "")
    return m.group(1) if m else ""


def google_scholar(query: str, num_results: int = 10) -> list[SearchResult]:
    try:
        client = _get_client()
        data = client.search({"engine": "google_scholar", "q": query, "num": num_results}).data
        results = data.get("organic_results", [])
        logger.info(f"SerpAPI scholar: {len(results)} organic_results for '{query[:60]}'")
        out: list[SearchResult] = []
        for r in results:
            pub = r.get("publication_info", {}) or {}
            out.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", "") or pub.get("summary", ""),
                source_type=SourceType.SCHOLAR,
                date=_year_from_citation(pub) or r.get("date", ""),
                raw_data=r,
            ))
        return [s for s in out if s.title.strip() and s.url][:num_results]
    except Exception as e:
        logger.error(f"SerpAPI scholar search failed: {e}")
        return []


def _news_snippet(r: dict[str, Any]) -> str:
    """google_news returns no article text, so use the provenance it does carry.
    Never invents text."""
    src = r.get("source") or {}
    if isinstance(src, str):
        return src
    name = str(src.get("name") or "").strip()
    authors = src.get("authors") or []
    who = ", ".join(str(a).strip() for a in authors if str(a).strip())
    if name and who:
        return f"{name} - {who}"
    return name or who


def google_news(query: str, num_results: int = 10) -> list[SearchResult]:
    try:
        client = _get_client()
        data = client.search({"engine": "google_news", "q": query, "num": num_results}).data
        results = data.get("news_results", []) or data.get("organic_results", [])
        logger.info(f"SerpAPI news: {len(results)} results for '{query[:60]}'")
        out: list[SearchResult] = []
        for r in results:
            out.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=_news_snippet(r),
                source_type=SourceType.NEWS,
                date=r.get("iso_date", "") or r.get("date", ""),
                raw_data=r,
            ))
        return [s for s in out if s.title.strip() and s.url][:num_results]
    except Exception as e:
        logger.error(f"SerpAPI news search failed: {e}")
        return []


def search(
    query: str,
    source_type: SourceType = SourceType.GOOGLE,
    num_results: int = 10,
) -> list[SearchResult]:
    if source_type == SourceType.SCHOLAR:
        return google_scholar(query, num_results=num_results)
    if source_type == SourceType.NEWS:
        return google_news(query, num_results=num_results)
    return google_search(query, num_results=num_results)
