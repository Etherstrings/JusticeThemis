# -*- coding: utf-8 -*-
"""Tests for normalization accuracy improvements."""

from __future__ import annotations

from app.normalizer import normalize_candidate
from app.sources.types import SourceCandidate


def test_normalize_candidate_dedupes_repeated_numeric_fact_mentions() -> None:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url="https://example.com/trade-data",
            candidate_title="U.S. trade data shows exports rose 12% as imports stabilized",
            candidate_summary=(
                "The latest Census release showed trade conditions improved as exports rose 12% "
                "and inventories stabilized."
            ),
        )
    )

    assert len(normalized.numeric_facts) == 1
    assert normalized.numeric_facts[0].metric == "percentage"
    assert normalized.numeric_facts[0].value == 12.0


def test_normalize_candidate_extracts_basis_points_usd_amount_and_jobs_count() -> None:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url="https://example.com/macro-snapshot",
            candidate_title="Trade deficit widens while payrolls rise and rate path stays in focus",
            candidate_summary=(
                "The trade deficit widened to $57.3 billion in February while nonfarm payrolls increased "
                "by 271,000 jobs. Officials said a 25 basis point rate cut remains under discussion."
            ),
        )
    )

    facts = {
        (fact.metric, fact.unit, fact.subject): fact.value
        for fact in normalized.numeric_facts
    }

    assert facts[("usd_amount", "usd", "deficit")] == 57_300_000_000.0
    assert facts[("jobs_count", "jobs", "payrolls")] == 271_000.0
    assert facts[("basis_points", "basis_points", "rates")] == 25.0


def test_normalize_candidate_keeps_subject_inference_for_decimal_numbers() -> None:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url="https://example.com/decimal-subjects",
            candidate_title="Macro snapshot",
            candidate_summary=(
                "The account showed $57.3 billion in exports. "
                "Officials discussed a 12.5 basis point rate move. "
                "The White House kept a 25.0% tariff on steel imports."
            ),
        )
    )

    facts = {
        (fact.metric, fact.unit, fact.subject): fact.value
        for fact in normalized.numeric_facts
    }

    assert facts[("usd_amount", "usd", "exports")] == 57_300_000_000.0
    assert facts[("basis_points", "basis_points", "rates")] == 12.5
    assert facts[("tariff_rate", "percent", "steel")] == 25.0
