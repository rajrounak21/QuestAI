from __future__ import annotations

import logging
from typing import Any

import uuid

from fastapi import APIRouter, File, Form, Header, UploadFile

from fastapi.responses import Response

from job_agent.agent.job_agent import run_job_search
from job_agent.services.job_memory import get_session, save_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

MAX_PDF_BYTES = 5 * 1024 * 1024


@router.post("/search")
async def search_jobs(
    query: str | None = Form(default=None),
    resume: UploadFile | None = File(default=None),
    locations: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    x_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Supports multipart: query text + optional resume PDF + optional follow-up locations."""
    # session handling for memory (skills)
    eff_session = session_id or x_session_id or str(uuid.uuid4())
    logger.info(f"Job search request: query='{query}' resume={resume.filename if resume else None} locations={locations} session={eff_session}")

    resume_bytes: bytes | None = None
    if resume is not None:
        try:
            content = await resume.read()
            if len(content) > MAX_PDF_BYTES:
                return {"jobs": [], "total_results": 0, "error": "Resume too large (max 5MB)."}
            if resume.content_type and "pdf" not in resume.content_type.lower() and not resume.filename.lower().endswith(".pdf"):
                return {"jobs": [], "total_results": 0, "error": "Please upload a PDF resume."}
            resume_bytes = content
            logger.info(f"Resume received: {len(content)} bytes")
        except Exception as e:
            logger.error(f"Resume read failed: {e}")
            return {"jobs": [], "total_results": 0, "error": f"Failed to read resume: {e}"}

    extra_locations: list[str] | None = None
    if locations:
        extra_locations = [s.strip() for s in locations.split(",") if s.strip()][:4]

    # Augment query with locations if follow-up
    effective_query = query or ""
    if extra_locations and not query:
        # resume-only + follow-up locations
        effective_query = f"jobs in {', '.join(extra_locations)}"
    elif extra_locations and query:
        # if query already has locations, don't duplicate; check if profile will have them
        # simple append if not already present
        loc_lower = effective_query.lower()
        missing = [l for l in extra_locations if l.lower() not in loc_lower]
        if missing:
            effective_query = f"{effective_query} in {', '.join(missing)}"

    result = run_job_search(user_query=effective_query, resume_bytes=resume_bytes, session_id=eff_session)

    # save memory for Phase 3 (keep enriched resume data + raw_text)
    try:
        if result.get("profile"):
            # include resume_text from result for memory
            prof = dict(result["profile"])
            if result.get("resume_text"):
                prof["raw_text"] = result["resume_text"]
            save_session(eff_session, prof, resume_bytes, resume_text=result.get("resume_text"))
    except Exception as e:
        logger.warning(f"save_session failed: {e}")

    # --- Phase 2 deterministic matching ---
    try:
        from job_agent.services.job_matcher import match_jobs
        profile = result.get("profile") or {}
        user_skills = profile.get("skills") or []
        jobs = result.get("jobs") or []
        if jobs and user_skills:
            result["jobs"] = match_jobs(user_skills, jobs)
        elif jobs:
            # no resume skills → still set 0% for consistent frontend
            for j in jobs:
                j["matched_skills"] = []
                j["missing_skills"] = []
                j["matched_count"] = 0
                j["total_user_skills"] = 0
                j["match_percentage"] = 0
    except Exception as e:
        logger.warning(f"job matching failed: {e}")

    base: dict[str, Any] = {"session_id": eff_session}
    if result.get("error"):
        return {
            **base,
            "profile": result.get("profile"),
            "jobs": [],
            "total_results": 0,
            "error": result["error"],
            "progress_steps": result.get("progress_steps", []),
        }

    if result.get("follow_up_question"):
        return {
            **base,
            "profile": result.get("profile"),
            "jobs": [],
            "total_results": 0,
            "follow_up_question": result["follow_up_question"],
            "progress_steps": result.get("progress_steps", []),
        }

    return {
        **base,
        "profile": result.get("profile"),
        "jobs": result.get("jobs", []),
        "total_results": result.get("total_results", 0),
        "search_requests": result.get("search_requests"),
        "progress_steps": result.get("progress_steps", []),
    }


@router.post("/search-json")
async def search_jobs_json(body: dict[str, Any]) -> dict[str, Any]:
    """JSON alternative: {query: str, locations?: str, session_id?: str} — no file upload."""
    query = (body.get("query") or "").strip()
    locations = body.get("locations")
    session_id = body.get("session_id") or str(uuid.uuid4())
    extra = None
    if locations:
        extra = [s.strip() for s in locations.split(",") if s.strip()][:4]
    # same augmentation as multipart
    effective = query
    if extra:
        if not effective:
            effective = f"jobs in {', '.join(extra)}"
        else:
            missing = [l for l in extra if l.lower() not in effective.lower()]
            if missing:
                effective = f"{effective} in {', '.join(missing)}"

    result = run_job_search(user_query=effective, resume_bytes=None, session_id=session_id)

    try:
        if result.get("profile"):
            save_session(session_id, result["profile"], None)
    except Exception:
        pass

    # --- Phase 2 deterministic matching ---
    try:
        from job_agent.services.job_matcher import match_jobs
        profile = result.get("profile") or {}
        user_skills = profile.get("skills") or []
        jobs = result.get("jobs") or []
        if jobs and user_skills:
            result["jobs"] = match_jobs(user_skills, jobs)
        elif jobs:
            for j in jobs:
                j["matched_skills"] = []
                j["missing_skills"] = []
                j["matched_count"] = 0
                j["total_user_skills"] = 0
                j["match_percentage"] = 0
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"job matching failed: {e}")

    base = {"session_id": session_id}
    if result.get("error"):
        return {**base, "profile": result.get("profile"), "jobs": [], "total_results": 0, "error": result["error"], "progress_steps": result.get("progress_steps", [])}
    if result.get("follow_up_question"):
        return {**base, "profile": result.get("profile"), "jobs": [], "total_results": 0, "follow_up_question": result["follow_up_question"], "progress_steps": result.get("progress_steps", [])}
    return {**base, "profile": result.get("profile"), "jobs": result.get("jobs", []), "total_results": result.get("total_results", 0), "search_requests": result.get("search_requests"), "progress_steps": result.get("progress_steps", [])}


@router.post("/prepare")
async def prepare_application(body: dict[str, Any]) -> dict[str, Any]:
    """Phase 3 step 1: Analyze resume + job → structured analysis (1 LLM, cached)."""
    session_id = (body.get("session_id") or "").strip()
    job_id = (body.get("job_id") or "").strip()
    job_data = body.get("job")
    force = body.get("force", False)
    if not session_id:
        return {"error": "session_id required (from search). Upload resume first."}
    sess = get_session(session_id)
    if not sess:
        return {"error": "Session expired or not found. Please search again."}
    if not job_data:
        return {"error": "job data required. Send selected job object."}
    # Return cached if same job and not forced — escapes LLM
    if not force and sess.get("_analysis") and sess.get("_job", {}).get("id") == job_data.get("id"):
        logger.info(f"Prepare cache hit for {job_id}, skipping LLM")
        return {"analysis": sess["_analysis"], "session_id": session_id, "cached": True}
    resume_data = sess.get("profile") or {}
    if not resume_data.get("raw_text") and sess.get("resume_text"):
        resume_data["raw_text"] = sess["resume_text"]
    try:
        from job_agent.services.application_analyzer import analyze_application
        analysis = analyze_application(resume_data, job_data)
        sess["_analysis"] = analysis.model_dump()
        sess["_job"] = job_data
        sess["_ts"] = __import__("time").time()
        return {"analysis": analysis.model_dump(), "session_id": session_id, "cached": False}
    except Exception as e:
        logger.exception(f"Prepare failed: {e}")
        return {"error": f"Analysis failed: {e}"}


@router.post("/generate-cv")
async def generate_cv(body: dict[str, Any]) -> Response:
    """Phase 3 step 2: Generate tailored CV PDF (fpdf2, no LLM) — ephemeral file response."""
    session_id = (body.get("session_id") or "").strip()
    job_id = (body.get("job_id") or "").strip()
    job_data = body.get("job")
    analysis_data = body.get("analysis")
    if not session_id:
        return Response(content=b'{"error":"session_id required"}', status_code=400, media_type="application/json")
    sess = get_session(session_id)
    if not sess:
        return Response(content=b'{"error":"Session expired"}', status_code=400, media_type="application/json")
    resume_data = sess.get("profile") or {}
    if not resume_data.get("raw_text") and sess.get("resume_text"):
        resume_data["raw_text"] = sess["resume_text"]
    # Prefer passed job/analysis, else cached
    if not job_data:
        job_data = sess.get("_job")
    if not analysis_data:
        analysis_data = sess.get("_analysis")
    if not job_data:
        return Response(content=b'{"error":"job data required"}', status_code=400, media_type="application/json")
    if not analysis_data:
        # analyze on fly if missing
        try:
            from job_agent.services.application_analyzer import analyze_application
            analysis_obj = analyze_application(resume_data, job_data)
            analysis_data = analysis_obj.model_dump()
        except Exception as e:
            return Response(content=f'{{"error":"analysis missing: {e}"}}'.encode(), status_code=400, media_type="application/json")
    try:
        from job_agent.services.cv_generator import generate_cv_pdf
        pdf_bytes = generate_cv_pdf(resume_data, analysis_data, job_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="CV_{resume_data.get("name","Candidate")}_{job_data.get("title","Job")[:20]}.pdf"'},
        )
    except Exception as e:
        logger.exception(f"CV generation failed: {e}")
        return Response(content=f'{{"error":"CV generation failed: {e}"}}'.encode(), status_code=500, media_type="application/json")
