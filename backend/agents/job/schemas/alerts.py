from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# User-facing limits: an alert holds up to 2 roles and 2 locations.
# The search cap is the full cross product (2 x 2 = 4) so a maxed-out alert is
# never silently trimmed. Each pair is one SerpApi call per run, which returns
# ~10 jobs, so 4 calls is the point where cost starts to matter.
MAX_ALERT_QUERIES = 2
MAX_ALERT_LOCATIONS = 2
MAX_ALERT_SEARCHES = 4


def clean_list(values: list[str] | None, cap: int) -> list[str]:
    """Trim, drop blanks, dedupe case-insensitively, cap the length."""
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= cap:
            break
    return out


class AlertCreate(BaseModel):
    # `query`/`location` are the original single-value fields and stay supported
    # so existing n8n calls and older frontends keep working.
    query: str | None = Field(default=None, description="Single job query (legacy, still supported)")
    location: str | None = Field(default=None, description="Single location (legacy, still supported)")
    queries: list[str] = Field(default_factory=list, description="Job roles to search, e.g. ['AI Engineer', 'ML Engineer']")
    locations: list[str] = Field(default_factory=list, description="Locations to search, e.g. ['Bangalore', 'Remote']")
    experience: str | None = Field(default=None, description="e.g. '0-1 years'")
    frequency: Literal["daily", "weekly"] = Field(default="daily")
    time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$", description="HH:MM 24h IST")
    email: str | None = Field(
        default=None,
        description="Recipient. Defaults to the logged-in user's email when omitted.",
    )

    def resolved_queries(self) -> list[str]:
        merged = clean_list([self.query, *self.queries], MAX_ALERT_QUERIES)
        return merged

    def resolved_locations(self) -> list[str]:
        locs = clean_list([self.location, *self.locations], MAX_ALERT_LOCATIONS)
        return locs or ["India"]


class AlertPatch(BaseModel):
    """Edit the user's single alert. Every field is optional.

    `sent` is intentionally not editable — clearing it would re-send every job
    the user has already been emailed.
    """

    query: str | None = None
    location: str | None = None
    queries: list[str] | None = None
    locations: list[str] | None = None
    experience: str | None = None
    frequency: Literal["daily", "weekly"] | None = None
    time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    email: str | None = Field(
        default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    is_active: bool | None = None

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in self.__class__.model_fields)


class Alert(BaseModel):
    # `id` is the public alert id ("alert_xxxx"). It is assigned once and never
    # changes, including across edits, so n8n can keep using it.
    id: str
    user_id: str | None = None
    # Mirrors of the first entry, kept so existing consumers reading a single
    # string keep working now that an alert can hold many.
    query: str
    location: str
    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience: str | None = None
    frequency: Literal["daily", "weekly"] = "daily"
    time: str = "09:00"
    email: str
    created_at: datetime
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    sent: list[dict] = Field(default_factory=list)
    sent_count: int = 0
    is_active: bool = True
    status: str = "active"

    # The pre-DB field name. Kept so nothing downstream has to know that `sent`
    # used to be a flat list of strings.
    @property
    def sent_job_ids(self) -> list[str]:
        return [e["id"] for e in self.sent if isinstance(e, dict) and e.get("id")]


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
    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience: str | None = None
    email: str


class DueAlertsResponse(BaseModel):
    due_alerts: list[DueAlertItem]


class AlertRunResponse(BaseModel):
    alert_id: str
    new_jobs: list[dict] = Field(default_factory=list)
    count: int = 0
    searches_run: int = 0
    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    total_fetched: int = 0
    filtered_fresh: int = 0
    filtered_duplicate: int = 0
    searches_skipped_by_cap: int = 0
    seniority_level: str | None = None
    seniority_excluded: int = 0


class DeleteResponse(BaseModel):
    deleted: bool = True
    alert_id: str
