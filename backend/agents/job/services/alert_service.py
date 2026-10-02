from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from datetime import timezone

from backend.agents.job.schemas.alerts import (
    MAX_ALERT_LOCATIONS,
    MAX_ALERT_QUERIES,
    MAX_ALERT_SEARCHES,
    Alert,
    AlertCreate,
    AlertPatch,
    clean_list,
)
from backend.database import job_alerts

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    # Fallback for Windows without tzdata installed (UTC+5:30)
    IST = timezone(timedelta(hours=5, minutes=30))

# Legacy in-memory store. Alerts live in Mongo now; this dict only backs the
# scheduling unit tests, which exercise create_alert() without a user_id.
_alerts: dict[str, Alert] = {}

# Fresh buckets considered "fresh" for daily alerts
# Unknown / Older / 1 week ago are not fresh
FRESH_BUCKETS = {"Today", "1 day ago", "3 days ago"}


def plan_searches(
    queries: list[str],
    locations: list[str],
    cap: int = MAX_ALERT_SEARCHES,
) -> tuple[list[tuple[str, str]], int]:
    """Build the (role, location) pairs an alert will search.

    Every role is matched against every location so one alert covers the whole
    cross product. When that exceeds `cap` (each pair costs a SerpApi call) we
    cut round-robin rather than truncating, so each role keeps at least one
    location before any role gets a second one.

    Returns (pairs, number_of_pairs_dropped_by_the_cap).
    """
    pairs = [(q, loc) for q in queries for loc in locations]
    if len(pairs) <= cap:
        return pairs, 0

    # Round-robin over roles: role0/loc0, role1/loc0, ... then loc1, and so on.
    kept: list[tuple[str, str]] = []
    for loc in locations:
        for q in queries:
            pair = (q, loc)
            if len(kept) >= cap:
                break
            kept.append(pair)
        if len(kept) >= cap:
            break
    return kept, len(pairs) - len(kept)


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


def _to_alert(doc: dict[str, Any] | None) -> Alert | None:
    """Mongo doc -> Alert model."""
    if not doc:
        return None
    sent = doc.get("sent") or []
    return Alert(
        id=doc.get("alert_id") or "",
        user_id=doc.get("user_id"),
        query=doc.get("query") or "",
        location=doc.get("location") or "",
        queries=doc.get("queries") or [],
        locations=doc.get("locations") or [],
        experience=doc.get("experience"),
        frequency=doc.get("frequency") or "daily",
        time=doc.get("time") or "09:00",
        email=doc.get("email") or "",
        created_at=doc.get("created_at") or datetime.now(IST),
        last_run_at=doc.get("last_run_at"),
        next_run_at=doc.get("next_run_at"),
        sent=[e for e in sent if isinstance(e, dict)],
        sent_count=len(sent),
        is_active=bool(doc.get("is_active", True)),
        status=doc.get("status") or "active",
    )


def create_alert(data: AlertCreate, user_id: str | None = None,
                 default_email: str | None = None) -> Alert:
    """Create the user's single alert in Mongo.

    `user_id` is required in production (the endpoint is JWT-protected) but kept
    optional so test helpers can still exercise the scheduling maths.
    """
    alert_id = f"alert_{uuid.uuid4().hex[:8]}"
    now = datetime.now(IST)
    # validate time hour/minute ranges
    h, m = _parse_time(data.time)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time, expected HH:MM 00:00-23:59")

    queries = data.resolved_queries()
    if not queries:
        raise ValueError("At least one job role is required")
    locations = data.resolved_locations()

    email = (data.email or default_email or "").strip()
    if not email:
        raise ValueError("A recipient email is required")

    next_run = _compute_next_run(data.frequency, data.time, now)
    doc = {
        "alert_id": alert_id,
        "query": queries[0],
        "location": locations[0],
        "queries": queries,
        "locations": locations,
        "experience": data.experience.strip() if data.experience else None,
        "frequency": data.frequency,
        "time": data.time,
        "email": email,
        "created_at": now,
        "last_run_at": None,
        "next_run_at": next_run,
        "sent": [],
        "is_active": True,
        "status": "active",
    }
    if user_id:
        try:
            stored = job_alerts.create_alert(user_id, doc)
        except job_alerts.DuplicateAlertError as e:
            raise ValueError(str(e)) from e
        logger.info(
            f"Alert created {alert_id} user={user_id} roles={queries} locations={locations} "
            f"searches={len(plan_searches(queries, locations)[0])} next_run={next_run.isoformat()}"
        )
        return _to_alert(stored)  # type: ignore[return-value]

    # No owner: keep it in memory for the unit tests of the scheduling maths.
    alert = Alert(**{**doc, "id": alert_id})
    _alerts[alert_id] = alert
    return alert


