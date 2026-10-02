from __future__ import annotations

from pydantic import BaseModel, Field


class JobProfile(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    employment_type: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_mode: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    name: str | None = None
    email: str | None = None
    links: list[str] = Field(default_factory=list)
    raw_text: str | None = None


class JobSearchRequest(BaseModel):
    query: str
    location: str = "India"
    google_domain: str = "google.com"
    gl: str = "us"
    hl: str = "en"


class JobSource(BaseModel):
    engine: str = "google_jobs"
    job_url: str = ""
    search_url: str = ""
    serpapi_link: str = ""


class JobListing(BaseModel):
    id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str | None = None
    salary: str | None = None
    employment_type: str | None = None
    work_mode: str | None = None
    posted_at: str | None = None
    posted_label: str | None = None
    freshness_bucket: str = "Unknown"
    source: str = ""
    job_url: str = ""
    apply_url: str | None = None
    thumbnail: str | None = None
    extensions: list[str] = Field(default_factory=list)
    detected_extensions: dict = Field(default_factory=dict)
    job_highlights: list[dict] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_count: int = 0
    total_user_skills: int = 0
    match_percentage: int = 0
    raw_source: JobSource = Field(default_factory=JobSource)


class JobSearchResponse(BaseModel):
    request: JobSearchRequest | None = None
    jobs: list[JobListing] = Field(default_factory=list)
    total_results: int = 0
    raw_count: int = 0
    error: str | None = None
