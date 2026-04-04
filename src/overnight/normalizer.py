# -*- coding: utf-8 -*-
"""Minimal normalization for overnight source candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from src.overnight.types import SourceCandidate


_ENTITY_PATTERNS = (
    ("USTR", "organization", re.compile(r"\b(?:USTR|United States Trade Representative)\b", re.IGNORECASE)),
    ("Federal Reserve", "organization", re.compile(r"\b(?:Federal Reserve|Fed)\b", re.IGNORECASE)),
    ("White House", "organization", re.compile(r"\bWhite House\b", re.IGNORECASE)),
)
_PERCENT_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_TARIFF_SUBJECT_KEYWORDS = {
    "steel": "steel",
    "aluminum": "aluminum",
    "aluminium": "aluminum",
    "copper": "copper",
    "semiconductor": "semiconductor",
    "semiconductors": "semiconductor",
    "chip": "chips",
    "chips": "chips",
    "auto": "autos",
    "autos": "autos",
    "vehicle": "vehicles",
    "vehicles": "vehicles",
}
_CLAUSE_SEPARATOR_PATTERN = re.compile(r"\n|[.;,]|\bwhile\b|\band\b|\bbut\b", re.IGNORECASE)
_TARIFF_SUBJECT_FALLBACK_PATTERNS = (
    re.compile(r"(?P<subject>[a-z-]+)\s+tariff", re.IGNORECASE),
    re.compile(r"tariff(?:\s+\w+){0,6}\s+(?:on|for)\s+(?:imported\s+)?(?P<subject>[a-z-]+)", re.IGNORECASE),
    re.compile(r"(?:on|for)\s+(?:imported\s+)?(?P<subject>[a-z-]+)", re.IGNORECASE),
)


@dataclass(frozen=True)
class NumericFact:
    metric: str
    value: float
    unit: str
    context: str
    subject: str | None = None


@dataclass(frozen=True)
class EntityMention:
    name: str
    entity_type: str
    matched_text: str


@dataclass(frozen=True)
class NormalizedSourceItem:
    canonical_url: str
    title: str
    summary: str
    document_type: str
    entities: tuple[EntityMention, ...]
    numeric_facts: tuple[NumericFact, ...]
    title_hash: str
    body_hash: str
    content_hash: str
    raw_id: int | None = None


def normalize_candidate(candidate: SourceCandidate) -> NormalizedSourceItem:
    """Canonicalize a collected source candidate into a small normalized record."""

    canonical_url = _canonicalize_url(candidate.candidate_url)
    title = candidate.candidate_title.strip()
    summary = candidate.candidate_summary.strip()
    document_type = _infer_document_type(candidate)
    entities = _extract_entities(title, summary)
    numeric_facts = _extract_numeric_facts(title, summary)
    body_text = summary or title
    content_text = "\n".join(part for part in (title, summary) if part)

    return NormalizedSourceItem(
        canonical_url=canonical_url,
        title=title,
        summary=summary,
        document_type=document_type,
        entities=entities,
        numeric_facts=numeric_facts,
        title_hash=_stable_hash(title),
        body_hash=_stable_hash(body_text),
        content_hash=_stable_hash(content_text),
    )


def _canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _infer_document_type(candidate: SourceCandidate) -> str:
    text = " ".join(
        part.lower()
        for part in (
            candidate.candidate_type,
            candidate.candidate_section or "",
            candidate.candidate_title,
            candidate.candidate_url,
        )
        if part
    )

    if "fact sheet" in text:
        return "fact_sheet"
    if "calendar" in text or candidate.candidate_type == "calendar_event":
        return "calendar_release"
    if "press release" in text or "press-releases" in text or "statements-releases" in text:
        return "press_release"
    return "news_article"


def _extract_entities(title: str, summary: str) -> tuple[EntityMention, ...]:
    text = "\n".join(part for part in (title, summary) if part)
    entities: list[EntityMention] = []
    seen: set[tuple[str, str]] = set()

    for canonical_name, entity_type, pattern in _ENTITY_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        key = (canonical_name, entity_type)
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            EntityMention(
                name=canonical_name,
                entity_type=entity_type,
                matched_text=match.group(0),
            )
        )

    return tuple(entities)


def _extract_numeric_facts(title: str, summary: str) -> tuple[NumericFact, ...]:
    text = "\n".join(part for part in (title, summary) if part)
    facts: list[NumericFact] = []
    seen: set[tuple[str, float, str, str | None, str]] = set()

    for match in _PERCENT_PATTERN.finditer(text):
        context = text[max(0, match.start() - 40): min(len(text), match.end() + 40)].strip()
        metric = "tariff_rate" if "tariff" in context.lower() else "percentage"
        subject = _infer_numeric_fact_subject(text, metric, match.start(), match.end())
        fact = NumericFact(
            metric=metric,
            value=float(match.group("value")),
            unit="percent",
            context=context,
            subject=subject,
        )
        key = (fact.metric, fact.value, fact.unit, fact.subject, fact.context)
        if key in seen:
            continue
        seen.add(key)
        facts.append(fact)

    return tuple(facts)


def _infer_numeric_fact_subject(
    text: str,
    metric: str,
    match_start: int,
    match_end: int,
) -> str | None:
    if metric != "tariff_rate":
        return None

    window_start = max(0, match_start - 80)
    window_end = min(len(text), match_end + 80)
    window = text[window_start:window_end]
    relative_start = match_start - window_start

    keyword_subject = _infer_tariff_subject_from_keywords(window, relative_start)
    if keyword_subject:
        return keyword_subject

    before_text = window[:relative_start]
    after_text = window[relative_start:]

    for pattern in _TARIFF_SUBJECT_FALLBACK_PATTERNS:
        matches = list(pattern.finditer(before_text))
        if matches:
            subject = _normalize_tariff_subject(matches[-1].group("subject"))
            if subject:
                return subject

    for pattern in _TARIFF_SUBJECT_FALLBACK_PATTERNS[1:]:
        match = pattern.search(after_text)
        if match is None:
            continue
        subject = _normalize_tariff_subject(match.group("subject"))
        if subject:
            return subject

    return None


def _infer_tariff_subject_from_keywords(window: str, relative_start: int) -> str | None:
    separators = list(_CLAUSE_SEPARATOR_PATTERN.finditer(window))
    clause_start = max((match.end() for match in separators if match.end() <= relative_start), default=0)
    clause_end = min((match.start() for match in separators if match.start() >= relative_start), default=len(window))

    before_clause = window[clause_start:relative_start]
    after_clause = window[relative_start:clause_end]

    before_subject = _find_keyword_subject(before_clause, prefer_last=True)
    if before_subject:
        return before_subject

    after_subject = _find_keyword_subject(after_clause, prefer_last=False)
    if after_subject:
        return after_subject

    return None


def _find_keyword_subject(text: str, *, prefer_last: bool) -> str | None:
    matches: list[tuple[int, str]] = []
    for keyword, canonical_subject in _TARIFF_SUBJECT_KEYWORDS.items():
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
            matches.append((match.start(), canonical_subject))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0])
    return matches[-1][1] if prefer_last else matches[0][1]


def _normalize_tariff_subject(subject: str) -> str | None:
    normalized = subject.lower().strip(" .,;:-")
    normalized = re.sub(r"\b(imported|import|imports|products|product|goods|good)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
