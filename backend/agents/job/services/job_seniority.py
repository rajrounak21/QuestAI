"""Deterministic seniority gating.

The graph never filtered on seniority, so a resume parsed as "internship" still
surfaced postings that demand 8+ years. Skill matching only *scores* a job, it
never excludes anything, so those cards stayed in the list at 0%.

Two signals, in order of trustworthiness:
1. An explicit years requirement in the posting text ("8+ Years", "5-8 years").
2. An unambiguous senior word in the job *title* ("Senior", "Sr.", "Principal").

We filter after fetching rather than narrowing the SerpApi query: adding
"Internship" to the query over-restricts and can return nothing at all, while
the post-filter only removes postings the user is genuinely not eligible for.
"""
from __future__ import annotations

import re
from typing import Any

# Exclude a posting when it demands at least this many years.
# Senior users get no filtering at all. Thresholds are deliberately forgiving on
# the lower bound so a "3-5 years" posting still reaches an entry-level
# candidate, while "5-8" and "8+ years" do not.
EXCLUDE_AT_LEAST_YEARS: dict[str, int] = {
    "internship": 2,
    "entry_level": 4,
    "mid_level": 6,
    "senior": 99,
}

# Words that are unambiguous in a title. "lead" / "manager" are deliberately
# excluded — they show up in junior postings too ("reporting to the manager").
SENIOR_TITLE_RE = re.compile(
    r"\b(senior|sr\.?|principal|staff\s+engineer|architect|director|head\s+of)\b",
    re.IGNORECASE,
)

# "8+ years", "5-8 years", "3+ yrs of experience"
YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|to|-|–|—)\s*(?:\d{1,2})?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)
BARE_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def normalize_level(level: str | None) -> str:
    return (level or "").strip().lower().replace(" ", "_") or "unknown"


def detect_required_years(text: str) -> float | None:
    """Lowest number of years the posting asks for, or None if it says nothing.

    For a range like "5-8 years" the lower bound is what gates eligibility, so
    that is what we return.
    """
    if not text:
        return None
    m = YEARS_RE.search(text)
    if m:
        return float(m.group(1))
    # "8+ years" with no dash still matters, but a bare number is ambiguous:
    # "2 years ago" is history, not a requirement. Require a '+' or the absence
    # of a time word on either side of the match.
    for m in BARE_YEARS_RE.finditer(text):
        before = text[max(0, m.start() - 12):m.start()].lower()
        after = text[m.end():m.end() + 8].lower()
        if "+" in m.group(0):
            return float(m.group(1))
        if re.search(r"\b(ago|last|past|over|within)\s*$", before):
            continue
        if re.match(r"\s*\b(ago|last|past)\b", after):
            continue
        return float(m.group(1))
    return None


def is_senior_title(title: str) -> bool:
    return bool(SENIOR_TITLE_RE.search(title or ""))


def _job_blob(job: dict[str, Any]) -> str:
    highlights = job.get("job_highlights") or job.get("highlights") or []
    if isinstance(highlights, str):
        highlights = [highlights]
    parts = [
        job.get("title") or "",
        job.get("description") or "",
        job.get("job_description") or "",
        " ".join(str(h) for h in highlights),
        " ".join(str(e) for e in (job.get("extensions") or [])),
    ]
    return "\n".join(p for p in parts if p)


def exclusion_reason(job: dict[str, Any], level: str) -> str | None:
    """Why this job should be hidden from this user, or None to keep it."""
    threshold = EXCLUDE_AT_LEAST_YEARS.get(level)
    if threshold is None or level == "unknown":
        return None

    years = detect_required_years(_job_blob(job))
    if years is not None and years >= threshold:
        return f"requires {years:g}+ years (you are {level})"

    # A senior title is only disqualifying for the junior levels; a mid-level
    # user may legitimately be considered for "Senior" in some markets.
    if level in ("internship", "entry_level") and is_senior_title(job.get("title") or ""):
        return f"senior title ({job.get('title')})"

    return None


def filter_by_seniority(
    jobs: list[dict[str, Any]], level: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split jobs into (kept, dropped). Unknown level keeps everything."""
    lvl = normalize_level(level)
    if lvl == "unknown":
        return list(jobs), []
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for job in jobs:
        reason = exclusion_reason(job, lvl)
        if reason:
            job["seniority_excluded_reason"] = reason
            dropped.append(job)
        else:
            kept.append(job)
    return kept, dropped
