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
from backend.agents.travel.services.currency import SUPPORTED, currency_for

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
- For trips, also report budget_currency: the ISO code the user wrote (INR for
  ₹ / rs / rupees, USD for $, etc). Use "" if they wrote a bare number with no
  symbol - a number alone says nothing about the currency.
- Dates must be YYYY-MM-DD. If the user said a relative date and you are unsure
  of the exact day, use "".

Return ONLY valid JSON, no other text:
{{"agent": "<one of: {agents}>", "reason": "<6 words or fewer>", "confidence": <0.0-1.0>, "fields": {{...}}}}

Message: {query}"""

_ISO = r"\d{4}-\d{2}-\d{2}"

# Fields that must be present before a search can run. Derived from what each
# destination's form actually requires:
#   flights valid = origin && destination && departure_date
#   hotels  valid = location && check_in && check_out
#   trips   valid = origin && destination && departure_date && budget >= 100
#   jobs    runs on roles alone (locations are a filter, not a gate)
#   research / shopping need only the query itself
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "research": (),
    "shopping": (),
    "jobs": ("roles",),
    "flights": ("origin", "destination", "departure_date"),
    "hotels": ("location", "check_in", "check_out"),
    "trips": ("origin", "destination", "departure_date", "budget_max"),
}

# What the destination form would fall back to anyway. Reported as `assumed` so
# the UI can show what it decided rather than pretending the user said it. Dates
# are deliberately absent - guessing one would run a search nobody asked for.
FORM_DEFAULTS: dict[str, dict[str, Any]] = {
    "flights": {"passengers": 1, "cabin": "economy"},
    "hotels": {"guests": 2},
    "trips": {"travelers": 2, "duration_days": 5},
}


def _summarise(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:3])
    return str(value)


def _trip_currency(fields: dict[str, Any]) -> str:
    """Currency for a trip the user is about to hand over.

    A bare "under 40000" says nothing about the currency, and assuming USD made a
    rupee budget 83x too generous. So it comes from the origin city the user
    actually named, unless the model picked a symbol out of the sentence.
    """
    stated = str(fields.get("budget_currency") or "").strip().upper()
    if stated in SUPPORTED:
        return stated
    return currency_for(str(fields.get("origin") or ""))


def build_receipt(agent: str, fields: dict[str, Any]) -> dict[str, Any]:
    """What the router understood, what it will assume, and what is still needed.

    Computed before _merge_fields drops blanks, because the whole point is to
    notice what is absent.
    """
    required = REQUIRED_FIELDS.get(agent, ())
    defaults = FORM_DEFAULTS.get(agent, {})
    return {
        "understood": {k: _summarise(v) for k, v in fields.items()},
        "assumed": {k: v for k, v in defaults.items() if not fields.get(k)},
        "missing": [f for f in required if not fields.get(f)],
    }


def _finalise(agent: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Resolve the trip currency, then build the receipt. One place, because
    every return path needs both.

    The derived currency has to land in `fields` as well as the receipt: the trip
    form reads fields.budget_currency, so reporting it only in the receipt left
    the dropdown on its INR default while the router had decided GBP. It is also
    kept in `assumed` so a derivation is still visible rather than silent.
    """
    derived: str | None = None
    if agent == "trips":
        stated = str(fields.get("budget_currency") or "").strip().upper()
        fields["budget_currency"] = _trip_currency(fields)
        derived = None if stated in SUPPORTED else fields["budget_currency"]

    receipt = build_receipt(agent, fields)
    if derived:
        receipt["assumed"]["budget_currency"] = derived
    return {"fields": fields, "receipt": receipt}


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


_LEAD_NOISE = re.compile(
    r"^\s*(?:please\s+)?(?:(?:find|search|book|show|get|plan|arrange|make|look\s+for)\s+)?(?:me\s+)?"
    r"(?:a\s+)?(?:short|long|quick|weekend|holiday|vacation)?\s*"
    r"(?:\d+[-\s]*(?:days?|nights?)\s*)?"
    r"(?:trip|flights?|tickets?|hotels?|journey|travel)?\s*",
    re.I,
)
# Only for the left-hand side. Including a bare "to" here ate the first two
# letters of "Tokyo", because the destination is matched case-insensitively.
_LEAD_ORIGIN = re.compile(rf"{_LEAD_NOISE.pattern}(?:from|between|to|in)?\s*", re.I)


def _regex_fields(agent: str, q: str) -> dict[str, Any]:
    """Deterministic fallback extraction, used field-by-field when the LLM
    omits something. Mirrors the frontend travel parsers closely enough to be a
    useful backstop."""
    if agent in ("flights", "trips"):
        m = re.search(r"(.+?)\s+to\s+(.+)", q, re.I)
        out: dict[str, Any] = {}
        if m:
            # Without this the origin came back as "plan a 5 day trip from
            # Delhi", which then sat in the form as if the user had typed it.
            out["origin"] = _LEAD_ORIGIN.sub("", m.group(1)).strip()
            dest = _LEAD_NOISE.sub("", m.group(2)).strip()
            # Trailing budget/date clauses are not part of the destination.
            dest = re.split(r"\s+(?:under|below|up\s+to|budget|within|on)\s+", dest, maxsplit=1, flags=re.I)[0]
            out["destination"] = dest.strip()
        out["departure_date"] = _iso_from(q)
        if agent == "trips":
            # Same shape as the frontend parser: the currency can sit on either
            # side of the number. Capturing only the amount meant an explicit
            # "3000 INR" fell back to the origin's currency whenever this path ran.
            b = re.search(r"(?:budget|under|below|up\s+to|max|within)\s*(?:of\s*)?"
                          r"(?:(rs\.?|inr|₹|\$)\s*)?([\d,.]+)\s*(k)?\s*"
                          r"(inr|usd|gbp|aed|cad|aud|eur|sgd)?", q, re.I)
            if b:
                try:
                    n = float(b.group(2).replace(",", ""))
                    out["budget_max"] = n * 1000 if b.group(3) else n
                except ValueError:
                    pass
                sym = b.group(1) or b.group(4)
                if sym:
                    out["budget_currency"] = (
                        "INR" if re.search(r"inr|₹|rs", sym, re.I)
                        else sym.replace("$", "USD").upper()
                    )
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
        **_finalise(agent, fields),
    }


def _payload(agent: str, reason: str, confidence: float, fields: dict[str, Any]) -> dict[str, Any]:
    """Every return path gets the same shape, so callers never special-case."""
    return {
        "agent": agent,
        "reason": reason,
        "confidence": confidence,
        **_finalise(agent, fields),
    }


def classify_intent(query: str) -> dict[str, Any]:
    """Choose one specialist and pre-extract its form fields. Never runs a search."""
    q = (query or "").strip()
    if not q:
        return _payload(ASSISTANT, "empty", 0.0, {})

    # 1. Chit-chat is cheap to detect and must not cost an LLM call.
    if _looks_like_chitchat(q):
        return _payload(ASSISTANT, "greeting", 1.0, {})

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
        logger.info(
            "Intent router: %s -> %s (%s, missing=%s)",
            q[:60], out["agent"], out["reason"], out["receipt"]["missing"] or "none",
        )
        return out
    except Exception as exc:  # noqa: BLE001 - routing must never 500
        logger.warning("Intent routing failed (%s); using keyword fallback", exc)
        return _payload(_keyword_agent(q), "keyword fallback", 0.4, _regex_fields(_keyword_agent(q), q))
