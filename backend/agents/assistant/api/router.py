from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.agents.assistant.main import answer
from backend.auth.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ChatOut(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user: dict = Depends(get_current_user)) -> ChatOut:
    """Stateless conversational turn. Synchronous on purpose.

    A single short LLM call, so a 202 + polling contract would only add a
    round trip and a spinner. Declared as `def` (not `async def`) so FastAPI
    runs it in its threadpool and the event loop is never blocked.
    """
    result = answer(body.text)
    return ChatOut(reply=result["reply"])
