from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    query: str = Field(..., min_length=1, description="Job query e.g. 'AI Engineer Intern'")
    location: str = Field(default="India", min_length=1)
    experience: str | None = Field(default=None, description="e.g. '0-1 years'")
    frequency: Literal["daily", "weekly"] = Field(default="daily")
    time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$", description="HH:MM 24h IST")
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Recipient email")


class Alert(BaseModel):
    id: str
    query: str
    location: str
    experience: str | None = None
    frequency: Literal["daily", "weekly"] = "daily"
    time: str = "09:00"
    email: str
    created_at: datetime
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    sent_job_ids: list[str] = Field(default_factory=list)
    is_active: bool = True
    status: str = "active"


class AlertCreateResponse(BaseModel):
    alert_id: str
    status: str = "active"
    message: str = "Job alert created"


class AlertListResponse(BaseModel):
    alerts: list[Alert]


class DueAlertItem(BaseModel):
    alert_id: str
    query: str
    location: str
    experience: str | None = None
    email: str


class DueAlertsResponse(BaseModel):
    due_alerts: list[DueAlertItem]


class AlertRunResponse(BaseModel):
    alert_id: str
    new_jobs: list[dict] = Field(default_factory=list)
    count: int = 0


class DeleteResponse(BaseModel):
    deleted: bool = True
    alert_id: str
