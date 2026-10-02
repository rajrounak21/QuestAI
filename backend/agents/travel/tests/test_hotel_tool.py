import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.agents.travel.schemas.hotel import HotelSearchRequest
from backend.agents.travel.tools.google_hotels import google_hotels_search


def test_raw_response():
    request = HotelSearchRequest(
        location="Dubai Hotels",
        check_in="2026-10-15",
        check_out="2026-10-20",
        guests=2,
        currency="USD",
    )

    raw = google_hotels_search(request)

    output_path = os.path.join(os.path.dirname(__file__), "raw_hotel_response.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

    print(f"Raw response saved to {output_path}")
    print(f"Keys: {list(raw.keys())}")
    properties = raw.get("properties", [])
    print(f"Properties: {len(properties)}")

    if properties:
        first = properties[0]
        print(f"\nFirst property keys: {list(first.keys())}")
        print(f"Name: {first.get('name')}")
        print(f"Rating: {first.get('overall_rating')}")
        print(f"Reviews: {first.get('reviews')}")
        print(f"Rate per night: {first.get('rate_per_night')}")
        print(f"Total rate: {first.get('total_rate')}")
        print(f"Hotel class: {first.get('hotel_class')}")
        print(f"Amenities: {first.get('amenities', [])[:5]}")
        print(f"Images: {len(first.get('images', []))}")
        print(f"Link: {first.get('link', '')[:80]}")
        print(f"Free cancellation: {first.get('free_cancellation')}")


if __name__ == "__main__":
    test_raw_response()
