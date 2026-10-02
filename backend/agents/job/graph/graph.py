from __future__ import annotations

import json
import logging
import operator
import re
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.job.graph.state import JobState

logger = logging.getLogger(__name__)


# --- helpers ---
def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # reuse robust repair from resume_vision
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        # fallback regex extract
        def _list(k):
            m = re.search(rf'"{re.escape(k)}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if not m:
                return []
            return re.findall(r'"([^"]+)"', m.group(1))
        def _bool(k):
            m = re.search(rf'"{re.escape(k)}"\s*:\s*(true|false)', text, re.IGNORECASE)
            return m and m.group(1).lower() == "true"
        if '"is_not_job"' in text.lower():
            return {"is_not_job": True}
        # check for target_roles
        if '"target_roles"' in text or '"locations"' in text:
            return {
                "target_roles": _list("target_roles")[:4],
                "locations": _list("locations")[:4],
                "work_mode": _list("work_mode"),
                "employment_type": _list("employment_type"),
                "preferences": _list("preferences"),
            }
        if '"searches"' in text:
            # parse searches array manually
            searches = []
            for m in re.finditer(r'"q"\s*:\s*"([^"]+)"\s*,\s*"location"\s*:\s*"([^"]+)"', text):
                searches.append({"q": m.group(1), "location": m.group(2)})
            if searches:
                return {"searches": searches}
        raise


def _get_fast_llm():
    import os
    from dotenv import load_dotenv
    from langchain_groq import ChatGroq

    load_dotenv(override=True)
    return ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.0,
        max_tokens=800,
        api_key=os.getenv("GROQ_API_KEY"),
    )


# --- Nodes ---
def input_analyzer(state: JobState) -> dict[str, Any]:
    logger.info("Running input_analyzer")
    q = (state.get("user_query") or "").strip()
    has_resume = state.get("resume_bytes") is not None
    has_query = bool(q)

    if not has_query and not has_resume:
        return {
            "follow_up_question": "Tell me what job you're looking for, or upload your resume. For example: 'Python backend internships in India, preferably remote.'",
            "search_complete": True,
            "progress_steps": ["Waiting for input: query or resume"],
        }

    mode = "query+resume" if (has_query and has_resume) else ("resume_only" if has_resume else "query_only")
    return {"progress_steps": [f"Input mode: {mode}"]}


