# -*- coding: utf-8 -*-
"""Tests for evidence-point extraction."""

from __future__ import annotations

from app.normalizer import NumericFact
from app.services.evidence import build_evidence_points


def test_build_evidence_points_keeps_key_trade_sentences_and_numbers() -> None:
    points = build_evidence_points(
        summary=(
            "The nation's international trade deficit in goods and services increased to $57.3 billion in February "
            "from $54.7 billion in January (revised), as imports increased more than exports. "
            "February 2026 trade data will guide export-chain expectations."
        ),
        numeric_facts=(),
    )

    assert any("$57.3 billion" in point for point in points)
    assert any("imports increased more than exports" in point for point in points)


def test_build_evidence_points_adds_numeric_fact_context_when_available() -> None:
    points = build_evidence_points(
        summary="Tariff rate changes were announced for imported semiconductors.",
        numeric_facts=(
            NumericFact(
                metric="tariff_rate",
                value=25.0,
                unit="percent",
                context="The 25% tariff on imported semiconductors remains in place.",
                subject="semiconductors",
            ),
        ),
    )

    assert any("25.0 percent" in point for point in points)
    assert any("semiconductors" in point for point in points)


def test_build_evidence_points_skips_numeric_fact_when_summary_already_contains_same_number() -> None:
    points = build_evidence_points(
        summary="France’s CAC 40 jumped 1.3% in early trading as oil prices surged.",
        numeric_facts=(
            NumericFact(
                metric="percentage",
                value=1.3,
                unit="percent",
                context="France’s CAC 40 jumped 1.3% in early trading.",
                subject=None,
            ),
        ),
    )

    assert len(points) == 1


def test_build_evidence_points_filters_contact_boilerplate() -> None:
    points = build_evidence_points(
        summary=(
            "The attached tables and charts summarize the economic projections from the March 17-18 meeting. "
            "For media inquiries, email media@example.com or call 202-452-2955."
        ),
        numeric_facts=(),
    )

    assert any("economic projections" in point for point in points)
    assert all("For media inquiries" not in point for point in points)


def test_build_evidence_points_keeps_us_abbreviation_sentence_intact() -> None:
    points = build_evidence_points(
        summary=(
            "TOKYO (AP) — Global shares mostly rose as oil prices surged ahead of a deadline that U.S. "
            "President Donald Trump set for Iran to reopen the Strait of Hormuz."
        ),
        numeric_facts=(),
    )

    assert any("U.S. President Donald Trump" in point for point in points)


def test_build_evidence_points_skips_pdf_navigation_lines() -> None:
    points = build_evidence_points(
        summary=(
            "The attached tables and charts summarize the economic projections made by Federal Open Market Committee participants. "
            "Projections (PDF) | Accessible Materials"
        ),
        numeric_facts=(),
    )

    assert any("economic projections" in point for point in points)
    assert all("Accessible Materials" not in point for point in points)


def test_build_evidence_points_keeps_middle_initial_sentence_intact() -> None:
    points = build_evidence_points(
        summary=(
            "WASHINGTON — Today, United States Trade Representative Jamieson Greer, Health and Human Services "
            "Secretary Robert F. Kennedy, Jr, and Commerce Secretary Howard Lutnick issued the following statements."
        ),
        numeric_facts=(),
    )

    assert any("Robert F. Kennedy, Jr" in point for point in points)


def test_build_evidence_points_treats_usd_suffix_shorthand_as_existing_fact() -> None:
    points = build_evidence_points(
        summary="The deficit widened to $57.3B in February. Funding reached $1.2T for the program.",
        numeric_facts=(
            NumericFact(
                metric="usd_amount",
                value=57_300_000_000.0,
                unit="usd",
                context="The deficit widened to $57.3B in February.",
                subject="deficit",
            ),
            NumericFact(
                metric="usd_amount",
                value=1_200_000_000_000.0,
                unit="usd",
                context="Funding reached $1.2T for the program.",
                subject="funding",
            ),
        ),
    )

    assert len(points) == 2
    assert not any(point.startswith("usd_amount:") for point in points)
