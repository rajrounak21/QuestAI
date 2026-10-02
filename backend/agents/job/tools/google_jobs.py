from __future__ import annotations

import difflib
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import serpapi
from dotenv import load_dotenv

from backend.agents.job.schemas.job import JobSearchRequest

load_dotenv(override=True)

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None

# Substrings that mean "this is an Indian location" for SerpApi's gl param.
# Without gl=in, google.com returns a thinner Indian result set.
INDIA_LOCATION_HINTS = (
    "india",
    "bengaluru",
    "bangalore",
    "delhi",
    "mumbai",
    "pune",
    "hyderabad",
    "chennai",
    "patna",
    "kolkata",
    "gurgaon",
    "gurugram",
    "noida",
    "greater noida",
    "charkhi dadri",
    "haryana",
)

# Canonical spellings for the fuzzy pass. Kept separate from the hint substrings
# because this list is compared token-for-token.
INDIAN_CITIES = (
    "bengaluru", "bangalore", "delhi", "new delhi", "mumbai", "pune",
    "hyderabad", "chennai", "kolkata", "gurgaon", "gurugram", "noida",
    "patna", "ahmedabad", "jaipur", "lucknow", "kochi", "indore", "nagpur",
    "bhopal", "coimbatore", "madurai", "visakhapatnam", "bhubaneswar",
    "chandigarh", "dehradun", "ranchi", "guwahati", "shimla", "srinagar",
    "agra", "varanasi", "amritsar", "kanpur", "surat", "mysore", "mysuru",
    "hubballi", "mangaluru", "gwalior", "jamshedpur", "thanjavur",
    "kozhikode", "kollam",
)

# A token is compared against INDIAN_CITIES only if it is at least this long.
# Short tokens produce noisy matches ("puna" -> "pune" is a coin flip) and a
# wrong match here silently switches us to the wrong Google domain.
FUZZY_MIN_TOKEN_LEN = 4
# Tuned against a typo set and a foreign-location set: at 0.72 the foreign set
# picked up false positives (Singapore -> ?, Dubai -> ?); at 0.78 only "Remote"
# resolves to in, which is intentional.
FUZZY_CUTOFF = 0.78
# A fuzzy winner must beat the runner-up by this much to be trusted outright.
# "bangluru" ties "bengaluru" and "mangaluru" at 0.824 — an exact tie means we
# cannot tell a typo of Bengaluru from one of Mangaluru, so the location is left
# alone and the retry path resolves it against the live API instead.
FUZZY_MARGIN = 0.05

# How many alternate spellings to try when SerpApi rejects a location.
LOCATION_FALLBACKS = 3


def _token_candidates(token: str, n: int = LOCATION_FALLBACKS) -> list[str]:
    return difflib.get_close_matches(token, INDIAN_CITIES, n=n, cutoff=FUZZY_CUTOFF)


def _fuzzy_india_token(location: str) -> str | None:
    """Best-effort: a city this location almost certainly means, else None.

    Token-level only — matching the whole string produced false positives such as
    "Madrid" -> "madurai".
    """
    for raw in re.split(r"[,/|]+|\s+", location.lower()):
        token = raw.strip("-.,()")
        if len(token) < FUZZY_MIN_TOKEN_LEN:
            continue
        cands = _token_candidates(token, n=2)
        if not cands:
            continue
        if len(cands) == 1:
            return cands[0]
        best = difflib.SequenceMatcher(None, token, cands[0]).ratio()
        second = difflib.SequenceMatcher(None, token, cands[1]).ratio()
        if best - second >= FUZZY_MARGIN:
            return cands[0]
    return None


