from __future__ import annotations

import logging
import re
from typing import Any

from fpdf import FPDF

logger = logging.getLogger(__name__)

class CVPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

def _sanitize(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u2011","-").replace("\u2010","-").replace("\u2013","-").replace("\u2014","-").replace("\u2019","'").replace("\u201c",'"').replace("\u201d",'"').replace("\u2022","-").replace(chr(8226),"-").replace("•","-").replace("—","-").replace("’","'")
    try:
        t.encode("latin-1")
        return t
    except UnicodeEncodeError:
        return t.encode("latin-1","replace").decode("latin-1")

def _resolve_name(resume_data: dict[str, Any]) -> str:
    raw_name = (resume_data.get("name") or "").strip()
    projects = resume_data.get("projects") or []
    proj_names = [p.get("name","").lower() for p in projects]
    if raw_name and raw_name.lower() in proj_names:
        raw_name = ""
    if raw_name and len(raw_name) >= 2 and len(raw_name) < 40:
        return raw_name
    # Try raw_text first lines that look like person name
    raw = (resume_data.get("raw_text") or "")[:600]
    for line in raw.strip().splitlines():
        cand = line.strip()
        if not cand or len(cand) > 40 or "@" in cand or "http" in cand.lower():
            continue
        if any(k in cand.lower() for k in ["python","developer","engineer","project","skill","education","experience","sathi","email","phone","resume","curriculum"]):
            continue
        words = cand.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w[0].isalpha()):
            return cand
    # Fallback to email prefix or Candidate
    email = resume_data.get("email") or ""
    if email and "@" in email:
        return email.split("@")[0].replace("."," ").title()
    return "Candidate"

def _section_title(pdf: CVPDF, title: str):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(15,23,42)
    pdf.cell(0, 6, _sanitize(title), new_x="LMARGIN", new_y="NEXT")
    # underline
    y = pdf.get_y()
    pdf.set_draw_color(74,144,217)
    pdf.set_line_width(0.45)
    pdf.line(pdf.l_margin, y, pdf.l_margin + 18, y)
    pdf.ln(3)

