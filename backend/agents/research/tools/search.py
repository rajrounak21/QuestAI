# NOTE: RECONSTRUCTED FILE (original lost in folder move accident).
# Behavior rebuilt from observed call sites:
#  - collector calls search(query_text, source_type, num_results=10) -> list[SearchResult]
#  - travel destination_research calls google_search(q, num_results=5), google_news(q, num_results=5)
#    positionally and reads .title/.url/.snippet/.source_type.value
#  - evaluator rebuilds SearchResult(title, url, snippet, source_type, date, raw_data)
# SerpAPI engine parsing follows standard organic_results / news_results shapes.
# REVIEW: verify against real SerpAPI responses before production use.
from __future__ import annotations

import logging
import os
from typing import Any

import serpapi
from dotenv import load_dotenv

from backend.agents.research.schemas.sources import SearchResult, SourceType

load_dotenv()

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None


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
                snippet=r.get("snippet", pub.get("summary", "")),
                source_type=SourceType.SCHOLAR,
                date=pub.get("year", "") or r.get("date", ""),
                raw_data=r,
            ))
        return [s for s in out if s.title.strip() and s.url][:num_results]
    except Exception as e:
        logger.error(f"SerpAPI scholar search failed: {e}")
        return []


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
                snippet=r.get("snippet", ""),
                source_type=SourceType.NEWS,
                date=r.get("date", ""),
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
