from __future__ import annotations

import io
import logging
import sys
import uuid
from typing import Any

from backend.agents.research.graph.graph import get_graph
from backend.agents.research.memory.session import memory, build_context_for_question

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace"))],
)
logger = logging.getLogger(__name__)


def run_research(
    user_query: str,
    session_id: str | None = None,
    max_rounds: int = 3,
) -> dict[str, Any]:
    if session_id is None:
        session_id = str(uuid.uuid4())

    session = memory.get_or_create(session_id)

    is_followup = bool(session.conversation)
    if is_followup:
        user_query = build_context_for_question(session, user_query)
    else:
        session.research_goal = user_query

    graph = get_graph()

    initial_state = {
        "session_id": session_id,
        "user_query": user_query,
        "research_plan": None,
        "current_round": 1,
        "max_rounds": max_rounds,
        "search_queries": [],
        "raw_results": [],
        "processed_sources": [],
        "evidence": [],
        "identified_gaps": [],
        "follow_up_queries": [],
        "research_complete": False,
        "final_report": None,
        "searches_performed": [],
        "validation_issues": [],
        "resynthesis_count": 0,
    }

    logger.info(f"Starting research: {user_query}")
    result = graph.invoke(initial_state)

    report = result.get("final_report")

    session.research_plan = result.get("research_plan")
    session.evidence = result.get("evidence", [])
    session.gaps = result.get("identified_gaps", [])
    session.searches = result.get("searches_performed", [])
    session.current_round = result.get("current_round", 1)

    assistant_answer = ""
    if report:
        assistant_answer = _format_report(report)

    session.conversation.append({
        "user": user_query,
        "assistant": assistant_answer,
    })

    return {
        "session_id": session_id,
        "report": report,
        "formatted": assistant_answer,
        "evidence": result.get("evidence", []),
        "searches_performed": result.get("searches_performed", []),
    }


def _build_display_id_map(report: dict[str, Any]) -> dict[str, str]:
    all_refs = []
    for finding in report.get("findings", []):
        for ref in finding.get("evidence_refs", []):
            if ref not in all_refs:
                all_refs.append(ref)
    return {ref: str(i + 1) for i, ref in enumerate(all_refs)}


def _format_report(report: dict[str, Any]) -> str:
    display_map = _build_display_id_map(report)
    lines: list[str] = []

    goal = report.get("goal", "")
    lines.append(f"# Research Report\n")
    lines.append(f"**Goal:** {goal}\n")

    summary = report.get("executive_summary", "")
    if summary:
        lines.append(f"## Executive Summary\n")
        lines.append(f"{summary}\n")

    findings = report.get("findings", [])
    if findings:
        lines.append(f"## Key Findings\n")
        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. {f.get('title', 'Finding')}\n")

            explanation = f.get("explanation", "")
            refs = f.get("evidence_refs", [])
            if refs:
                display_refs = " ".join(f"[{display_map.get(r, r)}]" for r in refs if r in display_map)
                lines.append(f"{explanation} {display_refs}\n")
            else:
                lines.append(f"{explanation}\n")

            sources = f.get("sources", [])
            for s in sources:
                url = s.get("url", "")
                title = s.get("title", "")
                stype = s.get("source_type", "")
                if url:
                    lines.append(f"- [{title}]({url}) ({stype})")
            lines.append("")

    comparison = report.get("comparison", "")
    if comparison:
        lines.append(f"## Comparison / Analysis\n")
        lines.append(f"{comparison}\n")

    recent = report.get("recent_developments", "")
    if recent:
        lines.append(f"## Recent Developments\n")
        lines.append(f"{recent}\n")

    limitations = report.get("limitations", "")
    if limitations:
        lines.append(f"## Limitations\n")
        lines.append(f"{limitations}\n")

    val_notes = report.get("validation_notes", {})
    if val_notes:
        quality = val_notes.get("overall_quality", "unknown")
        issue_count = val_notes.get("issues_count", 0)
        lines.append(f"## Validation\n")
        lines.append(f"Quality: **{quality}** | Issues found: {issue_count}\n")

    sources = report.get("sources", [])
    if sources:
        lines.append(f"## Sources\n")
        for i, s in enumerate(sources, 1):
            title = s.get("title", "Untitled")
            url = s.get("url", "")
            stype = s.get("source_type", "")
            lines.append(f"[{i}] [{title}]({url}) ({stype})")
        lines.append("")

    return "\n".join(lines)


def interactive():
    print("=" * 60)
    print("  Research Agent V1")
    print("  Type your research question. Type 'quit' to exit.")
    print("=" * 60)

    session_id = str(uuid.uuid4())

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        result = run_research(user_input, session_id=session_id)
        print(result["formatted"])


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = run_research(query)
        print(result["formatted"])
    else:
        interactive()
