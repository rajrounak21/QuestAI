from __future__ import annotations

import re
from typing import Any

from backend.agents.job.services.skill_normalizer import normalize_skill, normalized_aliases

# Words that are too short to match without strict boundaries; treat specially
_SHORT_SKILLS = {"r", "c", "go", "js", "ts"}

def _phrase_pattern(skill: str) -> str:
    """Build regex pattern for a skill with aliases, phrase-aware, word boundaries."""
    variants = normalized_aliases(skill)
    # Build alternation: each variant escaped, spaces -> \s*[-_]*\s*
    alts: list[str] = []
    for v in variants:
        # Escape regex, then allow flexible separators for spaces
        # e.g. "fast api" -> fast\s*[-_]*\s*api
        parts = v.split()
        if len(parts) > 1:
            esc_parts = [re.escape(p) for p in parts]
            pat = r"\s*[-_]*\s*".join(esc_parts)
            alts.append(pat)
        else:
            alts.append(re.escape(v))
    # For very short skills, require strict word boundaries and not substrings
    # e.g. \bsql\b should NOT match mysql's sql part (handled by \b), 
    # \br\b should not match every "r" in words — we require it as standalone token
    # We'll still use \b but short skills will rarely match in job text unless exact
    if skill.strip().lower() in _SHORT_SKILLS:
        # require surrounding non-letter or boundary; already \b handles, but also ensure not part of longer identifier
        # Keep \b; for "c" we additionally require not followed by alphanum (already \b)
        combined = "(" + "|".join(alts) + ")"
        return r"\b" + combined + r"\b"
    else:
        combined = "(" + "|".join(alts) + ")"
        # phrase skills need word boundaries around whole phrase
        return r"\b" + combined + r"\b"

def _build_job_blob(job: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["title", "description"]:
        v = job.get(key)
        if v and isinstance(v, str):
            parts.append(v)
    # highlights
    for h in job.get("job_highlights", []) or []:
        if isinstance(h, dict):
            parts.append(h.get("title", ""))
            for it in h.get("items", []) or []:
                if isinstance(it, str):
                    parts.append(it)
    for e in job.get("extensions", []) or []:
        if isinstance(e, str):
            parts.append(e)
    blob = " ".join(p for p in parts if p)
    return blob.lower()

def match_jobs(user_skills: list[str], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich each job dict with matched/missing/percentage. Pure deterministic, 0 LLM."""
    if not user_skills:
        for job in jobs:
            job["matched_skills"] = []
            job["missing_skills"] = []
            job["matched_count"] = 0
            job["total_user_skills"] = 0
            job["match_percentage"] = 0
        return jobs

    # Normalize user skills to canonical deduped
    canon_skills: list[str] = []
    seen: set[str] = set()
    for s in user_skills:
        if not s or not isinstance(s, str):
            continue
        c = normalize_skill(s)
        if not c:
            continue
        if c not in seen:
            seen.add(c)
            canon_skills.append(c)

    total = len(canon_skills)
    # Precompile patterns
    patterns: dict[str, re.Pattern] = {}
    for skill in canon_skills:
        pat_str = _phrase_pattern(skill)
        try:
            patterns[skill] = re.compile(pat_str, re.IGNORECASE)
        except re.error:
            patterns[skill] = re.compile(re.escape(skill), re.IGNORECASE)

    for job in jobs:
        blob = _build_job_blob(job)
        matched: list[str] = []
        missing: list[str] = []
        for skill in canon_skills:
            pat = patterns[skill]
            if pat.search(blob):
                matched.append(skill)
            else:
                missing.append(skill)
        job["matched_skills"] = matched
        job["missing_skills"] = missing
        job["matched_count"] = len(matched)
        job["total_user_skills"] = total
        job["match_percentage"] = int(round(len(matched) / total * 100)) if total else 0
    return jobs
