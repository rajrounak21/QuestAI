from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.agents.job.main import run_job_search
from backend.auth.security import get_current_user
from backend.database.job_profiles import (
    delete_profile,
    get_profile_summary,
    has_profile,
    update_preferences,
    upsert_profile,
)
from backend.database.job_resume_files import (
    get_resume_pdf,
    has_resume_pdf,
    save_resume_pdf,
)
from backend.database.job_sessions import (
    delete_session,
    get_session_with_latest_search,
    insert_search,
    list_session_history,
    upsert_session_on_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

MAX_PDF_BYTES = 5 * 1024 * 1024


class SearchIn(BaseModel):
    query: str | None = None
    locations: str | None = None
    session_id: str | None = None


class PreferencesIn(BaseModel):
    target_roles: list[str] | None = None
    locations: list[str] | None = None
    work_mode: list[str] | None = None


# ---- helpers ----


def _run_and_match(
    user_id: str,
    query: str,
    locations: list[str] | None,
    resume_bytes: bytes | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run the graph, then apply deterministic skill matching. Never raises for
    agent-level failure — the result carries `error` / `follow_up_question`."""
    result = run_job_search(
        user_id=user_id,
        user_query=query,
        locations=locations,
        resume_bytes=resume_bytes,
    )

    profile = result.get("profile") or {}
    user_skills = profile.get("skills") or []
    jobs = result.get("jobs") or []

    # Seniority gate. Skill matching only scores, it never excludes, so without
    # this a resume parsed as "internship" still showed 8+ years postings.
    # Runs before matching so the cards the user sees are all eligible ones.
    level = profile.get("experience_level")
    if jobs and level:
        from backend.agents.job.services.job_seniority import filter_by_seniority

        jobs, dropped = filter_by_seniority(jobs, level)
        if dropped:
            logger.info(
                f"Seniority filter ({level}): dropped {len(dropped)} of "
                f"{len(jobs) + len(dropped)} jobs"
            )
        result["seniority_excluded"] = len(dropped)
        result["seniority_level"] = level

    if jobs and user_skills:
        from backend.agents.job.services.job_matcher import match_jobs

        jobs = match_jobs(user_skills, jobs)
    elif jobs:
        # No stored skills yet — keep the response shape stable at 0% so the
        # frontend renders the same card layout either way.
        for j in jobs:
            j["matched_skills"] = []
            j["missing_skills"] = []
            j["matched_count"] = 0
            j["total_user_skills"] = 0
            j["match_percentage"] = 0
    result["jobs"] = jobs
    # Keep the header count honest — it must match what is actually rendered.
    result["total_results"] = len(jobs)
    return result, jobs


def _locations_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    return parts[:4] or None


# NOTE: static paths are declared before /{session_id} on purpose. FastAPI
# matches routes in declaration order, so /profile, /search, /history and
# /alerts/* would otherwise be swallowed by the dynamic segment.


# ---- profile / onboarding ----


@router.get("/profile")
def read_profile(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """First call on /jobs. profile == None means the user still needs to onboard."""
    profile = get_profile_summary(user["id"])
    return {"profile": profile, "has_resume_pdf": has_resume_pdf(user["id"])}


@router.post("/profile")
async def create_or_replace_profile(
    resume: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Onboarding: upload the resume once, store the extracted skills."""
    content = await resume.read()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="Resume too large (max 5MB).")
    if not content:
        raise HTTPException(status_code=400, detail="Resume is empty.")
    filename = (resume.filename or "").strip()
    if resume.content_type and "pdf" not in resume.content_type.lower() and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF resume.")

    from backend.agents.job.services.resume_vision import parse_resume_pdf

    try:
        parsed = parse_resume_pdf(content)
    except Exception as e:
        logger.exception("Resume parse failed")
        raise HTTPException(status_code=502, detail=f"Resume parsing failed: {e}") from e

    if not parsed.get("skills"):
        raise HTTPException(
            status_code=422,
            detail="Could not find any skills in that resume. Try a text-based PDF.",
        )

    resume_hash = hashlib.md5(content).hexdigest()[:12]
    doc = upsert_profile(user["id"], parsed, resume_hash=resume_hash, resume_filename=filename)

    # Keep the PDF for preview. Replaces any previous resume — never appends.
    try:
        save_resume_pdf(user["id"], content, filename)
    except Exception:
        # The profile is already saved; a missing preview must not fail onboarding.
        logger.exception("Resume PDF storage failed (profile still saved)")

    logger.info(
        f"Profile saved user={user['id']} skills={len(parsed.get('skills', []))} "
        f"projects={len(parsed.get('projects', []) or [])} "
        f"education={len(parsed.get('education', []) or [])} "
        f"experience={len(parsed.get('experience', []) or [])}"
    )
    return {"profile": get_profile_summary(user["id"]), "saved": True}


@router.get("/profile/resume")
def read_resume_pdf(user: dict = Depends(get_current_user)) -> Response:
    """Stream the stored resume PDF for the profile panel preview."""
    content = get_resume_pdf(user["id"])
    if not content:
        raise HTTPException(status_code=404, detail="No resume stored")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@router.patch("/profile")
def patch_profile(
    body: PreferencesIn,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Let the user correct roles/locations later without a re-upload."""
    ok = update_preferences(
        user["id"],
        target_roles=body.target_roles,
        locations=body.locations,
        work_mode=body.work_mode,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="No profile to update. Upload a resume first.")
    return {"profile": get_profile_summary(user["id"])}


@router.delete("/profile")
def clear_profile(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    deleted = delete_profile(user["id"])
    return {"deleted": deleted, "session_id": None}


# ---- search ----


@router.post("/search")
async def search(
    query: str | None = Form(default=None),
    resume: UploadFile | None = File(default=None),
    locations: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Main search. `resume` is optional — after onboarding the stored profile
    supplies the skills, so the user never uploads it again."""
    user_id = user["id"]
    sid = session_id or str(uuid.uuid4())
    extra_locations = _locations_list(locations)

    resume_bytes: bytes | None = None
    if resume is not None:
        content = await resume.read()
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(status_code=400, detail="Resume too large (max 5MB).")
        resume_bytes = content or None

    if not (query or "").strip() and not extra_locations and resume_bytes is None:
        raise HTTPException(status_code=400, detail="Provide a query, locations, or a resume.")

    # Human-in-the-loop gate: with no stored skills every result would score 0%,
    # which is unusable. Force the resume upload instead of returning dead results.
    if resume_bytes is None and not has_profile(user_id):
        raise HTTPException(status_code=409, detail="resume_required")

    result, jobs = _run_and_match(
        user_id,
        (query or "").strip(),
        extra_locations,
        resume_bytes,
    )
    logger.info(f"Job search user={user_id} session={sid} jobs={len(jobs)}")

    profile = result.get("profile") or {}

    if result.get("error"):
        return {
            "session_id": sid,
            "profile": profile,
            "jobs": [],
            "total_results": 0,
            "error": result["error"],
            "progress_steps": result.get("progress_steps", []),
        }
    if result.get("follow_up_question"):
        return {
            "session_id": sid,
            "profile": profile,
            "jobs": [],
            "total_results": 0,
            "follow_up_question": result["follow_up_question"],
            "progress_steps": result.get("progress_steps", []),
        }

    upsert_session_on_search(
        user_id,
        sid,
        (query or "").strip(),
        len(jobs),
        target_roles=profile.get("target_roles") or [],
        locations=profile.get("locations") or [],
        work_mode=profile.get("work_mode") or [],
    )
    insert_search(user_id, sid, (query or "").strip(), jobs)

    return {
        "session_id": sid,
        "profile": profile,
        "jobs": jobs,
        "total_results": result.get("total_results", len(jobs)),
        "search_requests": result.get("search_requests"),
        "progress_steps": result.get("progress_steps", []),
    }


# ---- history ----


@router.get("/history")
def history(limit: int = 20, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    items = list_session_history(user["id"], limit=limit)
    for it in items:
        if it.get("_id") is not None:
            it["_id"] = str(it["_id"])
    return {"items": items}


@router.get("/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    session, latest = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="job session not found")
    if session.get("_id") is not None:
        session["_id"] = str(session["_id"])
    if latest and latest.get("_id") is not None:
        latest["_id"] = str(latest["_id"])
    return {"session": session, "latest": latest}


@router.post("/{session_id}/search")
def search_again(
    session_id: str,
    body: SearchIn,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Re-run inside an existing session. Reuses the stored profile's skills."""
    session, _ = get_session_with_latest_search(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="job session not found")

    query = (body.query or session.get("query") or "").strip()
    extra_locations = _locations_list(body.locations)
    if not query and not extra_locations:
        raise HTTPException(status_code=400, detail="Query is empty")

    # Same resume gate as the main search — a re-search without skills is useless.
    if not has_profile(user["id"]):
        raise HTTPException(status_code=409, detail="resume_required")

    result, jobs = _run_and_match(user["id"], query, extra_locations, None)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    if result.get("follow_up_question"):
        raise HTTPException(status_code=422, detail=result["follow_up_question"])

    profile = result.get("profile") or {}
    upsert_session_on_search(
        user["id"],
        session_id,
        query,
        len(jobs),
        target_roles=profile.get("target_roles") or [],
        locations=profile.get("locations") or [],
        work_mode=profile.get("work_mode") or [],
    )
    insert_search(user["id"], session_id, query, jobs)
    return {
        "session_id": session_id,
        "profile": profile,
        "jobs": jobs,
        "total_results": result.get("total_results", len(jobs)),
        "search_requests": result.get("search_requests"),
        "progress_steps": result.get("progress_steps", []),
    }


@router.delete("/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    deleted = delete_session(user["id"], session_id)
    return {"deleted": deleted, "session_id": session_id}
