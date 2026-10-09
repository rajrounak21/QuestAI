"""Verify that a trip revision actually re-searches instead of replaying the
previous run's cached results.

Run:  .venv\\Scripts\\python.exe -m backend.agents.travel.tests.verify_trip_revision

Costs 0 SerpApi searches - the flight agent is monkeypatched.

Background: update_trip_state used to recompute flight_input_hash from the NEW
inputs before dispatch ran. The cache guard then compared that new hash against
itself, matched, and returned the previous run's flights. So "change the dates"
or "make it cheaper" silently showed stale results while the trip header
displayed the new dates. Hashes are now written by the agent that actually
re-searched, so they always describe the results on the session.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.agents.travel.agent import trip_graph  # noqa: E402
from backend.agents.travel.schemas.trip import compute_flight_hash  # noqa: E402

OLD_DATE = "2026-10-02"
NEW_DATE = "2026-10-20"

calls: list[str] = []


def _fake_search(query: str) -> dict:
    calls.append(query)
    return {"flights": [{"flight_number": f"FRESH{len(calls)}", "price": 1}]}


def _state(departure_date: str, stored_hash: str) -> dict:
    return {
        "trip_session": {
            "origin": "DEL",
            "destination": "DXB",
            "departure_date": departure_date,
            "return_date": None,
            "travelers": 1,
            "flight_preferences": {},
            "budget": {},
            # leftovers from the previous run
            "flight_results": [{"flight_number": "STALE", "price": 999}],
            "flight_input_hash": stored_hash,
        }
    }


def main() -> int:
    import backend.agents.travel.tools.google_flights as gf
    from backend.agents.travel.services import flight_normalizer

    class _FakeFlight:
        def __init__(self, n):
            self.flight_number = n
            self.price = 1

        def model_dump(self):
            return {"flight_number": self.flight_number, "price": self.price}

    class _FakeResponse:
        def __init__(self, n):
            self.flights = [_FakeFlight(n)]
            self.total_results = 1

    def _fake_provider(req):
        calls.append(f"{req.origin} to {req.destination} on {req.departure_date}")
        return {}

    gf.google_flights_search = _fake_provider
    flight_normalizer.build_search_response = lambda req, raw: _FakeResponse(
        f"FRESH{len(calls)}"
    )
    # The search budget is asserted elsewhere; irrelevant here.
    trip_graph._bump_searches = lambda *a, **k: None

    old_hash = compute_flight_hash("DEL", "DXB", OLD_DATE, None, 1, {})
    failures: list[str] = []

    print("=== 1. changed dates -> must re-search, not replay ===")
    st = _state(NEW_DATE, old_hash)
    out = trip_graph.run_flight_search(st)
    if not calls:
        failures.append("no search ran, stale results were served")
    elif not out["flight_results"][0]["flight_number"].startswith("FRESH"):
        failures.append("stale flights returned after a date change")
    elif NEW_DATE not in calls[-1]:
        failures.append(f"searched the wrong date: {calls[-1]}")
    else:
        print(f"  searched: {calls[-1]}")
        print("  got fresh results, hash written with them  OK")
    if st["trip_session"]["flight_input_hash"] != compute_flight_hash(
        "DEL", "DXB", NEW_DATE, None, 1, {}
    ):
        failures.append("hash not written alongside the fresh results")

    # The graph merges dispatch's return into state and synthesize later writes
    # those results onto the session. Emulate that for the next call.
    st["trip_session"]["flight_results"] = out["flight_results"]

    print("\n=== 2. identical inputs again -> must reuse, not re-search ===")
    before = len(calls)
    again = trip_graph.run_flight_search(st)
    if len(calls) != before:
        failures.append("re-searched identical inputs, burning a SerpApi credit")
    elif "Reusing cached" not in (again["progress_steps"] or [""])[0]:
        failures.append(f"cache reuse not reported: {again['progress_steps']}")
    else:
        print(f"  {(again['progress_steps'] or [''])[0]}  OK")

    print("\n=== 3. travellers changed -> must re-search ===")
    before = len(calls)
    st["trip_session"]["travelers"] = 3
    trip_graph.run_flight_search(st)
    if len(calls) != before + 1:
        failures.append("traveller change did not invalidate the cache")
    else:
        print(f"  searched: {calls[-1]}  OK")

    print("\n=== 4. preferences changed -> must re-search ===")
    before = len(calls)
    st["trip_session"]["flight_preferences"] = {"stops": "direct"}
    trip_graph.run_flight_search(st)
    if len(calls) != before + 1:
        failures.append("preference change did not invalidate the cache")
    else:
        print(f"  searched: {calls[-1]}  OK")

    print("\n=== 5. return date must follow departure + duration ===")
    from backend.agents.travel.agent.trip_graph import update_trip_state
    from backend.agents.travel.schemas.trip import TripSession
    from backend.agents.travel.services import trip_memory

    _tok = trip_memory.use_user("verify-revision-user")
    _sid = "verify-return-date-session"
    trip_memory.trip_memory.save = lambda *a, **k: None
    from backend.database.collections import get_trip_sessions_collection
    get_trip_sessions_collection().delete_many(
        {"user_id": "verify-revision-user", "session_id": _sid}
    )

    base = TripSession(
        trip_id="t1",
        origin="Mumbai",
        destination="Bali",
        departure_date="2026-10-02",
        return_date="2026-10-07",
        duration_days=5,
        travelers=2,
    ).to_dict()

    def run_follow_up(extracted, changes=None):
        st = {
            "trip_session": dict(base),
            "extracted_params": extracted,
            "impact_analysis": {"affected_agents": [], "changes": changes or {}, "response": ""},
            "user_query": "make it 7 days",
        }
        out = update_trip_state(st)
        return out.get("trip_session") or {}

    # 5a. duration changes, departure does not
    got = run_follow_up(
        {"intent": "follow_up", "follow_up_type": "duration_change", "duration_days": 7},
        {"duration_days": 7, "return_date": "2026-10-09"},
    )
    if got.get("duration_days") != 7 or got.get("return_date") != "2026-10-09":
        failures.append(
            f"duration change left dates inconsistent: {got.get('duration_days')} days, "
            f"return {got.get('return_date')}"
        )
    else:
        print(f"  5 days -> 7 days, return_date -> {got.get('return_date')}  OK")

    # 5b. even when impact proposes NO return date at all
    got = run_follow_up(
        {"intent": "follow_up", "follow_up_type": "duration_change", "duration_days": 9},
        {"duration_days": 9},
    )
    if got.get("return_date") != "2026-10-11":
        failures.append(f"return_date not derived without a proposal: {got.get('return_date')}")
    else:
        print(f"  no proposed return date, derived -> {got.get('return_date')}  OK")

    # 5c. departure moves, duration stays
    got = run_follow_up(
        {
            "intent": "follow_up",
            "follow_up_type": "update_dates",
            "departure_date": "2026-10-20",
            "duration_days": 5,
        },
    )
    if got.get("return_date") != "2026-10-25":
        failures.append(f"departure move did not shift return_date: {got.get('return_date')}")
    else:
        print(f"  departure -> 2026-10-20, return_date -> {got.get('return_date')}  OK")

    # 5d. nothing changes -> return date must not move
    got = run_follow_up({"intent": "follow_up", "follow_up_type": "duration_change"}, {})
    if got.get("return_date") != "2026-10-07":
        failures.append(f"return_date moved with no change: {got.get('return_date')}")
    else:
        print(f"  no change, return_date stays {got.get('return_date')}  OK")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL REVISION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())