def update_alert(user_id: str, patch: AlertPatch) -> Alert | None:
    """Edit an existing alert. `sent`, `alert_id` and the run clock are untouched.

    next_run_at is recomputed only when the schedule actually changes, so editing
    just the roles does not push the next run a day out.
    """
    current = job_alerts.get_alert(user_id)
    if not current:
        return None

    patch_set: dict[str, Any] = {}
    if patch.queries is not None or patch.query is not None:
        merged = clean_list(
            [patch.query, *(patch.queries or [])],
            MAX_ALERT_QUERIES,
        )
        if not merged:
            raise ValueError("At least one job role is required")
        patch_set["queries"] = merged
        patch_set["query"] = merged[0]
    if patch.locations is not None or patch.location is not None:
        locs = clean_list(
            [patch.location, *(patch.locations or [])],
            MAX_ALERT_LOCATIONS,
        )
        if not locs:
            raise ValueError("At least one location is required")
        patch_set["locations"] = locs
        patch_set["location"] = locs[0]
    if patch.email is not None:
        patch_set["email"] = patch.email.strip()
    if patch.experience is not None:
        patch_set["experience"] = patch.experience.strip() or None
    if patch.is_active is not None:
        patch_set["is_active"] = patch.is_active
        patch_set["status"] = "active" if patch.is_active else "paused"

    schedule_changed = False
    if patch.frequency is not None and patch.frequency != current.get("frequency"):
        patch_set["frequency"] = patch.frequency
        schedule_changed = True
    if patch.time is not None and patch.time != current.get("time"):
        h, m = _parse_time(patch.time)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid time, expected HH:MM 00:00-23:59")
        patch_set["time"] = patch.time
        schedule_changed = True

    if not patch_set:
        return _to_alert(current)

    # Recompute the next run against the *new* schedule.
    freq = patch_set.get("frequency", current.get("frequency", "daily"))
    tm = patch_set.get("time", current.get("time", "09:00"))
    if not patch_set.get("is_active", current.get("is_active", True)):
        # Pausing: leave next_run_at alone so resuming does not skip a window.
        pass
    elif schedule_changed:
        base = current.get("last_run_at") or datetime.now(IST)
        if base.tzinfo is None:
            base = base.replace(tzinfo=IST)
        patch_set["next_run_at"] = _compute_next_run(freq, tm, base)
        logger.info(f"Alert {current.get('alert_id')} rescheduled -> {patch_set['next_run_at']}")

    updated = job_alerts.update_alert(user_id, patch_set)
    logger.info(
        f"Alert updated user={user_id} alert_id={current.get('alert_id')} "
        f"fields={sorted(patch_set)}"
    )
    return _to_alert(updated)


def list_alerts(user_id: str | None = None) -> list[Alert]:
    if user_id is not None:
        doc = job_alerts.get_alert(user_id)
        return [_to_alert(doc)] if doc else []  # type: ignore[list-item]
    out: list[Alert] = []
    for doc in job_alerts.get_job_alerts_collection().find({}):
        a = _to_alert(doc)
        if a:
            out.append(a)
    return out


def get_alert(alert_id: str) -> Alert | None:
    doc = job_alerts.get_alert_by_id(alert_id)
    if doc:
        return _to_alert(doc)
    return _alerts.get(alert_id)


