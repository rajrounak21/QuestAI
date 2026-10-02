"""Picks which specialist should handle a free-text query, and pre-extracts the
fields that specialist's form needs.

Design rules, both learned from earlier work:
1. This only *chooses and pre-fills*. It never runs a search. The user still
   presses the specialist's own search button.
2. Anything the LLM cannot confidently decide falls back to a deterministic
   keyword match, then to the Assistant — never to a paid specialist, and never
   to a silent full run.

Modelled on backend/agents/research/services/complexity.py, which is the same
shape (heuristic fast path -> LLM -> tolerant JSON parse -> safe fallback) and is
wired into a live endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.agents.research.services.llm import init_llm_light, invoke_with_timeout
from backend.agents.router.services.catalog import AGENTS, ASSISTANT

logger = logging.getLogger(__name__)

# Keep the call short: this sits between the user and their form.
MAX_TOKENS = 400
# init_llm_light pins 20s; a form that fills in half a minute later is useless.
CALL_TIMEOUT = 8.0

CHITCHAT_PHRASES = {
    "hi", "hello", "hey", "yo", "hii", "sup", "heya",
    "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "nice",
    "bye", "goodbye", "see you", "good morning", "good evening", "good night",
    "help", "what can you do", "what can you do?", "who are you",
    "who are you?", "how are you", "how are you?", "what are you",
}

# "hi there" / "hello!" / "thanks a lot"
_CHITCHAT_PREFIX = re.compile(
    r"^(hi|hello|hey|yo|sup|thanks|thank you|thx|bye|goodbye|good morning|"
    r"good evening|good night)\b[\s!,.?]*",
    re.I,
)

# Cheap, deterministic signals. Order matters: these run before the LLM so the
# common cases cost nothing and stay predictable.
_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("flights", re.compile(r"\b(flight|fly|flying|ticket|airfare|airline|airport|one[\s-]?way|round[\s-]?trip|fly me|air ticket)\w*", re.I)),
    ("hotels", re.compile(r"\b(hotel|hostel|resort|stay|staying|accommodation|lodging|guest ?house)\w*", re.I)),
    ("trips", re.compile(r"\b(trip|itinerary|itineraries|holiday|vacation|outing|plan my)\w*", re.I)),
    ("jobs", re.compile(r"\b(job|jobs|career|careers|hiring|internship|internships|vacancy|recruit\w*|opening)\b", re.I)),
    ("shopping", re.compile(r"\b(buy|shop|shopping|purchase|price|product|cheapest|under \d|budget for a)\w*", re.I)),
    ("research", re.compile(r"\b(research|compare|explain|find out|tell me about|what is|who is|why|how does|sources?|evidence|compare)\w*", re.I)),
)

INTENT_PROMPT = """You route a request from a chat input to exactly one specialist.

Specialists:
- research: look facts up on the web and answer with cited sources; explain a
  topic; compare ideas, approaches, frameworks or methods. Not products.
- shopping: find or compare products to buy, prices, deals, and stores.
- jobs: search job openings matching a resume, set up job alerts.
- flights: find flights between two cities.
- hotels: find hotels in a destination for given dates.
- trips: plan a whole trip end to end (flights + hotels + itinerary).
- assistant: greetings, thanks, small talk, "what can you do?", or a user
  thinking out loud who has not asked for a concrete task yet.

Rules:
- If the message is casual conversation with no concrete task, use "assistant".
- If it asks for something doable by exactly one specialist, use that one.
- Product shopping outranks research: "compare phones", "best laptop under
  50000", "cheapest headphones" are SHOPPING even though the word "compare"
  appears. Only use research for comparing non-product things.
- A message mentioning both flights and hotels is "trips" only if it asks for a
  whole itinerary. Otherwise pick the one it is mostly about, or "trips" if a
  coordinated trip is clearly intended.
- Extract the fields the chosen specialist's form needs, so it can be
  pre-filled. Use "" for anything the user did not say. NEVER invent a value.
  Fields per agent:
    jobs:     roles, locations, work_mode
    flights:  origin, destination, departure_date, return_date, passengers, cabin
    hotels:   location, check_in, check_out, guests
    trips:    origin, destination, departure_date, duration_days, travelers, budget_max
    shopping: query
    research: query
    assistant: (none needed)
- Dates must be YYYY-MM-DD. If the user said a relative date and you are unsure
  of the exact day, use "".

Return ONLY valid JSON, no other text:
{{"agent": "<one of: {agents}>", "reason": "<6 words or fewer>", "confidence": <0.0-1.0>, "fields": {{...}}}}

