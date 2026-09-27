from __future__ import annotations

from typing import Any

from job_agent.models.job_models import JobListing


def build_evidence(jobs: list[JobListing], raws: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for j in jobs:
        evidence.append(
            {
                "job_id": j.id,
                "title": j.title,
                "company": j.company,
                "source_type": "google_jobs",
                "job_url": j.job_url,
                "apply_url": j.apply_url,
                "source": j.source,
                "location": j.location,
                "posted_at": j.posted_at,
                "salary": j.salary,
                "search_url": j.raw_source.search_url,
            }
        )
    return evidence


def attach_meta(raws: list[dict[str, Any]]) -> dict[str, Any]:
    total_raw = sum(len(r.get("jobs_results", [])) for r in raws)
    first_meta = (raws[0].get("search_metadata", {}) if raws else {}) if raws else {}
    return {
        "engine": "google_jobs",
        "total_raw": total_raw,
        "num_queries": len(raws),
        "search_url": first_meta.get("google_jobs_url", "") or first_meta.get("google_url", ""),
    }
