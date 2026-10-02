"""Job alerts, persisted in Mongo.

Replaces the old in-memory dict. Alerts used to live in a module-level
`_alerts` dict, which meant a server restart silently deleted every alert and
wiped the `sent` history — so the same "Today"/"1 day ago" jobs were emailed
again on the next run.

One alert per user, enforced by a unique index on user_id (see
`ensure_job_indexes`). The public `alert_id` is assigned once at creation and
never changes, so an n8n workflow that already captured it keeps working after
the user edits their alert.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# How long a delivered job id stays in the `sent` history.
#
# Correctness argument: an alert only ever emails jobs whose freshness bucket is
# Today / "1 day ago" / "3 days ago" (see alert_service.FRESH_BUCKETS). A job
# older than that can never pass the freshness filter again, so remembering its
# id forever is pointless — the array would grow without bound while adding
# nothing. 7 days is a safety margin over the 3-day freshness window so a missed
# run (server down, SerpApi error) still suppresses re-sends.
SENT_HISTORY_DAYS = 7

# Fields the service layer may write. `sent`, `alert_id`, `created_at` and
# `last_run_at` are deliberately absent: resetting `sent` on edit would re-send
# every job the user has already been emailed.
#
# `next_run_at` is included because alert_service recomputes it when the schedule
# changes. It is not user-settable — AlertPatch has no such field, so a PATCH
# body cannot reach it; only the service sets it.
ALERT_EDITABLE_FIELDS = (
    "queries",
    "locations",
    "query",
    "location",
    "experience",
    "frequency",
    "time",
    "email",
    "is_active",
    "status",
    "next_run_at",
)


class DuplicateAlertError(Exception):
    """Raised when a user already has an alert — the product allows only one."""


class AlertNotFoundError(Exception):
    """Raised when the user has no alert to act on."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _col():
    from backend.database.collections import get_job_alerts_collection

    return get_job_alerts_collection()


def _sent_ids(sent: list[dict[str, Any]] | None) -> set[str]:
    """Ids of everything already emailed, tolerant of the old [str] shape."""
    out: set[str] = set()
    for entry in sent or []:
        if isinstance(entry, str):
            out.add(entry)
        elif isinstance(entry, dict) and entry.get("id"):
            out.add(str(entry["id"]))
    return out


def prune_sent(sent: list[dict[str, Any]] | None, now: datetime | None = None,
               days: int = SENT_HISTORY_DAYS) -> list[dict[str, Any]]:
    """Drop entries older than the retention window."""
    now = now or _utcnow()
    cutoff = now - timedelta(days=days)
    kept: list[dict[str, Any]] = []
    for entry in sent or []:
        if not isinstance(entry, dict):
            # Legacy plain-string entry with no timestamp: keep it rather than
            # risk re-sending, it will age out once rewritten by record_run.
            if isinstance(entry, str):
                kept.append({"id": entry, "seen_at": now})
            continue
        seen = entry.get("seen_at")
        if not isinstance(seen, datetime):
            kept.append({**entry, "seen_at": now})
            continue
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if seen >= cutoff:
            kept.append(entry)
    return kept


def create_alert(user_id: str, doc: dict[str, Any]) -> dict[str, Any]:
    """Insert the user's single alert. Raises if one already exists."""
    if get_alert(user_id) is not None:
        raise DuplicateAlertError("This account already has a job alert. Edit it instead.")
    doc = {**doc, "user_id": user_id, "sent": [], "last_run_at": None,
           "created_at": _utcnow()}
    _col().insert_one(doc)
    return doc


def get_alert(user_id: str) -> dict[str, Any] | None:
    return _col().find_one({"user_id": user_id})


def get_alert_by_id(alert_id: str) -> dict[str, Any] | None:
    return _col().find_one({"alert_id": alert_id})


def update_alert(user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a PATCH. Only ALERT_EDITABLE_FIELDS are writable."""
    allowed = {k: v for k, v in patch.items() if k in ALERT_EDITABLE_FIELDS}
    if not allowed:
        return get_alert(user_id)  # nothing editable in the request
    _col().update_one({"user_id": user_id}, {"$set": allowed})
    return get_alert(user_id)


def delete_alert(user_id: str) -> bool:
    return _col().delete_one({"user_id": user_id}).deleted_count > 0


def list_due_alerts(now: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Alerts whose next_run_at has arrived. Backs n8n's /due poll."""
    now = now or _utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cursor = _col().find({"is_active": True, "next_run_at": {"$ne": None, "$lte": now}})
    out: list[dict[str, Any]] = []
    for doc in cursor.limit(limit):
        # next_run_at is stored IST-aware; normalize to UTC for the comparison
        # Mongo already did, but keep the returned value unambiguous.
        out.append(doc)
    return out


def record_run(
    user_id: str,
    new_ids: list[str],
    last_run_at: datetime,
    next_run_at: datetime,
) -> list[dict[str, Any]]:
    """Append delivered ids, prune old ones, bump the run clock. Returns `sent`."""
    doc = get_alert(user_id)
    if not doc:
        return []
    seen = _sent_ids(doc.get("sent"))
    now = last_run_at if last_run_at.tzinfo else last_run_at.replace(tzinfo=timezone.utc)
    entries: list[dict[str, Any]] = [
        e for e in (doc.get("sent") or []) if isinstance(e, dict) and e.get("id")
    ]
    for job_id in new_ids:
        if not job_id:
            continue
        key = str(job_id)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"id": key, "seen_at": now})
    entries = prune_sent(entries, now=now)
    _col().update_one(
        {"user_id": user_id},
        {"$set": {"sent": entries, "last_run_at": last_run_at, "next_run_at": next_run_at}},
    )
    return entries


def count_all() -> int:
    return _col().count_documents({})
