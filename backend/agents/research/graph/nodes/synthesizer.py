from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.services.llm import init_llm
from backend.agents.research.services.progress import report as report_progress
from backend.agents.research.services.source_processor import select_evidence

logger = logging.getLogger(__name__)


SYNTHESIS_PROMPT = """You are a research synthesizer. Create a comprehensive research report from the collected evidence.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "executive_summary": "2-4 sentence summary",
  "findings": [
    {{
      "title": "Finding title",
      "explanation": "Detailed explanation with inline evidence references",
      "evidence_refs": ["ev_001", "ev_003"]
    }}
  ],
  "comparison": "Compare different perspectives if found",
  "recent_developments": "Recent developments if relevant",
  "limitations": "Limitations and gaps"
}}

Research goal: {goal}

Sub-questions:
{sub_questions}

Evidence bank (count: {evidence_count}):
{evidence_text}

Gaps:
{gaps}

Rules:
- ONLY reference evidence IDs that appear in the evidence bank above
- Do NOT invent or fabricate evidence IDs
- Each finding MUST cite at least one evidence ID
- CRITICAL: Each explanation must ONLY contain claims directly stated in the evidence supporting_text
- Do NOT infer, extrapolate, or generalize beyond what the evidence says
- Use hedging language: "suggests", "indicates", "according to", "the source notes"
- Do NOT make claims about what a source "aims to", "seeks to", or "intends to" unless the evidence explicitly states this
- Do NOT claim something "serves as" or "represents" a standard unless evidence says so
- Be specific: quote or closely paraphrase the evidence supporting_text
- Be honest about limitations
- Keep findings to 3-6 items
- When evidence is weak or ambiguous, say "the evidence suggests" rather than stating as fact"""


RESYNTHESIS_PROMPT = """You are a research synthesizer performing a RE-SYNTHESIS.
You have the SAME evidence bank -- you CANNOT reference evidence IDs not listed below.

Fix the issues identified by the validator while keeping all evidence references valid.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "executive_summary": "2-4 sentence summary",
  "findings": [
    {{
      "title": "Finding title",
      "explanation": "Detailed explanation with inline evidence references",
      "evidence_refs": ["ev_001", "ev_003"]
    }}
  ],
  "comparison": "Compare different perspectives if found",
  "recent_developments": "Recent developments if relevant",
  "limitations": "Limitations and gaps"
}}

Research goal: {goal}

Sub-questions:
{sub_questions}

Evidence bank (count: {evidence_count}):
{evidence_text}

Previous findings:
{previous_findings}

Validator feedback:
{validator_feedback}

Rules:
- You CANNOT add new evidence IDs -- only use IDs from the evidence bank
- Remove or rewrite claims that the validator identified as unsupported
- CRITICAL: Each explanation must ONLY contain claims directly stated in the evidence supporting_text
- Do NOT infer, extrapolate, or generalize beyond what the evidence says
- Use hedging language: "suggests", "indicates", "according to", "the source notes"
- Do NOT make claims about what a source "aims to", "seeks to", or "intends to" unless the evidence explicitly states this
- Reassign evidence references to better match claims
- Merge findings if evidence is insufficient for separate findings
- Keep findings to 3-6 items"""


def _build_evidence_text(evidence):
    lines = []
    for ev in evidence:
        ev_id = ev.get("id", "")
        claim = ev.get("claim", "")
        supporting = ev.get("supporting_text", "")
        src = ev.get("source", {})
        title = src.get("title", "Unknown")
        url = src.get("url", "")
        stype = src.get("source_type", "google")
        sub_q = ev.get("sub_question", "")
        lines.append(
            f"[{ev_id}] Claim: \"{claim}\"\n"
            f"  Source: {title} | {url} | {stype}\n"
            f"  Supporting: \"{supporting}\"\n"
            f"  Sub-question: {sub_q or 'N/A'}"
        )
    return "\n\n".join(lines)


