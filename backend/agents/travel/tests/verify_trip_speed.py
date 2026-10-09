"""Verify the trip follow-up speed and honesty fixes.

Run:  .venv\\Scripts\\python.exe -m backend.agents.travel.tests.verify_trip_speed

Costs 0 SerpApi searches - every provider call is stubbed. Runs against a
throwaway user scope and cleans up after itself.

Background: a "make it 7 days" follow-up took 25-31s and, when the departure
date had already passed, burned two SerpApi calls that could only 400 while
still reporting "Your trip is ready!" over stale cards. These checks pin the
fixes for all of that.
"""

import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.agents.travel.agent import trip_graph  # noqa: E402
from backend.agents.travel.agent.trip_graph import (  # noqa: E402
    _past_date_field,
    dispatch_agents,
    synthesize_itinerary,
    trip_currency,
)
from backend.agents.travel.schemas.trip import TripSession  # noqa: E402

FUTURE = (date.today() + timedelta(days=30)).isoformat()
FUTURE_END = (date.today() + timedelta(days=35)).isoformat()
PAST = (date.today() - timedelta(days=3)).isoformat()


def trip(dep=FUTURE, ret=FUTURE_END, budget_currency="", origin="Mumbai"):
    s = TripSession(
        trip_id="speed-test",
        origin=origin,
        destination="Bali",
        departure_date=dep,
        return_date=ret,
        duration_days=5,
        travelers=2,
        budget={"currency": budget_currency, "max_total": 2000} if budget_currency
        else {"max_total": 2000},
    )
    return s.to_dict()


def state(trip_dict, affected):
    return {
        "trip_session": trip_dict,
        "user_query": "make it 7 days",
        "impact_analysis": {"affected_agents": affected, "changes": {}, "response": ""},
        "extracted_params": {"intent": "follow_up"},
    }


