from __future__ import annotations

import json
import logging
import operator
import re
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


class ShoppingState(TypedDict):
    user_query: str
    extracted_params: dict[str, Any] | None
    products: list[dict[str, Any]]
    total_results: int
    error: str | None
    follow_up_question: str | None
    search_complete: bool
    progress_steps: Annotated[list[str], operator.add]


# --- LLM helpers ---

def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 600  # 10 minutes

def _cache_get(q: str) -> dict | None:
    import time
    key = q.strip().lower()
    if key in _CACHE:
        ts, data = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return data
        else:
            _CACHE.pop(key, None)
    return None

def _cache_set(q: str, data: dict):
    import time
    key = q.strip().lower()
    # keep max 100 entries
    if len(_CACHE) > 100:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest, None)
    _CACHE[key] = (time.time(), data)


SHOPPING_EXTRACT_PROMPT = """You are a shopping assistant. Extract a Google Shopping search query from the user's request.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "q": "search query for Google Shopping, 2-6 words, e.g. 'iPhone 15' or 'running shoes men' or 'wireless headphones'",
  "is_shopping": true
}}

Rules:
- q should be the core product the user wants to buy, concise and search-friendly
- Remove filler words like "I want to buy", "show me", "under $500" — keep only product terms
- Keep brand/model if mentioned (e.g. "iPhone 15 Pro" -> "iPhone 15 Pro")
- If the query is NOT about shopping/buying a product (e.g. weather, flights, hotels, general chat), return {{"error": "This query is not about shopping."}}
- Keep q in the same language as user query (default English)

User query: {query}"""


def extract_shopping_params_node(state: ShoppingState) -> dict[str, Any]:
    logger.info("Running extract_shopping_params node")
    user_query = state.get("user_query", "").strip()
    if not user_query:
        return {
            "error": "Please tell me what product you are looking for.",
            "search_complete": True,
            "progress_steps": ["Error: empty query"],
        }

    # Deterministic: use raw query directly, no LLM (clean, fast, no 4s throttle)
    # Shopping query needs no cleaning - SerpApi handles natural language fine
    q = user_query.strip()
    return {
        "extracted_params": {"q": q, "original_query": user_query},
        "progress_steps": [f"Search query: '{q}'"],
    }


def validate_shopping_params(state: ShoppingState) -> dict[str, Any]:
    params = state.get("extracted_params")
    if not params:
        return {
            "error": "Could not understand your shopping request.",
            "search_complete": True,
            "progress_steps": ["Error: extraction failed"],
        }

    q = (params.get("q") or "").strip()
    if not q or len(q) < 2:
        return {
            "follow_up_question": "What product are you looking for? For example: 'iPhone 15', 'running shoes', or 'wireless headphones'.",
            "search_complete": True,
            "progress_steps": ["Missing product query"],
        }

    return {
        "progress_steps": [f"Looking for '{q}' in India"],
    }


def search_shopping(state: ShoppingState) -> dict[str, Any]:
    logger.info("Running search_shopping node")
    params = state.get("extracted_params")
    if not params:
        return {
            "error": "No search parameters available.",
            "search_complete": True,
            "progress_steps": ["Error: no parameters"],
        }

    q = params["q"]
    # Check in-memory cache first (clean, helpful, not dump)
    cached = _cache_get(q)
    if cached is not None:
        logger.info(f"Cache hit for '{q}' -> {cached['total_results']} products in 0s")
        return cached

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from shopping_agent.models.shopping_models import ShoppingSearchRequest
        from shopping_agent.services.normalizer import build_combined_response, normalize_amazon_products, normalize_products
        from shopping_agent.tools.amazon import amazon_search
        from shopping_agent.tools.google_shopping import google_shopping_search

        request_dict = {
            "query": q,
            "location": "India",
            "gl": "in",
            "hl": "en",
            "google_domain": "google.co.in",
        }
        req = ShoppingSearchRequest(**request_dict)

        raw_by_source: dict[str, dict] = {}

        def fetch_google():
            return ("google", google_shopping_search(req))

        def fetch_amazon():
            return ("amazon", amazon_search(req))

        # Parallel with timeout: don't block Google on slow Amazon (clean)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(fetch_google): "google", executor.submit(fetch_amazon): "amazon"}
            for fut in as_completed(futures):
                src_name = futures.get(fut, "unknown")
                try:
                    src, data = fut.result(timeout=7)
                    raw_by_source[src] = data
                    logger.info(f"{src} fetched OK")
                except Exception as e:
                    logger.warning(f"{src_name} fetch failed/timeout: {e}")
                    raw_by_source.setdefault(src_name, {})

        # Ensure keys exist
        raw_by_source.setdefault("google", {"shopping_results": []})
        raw_by_source.setdefault("amazon", {"organic_results": []})

        google_products = normalize_products(raw_by_source["google"])
        amazon_products = normalize_amazon_products(raw_by_source["amazon"])

        all_products = google_products + amazon_products
        # Flat merged: keep duplicates for now, Store filter will show Amazon vs others
        response = build_combined_response(request_dict, all_products)

        products_data = [p.model_dump() for p in response.products]

        g_count = len(google_products)
        a_count = len(amazon_products)
        result = {
            "products": products_data,
            "total_results": response.total_results,
            "search_complete": True,
            "progress_steps": [
                f"Searched Google Shopping ({g_count}) + Amazon ({a_count})",
                f"Found {response.total_results} products",
            ],
        }
        # Cache for next time
        _cache_set(q, result)
        return result

    except ValueError as ve:
        # Missing API key
        logger.error(f"Config error: {ve}")
        return {
            "error": str(ve),
            "search_complete": True,
            "progress_steps": ["Error: configuration missing"],
        }
    except Exception as e:
        logger.error(f"Shopping search failed: {e}")
        return {
            "error": "Shopping search is temporarily unavailable. Please try again.",
            "search_complete": True,
            "progress_steps": ["Error: search failed"],
        }


def route_after_validate(state: ShoppingState) -> Literal["search_shopping", "END"]:
    if state.get("error") or state.get("follow_up_question"):
        return "END"
    return "search_shopping"


def build_shopping_graph() -> StateGraph:
    builder = StateGraph(ShoppingState)
    builder.add_node("extract_params", extract_shopping_params_node)
    builder.add_node("validate_params", validate_shopping_params)
    builder.add_node("search_shopping", search_shopping)

    builder.add_edge(START, "extract_params")
    builder.add_edge("extract_params", "validate_params")
    builder.add_conditional_edges(
        "validate_params",
        route_after_validate,
        {"search_shopping": "search_shopping", "END": END},
    )
    builder.add_edge("search_shopping", END)
    return builder.compile()


_compiled_shopping_graph = None


def get_shopping_graph():
    global _compiled_shopping_graph
    if _compiled_shopping_graph is None:
        _compiled_shopping_graph = build_shopping_graph()
    return _compiled_shopping_graph
