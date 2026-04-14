# -*- coding: utf-8 -*-
"""Minimal normalization for overnight source candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from app.sources.types import SourceCandidate


_ENTITY_PATTERNS = (
    ("USTR", "organization", re.compile(r"\b(?:USTR|United States Trade Representative)\b", re.IGNORECASE)),
    ("Federal Reserve", "organization", re.compile(r"\b(?:Federal Reserve|Fed)\b", re.IGNORECASE)),
    ("White House", "organization", re.compile(r"\bWhite House\b", re.IGNORECASE)),
)
_PERCENT_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_BASIS_POINTS_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:basis points?|bp)\b", re.IGNORECASE)
_USD_AMOUNT_PATTERN = re.compile(
    r"(?P<prefix>US\$|USD\s*|\$)\s*(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>trillion|billion|million|thousand|tn|bn|mn|m|k)?\b",
    re.IGNORECASE,
)
_JOBS_COUNT_PATTERN = re.compile(
    r"(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>million|thousand|m|k)?\s+(?P<lemma>jobs|job|payrolls?|workers|claims|openings|layoffs)\b",
    re.IGNORECASE,
)
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
_CLAUSE_SEPARATOR_PATTERN = re.compile(
    r"\n|;|(?<!\d)[.,]|[.,](?!\d)|\bwhile\b|\band\b|\bbut\b",
    re.IGNORECASE,
)
_TARIFF_SUBJECT_FALLBACK_PATTERNS = (
    re.compile(r"(?P<subject>[a-z-]+)\s+tariff", re.IGNORECASE),
    re.compile(r"tariff(?:\s+\w+){0,6}\s+(?:on|for)\s+(?:imported\s+)?(?P<subject>[a-z-]+)", re.IGNORECASE),
    re.compile(r"(?:on|for)\s+(?:imported\s+)?(?P<subject>[a-z-]+)", re.IGNORECASE),
)
_BASIS_POINTS_SUBJECT_KEYWORDS = {
    "fed funds": "rates",
    "policy rate": "rates",
    "rates": "rates",
    "rate": "rates",
    "yield spreads": "spread",
    "yield spread": "spread",
    "spreads": "spread",
    "spread": "spread",
    "yields": "yields",
    "yield": "yields",
}
_USD_AMOUNT_SUBJECT_KEYWORDS = {
    "trade deficit": "deficit",
    "deficit": "deficit",
    "surplus": "surplus",
    "exports": "exports",
    "imports": "imports",
    "revenue": "revenue",
    "spending": "spending",
    "funding": "funding",
    "budget": "budget",
    "buyback": "buyback",
    "buybacks": "buyback",
    "capex": "capex",
    "investment": "investment",
}
_JOBS_SUBJECT_KEYWORDS = {
    "nonfarm payrolls": "payrolls",
    "payrolls": "payrolls",
    "payroll": "payrolls",
    "job openings": "job_openings",
    "openings": "job_openings",
    "jobless claims": "jobless_claims",
    "claims": "jobless_claims",
    "layoffs": "layoffs",
    "jobs": "jobs",
    "job": "jobs",
    "employment": "employment",
}
_SCALE_MULTIPLIERS = {
    "thousand": 1_000.0,
    "k": 1_000.0,
    "million": 1_000_000.0,
    "m": 1_000_000.0,
    "mn": 1_000_000.0,
    "billion": 1_000_000_000.0,
    "bn": 1_000_000_000.0,
    "trillion": 1_000_000_000_000.0,
    "tn": 1_000_000_000_000.0,
}


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
    excerpt_source: str
    document_type: str
    published_at: str | None
    published_at_source: str
    entities: tuple[EntityMention, ...]
    numeric_facts: tuple[NumericFact, ...]
    title_hash: str
    body_hash: str
    content_hash: str
    capture_path: str = "direct"
    capture_provider: str = ""
    article_fetch_status: str = "not_attempted"
    raw_id: int | None = None


def normalize_candidate(candidate: SourceCandidate) -> NormalizedSourceItem:
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
        excerpt_source=(candidate.candidate_excerpt_source or "").strip(),
        document_type=document_type,
        published_at=(candidate.candidate_published_at or "").strip() or None,
        published_at_source=(candidate.candidate_published_at_source or "").strip(),
        entities=entities,
        numeric_facts=numeric_facts,
        title_hash=_stable_hash(title),
        body_hash=_stable_hash(body_text),
        content_hash=_stable_hash(content_text),
        capture_path=(candidate.capture_path or "direct").strip() or "direct",
        capture_provider=(candidate.capture_provider or "").strip(),
        article_fetch_status=(candidate.article_fetch_status or "not_attempted").strip() or "not_attempted",
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
    facts_by_signature: dict[tuple[str, float, str, str | None], NumericFact] = {}

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
        signature = (fact.metric, fact.value, fact.unit, fact.subject)
        existing = facts_by_signature.get(signature)
        if existing is None or len(fact.context) > len(existing.context):
            facts_by_signature[signature] = fact

    for match in _USD_AMOUNT_PATTERN.finditer(text):
        value = _parse_scaled_number(match.group("value"), match.group("scale"))
        context = text[max(0, match.start() - 60): min(len(text), match.end() + 60)].strip()
        subject = _infer_metric_subject(
            text=text,
            metric="usd_amount",
            match_start=match.start(),
            match_end=match.end(),
        )
        fact = NumericFact(
            metric="usd_amount",
            value=value,
            unit="usd",
            context=context,
            subject=subject,
        )
        signature = (fact.metric, fact.value, fact.unit, fact.subject)
        existing = facts_by_signature.get(signature)
        if existing is None or len(fact.context) > len(existing.context):
            facts_by_signature[signature] = fact

    for match in _JOBS_COUNT_PATTERN.finditer(text):
        value = _parse_scaled_number(match.group("value"), match.group("scale"))
        context = text[max(0, match.start() - 60): min(len(text), match.end() + 60)].strip()
        subject = _infer_metric_subject(
            text=text,
            metric="jobs_count",
            match_start=match.start(),
            match_end=match.end(),
        )
        if subject is None:
            lemma = str(match.group("lemma") or "").lower()
            subject = _JOBS_SUBJECT_KEYWORDS.get(lemma, "jobs")
        fact = NumericFact(
            metric="jobs_count",
            value=value,
            unit="jobs",
            context=context,
            subject=subject,
        )
        signature = (fact.metric, fact.value, fact.unit, fact.subject)
        existing = facts_by_signature.get(signature)
        if existing is None or len(fact.context) > len(existing.context):
            facts_by_signature[signature] = fact

    for match in _BASIS_POINTS_PATTERN.finditer(text):
        context = text[max(0, match.start() - 60): min(len(text), match.end() + 60)].strip()
        fact = NumericFact(
            metric="basis_points",
            value=float(match.group("value")),
            unit="basis_points",
            context=context,
            subject=_infer_metric_subject(
                text=text,
                metric="basis_points",
                match_start=match.start(),
                match_end=match.end(),
            ),
        )
        signature = (fact.metric, fact.value, fact.unit, fact.subject)
        existing = facts_by_signature.get(signature)
        if existing is None or len(fact.context) > len(existing.context):
            facts_by_signature[signature] = fact

    return tuple(facts_by_signature.values())


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


def _infer_metric_subject(
    *,
    text: str,
    metric: str,
    match_start: int,
    match_end: int,
) -> str | None:
    keyword_map = {
        "basis_points": _BASIS_POINTS_SUBJECT_KEYWORDS,
        "usd_amount": _USD_AMOUNT_SUBJECT_KEYWORDS,
        "jobs_count": _JOBS_SUBJECT_KEYWORDS,
    }.get(metric)
    if not keyword_map:
        return None
    return _infer_subject_from_keywords(text, match_start, match_end, keyword_map)


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


def _infer_subject_from_keywords(
    text: str,
    match_start: int,
    match_end: int,
    keyword_map: dict[str, str],
) -> str | None:
    window_start = max(0, match_start - 80)
    window_end = min(len(text), match_end + 80)
    window = text[window_start:window_end]
    relative_start = match_start - window_start

    separators = list(_CLAUSE_SEPARATOR_PATTERN.finditer(window))
    clause_start = max((match.end() for match in separators if match.end() <= relative_start), default=0)
    clause_end = min((match.start() for match in separators if match.start() >= relative_start), default=len(window))

    before_clause = window[clause_start:relative_start]
    after_clause = window[relative_start:clause_end]

    before_subject = _find_keyword_label(before_clause, keyword_map, prefer_last=True)
    if before_subject:
        return before_subject

    after_subject = _find_keyword_label(after_clause, keyword_map, prefer_last=False)
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


def _find_keyword_label(text: str, keyword_map: dict[str, str], *, prefer_last: bool) -> str | None:
    matches: list[tuple[int, str]] = []
    for keyword, label in keyword_map.items():
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
            matches.append((match.start(), label))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0])
    return matches[-1][1] if prefer_last else matches[0][1]


def _normalize_tariff_subject(subject: str) -> str | None:
    normalized = subject.lower().strip(" .,;:-")
    normalized = re.sub(r"\b(imported|import|imports|products|product|goods|good)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _parse_scaled_number(raw_value: str, raw_scale: str | None) -> float:
    normalized_value = float(str(raw_value).replace(",", ""))
    scale = str(raw_scale or "").strip().lower()
    return normalized_value * _SCALE_MULTIPLIERS.get(scale, 1.0)


def format_numeric_fact_value(fact: NumericFact, *, style: str = "compact") -> str:
    if fact.unit == "percent":
        return f"{fact.value:.1f}%" if style == "compact" else f"{fact.value:.1f} percent"
    if fact.unit == "basis_points":
        value_text = f"{int(fact.value)}" if float(fact.value).is_integer() else f"{fact.value:.1f}"
        return f"{value_text} bp" if style == "compact" else f"{value_text} basis points"
    if fact.unit == "usd":
        return _format_usd_value(fact.value, style=style)
    if fact.unit == "jobs":
        count = int(round(fact.value))
        return f"{count:,}" if style == "compact" else f"{count:,} jobs"
    if float(fact.value).is_integer():
        return f"{int(fact.value):,}"
    return f"{fact.value:,.2f}"


def _format_usd_value(value: float, *, style: str) -> str:
    absolute_value = abs(float(value))
    sign = "-" if float(value) < 0 else ""
    if absolute_value >= 1_000_000_000_000:
        scaled = absolute_value / 1_000_000_000_000
        return f"{sign}${scaled:.1f}T" if style == "compact" else f"{sign}${scaled:.1f} trillion"
    if absolute_value >= 1_000_000_000:
        scaled = absolute_value / 1_000_000_000
        return f"{sign}${scaled:.1f}B" if style == "compact" else f"{sign}${scaled:.1f} billion"
    if absolute_value >= 1_000_000:
        scaled = absolute_value / 1_000_000
        return f"{sign}${scaled:.1f}M" if style == "compact" else f"{sign}${scaled:.1f} million"
    if absolute_value >= 1_000:
        scaled = absolute_value / 1_000
        return f"{sign}${scaled:.1f}K" if style == "compact" else f"{sign}${scaled:.1f} thousand"
    return f"{sign}${absolute_value:,.2f}" if style == "compact" else f"{sign}${absolute_value:,.2f}"


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
