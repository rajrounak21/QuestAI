from __future__ import annotations

import json
import logging
import re
from typing import Any

from dotenv import load_dotenv

from job_agent.models.application_models import ApplicationAnalysis

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a resume-job matching analyst. Compare the resume data with the job description and return ONLY a JSON object (no markdown).

Resume Data:
Name: {name}
Skills: {skills}
Experience: {experience}
Projects: {projects}
Education: {education}
Raw resume snippet (first 1500 chars):
{raw_text}

Job Data:
Title: {job_title}
Company: {job_company}
Location: {job_location}
Description: {job_description}
Highlights: {job_highlights}

Return JSON with exactly this schema:
{{
  "job_title": "job title string",
  "relevant_skills": ["skill found in both resume and job"],
  "relevant_experience": ["experience title/company that matches job"],
  "relevant_projects": ["project name that matches job"],
  "gaps": ["skill/requirement in job not found in resume"],
  "summary": "2-sentence tailored summary reordering resume strengths for this job",
  "cv_recommendations": ["emphasize FastAPI backend work", "highlight Docker..."]
}}

Rules:
- relevant_skills must be subset of resume skills (case-insensitive) that also appear relevant to job description. Max 8.
- relevant_experience must reference existing experience titles/companies only. Max 3.
- relevant_projects must reference existing project names only. Max 4.
- gaps: list requirements from job not in resume (skills/tools). Max 5.
- summary: 2 sentences, rewords resume strengths for this job, no invented facts.
- cv_recommendations: 2-4 actionable reorder/emphasis tips.
- Do NOT invent skills, projects, education, companies.
- Must be valid JSON.
"""

def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        raise

def _get_llm():
    import os
    from langchain_groq import ChatGroq
    load_dotenv(override=True)
    return ChatGroq(model="openai/gpt-oss-20b", temperature=0.2, max_tokens=800, api_key=os.getenv("GROQ_API_KEY"))

def analyze_application(resume_data: dict[str, Any], job_data: dict[str, Any]) -> ApplicationAnalysis:
    # Build prompt
    skills = ", ".join((resume_data.get("skills") or [])[:15])
    exp_str = "; ".join([f"{e.get('title','')}@{e.get('company','')} ({e.get('duration','')})" for e in (resume_data.get("experience") or [])[:3]])
    proj_str = "; ".join([f"{p.get('name','')} ({p.get('stack','')}): {p.get('description','')}" for p in (resume_data.get("projects") or [])[:4]])
    edu_str = "; ".join([f"{e.get('degree','')} at {e.get('school','')} {e.get('year','')}" for e in (resume_data.get("education") or [])[:2]])
    raw_text = (resume_data.get("raw_text") or resume_data.get("resume_text") or "")[:1500]
    highlights = "; ".join([f"{h.get('title','')}: {', '.join(h.get('items',[])[:3])}" for h in (job_data.get("job_highlights") or [])[:2]])

    prompt = ANALYSIS_PROMPT.format(
        name=resume_data.get("name") or "Candidate",
        skills=skills or "none",
        experience=exp_str or "none",
        projects=proj_str or "none",
        education=edu_str or "none",
        raw_text=raw_text[:1500] or "none",
        job_title=job_data.get("title",""),
        job_company=job_data.get("company",""),
        job_location=job_data.get("location",""),
        job_description=(job_data.get("description") or "")[:2000],
        job_highlights=highlights or "none",
    )
    llm = _get_llm()
    raw = llm.invoke(prompt)
    text = raw.content if hasattr(raw, "content") else str(raw)
    try:
        data = _parse_json(text)
    except Exception as e:
        logger.warning(f"Analysis JSON parse failed, fallback: {e} raw {text[:400]}")
        # fallback minimal
        data = {
            "job_title": job_data.get("title",""),
            "relevant_skills": (resume_data.get("skills") or [])[:5],
            "relevant_experience": [],
            "relevant_projects": [p.get("name","") for p in (resume_data.get("projects") or [])[:2]],
            "gaps": [],
            "summary": f"Motivated {resume_data.get('target_roles',['Candidate'])[0] if resume_data.get('target_roles') else 'candidate'} with {skills[:80]} seeking {job_data.get('title','')}.",
            "cv_recommendations": ["Emphasize relevant skills and projects"],
        }

    # Validation: subset checks
    resume_skills_set = set(s.lower() for s in (resume_data.get("skills") or []))
    resume_proj_names = set((p.get("name") or "").lower() for p in (resume_data.get("projects") or []))
    resume_exp_titles = set((f"{e.get('title','')} {e.get('company','')}".lower().strip() for e in (resume_data.get("experience") or [])))

    def _filter_skills(lst):
        out=[]
        for s in lst or []:
            if not isinstance(s, str): continue
            if s.lower() in resume_skills_set:
                out.append(s)
            # also allow partial match if skill substring in resume skills
            elif any(s.lower() in rs or rs in s.lower() for rs in resume_skills_set):
                out.append(s)
        return out[:8]

    def _filter_projects(lst):
        out=[]
        for p in lst or []:
            if not isinstance(p, str): continue
            if any(p.lower() in name or name in p.lower() for name in resume_proj_names if name):
                out.append(p)
        # if none matched but we have projects, keep at least 1
        if not out and resume_data.get("projects"):
            out = [resume_data["projects"][0].get("name","")] if resume_data["projects"] else []
        return out[:4]

    relevant_skills = _filter_skills(data.get("relevant_skills"))
    # If empty but skills exist and job mentions some, fallback to intersection via deterministic matcher
    if not relevant_skills and resume_data.get("skills"):
        try:
            from job_agent.services.job_matcher import match_single
            tmp = match_single(resume_data["skills"], job_data.get("description",""), job_data.get("title",""))
            relevant_skills = tmp.get("matched_skills", [])[:5]
        except Exception:
            pass

    analysis = ApplicationAnalysis(
        job_title=str(data.get("job_title","") or job_data.get("title",""))[:120],
        relevant_skills=relevant_skills,
        relevant_experience=[str(x)[:120] for x in (data.get("relevant_experience") or []) if isinstance(x, str)][:3],
        relevant_projects=_filter_projects(data.get("relevant_projects")),
        gaps=[str(x)[:120] for x in (data.get("gaps") or []) if isinstance(x, str)][:5],
        summary=str(data.get("summary",""))[:500],
        cv_recommendations=[str(x)[:160] for x in (data.get("cv_recommendations") or []) if isinstance(x, str)][:4],
    )
    logger.info(f"Analysis: skills {analysis.relevant_skills} gaps {analysis.gaps}")
    return analysis
