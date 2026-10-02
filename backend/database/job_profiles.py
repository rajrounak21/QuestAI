from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# One document per user, keyed on user_id alone (no session_id).
# Written at onboarding from the uploaded resume PDF, then read on every search
# so the resume never has to be uploaded twice.
#
# Stored: the structured fields the LLM extracts (skills, projects, education,
# experience, links, roles).
# NOT stored: raw_text. The PDF itself lives in GridFS (job_resume_files.py) and
# is previewable, so keeping a scraped copy of the same text here would be
# duplicate sensitive data with no reader.

MAX_SKILLS = 20
MAX_ROLES = 6
MAX_LOCATIONS = 6
MAX_PROJECTS = 4
MAX_EDUCATION = 2
MAX_EXPERIENCE = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- Pure builders ----


def new_profile_doc(user_id: str, resume_hash: str | None = None) -> dict[str, Any]:
    now = _utcnow()
    return {
        "user_id": user_id,
        "name": None,
        "target_roles": [],
        "skills": [],
        "experience_level": None,
        "employment_type": [],
        "locations": [],
        "work_mode": [],
        "preferences": [],
        "links": [],
        "projects": [],
        "education": [],
        "experience": [],
        "resume_hash": resume_hash,
        "resume_filename": None,
        "created_at": now,
        "updated_at": now,
    }


def build_profile_update(
    parsed: dict[str, Any],
    resume_hash: str | None = None,
    resume_filename: str | None = None,
) -> dict[str, Any]:
    """Whitelist + cap the fields we keep from the resume parser output.

    Every whitelisted key is always written, so uploading a new resume fully
    REPLACES the old profile rather than merging into it.
    """
    set_doc: dict[str, Any] = {
        "name": parsed.get("name") or None,
        "target_roles": _str_list(parsed.get("target_roles"), MAX_ROLES),
        "skills": _str_list(parsed.get("skills"), MAX_SKILLS),
        "experience_level": parsed.get("experience_level") or None,
        "employment_type": _str_list(parsed.get("employment_type"), 4),
        "locations": _str_list(parsed.get("locations"), MAX_LOCATIONS),
        "work_mode": _str_list(parsed.get("work_mode"), 3),
        "preferences": _str_list(parsed.get("preferences"), 6),
        "links": _str_list(parsed.get("links"), 6),
        "projects": _dict_list(parsed.get("projects"), MAX_PROJECTS, ("name",)),
        "education": _dict_list(parsed.get("education"), MAX_EDUCATION, ("degree", "school")),
        "experience": _dict_list(parsed.get("experience"), MAX_EXPERIENCE, ("title", "company")),
        "updated_at": _utcnow(),
    }
    if resume_hash:
        set_doc["resume_hash"] = resume_hash
    if resume_filename:
        set_doc["resume_filename"] = resume_filename
    return set_doc


def _dict_list(value: Any, cap: int, required: tuple[str, ...]) -> list[dict[str, Any]]:
    """Keep only dicts that carry at least one of `required` keys, capped.

    Mirrors the sanitising the resume parser already does, so a malformed LLM
    response can't write junk into the profile.
    """
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if not any(str(item.get(k) or "").strip() for k in required):
            continue
        out.append({k: v for k, v in item.items() if isinstance(v, (str, int, float, bool, list))})
        if len(out) >= cap:
            break
    return out


def _str_list(value: Any, cap: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        out.append(cleaned)
        if len(out) >= cap:
            break
    return out


# ---- Thin DB ops ----


def upsert_profile(
    user_id: str,
    parsed: dict[str, Any],
    resume_hash: str | None = None,
    resume_filename: str | None = None,
) -> dict[str, Any]:
    """Create the profile doc on first onboarding, replace fields on re-upload."""
    from backend.database.collections import get_job_profiles_collection

    set_doc = build_profile_update(parsed, resume_hash, resume_filename)
    get_job_profiles_collection().update_one(
        {"user_id": user_id},
        {
            "$set": set_doc,
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": _utcnow(),
            },
        },
        upsert=True,
    )
    return {}


def get_profile(user_id: str) -> dict[str, Any] | None:
    """Read by the agent graph. Returns None when the user never onboarded."""
    from backend.database.collections import get_job_profiles_collection

    return get_job_profiles_collection().find_one({"user_id": user_id})


def get_profile_summary(user_id: str) -> dict[str, Any] | None:
    """Slim projection for GET /api/jobs/profile — no internal bookkeeping."""
    from backend.database.collections import get_job_profiles_collection

    projection = {
        # _id is an ObjectId and cannot be JSON-serialised — exclude it.
        "_id": 0,
        "name": 1,
        "target_roles": 1,
        "skills": 1,
        "experience_level": 1,
        "employment_type": 1,
        "locations": 1,
        "work_mode": 1,
        "preferences": 1,
        "links": 1,
        "projects": 1,
        "education": 1,
        "experience": 1,
        "resume_filename": 1,
        "updated_at": 1,
    }
    return get_job_profiles_collection().find_one({"user_id": user_id}, projection)


def update_preferences(
    user_id: str,
    target_roles: list[str] | None = None,
    locations: list[str] | None = None,
    work_mode: list[str] | None = None,
) -> bool:
    """Optional follow-up: let the user adjust roles/locations saved at onboarding."""
    from backend.database.collections import get_job_profiles_collection

    set_doc: dict[str, Any] = {}
    if target_roles is not None:
        set_doc["target_roles"] = _str_list(target_roles, MAX_ROLES)
    if locations is not None:
        set_doc["locations"] = _str_list(locations, MAX_LOCATIONS)
    if work_mode is not None:
        set_doc["work_mode"] = _str_list(work_mode, 3)
    if not set_doc:
        return False
    set_doc["updated_at"] = _utcnow()
    res = get_job_profiles_collection().update_one({"user_id": user_id}, {"$set": set_doc})
    return res.matched_count > 0


def delete_profile(user_id: str) -> bool:
    """Clear stored skills so /jobs shows the onboarding prompt again."""
    from backend.database.collections import get_job_profiles_collection

    res = get_job_profiles_collection().delete_one({"user_id": user_id})
    if res.deleted_count:
        # The stored PDF goes with the profile — never leave an orphaned file.
        try:
            from backend.database.job_resume_files import delete_resume_pdf

            delete_resume_pdf(user_id)
        except Exception:
            pass
    return res.deleted_count > 0


def has_profile(user_id: str) -> bool:
    from backend.database.collections import get_job_profiles_collection

    doc = get_job_profiles_collection().find_one(
        {"user_id": user_id, "skills": {"$exists": True, "$ne": []}}, {"_id": 1}
    )
    return doc is not None
