import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from backend.agents.travel.agent.hotel_agent import run_hotel_search


def test_agent():
    query = "Find hotels in Dubai for October 15-20 for 2 people"
    print(f"Query: {query}\n")

    result = run_hotel_search(query)

    print("Progress steps:")
    for step in result["progress_steps"]:
        print(f"  - {step}")

    if result["error"]:
        print(f"\nError: {result['error']}")
        return

    if result["follow_up_question"]:
        print(f"\nFollow-up: {result['follow_up_question']}")
        return

    print(f"\nExtracted params: {json.dumps(result['extracted_params'], indent=2)}")
    print(f"\nTotal hotels: {result['total_results']}")

    for i, hotel in enumerate(result["hotels"][:5], 1):
        print(f"\n--- Hotel {i} ---")
        print(f"  {hotel['name']}")
        print(f"  Rating: {hotel.get('rating')} ({hotel.get('reviews')} reviews)")
        print(f"  Stars: {hotel.get('hotel_class')}")
        print(f"  ${hotel['price_per_night']}/night (${hotel['total_price']} total)")
        print(f"  Amenities: {hotel.get('amenities', [])[:3]}")


if __name__ == "__main__":
    test_agent()