def generate_cv_pdf(resume_data: dict[str, Any], analysis: dict[str, Any] | Any, job_data: dict[str, Any]) -> bytes:
    if hasattr(analysis, "model_dump"):
        analysis = analysis.model_dump()

    pdf = CVPDF(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    primary = (15,23,42)
    accent = (37,99,235)
    muted = (100,116,139)

    name = _resolve_name(resume_data)
    role = (resume_data.get("target_roles") or [""])[0] if resume_data.get("target_roles") else ""
    # Header block with subtle background
    pdf.set_fill_color(15,23,42)
    pdf.rect(0,0,210,36, style="F")
    pdf.set_y(8)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(255,255,255)
    pdf.cell(0, 8, _sanitize(name.upper()), align="C", new_x="LMARGIN", new_y="NEXT")
    if role:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(200,215,255)
        pdf.cell(0, 5, _sanitize(role.title()), align="C", new_x="LMARGIN", new_y="NEXT")
    # Contact line inside header
    contacts = []
    if resume_data.get("email"):
        contacts.append(resume_data["email"])
    # try phone in raw_text
    raw = resume_data.get("raw_text") or ""
    m = re.search(r"\+?\d[\d\s\-]{8,14}\d", raw)
    if m:
        ph = m.group(0).strip()
        if ph not in contacts:
            contacts.append(ph)
    for e in (resume_data.get("education") or [])[:1]:
        if e.get("school"):
            contacts.append(e["school"])
    contacts.extend((resume_data.get("links") or [])[:2])
    # location from resume
    if resume_data.get("locations"):
        contacts.append(resume_data["locations"][0])
    if contacts:
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(180,195,255)
        pdf.cell(0, 4, _sanitize("  |  ".join(contacts[:4])), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)  # space after header

    # Summary — tailored, professional, no company name stuffing
    summary = _sanitize((analysis.get("summary") or "").strip() if isinstance(analysis, dict) else "")
    # Clean summary: if it mentions specific company like Crescendo Global redundantly, keep but not as header
    if summary:
        _section_title(pdf, "PROFESSIONAL SUMMARY")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(30,30,30)
        # Ensure 2-3 sentences, justify left
        pdf.multi_cell(0, 4.4, summary)
        pdf.ln(2)

    # Skills — relevant first, no gaps shown
    skills = resume_data.get("skills") or []
    relevant = [s for s in (analysis.get("relevant_skills") or []) if isinstance(s, str)]
    if skills:
        _section_title(pdf, "TECHNICAL SKILLS")
        ordered = []
        seen = set(s.lower() for s in [])
        for s in relevant:
            if s.lower() not in seen:
                ordered.append(s)
                seen.add(s.lower())
        for s in skills:
            if s.lower() not in seen:
                ordered.append(s)
                seen.add(s.lower())
        pdf.set_font("Helvetica", "", 8.2)
        pdf.set_text_color(45,45,45)
        # Render as wrapped line with bullets
        line = _sanitize("  •  ".join(ordered[:22]))
        pdf.multi_cell(0, 4.5, line)
        pdf.ln(2)

    # Experience — reorder by relevance, clean
    exps = resume_data.get("experience") or []
    rel_exp = [r.lower() for r in (analysis.get("relevant_experience") or [])]
    if exps:
        _section_title(pdf, "EXPERIENCE")
        def exp_key(e):
            txt = f"{e.get('title','')} {e.get('company','')}".lower()
            for re_ in rel_exp:
                if re_ and re_ in txt:
                    return 0
            return 1
        for e in sorted(exps, key=exp_key)[:3]:
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(15,23,42)
            title = _sanitize(e.get("title","") or "Experience")
            comp = _sanitize(e.get("company",""))
            dur = _sanitize(e.get("duration",""))
            pdf.cell(0, 4.8, _sanitize(f"{title}  -  {comp}" if comp else title), new_x="LMARGIN", new_y="NEXT")
            if dur:
                pdf.set_font("Helvetica", "I", 7)
                pdf.set_text_color(*muted)
                pdf.cell(0, 3.8, _sanitize(dur), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        pdf.ln(1)

    # Projects — relevant first, professional descriptions
    projs = resume_data.get("projects") or []
    rel_proj = [r.lower() for r in (analysis.get("relevant_projects") or [])]
    if projs:
        _section_title(pdf, "PROJECTS")
        def proj_key(p):
            name = (p.get("name") or "").lower()
            for rp in rel_proj:
                if rp and rp in name:
                    return 0
            return 1
        for p in sorted(projs, key=proj_key)[:4]:
            name_p = _sanitize(p.get("name","") or "Project")
            stack = _sanitize(p.get("stack",""))
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(15,23,42)
            pdf.cell(0, 4.6, _sanitize(name_p + (f"  |  {stack}" if stack else "")), new_x="LMARGIN", new_y="NEXT")
            if p.get("description"):
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60,60,60)
                desc = _sanitize(p["description"])
                # bullet
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 4, f"- {desc}")
                pdf.ln(0.5)
        pdf.ln(1)

    # Education
    edu = resume_data.get("education") or []
    if edu:
        _section_title(pdf, "EDUCATION")
        for e in edu[:2]:
            deg = _sanitize(e.get("degree",""))
            school = _sanitize(e.get("school",""))
            year = _sanitize(e.get("year",""))
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(15,23,42)
            pdf.cell(0, 4.5, _sanitize(f"{deg}  -  {school}"), new_x="LMARGIN", new_y="NEXT")
            if year:
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(*muted)
                pdf.cell(0, 3.8, year, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # No internal artifacts (no Tailored for banner, no CV Focus, no Gaps) — employer-ready

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1")
    if isinstance(out, bytearray):
        return bytes(out)
    return out
