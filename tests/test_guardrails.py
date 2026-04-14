# -*- coding: utf-8 -*-
"""Tests for analysis guardrails."""

from __future__ import annotations

from app.services.guardrails import assess_analysis_guardrails


def test_guardrails_mark_official_trade_item_as_ready() -> None:
    assessment = assess_analysis_guardrails(
        coverage_tier="official_policy",
        organization_type="official_policy",
        summary_quality="high",
        a_share_relevance="high",
        excerpt_source="body_selector:.field--name-body",
        published_at_source="section:nearby_time",
        beneficiary_directions=("进口替代制造链",),
        pressured_directions=("对美出口链",),
        price_up_signals=(),
        follow_up_checks=("确认税率、覆盖商品清单和生效日期。",),
    )

    assert assessment.analysis_status == "ready"
    assert assessment.analysis_confidence == "high"
    assert assessment.analysis_blockers == ()


def test_guardrails_mark_generic_official_policy_item_as_review() -> None:
    assessment = assess_analysis_guardrails(
        coverage_tier="official_policy",
        organization_type="official_policy",
        summary_quality="high",
        a_share_relevance="medium",
        excerpt_source="body_selector:main",
        published_at_source="section:time",
        beneficiary_directions=(),
        pressured_directions=(),
        price_up_signals=(),
        follow_up_checks=(
            "确认是否涉及关税、制裁、补贴、采购或价格机制。",
            "确认执行日期、行业清单和影响范围细则。",
        ),
    )

    assert assessment.analysis_status == "review"
    assert assessment.analysis_confidence == "medium"
    assert "missing_direct_market_mapping" in assessment.analysis_blockers


def test_guardrails_mark_editorial_low_relevance_item_as_background() -> None:
    assessment = assess_analysis_guardrails(
        coverage_tier="editorial_media",
        organization_type="wire_media",
        summary_quality="medium",
        a_share_relevance="low",
        excerpt_source="body_selector:main",
        published_at_source="html:meta_article_published_time",
        beneficiary_directions=(),
        pressured_directions=(),
        price_up_signals=(),
        follow_up_checks=("等待官方数据或正式文件确认。",),
    )

    assert assessment.analysis_status == "background"
    assert assessment.analysis_confidence == "low"
    assert "editorial_context_only" in assessment.analysis_blockers
