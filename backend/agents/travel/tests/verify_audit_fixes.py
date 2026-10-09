"""Verify the audit follow-ups: preview currency, validation node, no dead import.

Run:  .venv\\Scripts\\python.exe -m backend.agents.travel.tests.verify_audit_fixes

Costs a few Groq calls, no SerpApi.
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backend.agents.shared.json_llm import JsonCallFailed, invoke_json  # noqa: E402
from backend.agents.travel.agent.nodes import VALIDATE_TRIP_PROMPT  # noqa: E402
from backend.agents.travel.agent.trip_graph import (  # noqa: E402
    _merge_for_preview,
    _preview_summary,
)

NEW_TRIP = (
    "5-day trip from Mumbai to Bali departing 2026-12-10 for 2 people, "
    "budget 2000 dollars"
)


def main() -> int:
    failures: list[str] = []

    print("=== 1. the confirm line no longer says $ for a non-dollar budget ===")
    for cur, want in (("INR", "2000 INR"), ("EUR", "2000 EUR"), ("USD", "2000 USD")):
        line = _preview_summary({"origin": "Mumbai", "destination": "Bali",
                                 "budget": {"max_total": 2000, "currency": cur}})
        if want not in line:
            failures.append(f"{cur}: {line!r} missing {want!r}")
        elif "$" in line:
            failures.append(f"{cur}: still contains a hardcoded $")
        else:
            print(f"  {want:10} shown correctly  OK")
    bare = _preview_summary({"origin": "Mumbai", "destination": "Bali",
                             "budget": {"max_total": 2000}})
    if "2000 USD" not in bare:
        failures.append(f"missing currency fell back badly: {bare!r}")
    else:
        print("  2000 USD    falls back safely  OK")

    print("\n=== 2. the preview currency matches what searches will use ===")
    stored = {"origin": "Mumbai", "destination": "Bali", "duration_days": 5,
              "travelers": 2, "budget": {"max_total": 2000, "currency": ""}}
    got = (_merge_for_preview({"duration_days": 7}, stored, {}) or {}).get("budget") or {}
    if got.get("currency") != "INR":
        failures.append(f"unset currency did not resolve from origin: {got.get('currency')!r}")
    else:
        print("  stored empty -> INR (origin)  OK")
    got2 = (_merge_for_preview({"budget": {"currency": "EUR"}}, stored, {}) or {}).get("budget") or {}
    if got2.get("currency") != "EUR":
        failures.append(f"explicit currency ignored: {got2.get('currency')!r}")
    else:
        print("  explicit EUR respected  OK")

    print("\n=== 3. new-trip validation parses on the non-reasoning model ===")
    prompt = VALIDATE_TRIP_PROMPT.format(
        extracted_params=json.dumps(
            {"origin": "Mumbai", "destination": "Bali",
             "departure_date": "2026-12-10", "duration_days": 5, "travelers": 2},
            indent=2,
        ),
        today=date.today().strftime("%Y-%m-%d"),
        user_query=NEW_TRIP,
    )
    ok = 0
    tokens = []
    for _ in range(3):
        try:
            parsed, meta = invoke_json(prompt, max_tokens=1024, agent="verify-validate")
            ok += 1
            tokens.append(meta.get("tokens"))
            if "is_complete" not in parsed:
                failures.append("parsed but no is_complete key")
        except JsonCallFailed as e:
            failures.append(f"validation still unparseable (truncated={e.truncated})")
    if ok == 3:
        print(f"  3/3 parsed, tokens={tokens}  OK")

    print("\n=== 4. no dead import left behind ===")
    from backend.agents.travel.agent import trip_graph

    src = open(trip_graph.__file__, encoding="utf-8").read()
    if src.count("_parse_json") == 0:
        print("  _parse_json import removed  OK")
    else:
        failures.append(f"_parse_json still referenced {src.count('_parse_json')}x")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL AUDIT FIX CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())