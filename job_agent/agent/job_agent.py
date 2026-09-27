from __future__ import annotations

from typing import Any

from job_agent.agent.job_graph import get_job_graph


def run_job_search(
    user_query: str | None = None,
    resume_bytes: bytes | None = None,
    extra_locations: list[str] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Runner for Job Agent. Handles query/resume/both. extra_locations for follow-up."""
    initial_state: dict[str, Any] = {
        "user_query": user_query or "",
        "resume_bytes": resume_bytes,
        "session_id": session_id,
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

    # If user answered follow-up with locations, inject into query for profile builder
    # We'll handle by appending to user_query if extra_locations given and no location in profile yet
    # Simpler: pass as part of state via user_query augmentation
    if extra_locations:
        loc_str = ", ".join(extra_locations)
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