def _quick_parse_simple_query(q: str) -> dict[str, Any] | None:
    """Fast path for inline secondary search like 'AI Engineer in Delhi' — no LLM."""
    if not q:
        return None
    # Generic placeholder like "jobs in Delhi" should NOT create fake role "jobs"
    if q.strip().lower().startswith("jobs in ") and len(q.strip().split()) <= 6:
        loc_part = q.strip()[8:].strip(" ,")
        locs = [p.strip() for p in re.split(r",|\band\b", loc_part) if p.strip()]
        cleaned = [l for l in locs if l.lower() not in ["remote","hybrid","onsite"]]
        if cleaned:
            wm = [w for w in ["remote","hybrid","onsite"] if w in q.lower()]
            return {"target_roles": [], "locations": cleaned[:4], "work_mode": wm, "employment_type": [], "preferences": []}
        return None
    # If long/complex, let LLM handle
    if len(q) > 60 or len(q.split()) > 8:
        return None
    filler = {"please","find","search","for","me","i","want","need","looking","preferably","remote","hybrid","onsite"}
    tokens_lower = q.lower().split()
    if sum(1 for t in tokens_lower if t in filler) >= 4:
        return None
    locations: list[str] = []
    work_mode: list[str] = []
    for wm in ["remote", "hybrid", "onsite"]:
        if wm in q.lower():
            work_mode.append(wm)
    if " in " in q.lower():
        lower = q.lower()
        idx = lower.rfind(" in ")
        role_part = q[:idx].strip(" ,")
        loc_part = q[idx + 4 :].strip(" ,")
        # extract remote/hybrid/onsite from loc_part even when combined like "Bangalore remote"
        for wm in ["remote","hybrid","onsite","on-site"]:
            if re.search(r"\b" + re.escape(wm) + r"\b", loc_part, re.IGNORECASE):
                if wm.lower().replace("-","") not in [w.lower() for w in work_mode]:
                    work_mode.append("remote" if wm=="remote" else ("onsite" if "onsite" in wm else wm))
                loc_part = re.sub(r"\b" + re.escape(wm) + r"\b", " ", loc_part, flags=re.IGNORECASE)
        locs = [p.strip() for p in re.split(r",|\band\b", loc_part) if p.strip()]
        cleaned_locs = []
        for loc in locs:
            if not loc or loc.lower() in ["remote","hybrid","onsite","on-site"]:
                continue
            cleaned_locs.append(" ".join(loc.split()))  # collapse spaces
        # ignore generic role_part like "jobs"
        if role_part.lower() in ["jobs","job"]:
            role_part = ""
        if role_part and cleaned_locs:
            # support multiple roles comma separated e.g. "Python Developer, AI Engineer"
            roles = [r.strip() for r in role_part.split(",") if r.strip()]
            return {
                "target_roles": [r[:60] for r in roles][:3],
                "locations": cleaned_locs[:4],
                "work_mode": work_mode,
                "employment_type": [],
                "preferences": [],
            }
        if role_part and not cleaned_locs and work_mode:
            roles = [r.strip() for r in role_part.split(",") if r.strip()]
            return {
                "target_roles": [r[:60] for r in roles][:3],
                "locations": [],
                "work_mode": work_mode,
                "employment_type": [],
                "preferences": [],
            }
        if not role_part and cleaned_locs:
            return {"target_roles": [], "locations": cleaned_locs[:4], "work_mode": work_mode, "employment_type": [], "preferences": []}
    if len(q.split()) <= 5 and len(q) <= 40:
        if q.lower() in ["jobs","job"]:
            return {"target_roles": [], "locations": [], "work_mode": work_mode, "employment_type": [], "preferences": []}
        if any(c.isalpha() for c in q):
            # comma separated roles
            roles = [r.strip() for r in q.split(",") if r.strip()]
            return {
                "target_roles": [r[:60] for r in roles][:3],
                "locations": [],
                "work_mode": work_mode,
                "employment_type": [],
                "preferences": [],
            }
    return None


def resume_vision_parser(state: JobState) -> dict[str, Any]:
    logger.info("Running resume_vision_parser")
    pdf_bytes = state.get("resume_bytes")
    if not pdf_bytes:
        # No upload — reuse the skills stored at onboarding, so the user never
        # has to upload the same resume twice.
        user_id = state.get("user_id")
        if user_id:
            try:
                from backend.database.job_profiles import get_profile

                mem = get_profile(user_id)
                if mem and mem.get("skills"):
                    skills = mem.get("skills", [])
                    logger.info(f"Reusing stored profile skills: {len(skills)} skills")
                    return {
                        "resume_profile": {
                            "target_roles": mem.get("target_roles", []),
                            "skills": skills,
                            "experience_level": mem.get("experience_level"),
                            "employment_type": mem.get("employment_type", []),
                            "locations": [],
                            "work_mode": mem.get("work_mode", []),
                            "preferences": mem.get("preferences", []),
                        },
                        "resume_text": "",
                        "progress_steps": [f"Reused saved profile: {len(skills)} skills"],
                    }
            except Exception as e:
                logger.warning(f"Stored profile reuse failed: {e}")
        return {"progress_steps": ["No resume: skipping vision parse"]}

    try:
        from backend.agents.job.services.resume_vision import parse_resume_pdf

        result = parse_resume_pdf(pdf_bytes)
        # normalize to profile — include enriched fields for Phase 3
        profile = {
            "target_roles": result.get("target_roles", []) or [],
            "skills": result.get("skills", []) or [],
            "experience_level": result.get("experience_level"),
            "employment_type": result.get("employment_type", []) or [],
            "locations": result.get("locations", []) or [],
            "work_mode": result.get("work_mode", []) or [],
            "preferences": result.get("preferences", []) or [],
            "projects": result.get("projects", []) or [],
            "education": result.get("education", []) or [],
            "experience": result.get("experience", []) or [],
            "name": result.get("name"),
            "links": result.get("links", []) or [],
            "raw_text": result.get("raw_text", "") or "",
        }
        raw_text = result.get("raw_text", "") or ""
        logger.info(f"Resume parsed: roles={profile['target_roles']} skills={len(profile['skills'])} proj={len(profile['projects'])} edu={len(profile['education'])}")
        return {
            "resume_profile": profile,
            "resume_text": raw_text,
            "progress_steps": [f"Parsed resume: {', '.join(profile['target_roles'][:2]) or 'no roles detected'} ({len(raw_text)} chars, {len(profile['projects'])} projects)"],
        }
    except Exception as e:
        logger.warning(f"Resume vision parse failed: {e}")
        return {
            "resume_profile": {"target_roles": [], "skills": [], "experience_level": None, "employment_type": [], "locations": [], "work_mode": [], "preferences": []},
            "resume_text": "",
            "progress_steps": [f"Resume parse failed: {e}"],
        }


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0]*len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + cost)
        prev = cur
    return prev[-1]

