# -*- coding: utf-8 -*-
"""Analysis readiness guardrails for captured items."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisGuardrailAssessment:
    analysis_status: str
    analysis_confidence: str
    analysis_blockers: tuple[str, ...]


def assess_analysis_guardrails(
    *,
    coverage_tier: str,
    organization_type: str,
    summary_quality: str,
    a_share_relevance: str,
    excerpt_source: str,
    published_at_source: str,
    beneficiary_directions: tuple[str, ...],
    pressured_directions: tuple[str, ...],
    price_up_signals: tuple[str, ...],
    follow_up_checks: tuple[str, ...],
) -> AnalysisGuardrailAssessment:
    blockers: list[str] = []
    actionable_count = len(beneficiary_directions) + len(pressured_directions) + len(price_up_signals)
    source_bucket = coverage_tier.strip() or organization_type.strip()

    if a_share_relevance == "low":
        blockers.append("low_relevance")
    if source_bucket == "editorial_media":
        blockers.append("editorial_context_only")
    if summary_quality == "low":
        blockers.append("low_summary_quality")
    if not published_at_source.strip():
        blockers.append("missing_published_time_source")
    if not excerpt_source.strip() or excerpt_source.startswith("meta:") or excerpt_source == "body_fallback":
        blockers.append("weak_excerpt_basis")
    if actionable_count == 0 and a_share_relevance in {"high", "medium"}:
        blockers.append("missing_direct_market_mapping")
    if not follow_up_checks:
        blockers.append("missing_follow_up_checks")

    if (
        source_bucket in {"official_policy", "official_data"}
        and a_share_relevance == "high"
        and summary_quality == "high"
        and actionable_count > 0
        and "weak_excerpt_basis" not in blockers
        and "missing_published_time_source" not in blockers
    ):
        return AnalysisGuardrailAssessment(
            analysis_status="ready",
            analysis_confidence="high",
            analysis_blockers=tuple(_dedupe(blockers)),
        )

    if "low_relevance" in blockers or (
        source_bucket == "editorial_media" and a_share_relevance != "high"
    ):
        return AnalysisGuardrailAssessment(
            analysis_status="background",
            analysis_confidence="low",
            analysis_blockers=tuple(_dedupe(blockers)),
        )

    confidence = "medium"
    if source_bucket == "editorial_media" or summary_quality != "high":
        confidence = "low"

    return AnalysisGuardrailAssessment(
        analysis_status="review",
        analysis_confidence=confidence,
        analysis_blockers=tuple(_dedupe(blockers)),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered
