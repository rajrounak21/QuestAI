from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.agents.research.graph.state import ResearchState
from backend.agents.research.services.llm import init_llm
from backend.agents.research.services.progress import report as report_progress

logger = logging.getLogger(__name__)


VALIDATION_PROMPT = """You are a strict research report validator. Your job is to check whether EACH claim in the report is actually proven by its cited evidence.

STEP-BY-STEP PROCESS for EACH finding:

1. BREAK the finding's explanation into individual atomic claims.
   Example: "Practitioners commonly use BLEU, ROUGE, and Recall"
   becomes:
     A1: "Practitioners commonly use BLEU"
     A2: "Practitioners commonly use ROUGE"
     A3: "Practitioners commonly use Recall"

2. For EACH atomic claim, read the supporting_text of its cited evidence.
   Ask yourself:
   - Does the supporting_text EXPLICITLY mention this specific concept?
   - Does the evidence establish the STRENGTH the claim asserts?
     ("commonly adopt" requires evidence of widespread use, not just that something exists)
   - If the claim says "X and Y", are BOTH supported?
   - If the claim says "increasingly", does the evidence show growth?

3. Assign a verdict per atomic claim:
   - "supported": evidence explicitly states or strongly implies this exact claim
   - "unsupported": evidence does not mention this, or only tangentially relates

4. Overall finding verdict:
   - "supported" if ALL atomic claims are supported
   - "partially_supported" if SOME are supported and SOME are not
   - "unsupported" if NONE are supported

BE STRICT. If the evidence says "evaluation frameworks exist" but the claim says "practitioners commonly adopt these frameworks", that is NOT supported unless the evidence explicitly mentions adoption.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "finding_verdicts": [
    {{
      "finding_index": 1,
      "overall_verdict": "supported/partially_supported/unsupported",
      "atomic_claims": [
        {{
          "claim": "the atomic claim text",
          "verdict": "supported/unsupported",
          "evidence_check": "what the cited evidence actually says about this claim"
        }}
      ]
    }}
  ],
  "issues": ["general issues with the report structure or methodology"],
  "uncited_evidence": ["ev_009"],
  "overall_quality": "good/acceptable/weak"
}}

Research goal: {goal}

Findings:
{findings_text}

Evidence bank:
{evidence_text}

If all findings are fully supported with no issues, return: {{"finding_verdicts": [], "issues": [], "uncited_evidence": [], "overall_quality": "good"}}"""


def _build_findings_text(report):
    if not report:
        return "No report"
    lines = []
    for i, f in enumerate(report.get("findings", []), 1):
        refs = f.get("evidence_refs", [])
        lines.append(
            f"{i}. \"{f.get('title', '')}\"\n"
            f"   Explanation: {f.get('explanation', '')}\n"
            f"   Cited evidence: [{', '.join(refs)}]"
        )
    return "\n\n".join(lines) or "No findings"


def _build_evidence_text(evidence):
    lines = []
    for ev in evidence:
        ev_id = ev.get("id", "")
        claim = ev.get("claim", "")
        src = ev.get("source", {})
        title = src.get("title", "Unknown")
        url = src.get("url", "")
        stype = src.get("source_type", "google")
        supporting = ev.get("supporting_text", "")
        lines.append(
            f"[{ev_id}] Claim: \"{claim}\"\n"
            f"  Source: {title} ({stype}) | {url}\n"
            f"  Supporting: \"{supporting}\""
        )
    return "\n\n".join(lines) or "No evidence"


