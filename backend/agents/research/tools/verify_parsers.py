"""Check the research parsers against live SerpApi responses.

    python -m backend.agents.research.tools.verify_parsers

Costs 3 searches. The process_sources() check is the important one: it drops
sources with an empty snippet, so a parser can look perfect while contributing
nothing.
"""

from __future__ import annotations

import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv(override=True)

if not os.getenv("SERP_API_KEY"):
    sys.exit("SERP_API_KEY not set")

import serpapi  # noqa: E402

from backend.agents.research.schemas.sources import SourceType  # noqa: E402
from backend.agents.research.services.source_processor import process_sources  # noqa: E402
from backend.agents.research.tools.search import (  # noqa: E402
    google_news,
    google_search,
    google_scholar,
)

CASES = [
    ("google", {"engine": "google", "q": "retrieval augmented generation evaluation", "num": 3}),
    ("google_scholar", {"engine": "google_scholar", "q": "retrieval augmented generation", "num": 3}),
    ("google_news", {"engine": "google_news", "q": "artificial intelligence", "num": 3}),
]

client = serpapi.Client(api_key=os.environ["SERP_API_KEY"])

print("=" * 78)
print("RAW PAYLOAD KEYS AND FIRST RESULT - what the parser actually receives")
print("=" * 78)

for label, params in CASES:
    data = client.search(params).data
    key = "news_results" if label == "google_news" else "organic_results"
    rows = data.get(key) or []
    print(f"\n--- {label} ---")
    print(f"  returned key present : {key in data}  (count={len(rows)})")
    print(f"  top-level keys       : {sorted(data.keys())[:14]}")
    if rows:
        first = rows[0]
        print(f"  first-result keys    : {sorted(first.keys())}")
        for k in ("title", "link", "snippet", "date", "publication_info"):
            if k in first:
                v = first[k]
                print(f"    {k:18}: {str(v)[:100]}")

print()
print("=" * 78)
print("PARSER OUTPUT - through the real SearchResult dataclasses")
print("=" * 78)

ENGINES = (
    (google_search, SourceType.GOOGLE, "google"),
    (google_scholar, SourceType.SCHOLAR, "google_scholar"),
    (google_news, SourceType.NEWS, "google_news"),
)

# The three engines swallow exceptions and return [], so an empty result can mean
# a dropped connection rather than a broken parser. SerpApi resets connections
# often enough to matter, so retry once before calling it a parser bug.
def fetch(fn):
    for attempt in (1, 2):
        out = fn("retrieval augmented generation evaluation", num_results=3)
        if out:
            return out
        if attempt == 1:
            print("  (empty - retrying once; a reset connection looks the same as a broken parser)")
            time.sleep(3)
    return []


failures = []

for fn, stype, label in ENGINES:
    out = fetch(fn)
    print(f"\n--- {label} -> {len(out)} SearchResult ---")
    if not out:
        failures.append(f"{label}: no results after 2 attempts - check the API key and connection")
        continue
    for s in out:
        missing = [f for f in ("title", "url") if not getattr(s, f)]
        if missing:
            failures.append(f"{label}: result missing {missing}: {s.title!r}")
        if s.source_type is not stype:
            failures.append(f"{label}: wrong source_type {s.source_type}")
        print(f"  [{s.source_type.value:7}] date={s.date or '-':12} {s.title[:58]}")
        print(f"             snippet: {s.snippet[:70] or '(empty)'}")
        print(f"             url    : {s.url[:78]}")
        print(f"             raw_data keys: {len(s.raw_data)}")

print()
print("=" * 78)
print("DOWNSTREAM - process_sources() drops empty snippets")
print("=" * 78)

for fn, _, label in ENGINES:
    raw = fetch(fn)
    kept = process_sources(list(raw))
    blank = sum(1 for s in raw if not s.snippet.strip())
    status = "OK " if kept else "DEAD"
    print(f"  [{status}] {label:15} fetched={len(raw)}  blank_snippets={blank}  survive_processing={len(kept)}")
    if raw and not kept:
        failures.append(f"{label}: fetched {len(raw)} but process_sources() kept 0")
    if not raw:
        failures.append(f"{label}: no results after 2 attempts - check the API key and connection")

print()
print("=" * 78)
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS - every engine parses into populated SearchResults and survives process_sources()")