def _build_sources_from_refs(findings, evidence_map):
    seen_urls = set()
    sources = []
    for finding in findings:
        finding_sources = []
        for ref in finding.get("evidence_refs", []):
            ev = evidence_map.get(ref)
            if not ev:
                continue
            src = ev.get("source", {})
            url = src.get("url", "")
            if not url:
                continue
            finding_sources.append({
                "title": src.get("title", ""),
                "url": url,
                "source_type": src.get("source_type", ""),
            })
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append({
                    "title": src.get("title", ""),
                    "url": url,
                    "source_type": src.get("source_type", ""),
                })
        finding["sources"] = finding_sources
    return sources


def _format_findings_for_feedback(report):
    if not report:
        return "No previous findings"
    lines = []
    for i, f in enumerate(report.get("findings", []), 1):
        refs = f.get("evidence_refs", [])
        lines.append(f"{i}. {f.get('title', '')}: {f.get('explanation', '')[:200]}... [refs: {', '.join(refs)}]")
    return "\n".join(lines) or "No previous findings"


def synthesizer_node(state):
    logger.info("Running synthesizer node")
    report_progress(
        "synthesizing",
        "Rewriting report" if state.get("resynthesis_count") else "Writing report",
    )

    plan = state.get("research_plan", {})
    evidence = state.get("evidence", [])
    gaps = state.get("identified_gaps", [])
    goal = state.get("user_query", "")
    resynthesis_count = state.get("resynthesis_count", 0)
    validation_issues = state.get("validation_issues", [])
    previous_report = state.get("final_report")

    selected = select_evidence(evidence)
    evidence_map = {ev.get("id", ""): ev for ev in selected}

    sub_questions = "\n".join(
        f"- {sq.get('question', '')}"
        for sq in plan.get("sub_questions", [])
    ) or "No sub-questions defined"

    evidence_text = _build_evidence_text(selected)

    gaps_text = "\n".join(
        f"- [{g.get('status', '')}] {g.get('question', '')}"
        for g in gaps
    ) or "No gaps identified"

    if resynthesis_count > 0 and validation_issues:
        feedback_text = "\n".join(
            f"- {issue.get('reason', str(issue))}" if isinstance(issue, dict) else f"- {issue}"
            for issue in validation_issues
        )
        prompt = RESYNTHESIS_PROMPT.format(
            goal=goal,
            sub_questions=sub_questions,
            evidence_count=len(selected),
            evidence_text=evidence_text or "No evidence collected",
            previous_findings=_format_findings_for_feedback(previous_report),
            validator_feedback=feedback_text,
        )
    else:
        prompt = SYNTHESIS_PROMPT.format(
            goal=goal,
            sub_questions=sub_questions,
            evidence_count=len(selected),
            evidence_text=evidence_text or "No evidence collected",
            gaps=gaps_text,
        )

    try:
        llm = init_llm(temperature=0.2, max_tokens=4096)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        result = json.loads(text.strip().removeprefix("```json").removesuffix("```"))

        findings = result.get("findings", [])
        for f in findings:
            refs = f.get("evidence_refs", [])
            f["evidence_refs"] = [r for r in refs if r in evidence_map]

        sources = _build_sources_from_refs(findings, evidence_map)

        report = {
            "goal": goal,
            "executive_summary": result.get("executive_summary", ""),
            "findings": findings,
            "comparison": result.get("comparison", ""),
            "recent_developments": result.get("recent_developments", ""),
            "limitations": result.get("limitations", ""),
            "sources": sources,
        }

    except Exception as e:
        logger.error(f"Synthesis failed: {e}, using fallback")
        report = _fallback_synthesis(goal, evidence, gaps)

    return {"final_report": report}


def _fallback_synthesis(goal, evidence, gaps):
    findings = []
    for i, e in enumerate(evidence[:6]):
        findings.append({
            "title": f"Finding {i + 1}",
            "explanation": e.get("claim", e.get("supporting_text", "")),
            "evidence_refs": [e.get("id", "")],
            "sources": [],
        })

    evidence_map = {e.get("id", ""): e for e in evidence}
    sources = _build_sources_from_refs(findings, evidence_map)

    limitations = "This report was generated from limited evidence." if gaps else ""

    return {
        "goal": goal,
        "executive_summary": f"Research on: {goal}. Found {len(evidence)} evidence items.",
        "findings": findings,
        "comparison": "",
        "recent_developments": "",
        "limitations": limitations,
        "sources": sources,
    }
