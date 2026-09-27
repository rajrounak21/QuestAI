from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

VISION_MODELS = [
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-11b-vision-preview",
]

RESUME_VISION_PROMPT = """You are a resume parser. Extract structured information from this resume image.

Return ONLY a JSON object (no markdown, no explanation) with this schema:
{
  "target_roles": ["role 1", "role 2"],
  "skills": ["skill1", "skill2"],
  "experience_level": "internship|entry_level|mid_level|senior|unknown",
  "employment_type": ["internship","full-time","contract"],
  "locations": ["location1"],
  "work_mode": ["remote","onsite","hybrid"],
  "projects": [{"name": "Project Name", "stack": "Python, FastAPI", "description": "1 sentence"}],
  "education": [{"degree": "B.Tech", "school": "University", "year": "2023"}],
  "experience": [{"title": "Backend Intern", "company": "XYZ", "duration": "3 months"}],
  "name": "Full Name",
  "links": ["https://github.com/..."]
}

Rules:
- target_roles: infer from title, objective, experience. e.g. Python Developer, AI Engineer, Backend Developer. Max 4.
- skills: extract technical skills only (languages, frameworks, tools). Max 15.
- experience_level: internship if student/intern mentioned, entry_level if 0-2 yrs, else mid/senior.
- locations: ONLY if explicitly mentioned in resume. Do NOT invent.
- work_mode, employment_type: only if explicit.
- projects: up to 4, each with name, stack (tech used), 1-sentence description.
- education: up to 2, degree + school.
- experience: up to 3, title + company + duration if present.
- Do NOT include raw_text (provided separately).
- If image is blank/unreadable, return empty arrays.
"""


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError as je:
        # Attempt to extract outermost JSON object via regex
        logger.warning(f"JSON parse failed at {je}, attempting repair")
        # Find first { and last } 
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            # Repair common issues: unterminated strings are truncated, try to close
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Try to fix truncated JSON by closing open structures
                # Count open braces/brackets vs close
                # Simplest: trim to last complete field
                truncated = candidate[: je.colno] if je.colno > 0 else candidate
                # Find last complete comma or quote before error
                last_comma = truncated.rfind(",")
                if last_comma > 0:
                    attempt = truncated[:last_comma] + "}"
                    # Fix dangling open arrays/objects
                    open_braces = attempt.count("{") - attempt.count("}")
                    open_brackets = attempt.count("[") - attempt.count("]")
                    attempt += "}" * max(0, open_braces)
                    attempt += "]" * max(0, open_brackets)
                    try:
                        return json.loads(attempt)
                    except Exception:
                        pass
                # Final fallback: extract arrays via regex for each field
                logger.warning(f"JSON repair failed, using regex extraction for {candidate[:200]}")
                return _regex_extract_profile(text)
        raise


def _regex_extract_profile(text: str) -> dict[str, Any]:
    """Fallback when LLM returns invalid JSON — extract fields via regex, never fails."""
    def _list_for_key(key: str) -> list[str]:
        # Match "key": [ ... ]
        m = re.search(rf'"{re.escape(key)}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if not m:
            return []
        inner = m.group(1)
        # Extract quoted strings
        items = re.findall(r'"([^"]+)"', inner)
        # Also handle single quotes
        if not items:
            items = re.findall(r"'([^']+)'", inner)
        return [i.strip() for i in items if i.strip()]

    def _str_for_key(key: str) -> str | None:
        m = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', text)
        if m:
            v = m.group(1).strip()
            return v if v and v.lower() != "null" else None
        # Check for null
        m2 = re.search(rf'"{re.escape(key)}"\s*:\s*null', text)
        if m2:
            return None
        return None

    return {
        "target_roles": _list_for_key("target_roles")[:4],
        "skills": _list_for_key("skills")[:15],
        "experience_level": _str_for_key("experience_level"),
        "employment_type": _list_for_key("employment_type"),
        "locations": _list_for_key("locations"),
        "work_mode": _list_for_key("work_mode"),
        "preferences": _list_for_key("preferences"),
        "projects": [],
        "education": [],
        "experience": [],
        "name": _str_for_key("name"),
        "links": _list_for_key("links"),
        "raw_text": "",
    }


def pdf_to_base64_images(pdf_bytes: bytes, dpi: int = 200, max_pages: int = 2) -> list[str]:
    """Render PDF pages to base64 PNGs. Uses PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[str] = []
    for i in range(min(len(doc), max_pages)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        images.append(b64)
        logger.info(f"Rendered resume page {i+1}/{min(len(doc), max_pages)} dpi={dpi} size={len(png_bytes)} bytes")
    doc.close()
    return images


def pdf_text_fallback(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Fallback: extract text via PyMuPDF if vision fails."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []
    for i in range(min(len(doc), max_pages)):
        page = doc.load_page(i)
        texts.append(page.get_text() or "")
    doc.close()
    combined = "\n\n".join(t.strip() for t in texts if t.strip())
    if combined:
        logger.info(f"Fallback text extraction: {len(combined)} chars")
    return combined


def _call_groq_vision(base64_images: list[str], prompt: str = RESUME_VISION_PROMPT) -> dict[str, Any]:
    """Call Groq vision model with one or more images. Tries model chain on failure."""
    import groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found")

    client = groq.Groq(api_key=api_key)

    # Build message with multiple images
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for b64 in base64_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    last_err = None
    for model in VISION_MODELS:
        try:
            logger.info(f"Trying Groq vision model: {model}")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0.0,
                max_tokens=2048,
            )
            text = resp.choices[0].message.content or ""
            logger.info(f"Groq vision response ({model}): {len(text)} chars")
            try:
                return _parse_json(text)
            except Exception:
                # if not JSON, treat as raw_text
                logger.warning(f"Groq vision non-JSON response from {model}, wrapping as raw_text")
                return {
                    "raw_text": text,
                    "target_roles": [],
                    "skills": [],
                    "experience_level": None,
                    "employment_type": [],
                    "locations": [],
                    "work_mode": [],
                    "preferences": [],
                }
        except Exception as e:
            logger.warning(f"Groq vision model {model} failed: {e}")
            last_err = e
            continue
    raise RuntimeError(f"All Groq vision models failed: {last_err}")


def parse_resume_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """PDF bytes -> structured info.

    Strategy (Groq vision not available on this account - fallback optimized):
    1. Try fast text extraction via PyMuPDF.
    2. If enough text (>80 chars), use LLM structuring directly (fast, accurate for text PDFs).
    3. If too little text (scanned), try vision path (PDF->PNG->Groq vision). If vision fails, fallback to whatever text exists.
    This keeps vision-first spec when needed, but avoids 3 failed vision calls for every normal resume.
    """
    if not pdf_bytes or len(pdf_bytes) < 100:
        return {
            "raw_text": "",
            "target_roles": [],
            "skills": [],
            "experience_level": None,
            "employment_type": [],
            "locations": [],
            "work_mode": [],
            "preferences": [],
            "error": "Empty PDF",
        }

    # Fast path: text extraction (PyMuPDF is accurate for text PDFs - vision not needed)
    quick_text = pdf_text_fallback(pdf_bytes)
    if quick_text and len(quick_text.strip()) > 80:
        try:
            result = _llm_extract_from_text(quick_text)
            logger.info(f"Resume text path succeeded: {len(quick_text)} chars, roles={result.get('target_roles')}")
            # Guard: if LLM returned empty roles/skills despite rich text, might be parse issue — still return it (don't vision-loop)
            return result
        except Exception as e:
            logger.warning(f"LLM text extract failed (text PDF, skipping vision): {e}")
            # For text PDFs, don't waste 3 vision calls (Groq has no vision on this key) — try once more with regex fallback
            try:
                # Re-attempt with same path but _llm_extract will fallback to regex internally
                result = _llm_extract_from_text(quick_text)
                if result.get("target_roles"):
                    return result
            except Exception:
                pass
            # Return partial if needed — still better than vision 404s
            return {
                "raw_text": quick_text,
                "target_roles": [],
                "skills": [],
                "experience_level": None,
                "employment_type": [],
                "locations": [],
                "work_mode": [],
                "preferences": [],
                "llm_error": str(e),
            }

    # Scanned / low-text path: only if text extraction was short (<80 chars)
    # For now skip vision if Groq vision unavailable; fallback to whatever text exists
    if len(quick_text.strip()) >= 80:
        # Already tried LLM above, return fallback
        return {
            "raw_text": quick_text,
            "target_roles": [],
            "skills": [],
            "experience_level": None,
            "employment_type": [],
            "locations": [],
            "work_mode": [],
            "preferences": [],
        }

    # Only for truly scanned PDFs (<80 chars) try vision once
    try:
        b64_images = pdf_to_base64_images(pdf_bytes, dpi=200, max_pages=2)
    except Exception as e:
        logger.error(f"PDF render failed: {e}")
        return {"raw_text": quick_text, "target_roles": [], "skills": [], "experience_level": None, "employment_type": [], "locations": [], "work_mode": [], "preferences": [], "render_error": str(e)}

    if not b64_images:
        return {"raw_text": quick_text, "target_roles": [], "skills": [], "experience_level": None, "employment_type": [], "locations": [], "work_mode": [], "preferences": []}

    try:
        result = _call_groq_vision(b64_images)
        result.setdefault("raw_text", quick_text)
        for k in ["target_roles", "skills", "employment_type", "locations", "work_mode", "preferences"]:
            result.setdefault(k, [])
        result.setdefault("experience_level", None)
        if len(result.get("raw_text", "")) < len(quick_text):
            result["raw_text"] = quick_text
        return result
    except Exception as e:
        logger.warning(f"Vision parse failed: {e}")
        return {"raw_text": quick_text, "target_roles": [], "skills": [], "experience_level": None, "employment_type": [], "locations": [], "work_mode": [], "preferences": [], "vision_error": str(e)}


def _llm_extract_from_text(text: str) -> dict[str, Any]:
    """Use ChatGroq text model to structure already-extracted text. Raw text kept separate."""
    import os
    from langchain_groq import ChatGroq

    load_dotenv(override=True)
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0.0, max_tokens=1400, api_key=os.getenv("GROQ_API_KEY"))
    # Truncate to avoid JSON blowup; keep first 5000 chars
    truncated = text[:5000].replace("\r", " ").strip()
    prompt = f"""Extract job profile from this resume text. Return ONLY JSON (no markdown, no extra text):
{{"target_roles": [], "skills": [], "experience_level": null, "employment_type": [], "locations": [], "work_mode": [], "preferences": [], "projects": [{{"name": "", "stack": "", "description": ""}}], "education": [{{"degree": "", "school": "", "year": ""}}], "experience": [{{"title": "", "company": "", "duration": ""}}], "name": "", "links": []}}
Rules:
- name: Person's full name ONLY from the header at the very top of resume (first 1-2 lines). NEVER use project names like "Sikhsha Sathi", "FamilyShield" as name. If top contains "Sikhsha Sathi" under PROJECTS heading, ignore it. Name is typically 2-3 capitalized words before email/phone.
- target_roles: 1-4 concise roles like Python Developer, AI Engineer, Backend Developer
- skills: technical skills only, max 15
- experience_level: internship|entry_level|mid_level|senior|null
- locations/work_mode/employment_type: ONLY if explicit in text, else []
- projects: up to 4, each with name, stack (tech), 1-sentence description — extract ONLY under PROJECTS heading, not header
- education: up to 2, degree + school — under EDUCATION heading
- experience: up to 3, title + company + duration — under EXPERIENCE heading
- Do NOT repeat resume text in JSON, keep values short (escape quotes properly)
- Must be valid JSON

Resume text:
{truncated}"""
    raw = llm.invoke(prompt)
    content = raw.content if hasattr(raw, "content") else str(raw)
    try:
        data = _parse_json(content)
    except Exception as e:
        logger.warning(f"_llm_extract JSON still invalid after repair: {e}, raw 500 chars: {content[:500]}")
        data = _regex_extract_profile(content)
    data["raw_text"] = text  # keep original PDF text separately, not from LLM
    for k in ["target_roles", "skills", "employment_type", "locations", "work_mode", "preferences", "projects", "education", "experience", "links"]:
        data.setdefault(k, [])
        if not isinstance(data[k], list):
            data[k] = []
    data.setdefault("experience_level", None)
    data.setdefault("name", None)
    # sanitize: trim empty, dedupe
    for k in ["target_roles", "skills", "locations", "work_mode", "employment_type"]:
        data[k] = [s.strip() for s in data[k] if isinstance(s, str) and s.strip()][:15 if k == "skills" else 4]
    # sanitize projects/education/experience
    data["projects"] = [p for p in data["projects"] if isinstance(p, dict) and p.get("name")][:4]
    data["education"] = [e for e in data["education"] if isinstance(e, dict) and (e.get("degree") or e.get("school"))][:2]
    data["experience"] = [ex for ex in data["experience"] if isinstance(ex, dict) and (ex.get("title") or ex.get("company"))][:3]
    return data