def main() -> int:
    failures: list[str] = []

    orig_flights = trip_graph.run_flight_search
    orig_hotels = trip_graph.run_hotel_search
    orig_bump = trip_graph._bump_searches
    trip_graph._bump_searches = lambda *a, **k: None

    try:
        print("=== 1. past departure date -> ask, never search ===")
        calls = []
        trip_graph.run_flight_search = lambda s: calls.append("flights") or {}
        trip_graph.run_hotel_search = lambda s: calls.append("hotels") or {}

        out = dispatch_agents(state(trip(dep=PAST), ["flights", "hotels"]))
        if calls:
            failures.append(f"searched anyway with a past date: {calls}")
        else:
            print("  0 provider calls spent  OK")
        qs = out.get("clarifying_questions") or []
        if not qs or qs[0].get("field") != "departure_date":
            failures.append(f"did not ask for a new departure date: {qs}")
        else:
            print(f"  asked: {qs[0]['question']!r}  OK")
        if "passed" not in (qs[0].get("why") or ""):
            failures.append("the reason does not explain the date already passed")
        else:
            print(f"  reason given  OK")
        if out.get("trip_session") is None:
            failures.append("the stored trip was dropped while asking")
        else:
            print("  stored trip kept intact  OK")

        print("\n=== 2. past return date is caught too ===")
        if _past_date_field(trip(dep=PAST, ret=PAST)) != "departure_date":
            failures.append("departure not detected as past")
        elif _past_date_field({"departure_date": FUTURE, "return_date": PAST}) != "return_date":
            failures.append("past return date not detected")
        elif _past_date_field(trip()) is not None:
            failures.append("a future trip was flagged as past")
        else:
            print("  departure, return, and the future case all correct  OK")

        print("\n=== 3. a failed sub-agent is reported, not swallowed ===")
        def boom_flight(s):
            calls.append("flights-real")
            raise RuntimeError("400 Bad Request for url: https://serpapi.com/search?api_key=SECRET")

        def ok_hotel(s):
            return {"hotel_results": [{"name": "H", "price_per_night": 90}]}

        trip_graph.run_flight_search = boom_flight
        trip_graph.run_hotel_search = ok_hotel
        out = dispatch_agents(state(trip(), ["flights", "hotels"]))
        warns = out.get("warnings") or []
        if not any("flights" in w for w in warns):
            failures.append(f"no warning surfaced for the failed search: {out}")
        else:
            print(f"  warning: {warns[0]}")
        if any("SECRET" in w or "api_key" in w for w in warns):
            failures.append("the provider API key leaked into a user-facing warning")
        else:
            print("  API key not leaked into the message  OK")
        if "reject" not in (warns[0] if warns else ""):
            failures.append("no human-readable reason given")
        else:
            print("  plain-language reason given  OK")
        if not out.get("hotel_results"):
            failures.append("the healthy sub-agent's result was lost")
        else:
            print("  the healthy sub-agent still returned results  OK")

        print("\n=== 4. flights and hotels run in parallel ===")
        def slow_flight(s):
            time.sleep(0.6)
            return {"flight_results": [{"flight_number": "AA1"}]}

        def slow_hotel(s):
            time.sleep(0.6)
            return {"hotel_results": [{"name": "H"}]}

        trip_graph.run_flight_search = slow_flight
        trip_graph.run_hotel_search = slow_hotel
        t0 = time.perf_counter()
        out = dispatch_agents(state(trip(), ["flights", "hotels"]))
        elapsed = time.perf_counter() - t0
        # Serial would be ~1.2s; parallel is ~0.6s.
        if elapsed >= 1.05:
            failures.append(f"dispatch looks serial ({elapsed:.2f}s for two 0.6s searches)")
        else:
            print(f"  two 0.6s searches in {elapsed:.2f}s (serial would be ~1.2s)  OK")
        if not out.get("flight_results") or not out.get("hotel_results"):
            failures.append("a parallel result was dropped")
        else:
            print("  both results collected  OK")

        print("\n=== 5. one currency for the whole trip ===")
        if trip_currency({"origin": "Mumbai", "budget": {}}) != "INR":
            failures.append("an unset currency did not fall back to the origin")
        elif trip_currency({"origin": "Mumbai", "budget": {"currency": "USD"}}) != "USD":
            failures.append("an explicitly stored USD budget was reinterpreted")
        elif trip_currency({"origin": "Mumbai", "budget": {"currency": "EUR"}}) != "EUR":
            failures.append("an explicitly chosen currency was ignored")
        elif trip_currency({"origin": "Atlantis", "budget": {}}) != "USD":
            failures.append("unknown origin with no currency did not fall back to USD")
        else:
            print("  unset -> origin, stored USD respected, EUR respected  OK")

        # The real sub-agents must pass that currency to the provider, not let
        # each one infer its own (flights used to say INR, hotels USD).
        import backend.agents.travel.tools.google_flights as gf
        import backend.agents.travel.tools.google_hotels as gh
        from backend.agents.travel.services import flight_normalizer, hotel_normalizer

        seen = {}
        # Test 4 replaced the real functions with sleeps - put them back first.
        trip_graph.run_flight_search = orig_flights
        trip_graph.run_hotel_search = orig_hotels
        orig_gf, orig_gh = gf.google_flights_search, gh.google_hotels_search
        orig_bsr = flight_normalizer.build_search_response
        orig_nh = hotel_normalizer.normalize_hotels

        def fake_gf(req):
            seen["flight_currency"] = req.currency
            seen["flight_dep"] = req.departure_date
            raise RuntimeError("stop here")

        def fake_gh(req):
            seen["hotel_currency"] = req.currency
            raise RuntimeError("stop here")

        gf.google_flights_search = fake_gf
        gh.google_hotels_search = fake_gh
        try:
            dispatch_agents(state(trip(), ["flights", "hotels"]))
        finally:
            gf.google_flights_search = orig_gf
            gh.google_hotels_search = orig_gh
            flight_normalizer.build_search_response = orig_bsr
            hotel_normalizer.normalize_hotels = orig_nh

        if seen.get("flight_currency") != "INR":
            failures.append(f"flight search currency was {seen.get('flight_currency')!r}")
        else:
            print("  flight search sent currency=INR  OK")
        if seen.get("hotel_currency") != "INR":
            failures.append(f"hotel search currency was {seen.get('hotel_currency')!r}")
        else:
            print("  hotel search sent currency=INR (was USD)  OK")
        if seen.get("flight_dep") != FUTURE:
            failures.append(f"flight departure was {seen.get('flight_dep')!r}")
        else:
            print("  departure date passed through unchanged  OK")

    finally:
        trip_graph.run_flight_search = orig_flights
        trip_graph.run_hotel_search = orig_hotels
        trip_graph._bump_searches = orig_bump

    print("\n=== 6. IATA codes: the flight 400 that removing the LLM caused ===")
    from backend.agents.travel.services.airports import resolve_iata

    iata_cases = [
        ("Mumbai", "BOM"), ("Bali", "DPS"), ("DEL", "DEL"),
        ("New York", "JFK"), ("San Francisco", "SFO"), ("London", "LHR"),
        ("Hong Kong", "HKG"), ("goa, india", "GOI"), ("goa", "GOI"),
        ("Dubai", "DXB"), ("Bali (Indonesia)", "DPS"), ("JFK, New York", "JFK"),
        ("Kuala Lumpur", "KUL"), ("Atlantis", None),
    ]
    wrong = [(p, resolve_iata(p), w) for p, w in iata_cases if resolve_iata(p) != w]
    if wrong:
        failures.append(f"IATA resolution wrong: {wrong}")
    else:
        print(f"  {len(iata_cases)} place names all correct  OK")
    # "New York" must be JFK, not NEW - a word inside the string is not a code.
    if resolve_iata("New York") == "NEW" or resolve_iata("San Francisco") == "SAN":
        failures.append("a word inside the place name was read as a code")
    else:
        print("  multi-word names not mistaken for codes  OK")

    print("\n=== 7. hotel results are dicts, and empty is not success ===")
    from backend.agents.travel.services.hotel_normalizer import normalize_hotels

    sample = normalize_hotels(
        {"properties": [{"name": "H", "link": "http://x",
                         "rate_per_night": {"extracted_lowest": 90}}]},
        "INR",
    )
    dumped = [h.model_dump() for h in sample]
    if not dumped or not isinstance(dumped[0], dict):
        failures.append("hotel results are not dicts - synthesize would crash")
    elif (sample[0].get("price_per_night") if isinstance(sample[0], dict) else None) is not None:
        failures.append("hotel dict missing price_per_night")
    else:
        print("  HotelResult -> dict conversion works  OK")

    trip_graph.run_flight_search = orig_flights
    trip_graph.run_hotel_search = orig_hotels
    trip_graph._bump_searches = lambda *a, **k: None
    import backend.agents.travel.tools.google_hotels as gh2

    def empty_hotels(req):
        return {"properties": []}

    orig_gh2 = gh2.google_hotels_search
    gh2.google_hotels_search = empty_hotels
    try:
        out = dispatch_agents(state(trip(), ["hotels"]))
    finally:
        gh2.google_hotels_search = orig_gh2
    if not any("No hotels" in w for w in (out.get("warnings") or [])):
        failures.append("an empty hotel result was treated as success")
    else:
        print(f"  warning: {(out.get('warnings') or [''])[0]}")
        print("  empty result reported instead of silently kept  OK")

    print("\n=== 8. the date question is a picker, and it cannot loop ===")
    # Free text produced answers like "10" that parsed to nothing, leaving the
    # stored date in the past and re-firing the same question forever.
    from datetime import date as _date

    def ask(convo=None):
        t = trip(dep=PAST)
        if convo is not None:
            t["conversation"] = convo
        out = dispatch_agents(state(t, ["flights", "hotels"]))
        return (out.get("clarifying_questions") or [{}])[0]

    first = ask()
    if first.get("inputType") != "date":
        failures.append(f"date question is not a picker: {first.get('inputType')!r}")
    else:
        print(f"  inputType=date  OK")
    if first.get("min") != _date.today().isoformat():
        failures.append(f"picker allows a past date: min={first.get('min')!r}")
    else:
        print(f"  min={first.get('min')} (today) blocks past dates  OK")
    if first.get("options"):
        failures.append("first ask should not jump straight to options")
    else:
        print("  first ask is a clean question  OK")

    again = ask([{"user": "departure_date: 10", "assistant": "What date?"}])
    if not again.get("options"):
        failures.append("loop breaker gave no clickable dates on the second ask")
    else:
        print(f"  second ask offers {len(again['options'])} dates  OK")
    if again["question"] == first["question"]:
        failures.append("the same open question is being repeated")
    else:
        print(f"  question changed: {again['question']!r}  OK")
    if again.get("inputType") != "date":
        failures.append("loop-breaker ask lost the date picker")

    st_clar = {
        "trip_session": trip(dep=PAST),
        "user_query": "make it 7 days",
        "clarifying_questions": [first],
        "message": first["question"],
        "extracted_params": {"intent": "follow_up"},
    }
    out_c = synthesize_itinerary(st_clar)
    passed_q = (out_c.get("clarifying_questions") or [{}])[0]
    if passed_q.get("inputType") != "date" or not passed_q.get("min"):
        failures.append(
            f"synthesize dropped the picker: {sorted(passed_q.keys())}"
        )
    else:
        print("  survives synthesize (picker reaches the user)  OK")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL TRIP SPEED/HONESTY CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())