def canonicalize_location(location: str) -> str:
    """Rewrite an unambiguous misspelled city to its real spelling.

    SerpApi does NOT fuzzy-match a location it cannot resolve — it answers 400
    Bad Request. "Banglore" is rejected outright, while "Delhi," resolves fine.
    So an unambiguous typo is corrected here to avoid a wasted round trip.

    An ambiguous one is deliberately left alone; see _location_fallbacks.
    """
    loc = location or ""
    parts = re.split(r"([,/|])", loc)
    for i, part in enumerate(parts):
        token = part.strip()
        if len(token) < FUZZY_MIN_TOKEN_LEN:
            continue
        match = _fuzzy_india_token(token)
        if match:
            lead = part[: len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            parts[i] = f"{lead}{match.capitalize()}{trail}"
    return "".join(parts)


def _location_fallbacks(location: str) -> list[str]:
    """Alternate spellings to try when SerpApi rejects `location`.

    Covers the ambiguous typos that canonicalize_location refuses to guess at.
    Each candidate swaps one token, keeping the rest of the string intact.
    """
    out: list[str] = []
    for raw in re.split(r"([,/|])", location):
        token = raw.strip()
        if len(token) < FUZZY_MIN_TOKEN_LEN:
            continue
        for cand in _token_candidates(token.lower()):
            out.append(cand)
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq[:LOCATION_FALLBACKS]


def _substitute_first_token(location: str, replacement: str) -> str:
    parts = re.split(r"([,/|])", location)
    for i, part in enumerate(parts):
        token = part.strip()
        if len(token) >= FUZZY_MIN_TOKEN_LEN:
            lead = part[: len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            return "".join(parts[:i] + [f"{lead}{replacement.capitalize()}{trail}"] + parts[i + 1:])
    return replacement


def _has_india_candidate(location: str) -> bool:
    """Does any token come close to an Indian city?

    Deliberately does not require a clear winner. "Bangluru" is an exact tie
    between Bengaluru and Mangaluru — we cannot say *which* city, but both are in
    India, so the country is not in doubt and `gl` must be `in`. Requiring a
    margin here would send these to google.com, where the typo resolves to
    US results instead of erroring, and the retry path would never trigger.
    """
    for raw in re.split(r"[,/|]+|\s+", location.lower()):
        token = raw.strip("-.,()")
        if len(token) < FUZZY_MIN_TOKEN_LEN:
            continue
        if _token_candidates(token, n=1):
            return True
    return False


def resolve_gl(location: str | None) -> str:
    """Map a free-text location to SerpApi's gl country code.

    Two passes. Substring hints catch the normal cases ("Delhi," and
    "Hajipur, Bihar, India" both work). The fuzzy pass then catches
    misspellings, which is our bug and not Google's: a location string only
    decides *our* choice of google.co.in vs google.com, and picking the wrong
    one returns a US-skewed result set.
    """
    loc = (location or "india").strip()
    if loc.lower() == "remote":
        # "Remote" is not a place; search the home market instead.
        loc = "India"
    low = loc.lower()
    if any(hint in low for hint in INDIA_LOCATION_HINTS):
        return "in"
    if _has_india_candidate(low):
        return "in"
    return "us"


def build_search_request(
    query: str,
    location: str | None = None,
    gl: str | None = None,
    hl: str = "en",
) -> JobSearchRequest:
    """Build one SerpApi request, deriving gl/google_domain from the location."""
    loc = (location or "India").strip()
    if loc.lower() == "remote":
        loc = "India"
    else:
        # Unambiguous misspellings are corrected up front so we spend one call
        # instead of a 400 plus a retry. Ambiguous ones are left as typed and
        # resolved by google_jobs_search's fallback.
        loc = canonicalize_location(loc) or loc
    resolved_gl = gl or resolve_gl(loc)
    domain = "google.co.in" if resolved_gl == "in" else "google.com"
    return JobSearchRequest(query=query, location=loc, gl=resolved_gl, hl=hl, google_domain=domain)


def build_search_requests(pairs: list[tuple[str, str | None]]) -> list[JobSearchRequest]:
    """Build requests for (query, location) pairs, skipping empty queries."""
    out: list[JobSearchRequest] = []
    for query, location in pairs:
        q = (query or "").strip()
        if not q:
            continue
        out.append(build_search_request(q, location))
    return out


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        api_key = os.getenv("SERP_API_KEY")
        if not api_key:
            raise ValueError("SERP_API_KEY not found in environment")
        _client = serpapi.Client(api_key=api_key)
    return _client


def _search_once(client: serpapi.Client, params: dict[str, Any]) -> dict[str, Any]:
    results = client.search(params)
    return results.data


def google_jobs_search(request: JobSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": request.query,
        "location": request.location,
        "google_domain": request.google_domain,
        "gl": request.gl,
        "hl": request.hl,
    }
    # remove empty location to avoid SerpApi error - but location is useful
    if not params["location"]:
        params.pop("location")
    logger.info(f"SerpAPI Google Jobs: q='{request.query}' location='{request.location}' gl={request.gl}")

    # SerpApi does not fuzzy-match an unresolvable location, it answers 400.
    # Retry with the closest real spellings before giving up, so "Banglore"
    # still returns Bengaluru jobs instead of zero.
    attempts = [request.location] + [
        _substitute_first_token(request.location, c)
        for c in _location_fallbacks(request.location)
    ]
    last_error: Exception | None = None
    for attempt in attempts:
        if attempt != request.location:
            logger.info(f"SerpApi rejected location '{request.location}', retrying '{attempt}'")
        try:
            params["location"] = attempt
            data = _search_once(_get_client(), params)
            count = len(data.get("jobs_results", []))
            logger.info(f"SerpAPI response: {count} jobs_results for q='{request.query}' location='{attempt}'")
            return data
        except Exception as e:
            # Only a bad-request means "unusable location". Anything else (quota,
            # network, auth) must surface immediately rather than burn retries.
            if not _is_bad_request(e):
                logger.error(f"SerpAPI Google Jobs search failed: {e}")
                raise
            last_error = e
    logger.error(f"SerpAPI Google Jobs search failed for all location attempts: {last_error}")
    raise last_error  # type: ignore[misc]


def _is_bad_request(exc: Exception) -> bool:
    """True when SerpApi rejected the request itself (unresolvable location)."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return int(status) == 400
    return "400" in str(exc)


def _run_one(req: JobSearchRequest) -> dict[str, Any]:
    """One SerpApi call. Never raises — a failure degrades to an empty result."""
    try:
        return google_jobs_search(req)
    except Exception as e:
        logger.warning(f"Skipping failed job search q='{req.query}': {e}")
        return {"jobs_results": [], "error": str(e), "search_metadata": {}}


def google_jobs_search_multi(requests: list[JobSearchRequest]) -> list[dict[str, Any]]:
    """Execute up to 3 searches in parallel, return raw responses in input order.

    These calls are independent, so a serial loop made the user wait for all of
    them (2-3 x ~1.5-2s). Running them concurrently brings the total down to
    roughly a single call's latency.
    """
    batch = requests[:3]
    if not batch:
        return []

    if len(batch) == 1:
        return [_run_one(batch[0])]

    with ThreadPoolExecutor(max_workers=len(batch)) as pool:
        # executor.map preserves input order, which normalize_jobs relies on.
        return list(pool.map(_run_one, batch))