def _needs_correction(parsed: dict[str, Any]) -> bool:
    """Gate for conditional LLM2 — true if any token looks like typo vs vocab."""
    try:
        from backend.agents.job.services.skill_normalizer import ROLE_VOCAB, LOCATION_VOCAB, ALIAS_MAP
        vocab = set([v.lower() for v in ROLE_VOCAB + LOCATION_VOCAB + list(ALIAS_MAP.keys()) + list(ALIAS_MAP.values())])
        # add plurals and common variants to avoid false positives
        vocab.update(["internships","interns","developers","engineers"])
        skip = {"internship","internships","intern","jobs","job","in","and","or"}
        for field in ["target_roles","locations"]:
            for phrase in parsed.get(field, []) or []:
                for tok in re.split(r"\s+", phrase.lower()):
                    tok = tok.strip(" ,.-")
                    if not tok or len(tok) < 3 or tok in skip:
                        continue
                    if tok in vocab or tok.rstrip("s") in vocab:
                        continue
                    # typo gate - check edit distance 1-2
                    for v in vocab:
                        if abs(len(v)-len(tok)) > 2:
                            continue
                        if len(tok) >= 5 and _levenshtein(tok, v) == 1:
                            return True
                        if len(tok) >= 6 and _levenshtein(tok, v) == 2:
                            # only for longer words to avoid false
                            if tok not in ["backend","frontend"]:
                                return True
                    if tok in ["gujrat","banglore","gurgram","enginner","enginerr","devloper","pyhton"]:
                        return True
        return False
    except Exception:
        return False