def get_alert_for_user(user_id: str) -> Alert | None:
    return _to_alert(job_alerts.get_alert(user_id))


def delete_alert(alert_id: str) -> bool:
    doc = job_alerts.get_alert_by_id(alert_id)
    if doc and doc.get("user_id"):
        ok = job_alerts.delete_alert(doc["user_id"])
        if ok:
            logger.info(f"Alert deleted {alert_id}")
        return ok
    if alert_id in _alerts:
        del _alerts[alert_id]
        logger.info(f"Alert deleted {alert_id} (in-memory)")
        return True
    return False


def delete_alert_for_user(user_id: str) -> bool:
    ok = job_alerts.delete_alert(user_id)
    if ok:
        logger.info(f"Alert deleted for user {user_id}")
    return ok


def get_due_alerts(now: datetime | None = None) -> list[Alert]:
    """Alerts that need to run now. Backs n8n's /due poll."""
    current = now or datetime.now(IST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=IST)
    # Mongo compares against UTC, so hand it an aware UTC value.
    utc_now = current.astimezone(timezone.utc)
    due: list[Alert] = []
    for doc in job_alerts.list_due_alerts(now=utc_now):
        a = _to_alert(doc)
        if a:
            due.append(a)
    if not due:
        # In-memory fallback for the scheduling unit tests.
        for alert in _alerts.values():
            if not alert.is_active or alert.next_run_at is None:
                continue
            nr = alert.next_run_at
            if nr.tzinfo is None:
                nr = nr.replace(tzinfo=IST)
            if current >= nr:
                due.append(alert)
    return due


def _tag_sources(raws: list[dict[str, Any]], reqs: list[Any]) -> dict[str, tuple[str, str]]:
    """Map normalized job id -> (role, location) that surfaced it.

    `raws` and `reqs` are index-aligned because google_jobs_search_multi keeps
    input order. The key is produced with the normalizer's own id rule so these
    line up with JobListing.id. First pair to surface a job wins.
    """
    from backend.agents.job.services.job_normalizer import derive_job_id

    out: dict[str, tuple[str, str]] = {}
    for idx, raw in enumerate(raws):
        if idx >= len(reqs) or not isinstance(raw, dict):
            continue
        req = reqs[idx]
        role, loc = req.query, req.location
        for job in raw.get("jobs_results", []) or []:
            if not isinstance(job, dict):
                continue
            key = derive_job_id(
                job,
                job.get("title") or "",
                job.get("company_name") or "",
                job.get("job_url") or "",
            )
            if key not in out:
                out[key] = (role, loc)
    return out


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
        new_jobs.append(job)
    return new_jobs, filtered_fresh, filtered_dup


