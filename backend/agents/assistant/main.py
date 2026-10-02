"""The Assistant: a short, stateless conversational reply.

Why this exists: a greeting used to fall into the research agent's "direct"
route, which stuffed the answer into `executive_summary` and rendered it as a
full "# Research Report". The logic was fine, the presentation was not. That
one LLM call now lives here and is rendered as plain text.

Stateless on purpose — no session, no Mongo, no graph. One prompt in, one
reply out.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.router.services.catalog import agent_catalog
from backend.agents.research.services.llm import init_llm, invoke_with_timeout

logger = logging.getLogger(__name__)

# 15s instead of the shared 30s default: this is a single short reply and the
# user is watching a disabled button, so a slow call is worse than a fallback.
REPLY_TIMEOUT = 15.0
MAX_TOKENS = 220

# Hard ceiling on what reaches the chat bubble. The prompt asks for 1-4
# sentences but the model is a reasoning model and drifts long, so the size is
# enforced here too. First N sentences, then clipped to MAX_CHARS.
MAX_SENTENCES = 4
MAX_CHARS = 320

SYSTEM_PROMPT = f"""You are the Assistant for QuestAI, a multi-agent workspace. You are a chat bubble, not an assistant that does work.

THE ONLY THINGS YOU CAN DO:
{agent_catalog()}

You have no tools, no search, no data, and no memory. You cannot look anything up.

ABSOLUTE RULES — breaking any of these is a failure:
1. Reply in 1 to 4 short sentences. Never more. No lists, no tables, no headings, no numbered steps.
2. No markdown at all: no **, no #, no -, no |, no backticks, no emoji.
3. Never describe yourself as a general-purpose assistant and never claim a capability that is not in the list above. If asked "what can you do", describe the specialists in plain words, then stop.
4. If the user describes a real task, do NOT attempt it. Reply in one sentence naming the specialist that will handle it, e.g. "That is Flights territory, I will take you there."
5. If you are unsure what they want, ask one short question.
6. Plain text only. One paragraph. No formatting of any kind."""

FALLBACK = (
    "I'm having trouble reaching my language model right now. "
    "You can still pick a specialist from the pills above, or try again in a moment."
)


def answer(text: str) -> dict[str, Any]:
    """One conversational turn. Never raises — returns a fallback on failure."""
    text = (text or "").strip()
    if not text:
        return {"reply": "Ask me anything — or pick a specialist from the pills above."}

    try:
        llm = init_llm(temperature=0.3, max_tokens=MAX_TOKENS)
        raw = invoke_with_timeout(
            llm,
            # The system prompt MUST go as a real system message. Inlining it in
            # the human turn is what let the model ignore every rule and invent
            # its own capabilities.
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=text)],
            timeout=REPLY_TIMEOUT,
        )
        reply = raw.content if hasattr(raw, "content") else str(raw)
        reply = _clean_reply(reply)
        if not reply:
            logger.warning("Assistant returned an empty reply")
            return {"reply": FALLBACK}
        return {"reply": reply}
    except Exception as exc:  # noqa: BLE001 - a chat bubble must never 500
        logger.warning("Assistant reply failed: %s", exc)
        return {"reply": FALLBACK}


def _clean_reply(raw: str) -> str:
    """Force a model reply into one short plain paragraph.

    The prompt asks for this, but a reasoning model still drifts into markdown
    tables and bullet lists. The chat bubble must never show that, so the size
    and shape are enforced here rather than trusted.
    """
    text = raw or ""
    # Drop any reasoning preamble some models prepend before the answer.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]

    # Markdown tables: keep only the first cell of each row, then drop rules.
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"[\s|:\-]+", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
            line = cells[0] if cells else ""
        lines.append(line)
    text = " ".join(lines)

    # Inline markers.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)
    # Leading list bullets on the joined text.
    text = re.sub(r"(?:^|\s)[-*•]\s+", " ", text)
    # Emoji / decoration the model adds despite instructions.
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]", "", text)
    # Whitespace tidy-up.
    text = re.sub(r"\s+", " ", text).strip()

    # Size ceiling: N sentences, then a hard character clip.
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    if len(parts) > MAX_SENTENCES:
        text = " ".join(parts[:MAX_SENTENCES])
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        dot = cut.rfind(".")
        text = (cut[: dot + 1] if dot > MAX_CHARS // 2 else cut).rstrip() + "…"
    # max_tokens can cut the model off mid-sentence; show that it was cut
    # rather than leaving a dangling comma in the bubble.
    if text and text[-1] not in ".!?…":
        text = text.rstrip(",;:- ") + "…"
    return text