def _deterministic_query_parse(q: str) -> dict[str, Any]:
    """Fully deterministic parse — no LLM. Handles modals + free text."""
    original = q
    lower = q.lower()
    work_mode: list[str] = []
    for wm in ["remote", "hybrid", "onsite", "on-site"]:
        if wm in lower:
            work_mode.append("remote" if wm == "remote" else ("onsite" if "onsite" in wm else wm))
            lower = lower.replace(wm, " ")
            lower = lower.replace("on-site", " ")
    # deduplicate work_mode
    work_mode = list(dict.fromkeys(work_mode))

    employment_type: list[str] = []
    for et, key in [("internship", "intern"), ("full-time", "full"), ("contract", "contract")]:
        if key in lower:
            employment_type.append(et)
            # keep word for role detection? remove only full phrase later

    # Location extraction — known India cities + generic
    KNOWN_LOCS = ["india","delhi","bangalore","bengaluru","patna","mumbai","pune","hyderabad","chennai","kolkata","gurgaon","gurugram","noida","greater noida","charkhi dadri","haryana","rewa","vasai-virar","navi mumbai","shahapur","jawhar","poladpur","mokhada","kolkata","bihar","andhra pradesh","karnataka","gandhi nagar","ambala","hisar","bhiwani","palwal","charkhi dadri","austin","texas"]
    locations: list[str] = []
    for loc in KNOWN_LOCS:
        if re.search(r"\b" + re.escape(loc) + r"\b", lower):
            # capitalize properly
            cap = loc.title() if loc != "india" else "India"
            if loc == "bengaluru": cap = "Bengaluru"
            if loc == "austin": cap = "Austin, Texas, United States"
            locations.append(cap)
            # remove from lower to avoid polluting role
            lower = re.sub(r"\b" + re.escape(loc) + r"\b", " ", lower)

    # Also catch " in <City>" pattern for unknown cities (incl typos like Gujrat)
    m = re.search(r"\bin\s+([a-zA-Z ,]+?)(?:\bremote\b|\bhybrid\b|\bonsite\b|$)", original, re.IGNORECASE)
    if m and not locations:
        cand = m.group(1).strip(" ,")
        # split comma
        parts = [p.strip().title() for p in cand.split(",") if p.strip()]
        # filter out generic job words
        filtered = [p for p in parts if p.lower() not in ["india","remote","jobs","job"]]
        if filtered:
            locations.extend(filtered[:2])
            # remove these from lower to not pollute role
            for loc in filtered:
                lower = re.sub(r"\b" + re.escape(loc.lower()) + r"\b", " ", lower)

    # Clean residual q for target role
    # Remove filler words
    filler = {"find","search","for","me","i","want","need","looking","preferably","please","show","give","get","the","a","an","in","to","of","and","or","internship","intern","jobs","job"}
    # Remove employment words from role core but keep role title
    lower_clean = re.sub(r"\b(internship|intern|full-time|full time|contract)\b", " ", lower, flags=re.IGNORECASE)
    tokens = [t for t in re.split(r"\s+", lower_clean.strip()) if t and t.lower() not in filler]
    # Also strip locations already removed
    target = " ".join(tokens).strip(" ,")
    # Title case role, handle AI/ML etc
    target_roles: list[str] = []
    if target:
        # Split by " or " / " and " for multiple roles
        parts = re.split(r"\s+or\s+|\s+and\s+|,", target, flags=re.IGNORECASE)
        for p in parts:
            p = p.strip()
            if not p or len(p) < 2:
                continue
            # Filter non-role noise
            if p.lower() in ["python","ai","backend","frontend","developer","engineer","data","science"] and len(p.split())==1:
                # keep single word roles too
                pass
            target_roles.append(p.title().replace("Ai", "AI").replace("Ml", "ML")[:60])
            if len(target_roles) >= 3:
                break
        # If still empty but original had words, fallback to original first 4 words title
        if not target_roles and original.strip():
            cand = original.strip().split()
            # remove locations already extracted
            cand = [c for c in cand if c.lower() not in ["in","india","remote"]]
            if cand:
                target_roles = [" ".join(cand[:4]).title()]

    # Deduplicate
    locations = list(dict.fromkeys(locations))[:4]
    target_roles = list(dict.fromkeys(target_roles))[:3]

    # Detect non-job query: if no role and no location and looks like weather/chat
    if not target_roles and not locations and any(w in original.lower() for w in ["weather","hotel","flight","salary of ceo","meaning of life"]):
        return {"target_roles":[],"locations":[],"work_mode":[],"employment_type":[],"preferences":[],"is_not_job": True}

    return {
        "target_roles": target_roles,
        "locations": locations,
        "work_mode": work_mode,
        "employment_type": employment_type,
        "preferences": [],
    }

