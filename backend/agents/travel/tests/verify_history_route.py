"""Live: what the trip history endpoint now returns, and whether the cards are
actually distinguishable.

Run:  .venv\\Scripts\\python.exe -m backend.agents.travel.tests.verify_history_route
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.auth.database import get_users_collection
from backend.auth.security import create_access_token

BASE = "http://127.0.0.1:8000"
email = get_users_collection().find_one({})["email"]
req = urllib.request.Request(
    f"{BASE}/api/trips/history?limit=20",
    headers={"Authorization": f"Bearer {create_access_token(email)}"},
)
with urllib.request.urlopen(req, timeout=30) as r:
    items = json.loads(r.read())["items"]

print(f"GET /api/trips/history -> {len(items)} trips\n")
ok = True
for it in items:
    print(f"  title      : {it.get('title')}")
    print(f"  origin     : {it.get('origin')!r} -> {it.get('destination')!r}")
    print(f"  dates      : {it.get('departure_date')} -> {it.get('return_date')}")
    print(f"  days/pax   : {it.get('duration_days')}d / {it.get('travelers')}")
    print(f"  budget     : {(it.get('budget') or {}).get('max_total')} {(it.get('budget') or {}).get('currency')}")
    raw = it.get("trip") or {}
    print(f"  trip leaked: {sorted(raw.keys()) if raw else '(none - good)'}")
    if "flight_results" in raw or "hotel_results" in raw or "itinerary" in raw:
        failures = "LEAKED HEAVY TRIP DATA"
        print(f"  FAIL: {failures}")
        ok = False
    print(f"  card shows  : [{it.get('origin_iata') or '...'}] -> [{it.get('destination_iata') or '...'}]")
    print()

titles = [it.get("title") for it in items]
print(f"titles: {titles}")

# Airport codes are what the card headlines, so every trip that has both ends
# must resolve them from the table.
for it in items:
    if it.get("origin") and it.get("destination"):
        if not it.get("origin_iata"):
            print(f"FAIL: no IATA for origin {it['origin']!r} ({it['session_id']})")
            ok = False
        if not it.get("destination_iata"):
            print(f"FAIL: no IATA for destination {it['destination']!r} ({it['session_id']})")
            ok = False

# Every trip must name its route, not a bare city.
for it in items:
    if it.get("origin") and it.get("destination"):
        if it.get("title") != f"{it['origin']} to {it['destination']}":
            print(f"FAIL: title is not the route for {it['session_id']}")
            ok = False

# Two trips can share a route, so the card needs more than the title to tell
# them apart. Check the disambiguating fields are present.
if len(items) >= 2 and titles[0] == titles[1]:
    twins = [a for a, b in zip(items, items[1:]) if a.get("title") == b.get("title")]
    for t in twins:
        disting = [t.get("travelers"), t.get("departure_date"), (t.get("budget") or {}).get("max_total")]
        print(f"  same route {t['title']!r} -> distinguished by {disting}")
        if not any(disting):
            print("  FAIL: nothing on the card tells these two trips apart")
            ok = False

payload = len(json.dumps(items))
print(f"\npayload for {len(items)} trips: {payload} bytes")
if payload > 20000:
    print("  FAIL: history payload is bloated")
    ok = False

print("\nHISTORY ROUTE CHECKS PASSED" if ok else "\nHISTORY ROUTE CHECKS FAILED")
sys.exit(0 if ok else 1)