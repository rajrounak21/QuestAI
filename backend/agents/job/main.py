from __future__ import annotations

from typing import Any

from backend.agents.job.graph.graph import get_job_graph


def run_job_search(
    user_id: str | None = None,
    user_query: str | None = None,
    locations: list[str] | None = None,
    resume_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Runner for the Job Agent.

    Skills come from three places, in priority order:
      1. `resume_bytes` — a fresh upload (first visit / onboarding).
      2. The user's stored profile in Mongo — read by `resume_vision_parser`
         via `user_id`. This is why the resume is only uploaded once.
      3. Nothing — search still runs, but with 0% skill matching.
    """
    initial_state: dict[str, Any] = {
        "user_id": user_id,
        "user_query": user_query or "",
        "resume_bytes": resume_bytes,
        "resume_profile": None,
        "resume_text": None,
        "query_profile": None,
        "profile": None,
        "search_requests": None,
        "jobs_raw": [],
        "jobs": [],
        "total_results": 0,
        "error": None,
        "follow_up_question": None,
        "search_complete": False,
        "progress_steps": [],
    }

    # Follow-up answers arrive as a locations list; fold them into the query
    # string so the deterministic query parser can pick them up.
    if locations:
        loc_str = ", ".join(locations)
        if initial_state["user_query"]:
            initial_state["user_query"] = f"{initial_state['user_query']} in {loc_str}"
        else:
            initial_state["user_query"] = f"jobs in {loc_str}"

    graph = get_job_graph()
    result = graph.invoke(initial_state)

    return {
        "profile": result.get("profile"),
        "jobs": result.get("jobs", []),
        "total_results": result.get("total_results", 0),
        "error": result.get("error"),
        "follow_up_question": result.get("follow_up_question"),
        "search_requests": result.get("search_requests"),
        "progress_steps": result.get("progress_steps", []),
        "search_complete": result.get("search_complete", False),
        "resume_text": result.get("resume_text"),
    }