def query_analyzer(state: JobState) -> dict[str, Any]:
    logger.info("Running query_analyzer (deterministic, conditional LLM2 for typo)")
    q = (state.get("user_query") or "").strip()
    if not q:
        return {"query_profile": {"target_roles": [], "locations": [], "work_mode": [], "employment_type": [], "preferences": []}, "progress_steps": ["No text query: using resume only"]}

    # Try fast structured parse first
    quick = _quick_parse_simple_query(q)
    if quick:
        # Gate typo correction for structured input like "Gujrat, enginner"
        if _needs_correction(quick):
            logger.info(f"Typo detected in quick parse {quick}, invoking LLM2 correction")
            corrected = _llm_correct_query(q)
            if corrected:
                return {"query_profile": corrected, "progress_steps": [f"Query corrected: {corrected['target_roles']}"]}
        logger.info(f"Deterministic quick parse (no LLM): {quick}")
        return {"query_profile": quick, "progress_steps": [f"Query: {quick['target_roles'][0] if quick['target_roles'] else q[:40]}"]}

    det = _deterministic_query_parse(q)
    if det.get("is_not_job"):
        return {"query_profile": {**det}, "progress_steps": ["Query not job-related"]}
    if _needs_correction(det):
        logger.info(f"Typo detected in deterministic parse {det}, invoking LLM2 correction")
        corrected = _llm_correct_query(q)
        if corrected:
            return {"query_profile": corrected, "progress_steps": [f"Query corrected: {corrected['target_roles']}"]}
    logger.info(f"Deterministic query parse (no LLM): {det}")
    return {"query_profile": det, "progress_steps": [f"Query: {', '.join(det['target_roles'][:2]) or q[:40]}"]}

def _llm_correct_query(q: str) -> dict[str, Any] | None:
    """Conditional LLM2 — correct typos like Gujrat->Gujarat, enginner->Engineer. Single call."""
    try:
        llm = _get_fast_llm()
        prompt = f"""Correct typos in this job search query. Return ONLY JSON:
{{"target_roles":["role"],"locations":["loc"],"work_mode":[],"employment_type":[]}}
Rules:
- Fix spelling: Gujrat->Gujarat, Banglore->Bangalore, enginner->Engineer, devloper->Developer, etc.
- Keep 1-3 roles, 1-4 locations, work_mode remote/hybrid/onsite only if present
- If no typo, return same intent
Query: {q}"""
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        data = _parse_json(text)
        # sanitize
        return {
            "target_roles": [str(x).strip()[:60] for x in data.get("target_roles", []) if str(x).strip()][:3],
            "locations": [str(x).strip() for x in data.get("locations", []) if str(x).strip()][:4],
            "work_mode": [str(x).strip().lower() for x in data.get("work_mode", []) if str(x).strip()][:2],
            "employment_type": [str(x).strip() for x in data.get("employment_type", []) if str(x).strip()][:2],
            "preferences": [],
        }
    except Exception as e:
        logger.warning(f"LLM correction failed: {e}")
        return None


def profile_builder(state: JobState) -> dict[str, Any]:
    logger.info("Running profile_builder")
    resume_p = state.get("resume_profile") or {}
    query_p = state.get("query_profile") or {}

    # Query takes priority for preferences; resume provides additional context
    # Merge with query winning on conflict
    def _merge_list(key: str) -> list[str]:
        qv = query_p.get(key, []) or []
        rv = resume_p.get(key, []) or []
        if qv:
            # query wins, but append resume items not duplicate (for skills)
            if key == "skills":
                merged = list(qv)
                for s in rv:
                    if s.lower() not in [m.lower() for m in merged]:
                        merged.append(s)
                return merged[:15]
            return qv
        return rv

    # target_roles: query wins if present else resume
    target_roles = query_p.get("target_roles") or []
    if not target_roles:
        target_roles = resume_p.get("target_roles") or []

    locations = query_p.get("locations") or []
    if not locations:
        locations = resume_p.get("locations") or []

    work_mode = query_p.get("work_mode") or []
    if not work_mode:
        work_mode = resume_p.get("work_mode") or []

    employment_type = query_p.get("employment_type") or []
    if not employment_type:
        employment_type = resume_p.get("employment_type") or []

    skills = _merge_list("skills")
    if not skills:
        skills = resume_p.get("skills", []) or []

    experience_level = query_p.get("experience_level") or resume_p.get("experience_level")

    profile = {
        "target_roles": target_roles[:4],
        "skills": skills[:15],
        "experience_level": experience_level,
        "employment_type": employment_type,
        "locations": locations[:4],
        "work_mode": work_mode,
        "preferences": query_p.get("preferences", []) or resume_p.get("preferences", []) or [],
        "projects": resume_p.get("projects", []) or [],
        "education": resume_p.get("education", []) or [],
        "experience": resume_p.get("experience", []) or [],
        "name": resume_p.get("name"),
        "links": resume_p.get("links", []) or [],
        "raw_text": resume_p.get("raw_text", "") or resume_p.get("resume_text", "") or "",
    }
    logger.info(f"Built profile: {profile}")
    return {"profile": profile, "progress_steps": [f"Profile: roles={profile['target_roles']} loc={profile['locations']} mode={profile['work_mode']}"]}


