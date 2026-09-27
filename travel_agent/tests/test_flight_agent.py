import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from travel_agent.agent.flight_agent import run_flight_search  # noqa: E402


def test_agent():
    query = "Find me flights from Delhi to Dubai on October 15"
    print(f"Query: {query}\n")

    result = run_flight_search(query)

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
    print(f"\nTotal flights: {result['total_results']}")

    for i, flight in enumerate(result["flights"][:3], 1):
        print(f"\n--- Flight {i} ---")
        print(f"  {flight['airline']} {flight['flight_number']}")
        print(f"  {flight['departure']['airport']} → {flight['arrival']['airport']}")
        print(f"  {flight['departure']['time']} → {flight['arrival']['time']}")
        print(f"  {flight['duration_display']} | {flight['stops']} stops")
        print(f"  {flight['currency']} {flight['price']}")


if __name__ == "__main__":
    test_agent()
