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


@dataclass(frozen=True)
class NumericFact:
    metric: str
    value: float
    unit: str
    context: str


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
    seen: set[tuple[str, float, str, str]] = set()

    for match in _PERCENT_PATTERN.finditer(text):
        context = text[max(0, match.start() - 40): min(len(text), match.end() + 40)].strip()
        metric = "tariff_rate" if "tariff" in context.lower() else "percentage"
        fact = NumericFact(
            metric=metric,
            value=float(match.group("value")),
            unit="percent",
            context=context,
        )
        key = (fact.metric, fact.value, fact.unit, fact.context)
        if key in seen:
            continue
        seen.add(key)
        facts.append(fact)

    return tuple(facts)


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