Message: {query}"""

_ISO = r"\d{4}-\d{2}-\d{2}"


def _iso_from(text: str) -> str:
    """Pull a YYYY-MM-DD out of free text, else ""."""
    m = re.search(_ISO, text)
    return m.group(0) if m else ""


def _int_or_none(raw: Any) -> int | None:
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _looks_like_chitchat(q: str) -> bool:
    low = q.strip().lower().rstrip("!.?,")
    if low in CHITCHAT_PHRASES:
        return True
    # A short greeting with nothing else in it, e.g. "hi there" / "hello!".
    if len(q.split()) <= 3 and _CHITCHAT_PREFIX.match(low):
        return True
    return False


def _keyword_agent(q: str) -> str:
    for name, pattern in _KEYWORDS:
        if pattern.search(q):
            return name
    return ASSISTANT


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _regex_fields(agent: str, q: str) -> dict[str, Any]:
    """Deterministic fallback extraction, used field-by-field when the LLM
    omits something. Mirrors the frontend travel parsers closely enough to be a
    useful backstop."""
    if agent in ("flights", "trips"):
        m = re.search(r"(.+?)\s+to\s+(.+)", q, re.I)
        out: dict[str, Any] = {}
        if m:
            out["origin"] = m.group(1).strip()
            out["destination"] = m.group(2).strip()
        out["departure_date"] = _iso_from(q)
        return out
    if agent == "hotels":
        m = re.search(r"\b(?:in|at|near)\s+(.+?)(?:\s+from\b|\s+for\b|$)", q, re.I)
        return {"location": m.group(1).strip() if m else q.strip()}
    if agent == "shopping":
        return {"query": q.strip()}
    if agent == "research":
        return {"query": q.strip()}
    return {}


def _merge_fields(agent: str, llm_fields: Any, q: str) -> dict[str, Any]:
    """LLM wins; anything it left blank is filled by the regex fallback."""
    out = dict(llm_fields) if isinstance(llm_fields, dict) else {}
    for k, v in _regex_fields(agent, q).items():
        if out.get(k) in (None, ""):
            out[k] = v
    # Drop blanks so the frontend only sees real values.
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def _clean_payload(agent: str, data: dict[str, Any], q: str) -> dict[str, Any]:
    fields = _merge_fields(agent, data.get("fields"), q)
    # Coerce the numeric fields the frontend expects as numbers.
    for key in ("passengers", "guests", "travelers", "duration_days"):
        if key in fields:
            n = _int_or_none(fields[key])
            if n is not None:
                fields[key] = n
    for key in ("departure_date", "return_date", "check_in", "check_out"):
        if key in fields:
            iso = _iso_from(str(fields[key]))
            fields[key] = iso
    if "budget_max" in fields:
        try:
            fields["budget_max"] = float(str(fields["budget_max"]).replace(",", "").strip())
        except ValueError:
            fields.pop("budget_max", None)

    if agent == "jobs":
        roles = fields.get("roles")
        if isinstance(roles, str):
            fields["roles"] = [r.strip() for r in roles.split(",") if r.strip()]
        locs = fields.get("locations")
        if isinstance(locs, str):
            fields["locations"] = [r.strip() for r in locs.split(",") if r.strip()]
        mode = str(fields.get("work_mode", "")).lower()
        fields["work_mode"] = mode if mode in ("remote", "hybrid", "onsite", "on-site") else ""
    elif agent in ("shopping", "research"):
        fields.setdefault("query", q.strip())
    elif agent == "assistant":
        return {}

    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return {
        "agent": agent,
        "reason": str(data.get("reason", ""))[:80],
        "confidence": max(0.0, min(1.0, conf)),
        "fields": fields,
    }


def classify_intent(query: str) -> dict[str, Any]:
    """Choose one specialist and pre-extract its form fields. Never runs a search."""
    q = (query or "").strip()
    if not q:
        return {"agent": ASSISTANT, "reason": "empty", "confidence": 0.0, "fields": {}}

    # 1. Chit-chat is cheap to detect and must not cost an LLM call.
    if _looks_like_chitchat(q):
        return {"agent": ASSISTANT, "reason": "greeting", "confidence": 1.0, "fields": {}}

    prompt = INTENT_PROMPT.format(agents=", ".join(AGENTS), query=q[:400])
    try:
        llm = init_llm_light(temperature=0.0, max_tokens=MAX_TOKENS)
        raw = invoke_with_timeout(llm, prompt, timeout=CALL_TIMEOUT)
        text = raw.content if hasattr(raw, "content") else str(raw)
        data = json.loads(_strip_fences(text))
        agent = str(data.get("agent", "")).strip().lower()
        if agent not in AGENTS:
            raise ValueError(f"model returned unknown agent: {agent!r}")
        out = _clean_payload(agent, data, q)
        logger.info("Intent router: %s -> %s (%s)", q[:60], out["agent"], out["reason"])
        return out
    except Exception as exc:  # noqa: BLE001 - routing must never 500
        logger.warning("Intent routing failed (%s); using keyword fallback", exc)
        agent = _keyword_agent(q)
        return {
            "agent": agent,
            "reason": "keyword fallback",
            "confidence": 0.4,
            "fields": _regex_fields(agent, q),
        }