def run_alert(alert_id: str) -> dict[str, Any]:
    """Execute alert: search every role x location pair -> freshness + uniqueness -> update state.

    Talks to the SerpApi tools layer directly rather than the LangGraph agent:
    an alert runs unattended on a schedule, so it must not depend on an LLM or
    on a logged-in user.

    Only the n8n scheduler calls this. It always writes state — the delivered ids
    and the bumped run clock — which is what makes a repeated call safe: the
    second run finds the same jobs in `sent` and returns none of them.
    """
    alert = get_alert(alert_id)
    if not alert:
        raise KeyError(f"Alert {alert_id} not found")

    queries = alert.queries or [alert.query]
    locations = alert.locations or [alert.location or "India"]
    pairs, skipped = plan_searches(queries, locations)

    from backend.agents.job.services.job_normalizer import normalize_jobs
    from backend.agents.job.tools.google_jobs import build_search_requests, google_jobs_search_multi

    reqs = build_search_requests(pairs)
    if not reqs:
        raise ValueError("Alert has no runnable job role")

    try:
        raws = google_jobs_search_multi(reqs)
    except Exception as e:
        logger.exception(f"run_alert {alert_id} SerpApi failure: {e}")
        return {
            "alert_id": alert_id,
            "new_jobs": [],
            "count": 0,
            "total_fetched": 0,
            "filtered_fresh": 0,
            "filtered_duplicate": 0,
            "searches_run": 0,
            "searches_skipped_by_cap": skipped,
            "queries": queries,
            "locations": locations,
            "error": str(e),
        }

    jobs: list[dict[str, Any]] = [j.model_dump() for j in normalize_jobs(raws)]
    total_fetched = len(jobs)

    # Tag each job with the role/location that surfaced it, so the email can say
    # why it was included. A job found by several pairs keeps the first one.
    source = _tag_sources(raws, reqs)
    tagged = 0
    for job in jobs:
        tag = source.get(job.get("id") or "")
        if tag:
            job["matched_role"] = tag[0]
            job["matched_location"] = tag[1]
            tagged += 1

    # Seniority gate. Alerts bypass the LangGraph agent, so they never went
    # through the router's filter — an alert on an internship profile was still
    # emailing 8+ years postings. The alert carries user_id, so the level now
    # comes from the stored resume profile. No profile -> level is None ->
    # filter_by_seniority keeps everything (safe default).
    level: str | None = None
    dropped_senior: list[dict[str, Any]] = []
    if alert.user_id:
        from backend.database.job_profiles import get_profile
        from backend.agents.job.services.job_seniority import filter_by_seniority

        profile = get_profile(alert.user_id) or {}
        level = profile.get("experience_level") or None
        if level:
            jobs, dropped_senior = filter_by_seniority(jobs, level)
            if dropped_senior:
                logger.info(
                    f"run_alert {alert_id} seniority filter ({level}): "
                    f"dropped {len(dropped_senior)} jobs"
                )
        else:
            # Alert exists but the user never uploaded a resume, so there is no
            # level to gate on. Keep everything rather than hide it.
            jobs = list(jobs)
    seniority_excluded = len(dropped_senior)

    new_jobs, filtered_fresh, filtered_dup = _filter_fresh_unique(alert, jobs)

    # Update state: add new ids + bump next_run/last_run
    new_ids = [j.get("id") for j in new_jobs if j.get("id")]
    # If ids missing, use job_url as id
    if len(new_ids) < len(new_jobs):
        for j in new_jobs:
            if not j.get("id") and j.get("job_url"):
                new_ids.append(j["job_url"])
    last_run = datetime.now(IST)
    next_run = _compute_next_run(alert.frequency, alert.time, last_run)
    alert.last_run_at = last_run
    alert.next_run_at = next_run
    if alert.user_id:
        # Persist: appends the new ids and prunes anything past the retention
        # window, so the list cannot grow forever.
        job_alerts.record_run(alert.user_id, new_ids, last_run, next_run)
    else:
        merged = list(alert.sent_job_ids) + [
            i for i in new_ids if i not in set(alert.sent_job_ids)
        ]
        seen: set[str] = set()
        alert.sent = [
            {"id": i, "seen_at": last_run} for i in merged if not (i in seen or seen.add(i))
        ]
        _alerts[alert_id] = alert

    logger.info(
        f"run_alert {alert_id} roles={len(queries)} locs={len(locations)} searches={len(reqs)} "
        f"fetched={total_fetched} tagged={tagged} senior_excluded={seniority_excluded} "
        f"fresh_excluded={filtered_fresh} dup_excluded={filtered_dup} new={len(new_jobs)} "
        f"skipped_by_cap={skipped} next_run={next_run}"
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
                "matched_role": j.get("matched_role"),
                "matched_location": j.get("matched_location"),
            }
        )

    return {
        "alert_id": alert_id,
        "new_jobs": minimal_jobs,
        "count": len(minimal_jobs),
        "total_fetched": total_fetched,
        "filtered_fresh": filtered_fresh,
        "filtered_duplicate": filtered_dup,
        "searches_run": len(reqs),
        "searches_skipped_by_cap": skipped,
        "queries": queries,
        "locations": locations,
        "seniority_level": level,
        "seniority_excluded": seniority_excluded,
    }


def clear_all() -> None:
    """Test helper — clear the in-memory fallback store only.

    Does NOT touch Mongo; use job_alerts.delete_alert(user_id) for that.
    """
    _alerts.clear()
