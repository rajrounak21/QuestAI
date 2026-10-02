import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.agents.travel.services.hotel_normalizer import normalize_hotels


def test_normalizer():
    raw_path = os.path.join(os.path.dirname(__file__), "raw_hotel_response.json")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    hotels = normalize_hotels(raw)

    print(f"Normalized {len(hotels)} hotels\n")

    for i, hotel in enumerate(hotels[:5], 1):
        print(f"--- Hotel {i} ---")
        print(f"  Name: {hotel.name}")
        print(f"  Rating: {hotel.rating} ({hotel.reviews} reviews)")
        print(f"  Stars: {hotel.hotel_class}")
        print(f"  Price: ${hotel.price_per_night}/night (${hotel.total_price} total)")
        print(f"  Images: {len(hotel.images)}")
        print(f"  Amenities: {hotel.amenities[:5]}")
        print(f"  Free cancel: {hotel.free_cancellation}")
        print(f"  Booking: {hotel.booking_link[:80]}")
        print()


if __name__ == "__main__":
    test_normalizer()
