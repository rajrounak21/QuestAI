from __future__ import annotations

import hashlib
import logging
from typing import Any

from job_agent.models.job_models import JobListing, JobSource
from job_agent.services.freshness import classify_freshness, freshness_sort_key

logger = logging.getLogger(__name__)


def _make_job_id(title: str, company: str, job_url: str) -> str:
    raw = f"{title}-{company}-{job_url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def normalize_jobs(raws: list[dict[str, Any]]) -> list[JobListing]:
    """Normalize multiple raw google_jobs responses into deduplicated sorted JobListing."""
    seen: dict[str, JobListing] = {}
    for raw in raws:
        jobs_results = raw.get("jobs_results", [])
        search_metadata = raw.get("search_metadata", {})
        search_url = search_metadata.get("google_jobs_url", "") or search_metadata.get("google_url", "")
        serpapi_link = search_metadata.get("google_jobs_url", "")  # fallback

        for item in jobs_results:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            company = (item.get("company_name") or item.get("company") or "").strip()
            if not company:
                continue
            # job_url is share_link or link (google jobs detail)
            job_url = (item.get("share_link") or item.get("link") or "").strip()
            if not job_url:
                logger.debug(f"Skipping job with no link: {title[:60]}")
                continue
            via = item.get("via", "") or ""
            location = item.get("location", "") or ""
            description = item.get("description")
            extensions = item.get("extensions", []) or []
            detected = item.get("detected_extensions", {}) or {}
            thumbnail = item.get("thumbnail", "") or ""
            job_highlights = item.get("job_highlights", []) or []

            # apply_url: first apply_options link
            apply_url = None
            apply_options = item.get("apply_options", []) or []
            if apply_options and isinstance(apply_options, list):
                first = apply_options[0]
                if isinstance(first, dict):
                    apply_url = first.get("link")

            salary = detected.get("salary")
            # fallback: salary often in extensions like "₹14,999–₹15,000 a month" or "16.25–18.44 an hour"
            if not salary and extensions:
                for ext in extensions:
                    if any(k in ext for k in ["₹", "$", "a month", "a year", "an hour", "per hour", "LPA", "lakh"]):
                        salary = ext
                        break
            employment_type = detected.get("schedule_type") or detected.get("employment_type")
            # work_mode inference from extensions / detected / location string
            work_mode = None
            ext_text = " ".join(extensions).lower() + " " + " ".join(str(v) for v in detected.values()).lower() + " " + location.lower()
            if "remote" in ext_text:
                work_mode = "remote"
            elif "hybrid" in ext_text:
                work_mode = "hybrid"
            elif "onsite" in ext_text or "on-site" in ext_text:
                work_mode = "onsite"
            # also show work_from_home flag
            if detected.get("work_from_home") is True:
                work_mode = "remote"

            posted_at = detected.get("posted_at") or None
            posted_label = None
            for ext in extensions:
                if "ago" in ext.lower() or "today" in ext.lower() or "yesterday" in ext.lower() or "hour" in ext.lower():
                    posted_label = ext
                    break
            if not posted_label and posted_at:
                posted_label = posted_at

            # id: use job_id if present else deterministic
            raw_id = item.get("job_id", "") or ""
            if raw_id and len(raw_id) > 8:
                # use short hash of job_id to keep stable
                job_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]
            else:
                job_id = _make_job_id(title, company, job_url)

            bucket = classify_freshness(posted_at, extensions)

            job = JobListing(
                id=job_id,
                title=title,
                company=company,
                location=location,
                description=description,
                salary=salary,
                employment_type=employment_type,
                work_mode=work_mode,
                posted_at=posted_at,
                posted_label=posted_label,
                freshness_bucket=bucket,
                source=via,
                job_url=job_url,
                apply_url=apply_url,
                thumbnail=thumbnail,
                extensions=extensions,
                detected_extensions=detected,
                job_highlights=job_highlights,
                raw_source=JobSource(job_url=job_url, search_url=search_url, serpapi_link=serpapi_link),
            )

            if job_id in seen:
                # keep most recent
                existing = seen[job_id]
                if freshness_sort_key(bucket) < freshness_sort_key(existing.freshness_bucket):
                    seen[job_id] = job
                continue
            # also dedup by job_url
            dup = False
            for existing in seen.values():
                if existing.job_url == job_url and job_url:
                    dup = True
                    break
            if dup:
                continue
            seen[job_id] = job

    jobs = list(seen.values())
    # sort by freshness (recent first)
    jobs.sort(key=lambda j: freshness_sort_key(j.freshness_bucket))
    logger.info(f"Normalized {len(jobs)} jobs from {sum(len(r.get('jobs_results',[])) for r in raws)} raw across {len(raws)} queries")
    return jobs
