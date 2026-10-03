"""Live check that travel results are labelled with the currency that was
actually requested, not a hardcoded USD.

Costs 1 SerpApi search. Run:
    python -m backend.agents.travel.tests.verify_currency
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

if not os.getenv("SERP_API_KEY"):
    sys.exit("SERP_API_KEY not set")

from backend.agents.travel.schemas.hotel import HotelSearchRequest
from backend.agents.travel.services.hotel_normalizer import build_hotel_search_response
from backend.agents.travel.tools.google_hotels import google_hotels_search

REQUEST = {
    "location": "Dubai",
    "check_in": "2027-02-01",
    "check_out": "2027-02-05",
    "guests": 2,
}

failures = []

for currency in ("USD", "INR"):
    req = {**REQUEST, "currency": currency}
    raw = google_hotels_search(HotelSearchRequest(**req))
    response = build_hotel_search_response(req, raw)

    echoed = raw.get("search_parameters", {}).get("currency")
    labelled = {h.currency for h in response.hotels}
    sample = response.hotels[0].price_per_night if response.hotels else None

    print(f"--- requested {currency} ---")
    print(f"  SerpApi echoed      : {echoed}")
    print(f"  response.request    : {response.request.currency}")
    print(f"  currencies on result: {labelled or '{} (no hotels)'}")
    print(f"  sample nightly      : {sample}")

    if echoed != currency:
        failures.append(f"{currency}: SerpApi echoed {echoed}")
    if response.request.currency != currency:
        failures.append(f"{currency}: request echoed {response.request.currency}")
    if labelled and labelled != {currency}:
        failures.append(f"{currency}: results labelled {labelled}")

print()
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS - results carry the requested currency, no hardcoded USD")