# Per-stage progress for the 202+poll UX.
# The API worker sets a (user_id, session_id) target before graph.invoke();
# nodes call report() and it lands in Mongo, where the frontend poll picks it up.
# Outside a worker run (CLI, tests) report() is a silent no-op.
from __future__ import annotations

from contextvars import ContextVar

class ResearchCancelledError(Exception):
    """Raised when user cancels research session while thread is executing."""
    pass


_current: ContextVar[dict | None] = ContextVar("research_progress", default=None)


def set_target(user_id: str, session_id: str):
    return _current.set({"user_id": user_id, "session_id": session_id})


def clear_target(token) -> None:
    _current.reset(token)


def check_cancellation() -> None:
    target = _current.get()
    if not target:
        return
    try:
        from backend.database.collections import get_research_collection
        col = get_research_collection()
        doc = col.find_one({"user_id": target["user_id"], "session_id": target["session_id"]}, {"status": 1})
        if not doc or doc.get("status") == "cancelled":
            raise ResearchCancelledError("Research cancelled or deleted by user")
    except ResearchCancelledError:
        raise
    except Exception:
        pass


def report(stage: str, detail: str = "") -> None:
    check_cancellation()
    target = _current.get()
    if not target:
        return
    try:
        from backend.database.research_sessions import set_progress

        set_progress(target["user_id"], target["session_id"], stage, detail)
    except ResearchCancelledError:
        raise
    except Exception:
        pass

