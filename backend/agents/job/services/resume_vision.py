from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# There is no image-based resume path in this module, and there used to be one
# that could never run. It read a GROQ_VISION_MODELS variable and, when that was
# empty, returned early - so the PDF-to-PNG renderer and the vision call below it
# were unreachable on every run.
#
# The account has no vision-capable model at all. Listing the live key returns 11
# models, none of them vision: gpt-oss-120b, gpt-oss-20b, qwen3.8-27b, allam-2-7b,
# two orpheus variants, two llama-prompt-guard models, gpt-oss-safeguard-20b and
# two whisper models. The model ids this path used to hardcode are dead too - two
# return 404 and one returns 400 decommissioned - which is what cost three failed
# round trips on every scanned PDF before falling back.
#
# Text PDFs are the normal case and are handled well below. A scanned PDF comes
# back with no skills, which the upload endpoint turns into a 422 asking for a
# text-based PDF.


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


def pdf_text_fallback(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Extract a resume's text layer with PyMuPDF, plus hyperlink targets."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []
    links: list[str] = []
    for i in range(min(len(doc), max_pages)):
        page = doc.load_page(i)
        texts.append(page.get_text() or "")
        # Hyperlink targets live in annotations, not in the text layer. Without
        # this the parser never sees a single URL (the visible label is just
        # "GitHub" / "Live Demo"), so `links` always came back empty.
        for link in page.get_links():
            uri = link.get("uri")
            if uri and uri not in links:
                links.append(uri)
    doc.close()
    combined = "\n\n".join(t.strip() for t in texts if t.strip())
    if links:
        combined = f"{combined}\n\nLinks:\n" + "\n".join(links)
    if combined:
        logger.info(f"Fallback text extraction: {len(combined)} chars ({len(links)} link URIs)")
    return combined


def parse_resume_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """PDF bytes -> structured info.

    Strategy:
    1. Extract text with PyMuPDF, including hyperlink targets from annotations -
       without those the parser never sees a URL, since the visible label is just
       "GitHub" / "Live Demo".
    2. If there is enough text (>80 chars), structure it with the text model. This
       is the normal case and needs no image model.
    3. If there is too little text, the PDF is scanned. There is no image path to
       try, so return whatever text exists with empty skills and let the caller
       ask for a text-based PDF.
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

    # Fast path: PyMuPDF text extraction is accurate for text PDFs.
    quick_text = pdf_text_fallback(pdf_bytes)
    if quick_text and len(quick_text.strip()) > 80:
        try:
            result = _llm_extract_from_text(quick_text)
            logger.info(f"Resume text path succeeded: {len(quick_text)} chars, roles={result.get('target_roles')}")
            return result
        except Exception as e:
            logger.warning(f"LLM text extract failed on a text PDF: {e}")
            # Retry once - _llm_extract_from_text falls back to regex internally
            # when the model returns JSON it could not parse.
            try:
                result = _llm_extract_from_text(quick_text)
                if result.get("target_roles"):
                    return result
            except Exception:
                pass
            # Partial is still better than nothing: the text survives even when
            # structuring failed.
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

    # Scanned / low-text PDF: extraction produced too little to structure. There is
    # no image model to fall back on (see the note at the top of this module), so
    # return what text exists. The upload endpoint turns the empty skills into a
    # 422 asking for a text-based PDF, which is honest rather than a fabricated
    # parse.
    logger.info("Scanned PDF with too little text to structure; no vision model available.")
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


def _llm_extract_from_text(text: str) -> dict[str, Any]:
    """Use ChatGroq text model to structure already-extracted text. Raw text kept separate."""
    import os
    from langchain_groq import ChatGroq

    load_dotenv(override=True)
    # gpt-oss-20b is a *reasoning* model: max_tokens covers reasoning tokens too.
    # At 1400 it spent ~1198 tokens reasoning and the JSON was cut off mid-string,
    # silently losing projects/education/experience. 8192 leaves room for both.
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0.0, max_tokens=8192, api_key=os.getenv("GROQ_API_KEY"))
    # Truncate to avoid prompt blowup; keep first 5000 chars
    truncated = text[:5000].replace("\r", " ").strip()
    prompt = f"""Extract job profile from this resume text. Return ONLY JSON (no markdown, no extra text):
{{"projects": [{{"name": "", "stack": "", "description": ""}}], "education": [{{"degree": "", "school": "", "year": ""}}], "experience": [{{"title": "", "company": "", "duration": ""}}], "name": "", "links": [], "target_roles": [], "skills": [], "experience_level": null, "employment_type": [], "locations": [], "work_mode": [], "preferences": []}}
Rules:
- Put projects, education and experience FIRST. If output gets cut off, these must survive.
- Keep every string short (names, stack, one short phrase) so the whole JSON fits.
- name: Person's full name ONLY from the header at the very top of resume (first 1-2 lines). NEVER use project names like "Sikhsha Sathi", "FamilyShield" as name. If top contains "Sikhsha Sathi" under PROJECTS heading, ignore it. Name is typically 2-3 capitalized words before email/phone.
- target_roles: 1-4 concise roles like Python Developer, AI Engineer, Backend Developer
- skills: technical skills only, max 15
- experience_level: internship|entry_level|mid_level|senior|null
- locations/work_mode/employment_type: ONLY if explicit in text, else []
- projects: up to 4, each with name, stack (tech), short description — extract ONLY under PROJECTS heading, not header
- education: up to 2, degree + school — under EDUCATION heading
- experience: up to 3, title + company + duration — under EXPERIENCE heading
- links: EVERY URL in the text (GitHub, LinkedIn, portfolio, live demos). Copy them exactly.
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
