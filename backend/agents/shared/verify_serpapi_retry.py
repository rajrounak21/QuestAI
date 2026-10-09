"""Verify the shared SerpApi client retries transient provider errors.

Run:  .venv\\Scripts\\python.exe -m backend.agents.shared.verify_serpapi_retry

Costs 0 SerpApi searches: every provider is stubbed.

Why this matters: destination research fans 5 searches out and only logs a
failure, so a single 503 used to permanently delete that source and the
itinerary was then built on whatever evidence happened to survive.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.agents.shared import serpapi_client  # noqa: E402


def main() -> int:
    failures: list[str] = []
    attempts = {"n": 0}

    class Flaky:
        def __init__(self, fail_times):
            self.fail = fail_times

        def search(self, params):
            attempts["n"] += 1
            if attempts["n"] <= self.fail:
                raise RuntimeError("503 Server Error: Service Unavailable for url: ...")
            return {"data": {"ok": True}}

    class BadRequest:
        def search(self, params):
            attempts["n"] += 1
            raise RuntimeError("400 Client Error: Bad Request for url: ...")

    print("=== transient provider errors are retried, bad requests are not ===")

    orig_client = serpapi_client._get_client
    orig_backoff = serpapi_client._BACKOFF_SECONDS
    serpapi_client._BACKOFF_SECONDS = 0.01
    try:
        attempts["n"] = 0
        serpapi_client._get_client = lambda: Flaky(1)
        recovered = serpapi_client.search({"engine": "google", "q": "x"})
        if not recovered["data"].get("ok") or attempts["n"] != 2:
            failures.append(f"one 503 did not recover (attempts={attempts['n']})")
        else:
            print("  one 503 -> recovered on the retry  OK")

        attempts["n"] = 0
        serpapi_client._get_client = lambda: Flaky(99)
        try:
            serpapi_client.search({"engine": "google", "q": "x"})
            failures.append("a permanent 503 did not raise")
        except RuntimeError:
            if attempts["n"] != 2:
                failures.append(f"gave up after {attempts['n']} attempts, expected 2")
            else:
                print("  permanent 503 -> gave up after 2 attempts  OK")

        attempts["n"] = 0
        serpapi_client._get_client = lambda: BadRequest()
        try:
            serpapi_client.search(
                {"engine": "google_flights", "departure_id": "Mumbai"}
            )
            failures.append("a 400 did not raise")
        except RuntimeError:
            if attempts["n"] != 1:
                failures.append(
                    f"a 400 was retried {attempts['n']}x - only burns a credit"
                )
            else:
                print("  400 bad request -> never retried  OK")

        # A healthy provider must not pay the backoff sleep.
        attempts["n"] = 0
        serpapi_client._get_client = lambda: Flaky(0)
        serpapi_client.search({"engine": "google", "q": "x"})
        if attempts["n"] != 1:
            failures.append(f"a healthy search took {attempts['n']} attempts")
        else:
            print("  healthy search -> single attempt  OK")

        # search() must not accept the removed agent kwarg: it would silently
        # accept it and drop the attribution that no longer exists.
        import inspect

        params = list(inspect.signature(serpapi_client.search).parameters)
        if params != ["params"]:
            failures.append(f"unexpected search() signature: {params}")
        else:
            print("  search(params) only - no dead agent kwarg  OK")
    finally:
        serpapi_client._get_client = orig_client
        serpapi_client._BACKOFF_SECONDS = orig_backoff

    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL SERPAPI RETRY CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())