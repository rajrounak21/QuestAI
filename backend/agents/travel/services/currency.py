"""Which currency a trip should be shown in.

SerpApi converts for us - pass currency=INR and google_hotels returns rupees at
their current rate. So this module never stores or fetches a rate; it only
decides which code to send, and that decision must never be a guess about a bare
number.

A user typing "under 40000" gives us nothing to work with. The currency comes
from somewhere they actually said: an explicit symbol, the dropdown they picked,
or a city they named. Anything else is a default, and the UI shows it so a wrong
one is visible instead of silent.

The country -> currency presets are shopping's, not a second copy of them.
"""

from __future__ import annotations

import re

from backend.agents.shopping.services.location import DEFAULT_LOCATION, LOCATION_PRESETS

# City names and IATA codes, because the trip form holds whatever the user typed
# while the flight extractor resolves IATA separately.
CITY_TO_COUNTRY: dict[str, str] = {
    # India
    "delhi": "in", "mumbai": "in", "bengaluru": "in", "bangalore": "in",
    "chennai": "in", "hyderabad": "in", "kolkata": "in", "pune": "in",
    "jaipur": "in", "ahmedabad": "in", "goa": "in", "lucknow": "in",
    "del": "in", "bom": "in", "blr": "in", "maa": "in", "hyd": "in", "ccu": "in",
    # UAE
    "dubai": "ae", "abu dhabi": "ae", "sharjah": "ae",
    "dxb": "ae", "auh": "ae",
    # United Kingdom
    "london": "uk", "manchester": "uk", "edinburgh": "uk", "glasgow": "uk",
    "lhr": "uk", "man": "uk", "edi": "uk",
    # United States
    "new york": "us", "san francisco": "us", "los angeles": "us",
    "chicago": "us", "seattle": "us", "boston": "us", "houston": "us",
    "jfk": "us", "lax": "us", "sfo": "us", "ord": "us", "sea": "us",
    # Singapore
    "singapore": "sg", "sin": "sg",
    # Germany
    "frankfurt": "de", "munich": "de", "berlin": "de", "hamburg": "de",
    "fra": "de", "muc": "de", "ber": "de",
    # Australia
    "sydney": "au", "melbourne": "au", "brisbane": "au", "perth": "au",
    "syd": "au", "mel": "au",
    # Canada
    "toronto": "ca", "vancouver": "ca", "montreal": "ca",
    "yyz": "ca", "yvr": "ca",
}

# Offered in the trip budget dropdown. Same set the shopping location picker has,
# so a trip never lands on a currency the rest of the app cannot show.
SUPPORTED = tuple(LOCATION_PRESETS[c]["currency"] for c in LOCATION_PRESETS)


def currency_for(place: str | None, fallback: str | None = None) -> str:
    """Currency for a city name or IATA code.

    Reads a place the user explicitly typed. "Bengaluru, India" works through the
    substring pass so the trailing country does not defeat the lookup.
    """
    key = (place or "").strip().lower()
    if not key:
        return fallback or LOCATION_PRESETS[DEFAULT_LOCATION]["currency"]

    country = CITY_TO_COUNTRY.get(key)
    if not country:
        # Word-boundary match so "Bengaluru, India" still resolves. A raw
        # substring pass would map Podgorica to India, because it contains "goa".
        for token, mapped in CITY_TO_COUNTRY.items():
            if re.search(rf"\b{re.escape(token)}\b", key):
                country = mapped
                break
    return LOCATION_PRESETS.get(country or "", {}).get("currency", fallback or "USD")