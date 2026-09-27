import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from travel_agent.services.flight_normalizer import normalize_flights  # noqa: E402


def test_normalizer():
    raw_path = os.path.join(os.path.dirname(__file__), "raw_response.json")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    flights = normalize_flights(raw, booking_link=raw.get("search_metadata", {}).get("google_flights_url", ""))

    print(f"Normalized {len(flights)} flights\n")

    for i, flight in enumerate(flights[:5], 1):
        print(f"--- Flight {i} ---")
        print(f"  Airline: {flight.airline}")
        print(f"  Flight #: {flight.flight_number}")
        print(f"  Logo: {flight.airline_logo}")
        print(f"  From: {flight.departure.airport} at {flight.departure.time}")
        print(f"  To: {flight.arrival.airport} at {flight.arrival.time}")
        print(f"  Duration: {flight.duration_display}")
        print(f"  Stops: {flight.stops}")
        if flight.stop_details:
            for stop in flight.stop_details:
                print(f"    Layover: {stop.airport} ({stop.duration})")
        print(f"  Price: {flight.currency} {flight.price}")
        print(f"  Segments: {len(flight.segments)}")
        print(f"  Booking: {flight.booking_link[:80]}...")
        print()


if __name__ == "__main__":
    test_normalizer()
