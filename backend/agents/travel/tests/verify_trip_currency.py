"""
Locks the trip budget currency ladder end to end, on both the LLM path and the
keyword fallback that runs when the intent model times out.

The bug this exists for: the derived currency was written only to
receipt.assumed, while the trip form reads fields.budget_currency. A London
origin silently got the INR default while the router had decided GBP - and Delhi
never showed it, because INR is the right answer there anyway.

Run: python -m backend.agents.travel.tests.verify_trip_currency
"""
from __future__ import annotations

import re
import sys

from backend.agents.router.services.intent import _finalise, _regex_fields
from backend.agents.travel.services.currency import SUPPORTED

# (query, expected currency). An explicit symbol must beat the origin-derived
# default; a bare number must fall through to the origin.
CASES = [
    ("trip from London to Tokyo under 3000 INR", "INR"),
    ("trip from London to Tokyo under 3000 usd", "USD"),
    ("trip from Delhi to Dubai under 40000", "INR"),
    ("trip from London to Tokyo under 3000", "GBP"),
    ("trip from DXB to DEL under 4k AED", "AED"),
    ("plan a 5 day trip from Delhi to Dubai under Rs 40000", "INR"),
    ("plan a 5 day trip from Delhi to Dubai under ₹40000", "INR"),
    ("trip from Singapore to Bali under 5000", "SGD"),
]

failures: list[str] = []

for label, extract in (
    ("fallback", lambda q: _finalise("trips", _regex_fields("trips", q))),
    ("fields vs receipt", None),
):
    if extract is None:
        continue
    for query, want in CASES:
        got = extract(query)["fields"]["budget_currency"]
        if got != want:
            failures.append(f"{label}: {query!r} -> {got}, want {want}")

# The form always gets a currency, and it is always one the form can render.
for query, want in CASES:
    out = _finalise("trips", _regex_fields("trips", query))
    cur = out["fields"].get("budget_currency")
    if cur != want:
        failures.append(f"ladder: {query!r} -> {cur}, want {want}")
    if cur not in SUPPORTED:
        failures.append(f"unrenderable: {query!r} -> {cur}")

# A derived currency is reported as an assumption; a stated one is not, because
# the user said it. Either way it must reach the form, never only the receipt.
# Detected from the raw query rather than the router's own output, so the test
# cannot agree with a bug.
SYMBOL = re.compile(r"[₹$]|\b(?:rs\.?|inr|usd|gbp|aed|cad|aud|eur|sgd)\b", re.I)
for query, _ in CASES:
    out = _finalise("trips", _regex_fields("trips", query))
    cur = out["fields"]["budget_currency"]
    assumed = out["receipt"]["assumed"].get("budget_currency")
    if SYMBOL.search(query):
        if assumed is not None:
            failures.append(f"stated currency should not be an assumption: {query!r}")
    elif assumed != cur:
        failures.append(f"derived currency must be visible as assumed: {query!r} {cur} vs {assumed}")

# Non-trip agents must not gain a currency.
for agent in ("flights", "hotels", "shopping", "research", "jobs"):
    out = _finalise(agent, {"origin": "Delhi"})
    if "budget_currency" in out["fields"]:
        failures.append(f"{agent} should not carry budget_currency")

if any(c not in SUPPORTED for _, c in CASES):
    failures.append("a test case uses a currency the form cannot render")

print("=== trip currency ladder ===")
for query, want in CASES:
    out = _finalise("trips", _regex_fields("trips", query))
    cur = out["fields"]["budget_currency"]
    src = "stated" if SYMBOL.search(query) else "derived"
    rec = out["receipt"]["assumed"].get("budget_currency")
    print(f"  {cur:4} ({src:7}) receipt.assumed={str(rec):5} {query}")

print()
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS - ladder correct, fields and receipt agree, no other agent affected")