# SerpAPI response shapes verified against live calls - see tools/verify_parsers.py
# (run `python -m backend.agents.research.tools.verify_parsers`).
#
# Three shape facts that are easy to get wrong, all confirmed by that script:
#  - google: organic_results[] carry title/link/snippet/date. date is a human
#    string like "Sep 23, 2025", not ISO.
#  - google_scholar: organic_results[] carry title/link/snippet plus
#    publication_info, but publication_info has only {authors, summary} - there
#    is NO "year" key. The year is only present inside the citation "summary"
#    string, in the form "Authors - Journal, 2020 - publisher".
#  - google_news: news_results[] carry title/link/date/iso_date/source, and NO
#    "snippet" key at all. SerpApi does not return article body text for this
#    engine. process_sources() drops sources whose snippet is empty, so leaving
#    this blank silently threw away every news result - see _news_snippet.
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
    """Pull the publication year out of publication_info.

    Live SerpApi responses put only {authors, summary} in publication_info - no
    "year" key. The year appears inside the citation summary, so try the
    canonical "... , 2020 - publisher" position first and fall back to any
    four-digit year in the string.
    """
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
    """Provenance line for a news hit.

    The google_news engine returns no article text, so there is nothing to
    quote. Rather than leave the snippet empty - which process_sources() treats
    as unusable and drops, losing the result entirely - build the one piece of
    real text the payload does carry: who published it and who wrote it.
    No text is ever invented here.
    """
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
                # iso_date is present and machine-parseable ("2026-10-02T19:58:00Z")
                # while date is a verbose local string. Prefer iso for freshness
                # reasoning downstream, fall back to date if a response omits it.
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
