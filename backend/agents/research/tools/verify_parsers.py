"""Verify the research SerpApi tools against live responses, then print exactly
what each engine's real payload looks like so the parsers can be checked.

Run once. Costs 3 SerpApi searches.
    python -m backend.agents.research.tools.verify_parsers
"""

from __future__ import annotations

import json
import os
import sys

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

failures = []

for fn, stype, label in (
    (google_search, SourceType.GOOGLE, "google"),
    (google_scholar, SourceType.SCHOLAR, "google_scholar"),
    (google_news, SourceType.NEWS, "google_news"),
):
    out = fn("retrieval augmented generation evaluation", num_results=3)
    print(f"\n--- {label} -> {len(out)} SearchResult ---")
    if not out:
        failures.append(f"{label}: parser returned 0 results")
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
print("DOWNSTREAM - process_sources() drops any source with an empty snippet,")
print("so an engine that yields blank snippets is silently a no-op. Checked here.")
print("=" * 78)

for fn, label in ((google_search, "google"), (google_scholar, "google_scholar"), (google_news, "google_news")):
    raw = fn("retrieval augmented generation evaluation", num_results=3)
    kept = process_sources(list(raw))
    blank = sum(1 for s in raw if not s.snippet.strip())
    status = "OK " if kept else "DEAD"
    print(f"  [{status}] {label:15} fetched={len(raw)}  blank_snippets={blank}  survive_processing={len(kept)}")
    if raw and not kept:
        failures.append(
            f"{label}: {len(raw)} results fetched but process_sources() kept 0 "
            f"(all snippets blank) - this engine contributes nothing downstream"
        )

print()
print("=" * 78)
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS - all three engines parse into populated SearchResult objects")
print("       and every engine survives process_sources() with at least 1 source")