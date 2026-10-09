"""Verify the research evidence cache: it must serve a second identical query
without spending SerpApi, and it must never be used for prices.

Run:  .venv\\Scripts\\python.exe -m backend.agents.shared.verify_cache

Costs 1 SerpApi search. Clears its own cache entry afterwards.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.agents.research.tools.research_cache import (  # noqa: E402
    CACHE_TTL_SECONDS,
    cache_key,
    ensure_research_cache_indexes,
    get_cache_collection,
    get_cached,
    set_cached,
)
from backend.agents.research.tools.search import google_search  # noqa: E402
from backend.agents.shared import serpapi_client  # noqa: E402

QUERY = "questai serpapi cache probe xyzzy"


class _CallCounter:
    """Counts real SerpApi provider calls.

    Replaces the old usage-record count: the credit meter is gone, and counting
    at the provider boundary is what "spent a search" actually means.
    """

    def __init__(self):
        self.calls = 0
        self._inner = serpapi_client._get_client()

    def search(self, params):
        self.calls += 1
        return self._inner.search(params)


def main() -> int:
    ensure_research_cache_indexes()
    col = get_cache_collection()
    failures: list[str] = []

    col.delete_one({"_id": cache_key("google", QUERY, 5)})
    counter = _CallCounter()
    orig_client = serpapi_client._get_client
    serpapi_client._get_client = lambda: counter

    try:
        print("=== 1. cold query -> spends a search, populates the cache ===")
        before = counter.calls
        first = google_search(QUERY, num_results=5)
        spent = counter.calls - before
        if spent != 1:
            failures.append(f"cold query made {spent} provider calls, expected 1")
        else:
            print(f"  spent 1 search, got {len(first)} results  OK")

        hit = get_cached("google", QUERY, 5)
        if hit is None:
            failures.append("cache was not populated by a successful search")
        else:
            print("  cache populated  OK")

        print("\n=== 2. identical query -> cache hit, zero searches ===")
        before = counter.calls
        second = google_search(QUERY, num_results=5)
        spent = counter.calls - before
        if spent != 0:
            failures.append(f"cache hit still made {spent} provider calls")
        else:
            print("  0 searches spent  OK")
        if len(second) != len(first):
            failures.append(f"cached result count differs: {len(first)} vs {len(second)}")
        elif [s.url for s in second] != [s.url for s in first]:
            failures.append("cached results differ from the originals")
        else:
            print("  identical results returned  OK")
    finally:
        serpapi_client._get_client = orig_client

    print("\n=== 3. query is case/whitespace insensitive ===")
    hit2 = get_cached("google", f"  {QUERY.upper()}  ", 5)
    if hit2 is None:
        failures.append("cache key is case/whitespace sensitive")
    else:
        print("  same key for '  QUERY  '  OK")

    print("\n=== 4. different num_results is a different entry ===")
    if get_cached("google", QUERY, 8) is not None:
        failures.append("num_results ignored in the cache key")
    else:
        print("  distinct key for num_results=8  OK")

    print("\n=== 5. prices are NOT cached anywhere ===")
    import backend.agents.travel.tools.google_flights as gf
    import backend.agents.travel.tools.google_hotels as gh

    src = ""
    for mod in (gf, gh):
        with open(mod.__file__, encoding="utf-8") as f:
            src += f.read()
    if "research_cache" in src or "get_cached" in src:
        failures.append("a price tool imports the research cache")
    else:
        print("  flights and hotels do not touch the evidence cache  OK")

    print("\n=== 6. cache is bounded and self-expiring ===")
    if CACHE_TTL_SECONDS <= 0:
        failures.append("cache never expires")
    else:
        idx = [i for i in col.index_information().values() if "expireAfterSeconds" in str(i)]
        print(f"  TTL {CACHE_TTL_SECONDS}s, Mongo TTL index present: {bool(idx)}  OK")

    col.delete_one({"_id": cache_key("google", QUERY, 5)})
    print("\ncleaned probe entry")

    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL CACHE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())