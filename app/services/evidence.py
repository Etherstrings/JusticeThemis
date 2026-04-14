# -*- coding: utf-8 -*-
"""Evidence-point extraction for downstream analysis."""

from __future__ import annotations

import re

from app.normalizer import NumericFact, format_numeric_fact_value


_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_ABBREVIATIONS = (
    ("U.S.", "US_ABBR"),
    ("U.K.", "UK_ABBR"),
    ("Mr.", "MR_ABBR"),
    ("Ms.", "MS_ABBR"),
    ("Dr.", "DR_ABBR"),
)
_INITIAL_ABBREVIATION_PATTERN = re.compile(r"\b([A-Z])\.")
_SKIP_SENTENCE_PATTERNS = (
    re.compile(r"^for media inquiries\b", re.IGNORECASE),
    re.compile(r"^attachment\s*\(", re.IGNORECASE),
    re.compile(r"^\[email protected\]$", re.IGNORECASE),
    re.compile(r"\baccessible materials\b", re.IGNORECASE),
    re.compile(r"\(pdf\)", re.IGNORECASE),
)


def build_evidence_points(
    *,
    summary: str,
    numeric_facts: tuple[NumericFact, ...],
) -> tuple[str, ...]:
    points: list[str] = []
    normalized = str(summary or "").strip()

    for sentence in _candidate_sentences(normalized):
        cleaned = sentence.strip()
        if not cleaned:
            continue
        points.append(cleaned)
        if len(points) >= 3:
            break

    for fact in numeric_facts:
        if _summary_already_mentions_fact(normalized, fact):
            continue
        context = fact.context.strip()
        if any(pattern.search(context) for pattern in _SKIP_SENTENCE_PATTERNS):
            continue
        subject = f" for {fact.subject}" if fact.subject else ""
        readable_value = format_numeric_fact_value(fact, style="readable")
        points.append(f"{fact.metric}: {readable_value}{subject}. {context}".strip())
        if len(points) >= 4:
            break

    return _dedupe(points)[:4]


def _candidate_sentences(summary: str) -> list[str]:
    normalized = str(summary or "").strip()
    if not normalized:
        return []

    protected = normalized
    for original, token in _ABBREVIATIONS:
        protected = protected.replace(original, token)
    protected = _INITIAL_ABBREVIATION_PATTERN.sub(lambda match: f"{match.group(1)}_INIT", protected)

    sentences = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(protected) if part.strip()]
    restored = []
    for sentence in sentences:
        candidate = sentence
        for original, token in _ABBREVIATIONS:
            candidate = candidate.replace(token, original)
        candidate = re.sub(r"\b([A-Z])_INIT", lambda match: f"{match.group(1)}.", candidate)
        if any(pattern.search(candidate) for pattern in _SKIP_SENTENCE_PATTERNS):
            continue
        restored.append(candidate)

    sentences = restored
    if not sentences:
        return [normalized]

    preferred: list[str] = []
    for sentence in sentences:
        if any(token in sentence for token in ("$", "%", "increased", "decreased", "rose", "fell", "tariff", "oil", "rate", "deficit", "imports", "exports")):
            preferred.append(sentence)
    return preferred or sentences[:2]


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def _summary_already_mentions_fact(summary: str, fact: NumericFact) -> bool:
    lowered_summary = summary.lower()
    raw_value = f"{fact.value}"
    compact_value = raw_value[:-2] if raw_value.endswith(".0") else raw_value
    if fact.unit == "percent":
        unit_tokens = {fact.unit.lower(), "%", "percent"}
        return (
            raw_value.lower() in lowered_summary or compact_value.lower() in lowered_summary
        ) and any(token in lowered_summary for token in unit_tokens)
    if fact.unit == "basis_points":
        return any(token in lowered_summary for token in {f"{compact_value} basis point", f"{compact_value} basis points", f"{compact_value} bp"})
    if fact.unit == "usd":
        return any(token in lowered_summary for token in _usd_fact_tokens(fact.value))
    if fact.unit == "jobs":
        jobs_value = f"{int(round(fact.value)):,}".lower()
        return any(token in lowered_summary for token in {f"{jobs_value} jobs", jobs_value.replace(",", "")})
    return raw_value.lower() in lowered_summary or compact_value.lower() in lowered_summary


def _usd_fact_tokens(value: float) -> set[str]:
    absolute_value = abs(float(value))
    if not absolute_value:
        return {"$0.0", "$0", "0.0", "0"}

    tokens: set[str] = set()
    for threshold, word, compact_suffixes in (
        (1_000_000_000_000, "trillion", ("t", "tn")),
        (1_000_000_000, "billion", ("b", "bn")),
        (1_000_000, "million", ("m", "mn")),
        (1_000, "thousand", ("k",)),
    ):
        if absolute_value < threshold:
            continue
        scaled = absolute_value / threshold
        for amount_text in _numeric_text_variants(scaled):
            tokens.add(f"${amount_text} {word}")
            tokens.add(f"{amount_text} {word}")
            for suffix in compact_suffixes:
                tokens.add(f"${amount_text}{suffix}")
                tokens.add(f"{amount_text}{suffix}")
        return tokens

    for amount_text in _numeric_text_variants(absolute_value):
        tokens.add(f"${amount_text}")
        tokens.add(amount_text)
    return tokens


def _numeric_text_variants(value: float) -> set[str]:
    fixed = f"{value:.1f}"
    trimmed = fixed.rstrip("0").rstrip(".")
    return {fixed.lower(), trimmed.lower()}
