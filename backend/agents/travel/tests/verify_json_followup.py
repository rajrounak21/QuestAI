"""Verify trip follow-up extraction no longer gets truncated.

Run:  .venv\\Scripts\\python.exe -m backend.agents.travel.tests.verify_json_followup

Costs a few Groq calls, no SerpApi.

Background this guards: extraction ran on gpt-oss (a reasoning model) with
max_tokens=1024. Groq counts reasoning tokens against max_tokens, so the model
spent 750-1000 tokens reasoning and the JSON was cut off mid-string. Measured
1 of 5 responses parsed. The failure was then reported to the user as "I
couldn't understand your trip request. Please try rephrasing" - advice that was
wrong, because their message was fine.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.agents.shared.json_llm import JsonCallFailed, invoke_json, loads_lenient  # noqa: E402
from backend.agents.travel.agent.nodes import IMPACT_PROMPT, TRIP_EXTRACT_PROMPT  # noqa: E402
from backend.database.trip_sessions import build_trip_context  # noqa: E402

TRIP = {
    "origin": "Mumbai", "destination": "Bali", "departure_date": "2026-10-02",
    "return_date": "2026-10-07", "duration_days": 5, "travelers": 2,
    "budget": {"currency": "USD", "max_total": 2000},
    "flight_preferences": {}, "hotel_preferences": {}, "interests": ["beach"],
}

FOLLOW_UPS = [
    "make it 7 days",
    "make the budget 2000",
    "change dates to 2026-10-20",
    "nonstop flights please",
    "make it cheaper",
]


def main() -> int:
    from datetime import date as _d

    today = _d.today().strftime("%Y-%m-%d")
    cur = build_trip_context(TRIP)
    import json as _json

    cur_text = _json.dumps(cur, ensure_ascii=False)
    failures: list[str] = []

    print("=== 1. lenient parser tolerates fences and trailing prose ===")
    for label, raw in [
        ("fenced", '```json\n{"a":1}\n```'),
        ("trailing prose", '{"a":1}  Hope that helps!'),
        ("plain", '{"a":1}'),
    ]:
        try:
            got = loads_lenient(raw)
            assert got == {"a": 1}, got
            print(f"  {label:15} OK")
        except Exception as e:
            failures.append(f"lenient parser failed on {label}: {e}")
    try:
        loads_lenient("not json at all")
        failures.append("lenient parser accepted garbage")
    except Exception:
        print(f"  {'rejects garbage':15} OK")

    print("\n=== 2. every follow-up parses, repeatedly ===")
    for msg in FOLLOW_UPS:
        prompt = TRIP_EXTRACT_PROMPT.format(
            query="Current trip (JSON): " + cur_text + "\nUser message: " + msg,
            today=today,
        )
        ok = 0
        tokens = []
        for _ in range(3):
            try:
                parsed, meta = invoke_json(prompt, max_tokens=1024, agent="verify")
                ok += 1
                tokens.append(meta.get("tokens"))
            except JsonCallFailed as e:
                if e.truncated:
                    failures.append(f"{msg!r} still truncated after retry")
        print(f"  {msg:26} {ok}/3  tokens={tokens}")
        if ok < 3:
            failures.append(f"{msg!r} only parsed {ok}/3")

    print("\n=== 3. a follow-up yields the right final values ===")
    prompt = TRIP_EXTRACT_PROMPT.format(
        query="Current trip (JSON): " + cur_text + "\nUser message: make it 7 days",
        today=today,
    )
    parsed, meta = invoke_json(prompt, max_tokens=1024, agent="verify")
    if parsed.get("intent") != "follow_up":
        failures.append(f"intent is {parsed.get('intent')!r}, expected follow_up")
    else:
        print(f"  intent = follow_up  OK")
    if parsed.get("duration_days") != 7:
        failures.append(f"duration_days is {parsed.get('duration_days')!r}, expected 7")
    else:
        print(f"  duration_days = 7 (5 + 2)  OK")

    print("\n=== 4. detect_impact parses on the same follow-up ===")
    for msg in ("make it 7 days", "make the budget 2000"):
        ip = IMPACT_PROMPT.format(current_state=cur_text, change_request=msg, query=msg)
        try:
            impact, m2 = invoke_json(ip, max_tokens=1024, agent="verify-impact")
            print(f"  {msg:24} changes={list((impact.get('changes') or {}).keys())}  OK")
        except JsonCallFailed as e:
            failures.append(f"impact failed for {msg!r} (truncated={e.truncated})")

    print("\n=== 5. a truncated answer is reported as OUR problem ===")
    big = TRIP_EXTRACT_PROMPT.format(
        query="Current trip (JSON): " + cur_text + "\nUser message: make it 7 days",
        today=today,
    )
    try:
        _, m3 = invoke_json(big, max_tokens=160, agent="verify-trunc")
        if m3.get("truncated") or m3.get("retried"):
            print(f"  retried={m3.get('retried')} truncated={m3.get('truncated')}  OK")
        else:
            print("  budget was sufficient, no retry needed  OK")
    except JsonCallFailed as e:
        if e.truncated:
            print(f"  reported truncated=True even when unrecoverable  OK")
        else:
            failures.append(f"unrecoverable failure not flagged as truncated: {e}")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL FOLLOW-UP JSON CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())