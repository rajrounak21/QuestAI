from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from job_agent.models.alert_models import AlertCreate
from job_agent.services import alert_service
from job_agent.services.alert_service import IST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs/alerts", tags=["alerts"])


@router.post("")
def create_alert(body: AlertCreate):
    """POST /api/jobs/alerts — Create an alert (in-memory)."""
    try:
        alert = alert_service.create_alert(body)
        return {"alert_id": alert.id, "status": "active", "message": "Job alert created"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("")
def list_alerts():
    """GET /api/jobs/alerts — List all alerts (in-memory)."""
    alerts = alert_service.list_alerts()
    return {"alerts": [a.model_dump() for a in alerts]}


# due must be before {alert_id} to avoid route conflict
@router.get("/due")
def get_due_alerts(now: str | None = None):
    """GET /api/jobs/alerts/due — Alerts that need to run now (for n8n).

    Optional ?now=ISO datetime for testing, e.g. 2026-09-25T09:01:00+05:30
    """
    current: datetime | None = None
    if now:
        try:
            # fromisoformat handles +05:30
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
                "query": a.query,
                "location": a.location,
                "experience": a.experience,
                "email": a.email,
                "frequency": a.frequency,
                "time": a.time,
                "next_run_at": a.next_run_at.isoformat() if a.next_run_at else None,
            }
            for a in due
        ]
    }


@router.delete("/{alert_id}")
def delete_alert(alert_id: str):
    """DELETE /api/jobs/alerts/{alert_id}"""
    ok = alert_service.delete_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"deleted": True, "alert_id": alert_id}


@router.post("/{alert_id}/run")
def run_alert(alert_id: str):
    """POST /api/jobs/alerts/{alert_id}/run — Execute alert via existing Job Agent → fresh+unique jobs."""
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    try:
        result = alert_service.run_alert(alert_id)
        # result already has alert_id, new_jobs, count, etc.
        return result
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        logger.exception(f"run_alert failed {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Run failed: {e}")


# Extra: get single alert (useful for Swagger/debug, not required but handy)
@router.get("/{alert_id}")
def get_alert(alert_id: str):
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert.model_dump()
