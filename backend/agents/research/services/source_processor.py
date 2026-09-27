from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from backend.agents.research.schemas.sources import ProcessedSource, SearchResult, SourceType
from backend.agents.research.services.llm import init_llm_light

logger = logging.getLogger(__name__)

MAX_SYNTHESIS_EVIDENCE = 15


def process_sources(raw_results: list[SearchResult]) -> list[ProcessedSource]:
    seen_urls: set[str] = set()
    processed: list[ProcessedSource] = []

    for r in raw_results:
        if not r.title.strip() or not r.snippet.strip():
            continue
        if r.url in seen_urls:
            continue
        seen_urls.add(r.url)
        processed.append(ProcessedSource(
            title=r.title,
            url=r.url,
            source_type=r.source_type,
            date=r.date,
            snippet=r.snippet,
        ))

    return processed


_EXTRACTION_PROMPT = """Extract evidence from these sources.

Return ONLY valid JSON:
{{"extractions": [{{"claim": "what the source says", "supporting_text": "exact text from snippet", "relevance": "high/medium/low/discard", "sub_question": "which question it answers", "source_index": 0}}]}}

Rules:
- claim = one clear statement the source makes
- supporting_text = the exact snippet text that supports it
- relevance = discard if not relevant
- source_index = which source (0-based)
- Keep claims SHORT (under 30 words)
- Keep supporting_text SHORT (under 100 words)

Sub-questions:
{questions}

Sources:
{sources}"""


def extract_evidence(
    sources: list[ProcessedSource],
    sub_questions: list[str],
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    if not sources:
        return []

    questions_text = "\n".join(f"- {q}" for q in sub_questions)

    for attempt in range(max_retries + 1):
        batch_size = 5 if attempt > 0 else 8
        source_descriptions = []
        for i, s in enumerate(sources[:batch_size]):
            source_descriptions.append(
                f"Source {i}:\n"
                f"Title: {s.title}\n"
                f"URL: {s.url}\n"
                f"Type: {s.source_type.value}\n"
                f"Snippet: {s.snippet[:120]}"
            )

        sources_text = "\n\n".join(source_descriptions)
        prompt = _EXTRACTION_PROMPT.format(
            questions=questions_text,
            sources=sources_text,
        )

        try:
            llm = init_llm_light(temperature=0.0, max_tokens=2048)
            raw = llm.invoke(prompt)
            text = raw.content if hasattr(raw, "content") else str(raw)
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            if not text or text[0] != "{":
                raise ValueError(f"Not JSON: {text[:80]}")

            result = json.loads(text)

            extractions = []
            for ext in result.get("extractions", []):
                if ext.get("relevance", "").lower() == "discard":
                    continue
                idx = min(ext.get("source_index", 0), len(sources) - 1)
                extractions.append({
                    "source": sources[idx].to_dict(),
                    "claim": ext.get("claim", ""),
                    "supporting_text": ext.get("supporting_text", ""),
                    "sub_question": ext.get("sub_question", ""),
                    "relevance": ext.get("relevance", "medium"),
                })

            for i, ext in enumerate(extractions):
                ext["id"] = f"ev_{i + 1:03d}"

            if extractions:
                logger.info(f"Evidence extraction: {len(extractions)} items (attempt {attempt + 1})")
                return extractions
            else:
                logger.warning(f"Evidence extraction: 0 items (attempt {attempt + 1})")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Evidence extraction parse error (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                continue
        except Exception as e:
            logger.error(f"Evidence extraction failed: {e}")
            break

    logger.error("Evidence extraction failed after all retries, using fallback")
    fallback = []
    for i, s in enumerate(sources):
        fallback.append({
            "id": f"ev_{i + 1:03d}",
            "source": s.to_dict(),
            "claim": s.snippet[:150],
            "supporting_text": s.snippet,
            "sub_question": "",
            "relevance": "medium",
        })
    return fallback


def select_evidence(
    evidence: list[dict[str, Any]],
    max_items: int = MAX_SYNTHESIS_EVIDENCE,
) -> list[dict[str, Any]]:
    if len(evidence) <= max_items:
        return evidence

    relevance_order = {"high": 0, "medium": 1, "low": 2}
    scored = []
    for ev in evidence:
        rel = relevance_order.get(ev.get("relevance", "medium"), 1)
        scored.append((rel, ev))

    scored.sort(key=lambda x: x[0])

    selected = []
    seen_claims: set[str] = set()
    source_type_counts: Counter = Counter()
    sub_q_coverage: set[str] = set()

    for _, ev in scored:
        if len(selected) >= max_items:
            break

        claim_key = ev.get("claim", "")[:80].lower().strip()
        if claim_key in seen_claims:
            continue
        seen_claims.add(claim_key)

        st = ev.get("source", {}).get("source_type", "google")
        if source_type_counts[st] >= max_items * 0.5:
            continue
        source_type_counts[st] += 1

        sub_q = ev.get("sub_question", "")
        if sub_q and sub_q in sub_q_coverage:
            remaining = max_items - len(selected)
            needed = len(set(
                e.get("sub_question", "") for e in evidence
                if e.get("sub_question", "")
            )) - len(sub_q_coverage)
            if needed > 0 and remaining <= needed:
                continue

        selected.append(ev)
        if sub_q:
            sub_q_coverage.add(sub_q)

    logger.info(f"Evidence selection: {len(selected)} from {len(evidence)} (budget: {max_items})")
    return selected
