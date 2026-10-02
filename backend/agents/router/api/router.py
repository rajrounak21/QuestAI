from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.agents.router.services.catalog import AGENTS, ASSISTANT, DESTINATIONS
from backend.agents.router.services.intent import classify_intent
from backend.auth.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


class RouteIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class RouteOut(BaseModel):
    agent: str
    reason: str = ""
    confidence: float = 0.0
    fields: dict = {}
    # None for the Assistant: the Home page renders its reply inline instead of
    # navigating, so there is no path to send the user to.
    path: str | None = None


@router.post("/route", response_model=RouteOut)
def route(body: RouteIn, user: dict = Depends(get_current_user)) -> RouteOut:
    """Choose a specialist and pre-extract its form fields.

    Chooses only — it does not run anything. The caller navigates to `path` and
    the destination page pre-fills its form; the user still presses Search.
    """
    out = classify_intent(body.query)
    agent = out["agent"]
    if agent not in AGENTS:
        agent = ASSISTANT
    return RouteOut(
        agent=agent,
        reason=out.get("reason", ""),
        confidence=out.get("confidence", 0.0),
        fields=out.get("fields", {}),
        path=None if agent == ASSISTANT else DESTINATIONS.get(agent),
    )
