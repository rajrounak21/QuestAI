# Per-stage progress for the 202+poll UX.
# The API worker sets a (user_id, session_id) target before graph.invoke();
# nodes call report() and it lands in Mongo, where the frontend poll picks it up.
# Outside a worker run (CLI, tests) report() is a silent no-op.
from __future__ import annotations

from contextvars import ContextVar

_current: ContextVar[dict | None] = ContextVar("research_progress", default=None)


def set_target(user_id: str, session_id: str):
    return _current.set({"user_id": user_id, "session_id": session_id})


def clear_target(token) -> None:
    _current.reset(token)


def report(stage: str, detail: str = "") -> None:
    target = _current.get()
    if not target:
        return
    try:
        from backend.database.research_sessions import set_progress

        set_progress(target["user_id"], target["session_id"], stage, detail)
    except Exception:
        pass
