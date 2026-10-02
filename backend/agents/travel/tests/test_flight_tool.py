import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.agents.travel.schemas.flight import FlightSearchRequest, TripType  # noqa: E402
from backend.agents.travel.tools.google_flights import google_flights_search  # noqa: E402


def test_raw_response():
    request = FlightSearchRequest(
        origin="DEL",
        destination="DXB",
        departure_date="2026-10-15",
        trip_type=TripType.ONE_WAY,
        passengers=1,
        currency="USD",
    )

    raw = google_flights_search(request)

    output_path = os.path.join(os.path.dirname(__file__), "raw_response.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

    print(f"Raw response saved to {output_path}")
    print(f"Keys: {list(raw.keys())}")
    print(f"Best flights: {len(raw.get('best_flights', []))}")
    print(f"Other flights: {len(raw.get('other_flights', []))}")

    if raw.get("best_flights"):
        first = raw["best_flights"][0]
        print(f"\nFirst best flight keys: {list(first.keys())}")
        if first.get("flights"):
            seg = first["flights"][0]
            print(f"First segment keys: {list(seg.keys())}")
            print(f"Segment sample: {json.dumps(seg, indent=2)[:1000]}")


if __name__ == "__main__":
    test_raw_response()