def _clean_report(report, verdicts, evidence):
    unsupported_indices = set()
    for v in verdicts:
        if v.get("overall_verdict") == "unsupported":
            idx = v.get("finding_index", 0) - 1
            unsupported_indices.add(idx)

    if not unsupported_indices:
        return report

    original_count = len(report.get("findings", []))
    report["findings"] = [
        f for i, f in enumerate(report.get("findings", []))
        if i not in unsupported_indices
    ]
    removed = original_count - len(report["findings"])
    if removed:
        logger.info(f"Post-processing: removed {removed} unsupported findings")

    evidence_map = {ev.get("id", ""): ev for ev in evidence}
    seen_urls = set()
    sources = []
    for finding in report.get("findings", []):
        finding["sources"] = []
        for ref in finding.get("evidence_refs", []):
            ev = evidence_map.get(ref)
            if not ev:
                continue
            src = ev.get("source", {})
            url = src.get("url", "")
            if not url:
                continue
            finding["sources"].append({
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
    report["sources"] = sources

    return report


def _fallback_validate(report, evidence):
    evidence_ids = {ev.get("id", "") for ev in evidence}
    all_issues = []
    invalid_findings = []

    for i, finding in enumerate(report.get("findings", []), 1):
        refs = finding.get("evidence_refs", [])
        if not refs:
            all_issues.append({
                "type": "no_evidence",
                "finding_index": i,
                "reason": f"Finding {i} has no evidence references",
            })
            invalid_findings.append(i - 1)
            continue
        for ref in refs:
            if ref not in evidence_ids:
                all_issues.append({
                    "type": "invalid_ref",
                    "finding_index": i,
                    "reason": f"Finding {i} cites {ref} which does not exist in evidence bank",
                })
                invalid_findings.append(i - 1)

    if invalid_findings:
        report["findings"] = [
            f for i, f in enumerate(report.get("findings", []))
            if i not in set(invalid_findings)
        ]
        evidence_map = {ev.get("id", ""): ev for ev in evidence}
        seen_urls = set()
        sources = []
        for finding in report.get("findings", []):
            finding["sources"] = []
            for ref in finding.get("evidence_refs", []):
                ev = evidence_map.get(ref)
                if not ev:
                    continue
                src = ev.get("source", {})
                url = src.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    finding["sources"].append({"title": src.get("title", ""), "url": url, "source_type": src.get("source_type", "")})
                    sources.append({"title": src.get("title", ""), "url": url, "source_type": src.get("source_type", "")})
        report["sources"] = sources
        logger.info(f"Fallback validation: removed {len(invalid_findings)} findings with invalid refs")

    report["validation_notes"] = {
        "overall_quality": "fallback_check",
        "issues_count": len(all_issues),
        "uncited_count": 0,
        "verdicts": [],
    }

    return report, all_issues


def validator_node(state: ResearchState) -> dict[str, Any]:
    logger.info("Running validator node")
    report_progress("validating", "Checking every claim")

    report = state.get("final_report")
    if not report:
        return {"final_report": report, "validation_issues": [], "resynthesis_count": state.get("resynthesis_count", 0)}

    evidence = state.get("evidence", [])
    goal = state.get("user_query", "")
    resynthesis_count = state.get("resynthesis_count", 0)

    cited_ids = set()
    for finding in report.get("findings", []):
        for ref in finding.get("evidence_refs", []):
            cited_ids.add(ref)
    evidence = [ev for ev in evidence if ev.get("id", "") in cited_ids]

    findings_text = _build_findings_text(report)
    evidence_text = _build_evidence_text(evidence)

    prompt = VALIDATION_PROMPT.format(
        goal=goal,
        findings_text=findings_text,
        evidence_text=evidence_text,
    )

    try:
        llm = init_llm(temperature=0.0, max_tokens=8192)
        raw = llm.invoke(prompt)
        text = raw.content if hasattr(raw, "content") else str(raw)
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)

        verdicts = result.get("finding_verdicts", [])
        issues = result.get("issues", [])
        uncited = result.get("uncited_evidence", [])

        all_issues = []
        for v in verdicts:
            finding_idx = v.get("finding_index", 0)
            for ac in v.get("atomic_claims", []):
                if ac.get("verdict") == "unsupported":
                    all_issues.append({
                        "type": "unsupported_sub_claim",
                        "finding_index": finding_idx,
                        "sub_claim": ac.get("claim", ""),
                        "evidence_check": ac.get("evidence_check", ""),
                        "reason": f"Finding {finding_idx}, sub-claim \"{ac.get('claim', '')}\": {ac.get('evidence_check', '')}",
                    })

        for issue in issues:
            all_issues.append({"type": "general", "reason": issue})

        uncited_info = []
        for ev_id in uncited:
            uncited_info.append({"type": "uncited_evidence", "evidence_id": ev_id, "reason": f"Evidence {ev_id} is relevant but not cited"})

        if verdicts:
            safe = [f"F{v.get('finding_index', '?')}: {v.get('overall_verdict', '?')}" for v in verdicts]
            logger.info(f"Validator verdicts: {safe}")
        if all_issues:
            safe = [i.get("reason", str(i))[:100] for i in all_issues]
            logger.info(f"Validator found {len(all_issues)} blocking issues: {safe}")
        if uncited_info:
            logger.info(f"Validator notes {len(uncited_info)} uncited evidence items")

        report["validation_notes"] = {
            "overall_quality": result.get("overall_quality", "unknown"),
            "issues_count": len(all_issues),
            "uncited_count": len(uncited_info),
            "verdicts": verdicts,
        }

        report = _clean_report(report, verdicts, evidence)

    except Exception as e:
        logger.error(f"Validator LLM failed ({e}), running fallback checks")
        report, all_issues = _fallback_validate(report, evidence)

    return {
        "final_report": report,
        "validation_issues": all_issues,
        "resynthesis_count": resynthesis_count,
    }