def validate_profile(state: JobState) -> dict[str, Any]:
    logger.info("Running validate_profile")
    profile = state.get("profile") or {}
    query_p = state.get("query_profile") or {}

    # Check is_not_job
    if query_p.get("is_not_job"):
        return {
            "error": "This doesn't look like a job search. Try: 'Python backend internships in India' or upload your resume.",
            "search_complete": True,
            "progress_steps": ["Error: not a job query"],
        }

    target_roles = profile.get("target_roles") or []
    locations = profile.get("locations") or []

    if not target_roles:
        return {
            "follow_up_question": "What role are you looking for? For example: 'Python Developer', 'AI Engineer Intern', or 'Backend Developer'. You can also upload your resume.",
            "search_complete": True,
            "progress_steps": ["Missing target role — need follow-up"],
        }

    if not locations:
        return {
            "follow_up_question": "Where would you like to work? Add up to 3-4 preferred locations (e.g. India, Bangalore, Remote, Delhi). You can also specify work mode: remote / hybrid / onsite.",
            "search_complete": True,
            "progress_steps": ["Missing location — need follow-up"],
        }

    return {"progress_steps": [f"Validated: searching {target_roles} in {locations}"]}


def search_planner(state: JobState) -> dict[str, Any]:
    logger.info("Running search_planner (deterministic, no LLM)")
    profile = state.get("profile") or {}
    # Deterministic: 2-3 from target_roles — no LLM needed (skills not used for q, as requested)
    roles = (profile.get("target_roles") or [])[:3]
    locs = profile.get("locations") or ["India"]
    # pick first non-remote location as main
    main_loc = next((l for l in locs if l.lower() != "remote"), locs[0])
    # handle Remote in work_mode/locations
    work_mode = profile.get("work_mode") or []
    has_remote = "remote" in [w.lower() for w in work_mode] or any("remote" in loc.lower() for loc in locs)
    searches: list[dict[str, Any]] = []
    for role in roles[:2]:
        searches.append({"q": role, "location": main_loc})
        if len(searches) >= 3:
            break
    if has_remote and len(searches) < 3:
        # add remote variant of first role with same main location (India jobs understands "Remote" in q)
        q_remote = f"{roles[0]} Remote" if roles else "Remote"
        if not any(s["q"] == q_remote for s in searches):
            searches.append({"q": q_remote, "location": main_loc})
    if not searches and roles:
        searches = [{"q": roles[0], "location": main_loc}]
    # Junior candidates: spend a leftover search slot on an entry-level variant
    # so the eligible jobs are actually in the pool. The hard gate lives in
    # job_seniority.py; this only widens the funnel.
    level = (profile.get("experience_level") or "").strip().lower()
    if roles and len(searches) < 3 and level in ("internship", "entry_level"):
        qualifier = "Internship" if level == "internship" else "Fresher"
        q_junior = f"{roles[0]} {qualifier}"
        if not any(s["q"] == q_junior for s in searches):
            searches.append({"q": q_junior, "location": main_loc})
    # ensure 2-3 quota safe
    searches = searches[:3]
    logger.info(f"Planned searches (fallback, level={level or 'unknown'}): {searches}")
    return {"search_requests": searches, "progress_steps": [f"Planned {len(searches)} searches (fallback)"]}


