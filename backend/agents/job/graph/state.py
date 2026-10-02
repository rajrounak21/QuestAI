from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class JobState(TypedDict):
    user_id: str | None
    user_query: str | None
    resume_bytes: bytes | None
    resume_profile: dict[str, Any] | None
    resume_text: str | None
    query_profile: dict[str, Any] | None
    profile: dict[str, Any] | None
    search_requests: list[dict[str, Any]] | None
    jobs_raw: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    total_results: int
    error: str | None
    follow_up_question: str | None
    search_complete: bool
    progress_steps: Annotated[list[str], operator.add]
