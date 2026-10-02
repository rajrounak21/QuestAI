from __future__ import annotations

# Why presets instead of free text: SerpApi needs an exact, valid combo of
# google_domain + gl/hl + amazon_domain. Free-text locations produce invalid
# combos and silently wrong results, so the frontend sends a country code and
# the backend maps it here. Unknown codes fall back to India.

LOCATION_PRESETS: dict[str, dict[str, str]] = {
    "in": {
        "label": "India",
        "location": "India",
        "gl": "in",
        "hl": "en",
        "google_domain": "google.co.in",
        "amazon_domain": "amazon.in",
        "currency": "INR",
    },
    "us": {
        "label": "United States",
        "location": "United States",
        "gl": "us",
        "hl": "en",
        "google_domain": "google.com",
        "amazon_domain": "amazon.com",
        "currency": "USD",
    },
    "uk": {
        "label": "United Kingdom",
        "location": "United Kingdom",
        "gl": "uk",
        "hl": "en",
        "google_domain": "google.co.uk",
        "amazon_domain": "amazon.co.uk",
        "currency": "GBP",
    },
    "ae": {
        "label": "UAE",
        "location": "United Arab Emirates",
        "gl": "ae",
        "hl": "en",
        "google_domain": "google.ae",
        "amazon_domain": "amazon.ae",
        "currency": "AED",
    },
    "ca": {
        "label": "Canada",
        "location": "Canada",
        "gl": "ca",
        "hl": "en",
        "google_domain": "google.ca",
        "amazon_domain": "amazon.ca",
        "currency": "CAD",
    },
    "au": {
        "label": "Australia",
        "location": "Australia",
        "gl": "au",
        "hl": "en",
        "google_domain": "google.com.au",
        "amazon_domain": "amazon.com.au",
        "currency": "AUD",
    },
    "de": {
        "label": "Germany",
        "location": "Germany",
        "gl": "de",
        "hl": "de",
        "google_domain": "google.de",
        "amazon_domain": "amazon.de",
        "currency": "EUR",
    },
    "sg": {
        "label": "Singapore",
        "location": "Singapore",
        "gl": "sg",
        "hl": "en",
        "google_domain": "google.com.sg",
        "amazon_domain": "amazon.sg",
        "currency": "SGD",
    },
}

DEFAULT_LOCATION = "in"


def resolve_location(code: str | None) -> tuple[str, dict[str, str]]:
    """Returns (code, preset). Unknown/empty codes fall back to India."""
    key = (code or "").strip().lower()
    if key not in LOCATION_PRESETS:
        key = DEFAULT_LOCATION
    return key, LOCATION_PRESETS[key]