def google_jobs_search_node(state: JobState) -> dict[str, Any]:
    logger.info("Running google_jobs_search_node")
    sreqs = state.get("search_requests") or []
    if not sreqs:
        return {"error": "No search plan available.", "search_complete": True, "progress_steps": ["Error: no search plan"]}

    try:
        from backend.agents.job.tools.google_jobs import build_search_requests, google_jobs_search_multi

        # Location -> gl/google_domain mapping lives in the tools layer so the
        # alert runner builds requests the exact same way.
        reqs = build_search_requests([(s.get("q"), s.get("location")) for s in sreqs])

        raws = google_jobs_search_multi(reqs)
        # count raw
        total_raw = sum(len(r.get("jobs_results", [])) for r in raws)
        return {
            "jobs_raw": raws,
            "progress_steps": [f"Searched Google Jobs ({len(reqs)} queries)", f"Got {total_raw} raw results"],
        }
    except ValueError as ve:
        logger.error(f"Config error: {ve}")
        return {"error": str(ve), "search_complete": True, "progress_steps": ["Error: configuration missing"]}
    except Exception as e:
        logger.error(f"Google Jobs search failed: {e}")
        return {"error": "Job search is temporarily unavailable. Please try again.", "search_complete": True, "progress_steps": ["Error: search failed"]}


def normalize_validate_node(state: JobState) -> dict[str, Any]:
    logger.info("Running normalize_validate_node")
    raws = state.get("jobs_raw") or []
    if not raws:
        return {"jobs": [], "total_results": 0, "search_complete": True, "progress_steps": ["No raw results to normalize"]}

    try:
        from backend.agents.job.services.job_normalizer import normalize_jobs

        jobs = normalize_jobs(raws)
        jobs_data = [j.model_dump() for j in jobs]
        return {
            "jobs": jobs_data,
            "total_results": len(jobs_data),
            "search_complete": True,
            "progress_steps": [f"Normalized {len(jobs_data)} jobs (deduped & sorted by freshness)"],
        }
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        return {"error": f"Normalization failed: {e}", "search_complete": True, "progress_steps": ["Error: normalization"]}


def route_after_validate(state: JobState) -> Literal["search_planner", "END"]:
    if state.get("error") or state.get("follow_up_question"):
        return "END"
    return "search_planner"


def route_after_input(state: JobState) -> Literal["resume_vision_parser", "query_analyzer", "END"]:
    if state.get("error") or state.get("follow_up_question"):
        return "END"
    # Always enter resume_vision_parser. With bytes it parses the upload; with
    # none it loads the skills stored at onboarding. Skipping it for no-upload
    # searches meant profile_builder saw an empty resume_profile, so every job
    # came back with total_user_skills=0 and no match score.
    return "resume_vision_parser"


def build_job_graph():
    builder = StateGraph(JobState)
    builder.add_node("input_analyzer", input_analyzer)
    builder.add_node("resume_vision_parser", resume_vision_parser)
    builder.add_node("query_analyzer", query_analyzer)
    builder.add_node("profile_builder", profile_builder)
    builder.add_node("validate_profile", validate_profile)
    builder.add_node("search_planner", search_planner)
    builder.add_node("google_jobs_search", google_jobs_search_node)
    builder.add_node("normalize_validate", normalize_validate_node)

    builder.add_edge(START, "input_analyzer")
    builder.add_conditional_edges("input_analyzer", route_after_input, {
        "resume_vision_parser": "resume_vision_parser",
        "query_analyzer": "query_analyzer",
        "END": END,
    })
    builder.add_edge("resume_vision_parser", "query_analyzer")
    builder.add_edge("query_analyzer", "profile_builder")
    builder.add_edge("profile_builder", "validate_profile")
    builder.add_conditional_edges("validate_profile", route_after_validate, {
        "search_planner": "search_planner",
        "END": END,
    })
    builder.add_edge("search_planner", "google_jobs_search")
    builder.add_edge("google_jobs_search", "normalize_validate")
    builder.add_edge("normalize_validate", END)
    return builder.compile()


_compiled_job_graph = None


def get_job_graph():
    global _compiled_job_graph
    if _compiled_job_graph is None:
        _compiled_job_graph = build_job_graph()
    return _compiled_job_graph
