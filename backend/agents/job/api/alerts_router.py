from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.job.schemas.alerts import AlertCreate, AlertPatch
from backend.agents.job.services import alert_service
from backend.agents.job.services.alert_service import IST
from backend.auth.security import get_current_user, require_service_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs/alerts", tags=["alerts"])

# Auth split, and it is deliberate:
#
#   Browser  -> get_current_user. A user only ever sees and edits their own
#               single alert, because every query is scoped by user_id.
#   n8n      -> require_service_key. The scheduler is not a logged-in user, so a
#               JWT is impossible there, but it must not be an open door
#               either: GET /alerts returns every user's email address, and
#               /{id}/run spends SerpApi quota.
#
# Both are mounted before jobs_router in main.py because jobs_router owns
# GET /api/jobs/{session_id} and would otherwise swallow "/api/jobs/alerts".


def _public(alert) -> dict:
    """Alert -> response body. `sent` is summarised, never dumped."""
    return {
        "alert_id": alert.id,
        "queries": alert.queries,
        "locations": alert.locations,
        "query": alert.query,
        "location": alert.location,
        "experience": alert.experience,
        "frequency": alert.frequency,
        "time": alert.time,
        "email": alert.email,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "last_run_at": alert.last_run_at.isoformat() if alert.last_run_at else None,
        "next_run_at": alert.next_run_at.isoformat() if alert.next_run_at else None,
        "sent_count": alert.sent_count,
        "is_active": alert.is_active,
        "status": alert.status,
    }


@router.post("")
def create_alert(body: AlertCreate, user: dict = Depends(get_current_user)):
    """POST /api/jobs/alerts — create this user's single alert.

    A stored resume is required. It is what supplies `experience_level`, which
    run_alert feeds to the seniority gate — without it every posting passes
    through and the digest fills up with senior jobs the user cannot apply to.
    The frontend opens the upload gate first; this is the enforcement.
    """
    from backend.database.job_profiles import has_profile

    if not has_profile(user["id"]):
        raise HTTPException(
            status_code=409,
            detail="Upload your resume to create a job alert.",
        )
    try:
        alert = alert_service.create_alert(
            body,
            user_id=user["id"],
            # The account email is the default recipient, so the user does not
            # have to type it. An explicit `email` in the body still wins.
            default_email=user.get("email"),
        )
    except ValueError as ve:
        msg = str(ve)
        # One alert per user is a product rule, not a bad request.
        status_code = 409 if "already has a job alert" in msg else 400
        raise HTTPException(status_code=status_code, detail=msg)
    return {"alert_id": alert.id, "status": alert.status, "message": "Job alert created",
            "alert": _public(alert)}


@router.get("")
def list_alerts(user: dict = Depends(get_current_user)):
    """GET /api/jobs/alerts — this user's alert, if any."""
    alerts = alert_service.list_alerts(user_id=user["id"])
    return {"alerts": [_public(a) for a in alerts]}


@router.patch("")
def patch_alert(body: AlertPatch, user: dict = Depends(get_current_user)):
    """PATCH /api/jobs/alerts — edit the existing alert.

    Roles, locations, email, schedule and the paused state are all editable.
    `sent` is not: clearing it would re-send every job already emailed. The
    public alert_id never changes, so an n8n workflow that captured it keeps
    working after an edit.
    """
    if body.is_empty():
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        alert = alert_service.update_alert(user["id"], body)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    if not alert:
        raise HTTPException(status_code=404, detail="No job alert to edit. Create one first.")
    return {"alert": _public(alert), "message": "Job alert updated"}


@router.delete("")
def delete_own_alert(user: dict = Depends(get_current_user)):
    """DELETE /api/jobs/alerts — remove this user's alert."""
    ok = alert_service.delete_alert_for_user(user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="No job alert found")
    return {"deleted": True}


# ---- n8n surface ----
# Shape is unchanged from the pre-Mongo version so an existing workflow keeps
# working: same paths, same keys, same alert_id.


# due must be before {alert_id} to avoid route conflict
@router.get("/due")
def get_due_alerts(
    now: str | None = None,
    _: None = Depends(require_service_key),
):
    """GET /api/jobs/alerts/due — Alerts that need to run now (for n8n).

    Optional ?now=ISO datetime for testing, e.g. 2026-09-25T09:01:00+05:30
    """
    current: datetime | None = None
    if now:
        try:
            current = datetime.fromisoformat(now)
            if current.tzinfo is None:
                current = current.replace(tzinfo=IST)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid now param, expected ISO datetime: {e}")
    due = alert_service.get_due_alerts(now=current)
    return {
        "due_alerts": [
            {
                "alert_id": a.id,
                # `query`/`location` stay as the first entry for older n8n
                # workflows; `queries`/`locations` carry the full set.
                "query": a.query,
                "location": a.location,
                "queries": a.queries or [a.query],
                "locations": a.locations or [a.location],
                "experience": a.experience,
                "email": a.email,
                "frequency": a.frequency,
                "time": a.time,
                "next_run_at": a.next_run_at.isoformat() if a.next_run_at else None,
            }
            for a in due
        ]
    }


@router.post("/{alert_id}/run")
def run_alert(alert_id: str, _: None = Depends(require_service_key)):
    """POST /api/jobs/alerts/{alert_id}/run — Execute alert, return new jobs."""
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    try:
        return alert_service.run_alert(alert_id)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception(f"run_alert failed {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Run failed: {e}")


@router.get("/{alert_id}")
def get_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """GET /api/jobs/alerts/{alert_id} — read one of your own alerts."""
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    if alert.user_id and alert.user_id != user["id"]:
        # Do not confirm the existence of somebody else's alert.
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return _public(alert)


@router.delete("/{alert_id}")
def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """DELETE /api/jobs/alerts/{alert_id} — kept for older callers."""
    alert = alert_service.get_alert(alert_id)
    if not alert or (alert.user_id and alert.user_id != user["id"]):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    if not alert_service.delete_alert(alert_id):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"deleted": True, "alert_id": alert_id}
