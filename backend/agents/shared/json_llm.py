"""Single entry point for LLM calls whose output must be JSON.

Why this exists: extraction and classification used to run on a *reasoning*
model (gpt-oss) with a tight max_tokens. Groq counts reasoning tokens against
max_tokens, so a reasoning model can spend 750-1000 tokens reasoning and leave
nothing for the JSON itself. Measured on the real trip-extraction prompt with
max_tokens=1024: 1 of 5 responses parsed. The rest were cut off mid-string and
surfaced to the user as "I couldn't understand your trip request" - advice that
was wrong, because the message was fine and the budget was not.

This module uses the non-reasoning model for those calls, so the entire budget
goes to the answer, and it treats a truncated response as a budget problem
rather than a user-input problem.

Reasoning models are still used where reasoning earns its cost (synthesis,
critique, gap analysis). Only the parse-a-structured-answer calls move here.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

from backend.agents.research.services.llm import MODEL_JSON, RateLimitedChatGroq

load_dotenv(override=True)

logger = logging.getLogger(__name__)

_CALL_TIMEOUT = 25.0


class JsonCallFailed(Exception):
    """The model did not return parseable JSON.

    `truncated` distinguishes "we ran out of budget mid-answer" (retry may help,
    and the user's message was fine) from a genuinely unparseable reply.
    """

    def __init__(self, message: str, *, truncated: bool = False, raw: str = "") -> None:
        super().__init__(message)
        self.truncated = truncated
        self.raw = raw


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def strip_fences(text: str) -> str:
    return _FENCE.sub("", (text or "").strip()).strip()


def loads_lenient(text: str) -> dict[str, Any]:
    """Parse JSON, tolerating fences and a trailing sentence after the object.

    Models occasionally append a note after the JSON. That is not a reason to
    discard an otherwise complete answer.
    """
    candidate = strip_fences(text)
    if not candidate:
        raise ValueError("empty response")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(candidate[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _finish_reason(response: Any) -> str:
    meta = getattr(response, "response_metadata", None) or {}
    return str(meta.get("finish_reason") or "")


def invoke_json(
    prompt: str,
    *,
    max_tokens: int = 800,
    agent: str = "unknown",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one JSON-producing LLM call. Returns (parsed, meta).

    meta carries: engine, tokens used, whether the first answer was truncated,
    and whether a larger retry succeeded. A caller that needs to tell "our
    budget was too small" apart from "the model genuinely had nothing useful"
    should read meta["truncated"].

    Raises JsonCallFailed when no attempt produced JSON.
    """
    budget = max(128, int(max_tokens))
    attempts: list[dict[str, Any]] = []
    first_truncated = False

    for attempt in range(2):
        llm = RateLimitedChatGroq(
            model=MODEL_JSON,
            temperature=0.0,
            max_tokens=budget,
            request_timeout=_CALL_TIMEOUT,
            api_key=os.getenv("GROQ_API_KEY"),
        )
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        reason = _finish_reason(response)
        truncated = reason == "length"
        if attempt == 0:
            first_truncated = truncated

        try:
            parsed = loads_lenient(text)
        except Exception as exc:
            attempts.append({"budget": budget, "reason": reason, "error": str(exc)[:120]})
            logger.warning(
                "JSON call unparseable (agent=%s, budget=%s, finish=%s): %s",
                agent, budget, reason or "?", exc,
            )
            # Cut off mid-answer: a bigger budget is the actual fix.
            budget = budget * 2
            continue

        usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
        return parsed, {
            "agent": agent,
            "model": MODEL_JSON,
            "tokens": usage.get("completion_tokens"),
            "budget": budget,
            "truncated": first_truncated,
            "retried": attempt > 0,
            "attempts": attempts,
        }

    raise JsonCallFailed(
        "model did not return parseable JSON",
        truncated=first_truncated,
        raw=attempts[-1].get("error", "") if attempts else "",
    )