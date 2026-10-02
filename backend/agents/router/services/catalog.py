"""Shared description of every specialist, plus the conversational Assistant.

Kept in one place because both the intent classifier and the Assistant's system
prompt need to agree on exactly what agents exist. If a specialist is added
here it becomes routable, and the Assistant can talk about it, in one edit.
"""

from __future__ import annotations

# The six task specialists. "assistant" is deliberately last: it is the
# conversational fallback, never the first choice.
TASK_AGENTS = (
    "research",
    "shopping",
    "jobs",
    "flights",
    "hotels",
    "trips",
)

ASSISTANT = "assistant"

AGENTS = TASK_AGENTS + (ASSISTANT,)

# Where the frontend should send the user for each specialist. "assistant" has
# no destination on purpose: the Home page renders its reply inline instead of
# navigating anywhere.
DESTINATIONS: dict[str, str] = {
    "research": "/research",
    "shopping": "/shopping",
    "jobs": "/jobs",
    "flights": "/flights",
    "hotels": "/hotels",
    "trips": "/trips",
}

# One line per specialist, used verbatim in the Assistant's system prompt so it
# can answer "what can you do?" without inventing anything.
AGENT_DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("Research", "look something up on the web and answer with cited sources, comparisons and evidence."),
    ("Shopping", "find and compare products, prices and stores."),
    ("Jobs", "search job openings that match your resume, and set up a recurring job alert."),
    ("Flights", "find flight options between two cities."),
    ("Hotels", "find hotels in a destination for your dates."),
    ("Trips", "plan a whole trip end to end: flights, hotels and an itinerary."),
    ("Assistant", "answer casual questions, greetings, and help you work out what to ask for."),
)


def agent_catalog() -> str:
    """Human-readable catalog for prompts."""
    return "\n".join(f"- {name}: {desc}" for name, desc in AGENT_DESCRIPTIONS)
