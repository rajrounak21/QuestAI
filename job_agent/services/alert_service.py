from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from datetime import timezone

from job_agent.models.alert_models import Alert, AlertCreate

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    # Fallback for Windows without tzdata installed (UTC+5:30)
    IST = timezone(timedelta(hours=5, minutes=30))

# In-memory store — swap with MongoDB later (keep interface)
_alerts: dict[str, Alert] = {}

# Fresh buckets considered "fresh" for daily alerts
# Unknown / Older / 1 week ago are not fresh
FRESH_BUCKETS = {"Today", "1 day ago", "3 days ago"}


def _parse_time(time_str: str) -> tuple[int, int]:
    h, m = time_str.split(":")
    return int(h), int(m)


def _compute_next_run(frequency: str, time_str: str, from_dt: datetime | None = None) -> datetime:
    """Next run after from_dt (IST). Daily = next day at time if time passed, Weekly = +7 days."""
    now = from_dt or datetime.now(IST)
    # ensure IST aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    hour, minute = _parse_time(time_str)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        if frequency == "weekly":
            candidate = candidate + timedelta(days=7)
        else:
            candidate = candidate + timedelta(days=1)
    return candidate


def create_alert(data: AlertCreate) -> Alert:
    alert_id = f"alert_{uuid.uuid4().hex[:8]}"
    now = datetime.now(IST)
    next_run = _compute_next_run(data.frequency, data.time, now)
    # validate time hour/minute ranges
    h, m = _parse_time(data.time)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time, expected HH:MM 00:00-23:59")
    alert = Alert(
        id=alert_id,
        query=data.query.strip(),
        location=data.location.strip(),
        experience=data.experience.strip() if data.experience else None,
        frequency=data.frequency,
        time=data.time,
        email=data.email.strip(),
        created_at=now,
        last_run_at=None,
        next_run_at=next_run,
        sent_job_ids=[],
        is_active=True,
        status="active",
    )
    _alerts[alert_id] = alert
    logger.info(f"Alert created {alert_id} next_run={next_run.isoformat()}")
    return alert


def list_alerts() -> list[Alert]:
    return list(_alerts.values())


def get_alert(alert_id: str) -> Alert | None:
    return _alerts.get(alert_id)


def delete_alert(alert_id: str) -> bool:
    if alert_id in _alerts:
        del _alerts[alert_id]
        logger.info(f"Alert deleted {alert_id}")
        return True
    return False


def get_due_alerts(now: datetime | None = None) -> list[Alert]:
    """Due if active and now >= next_run_at. Uses IST."""
    current = now or datetime.now(IST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=IST)
    due: list[Alert] = []
    for alert in _alerts.values():
        if not alert.is_active:
            continue
        if alert.next_run_at is None:
            continue
        # Ensure next_run_at is IST aware
        nr = alert.next_run_at
        if nr.tzinfo is None:
            nr = nr.replace(tzinfo=IST)
        if current >= nr:
            due.append(alert)
    return due


def _filter_fresh_unique(alert: Alert, jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    """Return (new_jobs, filtered_fresh_count_excluded, filtered_duplicate_count)."""
    sent = set(alert.sent_job_ids)
    new_jobs: list[dict[str, Any]] = []
    filtered_fresh = 0
    filtered_dup = 0
    for job in jobs:
        bucket = job.get("freshness_bucket") or "Unknown"
        # Unknown/Older/1 week ago → not fresh
        if bucket not in FRESH_BUCKETS:
            filtered_fresh += 1
            continue
        job_id = job.get("id") or ""
        if not job_id:
            # fallback to job_url uniqueness
            job_id = job.get("job_url") or str(job.get("title"))
        if job_id in sent:
            filtered_dup += 1
            continue
        # also check job_url dup if ids differ but url same
        job_url = job.get("job_url") or ""
        if job_url and any(job_url == (j.get("job_url") or "") for j in jobs if False):
            pass  # already deduped in normalizer
        new_jobs.append(job)
    return new_jobs, filtered_fresh, filtered_dup


def run_alert(alert_id: str) -> dict[str, Any]:
    """Execute alert: call existing Job Agent → freshness + uniqueness → update state."""
    alert = get_alert(alert_id)
    if not alert:
        raise KeyError(f"Alert {alert_id} not found")

    # Build effective query for Job Agent
    effective_query = alert.query
    if alert.location and alert.location.lower() not in effective_query.lower():
        effective_query = f"{effective_query} in {alert.location}"

    # Call existing Job Agent (reuses google_jobs + normalizer + freshness sort)
    from job_agent.agent.job_agent import run_job_search

    result = run_job_search(user_query=effective_query, resume_bytes=None, session_id=None)

    if result.get("error"):
        logger.warning(f"run_alert {alert_id} job search error: {result.get('error')}")
        return {
            "alert_id": alert_id,
            "new_jobs": [],
            "count": 0,
            "total_fetched": 0,
            "filtered_fresh": 0,
            "filtered_duplicate": 0,
            "error": result.get("error"),
        }
    if result.get("follow_up_question"):
        logger.info(f"run_alert {alert_id} follow_up: {result.get('follow_up_question')}")
        return {
            "alert_id": alert_id,
            "new_jobs": [],
            "count": 0,
            "total_fetched": 0,
            "filtered_fresh": 0,
            "filtered_duplicate": 0,
            "follow_up": result.get("follow_up_question"),
        }

    jobs: list[dict[str, Any]] = result.get("jobs") or []
    total_fetched = len(jobs)

    new_jobs, filtered_fresh, filtered_dup = _filter_fresh_unique(alert, jobs)

    # Update state: add new ids + bump next_run/last_run
    new_ids = [j.get("id") for j in new_jobs if j.get("id")]
    # If ids missing, use job_url as id
    if len(new_ids) < len(new_jobs):
        for j in new_jobs:
            if not j.get("id") and j.get("job_url"):
                new_ids.append(j["job_url"])
    alert.sent_job_ids.extend(new_ids)
    # Deduplicate sent list preserve order
    seen = set()
    deduped: list[str] = []
    for _id in alert.sent_job_ids:
        if _id not in seen:
            seen.add(_id)
            deduped.append(_id)
    alert.sent_job_ids = deduped
    alert.last_run_at = datetime.now(IST)
    alert.next_run_at = _compute_next_run(alert.frequency, alert.time, alert.last_run_at)
    # persist back
    _alerts[alert_id] = alert

    logger.info(
        f"run_alert {alert_id} fetched={total_fetched} fresh_excluded={filtered_fresh} dup_excluded={filtered_dup} new={len(new_jobs)} next_run={alert.next_run_at}"
    )

    # Return minimal job fields for email n8n (keep full for now, frontend can pick)
    minimal_jobs = []
    for j in new_jobs:
        minimal_jobs.append(
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company"),
                "location": j.get("location"),
                "posted": j.get("posted_label") or j.get("posted_at"),
                "posted_at": j.get("posted_at"),
                "freshness_bucket": j.get("freshness_bucket"),
                "employment_type": j.get("employment_type"),
                "work_mode": j.get("work_mode"),
                "job_url": j.get("job_url"),
                "apply_url": j.get("apply_url"),
                "thumbnail": j.get("thumbnail"),
                "extensions": j.get("extensions"),
            }
        )

    return {
        "alert_id": alert_id,
        "new_jobs": minimal_jobs,
        "count": len(minimal_jobs),
        "total_fetched": total_fetched,
        "filtered_fresh": filtered_fresh,
        "filtered_duplicate": filtered_dup,
    }


def clear_all() -> None:
    """Test helper — clear in-memory alerts."""
    _alerts.clear()
