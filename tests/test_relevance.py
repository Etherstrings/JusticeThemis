# -*- coding: utf-8 -*-
"""Tests for deterministic A-share relevance assessment."""

from __future__ import annotations

from app.services.relevance import assess_a_share_relevance


def test_assess_a_share_relevance_marks_trade_policy_as_high() -> None:
    assessment = assess_a_share_relevance(
        source_id="ustr_press_releases",
        title="USTR announces tariff adjustment for semiconductor supply chain imports",
        summary=(
            "The release details a new tariff framework for semiconductors, critical minerals, "
            "and related supply chain imports."
        ),
        coverage_tier="official_policy",
        organization_type="official_policy",
    )

    assert assessment.label == "high"
    assert "贸易/关税/供应链" in assessment.reason


def test_assess_a_share_relevance_marks_ceremonial_sports_item_as_low() -> None:
    assessment = assess_a_share_relevance(
        source_id="whitehouse_news",
        title="Presidential Message on the NCAA College Basketball National Championship Game",
        summary="The President congratulates the teams competing in the national championship tonight.",
        coverage_tier="official_policy",
        organization_type="official_policy",
    )

    assert assessment.label == "low"
    assert "礼仪/体育" in assessment.reason


def test_assess_a_share_relevance_keeps_energy_market_story_high() -> None:
    assessment = assess_a_share_relevance(
        source_id="ap_business",
        title="Asian shares mostly higher ahead of Trump's deadline for Iran to reopen oil route",
        summary=(
            "TOKYO (AP) — Asian shares mostly rose as oil prices surged ahead of a Strait of Hormuz "
            "deadline and shipping risk remained elevated."
        ),
        coverage_tier="editorial_media",
        organization_type="wire_media",
        candidate_url="https://apnews.com/article/financial-markets-iran-oil-bcd3342cd0b4e60ebedc1e81db08f465",
    )

    assert assessment.label == "high"
    assert "油气/能源价格" in assessment.reason


def test_assess_a_share_relevance_does_not_treat_dhs_customs_story_as_trade_high() -> None:
    assessment = assess_a_share_relevance(
        source_id="whitehouse_news",
        title="Liberating the Department of Homeland Security From the Democrat-Caused Shutdown",
        summary=(
            "The memorandum discusses Homeland Security, immigration enforcement, Customs and Border "
            "Protection staffing, and shutdown impacts."
        ),
        coverage_tier="official_policy",
        organization_type="official_policy",
    )

    assert assessment.label == "medium"
    assert "官方政策源" in assessment.reason


def test_assess_a_share_relevance_keeps_fed_enforcement_item_at_medium() -> None:
    assessment = assess_a_share_relevance(
        source_id="fed_news",
        title="Federal Reserve Board issues enforcement action with former employee of United Bank",
        summary="The action concerns embezzlement of bank funds and an enforcement order.",
        coverage_tier="official_policy",
        organization_type="official_policy",
    )

    assert assessment.label == "medium"
