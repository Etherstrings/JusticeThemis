# -*- coding: utf-8 -*-
"""Tests for official-first handoff packaging."""

from __future__ import annotations

from app.services.handoff import HandoffService


class FakeCaptureService:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items
        self.requested_limits: list[int] = []
        self.requested_dates: list[str | None] = []

    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None):
        self.requested_limits.append(limit)
        self.requested_dates.append(analysis_date)
        return {"total": len(self.items), "items": self.items[:limit]}


class FakeMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object] | None) -> None:
        self.snapshot = snapshot

    def get_daily_snapshot(self, *, analysis_date: str | None = None):
        return self.snapshot


def test_get_handoff_prioritizes_official_sources_and_includes_prompt() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse",
                "title": "White House official statement",
                "summary": "Official policy statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 95,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-04T23:00:00+00:00",
                "created_at": "2026-04-04T23:05:00",
                "a_share_relevance": "medium",
                "a_share_relevance_reason": "官方政策源，但当前标题未体现直接产业链信号。",
                "impact_summary": "先确认是否涉及关税、补贴或采购清单。",
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认是否有行业清单和执行细则。"],
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": ["missing_direct_market_mapping"],
                "entities": [],
                "numeric_facts": [],
            },
            {
                "item_id": 2,
                "source_id": "fed_news",
                "source_name": "Federal Reserve News",
                "canonical_url": "https://example.com/fed",
                "title": "Federal Reserve issues statement",
                "summary": "Official rates statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US rates",
                "coverage_focus": "Fed policy source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及利率/通胀/宏观数据。",
                "impact_summary": "先看利率预期变化对成长和金融风格的再定价。",
                "beneficiary_directions": ["银行/保险"],
                "pressured_directions": ["高估值成长链"],
                "price_up_signals": [],
                "follow_up_checks": ["确认后续FOMC路径。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
            },
            {
                "item_id": 3,
                "source_id": "cnbc_world",
                "source_name": "CNBC World",
                "canonical_url": "https://example.com/cnbc",
                "title": "Media market recap",
                "summary": "Editorial view.",
                "document_type": "news_article",
                "source_class": "market",
                "coverage_tier": "editorial_media",
                "organization_type": "editorial_media",
                "priority": 80,
                "is_mission_critical": False,
                "region_focus": "Global markets",
                "coverage_focus": "Media source.",
                "published_at": "2026-04-05T01:00:00+00:00",
                "created_at": "2026-04-05T01:05:00",
                "a_share_relevance": "medium",
                "a_share_relevance_reason": "媒体市场快讯，可作辅助参考。",
                "impact_summary": "媒体快讯可用于补足风险偏好变化。",
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["等待官方数据或正式文件确认。"],
                "analysis_status": "background",
                "analysis_confidence": "low",
                "analysis_blockers": ["editorial_context_only"],
                "entities": [],
                "numeric_facts": [],
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=20)

    assert handoff["total"] == 3
    assert handoff["official_item_count"] == 2
    assert handoff["editorial_item_count"] == 1
    assert handoff["items"][0]["source_id"] == "fed_news"
    assert handoff["groups"][0]["coverage_tier"] == "official_policy"
    assert handoff["groups"][0]["items"][0]["source_id"] == "fed_news"
    assert "官方源优先" in handoff["prompt_scaffold"]
    assert "a_share_relevance=high" in handoff["prompt_scaffold"]
    assert "source_capture_confidence" in handoff["prompt_scaffold"]
    assert "source_integrity" in handoff["prompt_scaffold"]
    assert "data_quality_flags" in handoff["prompt_scaffold"]
    assert "timeliness" in handoff["prompt_scaffold"]
    assert "llm_ready_brief" in handoff["prompt_scaffold"]


def test_get_handoff_includes_market_snapshot_for_downstream_reasoning() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 1,
                "source_id": "fed_news",
                "source_name": "Federal Reserve News",
                "canonical_url": "https://example.com/fed",
                "title": "Federal Reserve issues statement",
                "summary": "Official rates statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US rates",
                "coverage_focus": "Fed policy source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及利率/通胀/宏观数据。",
                "impact_summary": "先看利率预期变化对成长和金融风格的再定价。",
                "beneficiary_directions": ["银行/保险"],
                "pressured_directions": ["高估值成长链"],
                "price_up_signals": [],
                "follow_up_checks": ["确认后续FOMC路径。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
            }
        ]
    )
    market_snapshot_service = FakeMarketSnapshotService(
        {
            "analysis_date": "2026-04-07",
            "market_date": "2026-04-06",
            "session_name": "us_close",
            "headline": "标普500 +2.00%；纳指综指 +2.00%；VIX -10.00%。",
            "risk_signals": {
                "risk_mode": "risk_on",
            },
        }
    )
    service = HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )

    handoff = service.get_handoff(limit=20)

    assert handoff["market_snapshot"]["analysis_date"] == "2026-04-07"
    assert handoff["market_snapshot"]["risk_signals"]["risk_mode"] == "risk_on"
    assert "market_snapshot" in handoff["prompt_scaffold"]


def test_get_handoff_forwards_analysis_date_to_capture_and_market_snapshot() -> None:
    capture_service = FakeCaptureService([])
    market_snapshot_service = FakeMarketSnapshotService({"analysis_date": "2026-04-09", "headline": "snapshot"})
    service = HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )

    handoff = service.get_handoff(limit=8, analysis_date="2026-04-09")

    assert handoff["market_snapshot"]["analysis_date"] == "2026-04-09"
    assert capture_service.requested_dates == ["2026-04-09"]


def test_get_handoff_excludes_stale_items_from_current_window() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse/fresh",
                "title": "Fresh White House policy update",
                "summary": "A timely policy update tied to the current overnight window.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "published_at": "2026-04-10T01:00:00+00:00",
                "created_at": "2026-04-10T09:01:00",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "timeliness": {
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "entities": [],
                "numeric_facts": [],
            },
            {
                "item_id": 2,
                "source_id": "bis_news_updates",
                "source_name": "BIS News Updates",
                "canonical_url": "https://example.com/bis/stale",
                "title": "Older BIS tariff notice",
                "summary": "A stale policy notice captured again today but published far outside the overnight window.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 97,
                "is_mission_critical": True,
                "published_at": "2025-08-19T12:55:00+00:00",
                "created_at": "2026-04-10T09:05:00",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "timeliness": {
                    "freshness_bucket": "stale",
                    "is_timely": False,
                    "timeliness_flags": ["stale_publication"],
                },
                "entities": [],
                "numeric_facts": [],
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=10)

    assert handoff["total"] == 1
    assert [item["item_id"] for item in handoff["items"]] == [1]


def test_get_handoff_exposes_structured_outline_for_downstream_models() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 11,
                "source_id": "fed_news",
                "source_name": "Federal Reserve News",
                "canonical_url": "https://example.com/fed",
                "title": "Federal Reserve issues statement",
                "summary": "Official rates statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US rates",
                "coverage_focus": "Fed policy source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "published_at_display": "2026-04-05 08:00 CST",
                "published_at_precision": "datetime",
                "source_authority": "primary_official",
                "content_metrics": {
                    "summary_sentence_count": 1,
                    "evidence_point_count": 1,
                    "numeric_fact_count": 0,
                    "entity_count": 1,
                },
                "content_completeness": "high",
                "body_detail_level": "detailed",
                "source_time_reliability": "high",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及利率/通胀/宏观数据。",
                "impact_summary": "先看利率预期变化对成长和金融风格的再定价。",
                "why_it_matters_cn": "偏紧的利率/通胀信号可能先影响估值切换。",
                "key_numbers": [],
                "fact_table": [{"fact_type": "sentence", "text": "Official rates statement."}],
                "policy_actions": ["利率路径维持偏紧"],
                "market_implications": [
                    {"implication_type": "beneficiary", "direction": "银行/保险", "stance": "positive"}
                ],
                "uncertainties": ["确认后续FOMC路径。"],
                "beneficiary_directions": ["银行/保险"],
                "pressured_directions": ["高估值成长链"],
                "price_up_signals": [],
                "follow_up_checks": ["确认后续FOMC路径。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "evidence_points": ["rates stayed restrictive"],
            },
            {
                "item_id": 12,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "canonical_url": "https://example.com/ap",
                "title": "AP reports oil and shipping costs rise",
                "summary": "Editorial context.",
                "document_type": "news_article",
                "source_class": "market",
                "coverage_tier": "editorial_media",
                "organization_type": "wire_media",
                "priority": 70,
                "is_mission_critical": False,
                "region_focus": "Global business",
                "coverage_focus": "Media source.",
                "published_at": "2026-04-05T01:00:00+00:00",
                "published_at_display": "2026-04-05 09:00 CST",
                "published_at_precision": "datetime",
                "source_authority": "editorial_context",
                "content_metrics": {
                    "summary_sentence_count": 1,
                    "evidence_point_count": 1,
                    "numeric_fact_count": 0,
                    "entity_count": 0,
                },
                "content_completeness": "medium",
                "body_detail_level": "summary",
                "source_time_reliability": "medium",
                "created_at": "2026-04-05T01:05:00",
                "a_share_relevance": "medium",
                "a_share_relevance_reason": "媒体市场快讯，可作辅助参考。",
                "impact_summary": "媒体快讯可用于补足风险偏好变化。",
                "why_it_matters_cn": "媒体快讯可用于补足风险偏好变化。",
                "key_numbers": [],
                "fact_table": [{"fact_type": "sentence", "text": "Editorial context."}],
                "policy_actions": [],
                "market_implications": [
                    {"implication_type": "price_up", "direction": "原油/燃料油", "stance": "inflationary"}
                ],
                "uncertainties": ["等待官方数据或正式文件确认。"],
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": ["原油/燃料油"],
                "follow_up_checks": ["等待官方数据或正式文件确认。"],
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": ["editorial_context_only"],
                "entities": [],
                "numeric_facts": [],
                "evidence_points": ["shipping costs moved higher"],
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=20)

    assert handoff["handoff_outline"]["priority_item_ids"] == [11, 12]
    assert handoff["handoff_outline"]["official_item_ids"] == [11]
    assert handoff["handoff_outline"]["editorial_item_ids"] == [12]
    assert handoff["handoff_outline"]["watch_item_ids"] == [12]
    assert handoff["handoff_outline"]["background_item_ids"] == []
    assert handoff["handoff_outline"]["field_priority"][:4] == [
        "published_at_display",
        "published_at_precision",
        "source_authority",
        "source_integrity",
    ]
    assert handoff["handoff_outline"]["field_priority"][4:] == [
        "content_metrics",
        "source_time_reliability",
        "data_quality_flags",
        "timeliness",
        "body_detail_level",
        "source_capture_confidence",
        "key_numbers",
        "fact_table",
        "cross_source_confirmation",
        "fact_conflicts",
        "event_cluster",
        "policy_actions",
        "market_implications",
        "uncertainties",
        "llm_ready_brief",
        "why_it_matters_cn",
        "evidence_points",
        "impact_summary",
    ]


def test_get_handoff_groups_items_by_event_cluster_for_downstream_models() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 21,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse",
                "title": "White House keeps 25% steel tariff",
                "summary": "Official tariff statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "conflicted",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
            {
                "item_id": 22,
                "source_id": "ustr_press_releases",
                "source_name": "USTR Press Releases",
                "canonical_url": "https://example.com/ustr",
                "title": "USTR confirms 25% steel tariff",
                "summary": "Official trade statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US trade policy",
                "coverage_focus": "Official trade source.",
                "published_at": "2026-04-05T00:20:00+00:00",
                "created_at": "2026-04-05T00:25:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "conflicted",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
            {
                "item_id": 23,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "canonical_url": "https://example.com/ap",
                "title": "AP says steel tariff could move to 15%",
                "summary": "Editorial follow-up.",
                "document_type": "news_article",
                "source_class": "market",
                "coverage_tier": "editorial_media",
                "organization_type": "wire_media",
                "priority": 70,
                "is_mission_critical": False,
                "region_focus": "Global business",
                "coverage_focus": "Media source.",
                "published_at": "2026-04-05T01:00:00+00:00",
                "created_at": "2026-04-05T01:05:00",
                "a_share_relevance": "high",
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "conflicted",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=20)

    assert "event_groups" in handoff
    assert len(handoff["event_groups"]) == 1
    group = handoff["event_groups"][0]
    assert group["cluster_id"] == "trade_policy__tariff_rate__steel"
    assert group["cluster_status"] == "conflicted"
    assert group["primary_item_id"] == 21
    assert group["item_ids"] == [21, 22, 23]
    assert group["official_source_count"] == 2
    assert group["items"][0]["item_id"] == 21


def test_get_handoff_uses_wider_recent_pool_before_truncating() -> None:
    media_items = [
        {
            "item_id": index,
            "source_id": f"media_{index}",
            "source_name": f"Media {index}",
            "canonical_url": f"https://example.com/media-{index}",
            "title": f"Media headline {index}",
            "summary": "Editorial market recap.",
            "document_type": "news_article",
            "source_class": "market",
            "coverage_tier": "editorial_media",
            "organization_type": "editorial_media",
            "priority": 70,
            "is_mission_critical": False,
            "region_focus": "Global markets",
            "coverage_focus": "Media source.",
            "published_at": f"2026-04-05T0{index}:00:00+00:00",
            "created_at": f"2026-04-05T0{index}:05:00",
            "a_share_relevance": "medium",
            "a_share_relevance_reason": "媒体市场快讯，可作辅助参考。",
            "impact_summary": "媒体快讯可用于补足风险偏好变化。",
            "beneficiary_directions": [],
            "pressured_directions": [],
            "price_up_signals": [],
                "follow_up_checks": ["等待官方数据或正式文件确认。"],
                "analysis_status": "background",
                "analysis_confidence": "low",
                "analysis_blockers": ["editorial_context_only"],
                "entities": [],
                "numeric_facts": [],
            }
        for index in range(1, 10)
    ]
    media_items.extend(
        {
            "item_id": index,
            "source_id": f"media_{index}",
            "source_name": f"Media {index}",
            "canonical_url": f"https://example.com/media-{index}",
            "title": f"Media headline {index}",
            "summary": "Editorial market recap.",
            "document_type": "news_article",
            "source_class": "market",
            "coverage_tier": "editorial_media",
            "organization_type": "editorial_media",
            "priority": 70,
            "is_mission_critical": False,
            "region_focus": "Global markets",
            "coverage_focus": "Media source.",
            "published_at": f"2026-04-05T{index}:00:00+00:00",
            "created_at": f"2026-04-05T{index}:05:00",
            "a_share_relevance": "medium",
            "a_share_relevance_reason": "媒体市场快讯，可作辅助参考。",
            "impact_summary": "媒体快讯可用于补足风险偏好变化。",
            "beneficiary_directions": [],
            "pressured_directions": [],
            "price_up_signals": [],
            "follow_up_checks": ["等待官方数据或正式文件确认。"],
            "analysis_status": "background",
            "analysis_confidence": "low",
            "analysis_blockers": ["editorial_context_only"],
            "entities": [],
            "numeric_facts": [],
        }
        for index in range(10, 13)
    )
    capture_service = FakeCaptureService(
        media_items
        + [
            {
                "item_id": 100,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse",
                "title": "White House official statement",
                "summary": "Official policy statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-04T23:00:00+00:00",
                "created_at": "2026-04-04T23:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及贸易/关税/供应链。",
                "impact_summary": "先看自主可控与出口链再定价。",
                "beneficiary_directions": ["自主可控半导体链"],
                "pressured_directions": ["对美出口链"],
                "price_up_signals": ["进口芯片/关键零部件"],
                "follow_up_checks": ["确认税率和执行日期。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
            }
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=10)

    assert capture_service.requested_limits == [30]
    assert handoff["total"] == 10
    assert handoff["items"][0]["source_id"] == "whitehouse_news"


def test_get_handoff_prioritizes_high_a_share_relevance_within_same_tier() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse-low",
                "title": "Ceremonial White House message",
                "summary": "A ceremonial message with no direct market signal.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-05T03:00:00+00:00",
                "created_at": "2026-04-05T03:05:00",
                "a_share_relevance": "low",
                "a_share_relevance_reason": "更偏礼仪/体育或泛政治表态。",
                "impact_summary": "当前更像噪音，不建议直接映射板块。",
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["等待更明确的产业或政策细则。"],
                "analysis_status": "background",
                "analysis_confidence": "low",
                "analysis_blockers": ["low_relevance"],
                "entities": [],
                "numeric_facts": [],
            },
            {
                "item_id": 2,
                "source_id": "ustr_press_releases",
                "source_name": "USTR Press Releases",
                "canonical_url": "https://example.com/ustr-high",
                "title": "USTR announces tariff action",
                "summary": "Tariff changes on semiconductor imports and supply chain materials.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 95,
                "is_mission_critical": True,
                "region_focus": "US trade policy",
                "coverage_focus": "Trade policy source.",
                "published_at": "2026-04-05T02:00:00+00:00",
                "created_at": "2026-04-05T02:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及贸易/关税/供应链。",
                "impact_summary": "先看自主可控、进口替代和出口链压力。",
                "beneficiary_directions": ["自主可控半导体链"],
                "pressured_directions": ["对美出口链"],
                "price_up_signals": ["进口芯片/关键零部件"],
                "follow_up_checks": ["确认税率和覆盖清单。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=10)

    assert handoff["items"][0]["source_id"] == "ustr_press_releases"


def test_get_handoff_prioritizes_ready_items_over_review_items_within_same_tier() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/review",
                "title": "Generic White House statement",
                "summary": "Official policy statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-05T03:00:00+00:00",
                "created_at": "2026-04-05T03:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "官方政策源，但需要补行业映射。",
                "impact_summary": "先确认是否涉及行业清单。",
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认是否有执行细则。"],
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": ["missing_direct_market_mapping"],
                "entities": [],
                "numeric_facts": [],
            },
            {
                "item_id": 2,
                "source_id": "ustr_press_releases",
                "source_name": "USTR Press Releases",
                "canonical_url": "https://example.com/ready",
                "title": "USTR announces tariff action",
                "summary": "Tariff changes on semiconductor imports and supply chain materials.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 95,
                "is_mission_critical": True,
                "region_focus": "US trade policy",
                "coverage_focus": "Trade policy source.",
                "published_at": "2026-04-05T02:00:00+00:00",
                "created_at": "2026-04-05T02:05:00",
                "a_share_relevance": "high",
                "a_share_relevance_reason": "涉及贸易/关税/供应链。",
                "impact_summary": "先看自主可控、进口替代和出口链压力。",
                "beneficiary_directions": ["自主可控半导体链"],
                "pressured_directions": ["对美出口链"],
                "price_up_signals": ["进口芯片/关键零部件"],
                "follow_up_checks": ["确认税率和覆盖清单。"],
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=10)

    assert handoff["items"][0]["source_id"] == "ustr_press_releases"


def test_get_handoff_event_groups_keep_full_cluster_membership_from_wider_pool() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 21,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/whitehouse",
                "title": "White House keeps 25% steel tariff",
                "summary": "Official tariff statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US policy",
                "coverage_focus": "Official policy source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "confirmed",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
            {
                "item_id": 22,
                "source_id": "ustr_press_releases",
                "source_name": "USTR Press Releases",
                "canonical_url": "https://example.com/ustr",
                "title": "USTR confirms 25% steel tariff",
                "summary": "Official trade statement.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 99,
                "is_mission_critical": True,
                "region_focus": "US trade policy",
                "coverage_focus": "Official trade source.",
                "published_at": "2026-04-05T00:20:00+00:00",
                "created_at": "2026-04-05T00:25:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "confirmed",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
            {
                "item_id": 23,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "canonical_url": "https://example.com/ap",
                "title": "AP confirms steel tariff context",
                "summary": "Editorial follow-up.",
                "document_type": "news_article",
                "source_class": "market",
                "coverage_tier": "editorial_media",
                "organization_type": "wire_media",
                "priority": 70,
                "is_mission_critical": False,
                "region_focus": "Global business",
                "coverage_focus": "Media source.",
                "published_at": "2026-04-05T01:00:00+00:00",
                "created_at": "2026-04-05T01:05:00",
                "a_share_relevance": "high",
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "confirmed",
                    "primary_item_id": 21,
                    "item_count": 3,
                    "source_count": 3,
                    "official_source_count": 2,
                    "member_item_ids": [21, 22, 23],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases", "ap_business"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
            },
        ]
    )
    service = HandoffService(capture_service=capture_service)

    handoff = service.get_handoff(limit=1)

    assert handoff["total"] == 1
    assert len(handoff["items"]) == 1
    assert len(handoff["event_groups"]) == 1
    assert handoff["event_groups"][0]["item_ids"] == [21, 22, 23]
    assert [item["item_id"] for item in handoff["event_groups"][0]["items"]] == [21, 22, 23]


def test_get_handoff_includes_ranked_mainlines_from_market_snapshot_and_event_groups() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 31,
                "source_id": "bis_news_updates",
                "source_name": "BIS News Updates",
                "canonical_url": "https://example.com/bis",
                "title": "BIS updates semiconductor export guidance",
                "summary": "Official semiconductor policy update.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US export control",
                "coverage_focus": "Official export-control source.",
                "published_at": "2026-04-05T00:00:00+00:00",
                "created_at": "2026-04-05T00:05:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "market_implications": [
                    {"implication_type": "beneficiary", "direction": "自主可控半导体链", "stance": "positive"}
                ],
                "event_cluster": {
                    "cluster_id": "semiconductor_supply_chain__guidance__31",
                    "cluster_status": "confirmed",
                    "primary_item_id": 31,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 1,
                    "member_item_ids": [31, 32],
                    "member_source_ids": ["bis_news_updates", "ap_business"],
                    "latest_published_at": "2026-04-05T00:30:00+00:00",
                    "topic_tags": ["semiconductor_supply_chain"],
                    "fact_signatures": [],
                },
            },
            {
                "item_id": 32,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "canonical_url": "https://example.com/ap",
                "title": "AP says chip shares led the rally",
                "summary": "Editorial semiconductor follow-up.",
                "document_type": "news_article",
                "source_class": "market",
                "coverage_tier": "editorial_media",
                "organization_type": "wire_media",
                "priority": 70,
                "is_mission_critical": False,
                "region_focus": "Global business",
                "coverage_focus": "Media source.",
                "published_at": "2026-04-05T00:30:00+00:00",
                "created_at": "2026-04-05T00:35:00",
                "a_share_relevance": "high",
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "market_implications": [
                    {"implication_type": "beneficiary", "direction": "自主可控半导体链", "stance": "positive"}
                ],
                "event_cluster": {
                    "cluster_id": "semiconductor_supply_chain__guidance__31",
                    "cluster_status": "confirmed",
                    "primary_item_id": 31,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 1,
                    "member_item_ids": [31, 32],
                    "member_source_ids": ["bis_news_updates", "ap_business"],
                    "latest_published_at": "2026-04-05T00:30:00+00:00",
                    "topic_tags": ["semiconductor_supply_chain"],
                    "fact_signatures": [],
                },
            },
            {
                "item_id": 33,
                "source_id": "eia_pressroom",
                "source_name": "EIA Pressroom",
                "canonical_url": "https://example.com/eia",
                "title": "EIA says shipping risks eased overnight",
                "summary": "Official energy update.",
                "document_type": "press_release",
                "source_class": "macro",
                "coverage_tier": "official_data",
                "organization_type": "official_data",
                "priority": 90,
                "is_mission_critical": False,
                "region_focus": "Energy markets",
                "coverage_focus": "Official energy source.",
                "published_at": "2026-04-05T01:00:00+00:00",
                "created_at": "2026-04-05T01:05:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "market_implications": [
                    {"implication_type": "pressured", "direction": "原油/燃料油", "stance": "negative"}
                ],
                "event_cluster": {
                    "cluster_id": "energy_shipping__oil__33",
                    "cluster_status": "confirmed",
                    "primary_item_id": 33,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [33],
                    "member_source_ids": ["eia_pressroom"],
                    "latest_published_at": "2026-04-05T01:00:00+00:00",
                    "topic_tags": ["energy_shipping"],
                    "fact_signatures": [],
                },
            },
        ]
    )
    market_snapshot_service = FakeMarketSnapshotService(
        {
            "analysis_date": "2026-04-07",
            "asset_board": {
                "analysis_date": "2026-04-07",
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 3.0},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": 5.0},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 6.0},
                    {"symbol": "XLE", "display_name": "能源板块", "change_pct": -3.0},
                ],
                "rates_fx": [],
                "precious_metals": [],
                "energy": [
                    {"symbol": "CL=F", "display_name": "WTI原油", "change_pct": -4.8},
                ],
                "industrial_metals": [],
                "risk_signals": {"risk_mode": "risk_on"},
            },
        }
    )
    service = HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )

    handoff = service.get_handoff(limit=20)

    assert [mainline["mainline_bucket"] for mainline in handoff["mainlines"]] == [
        "tech_semiconductor",
        "geopolitics_energy",
    ]
    assert handoff["mainlines"][0]["linked_event_ids"] == [
        "semiconductor_supply_chain__guidance__31",
    ]
    assert handoff["mainlines"][1]["linked_event_ids"] == [
        "energy_shipping__oil__33",
    ]


def test_get_handoff_includes_market_regimes_and_secondary_event_groups() -> None:
    capture_service = FakeCaptureService(
        [
            {
                "item_id": 41,
                "source_id": "bis_news_updates",
                "source_name": "BIS News Updates",
                "canonical_url": "https://example.com/bis-tech",
                "title": "BIS updates semiconductor guidance",
                "summary": "Official semiconductor update.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 100,
                "is_mission_critical": True,
                "region_focus": "US export control",
                "coverage_focus": "Official export-control source.",
                "published_at": "2026-04-10T00:00:00+00:00",
                "created_at": "2026-04-10T00:05:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "semiconductor_supply_chain__guidance__41",
                    "cluster_status": "confirmed",
                    "primary_item_id": 41,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [41],
                    "member_source_ids": ["bis_news_updates"],
                    "latest_published_at": "2026-04-10T00:00:00+00:00",
                    "topic_tags": ["semiconductor_supply_chain"],
                    "fact_signatures": [],
                },
            },
            {
                "item_id": 42,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "canonical_url": "https://example.com/trade",
                "title": "White House updates tariff language",
                "summary": "Trade update without clear market confirmation.",
                "document_type": "press_release",
                "source_class": "policy",
                "coverage_tier": "official_policy",
                "organization_type": "official_policy",
                "priority": 95,
                "is_mission_critical": True,
                "region_focus": "Trade",
                "coverage_focus": "Official trade source.",
                "published_at": "2026-04-10T00:30:00+00:00",
                "created_at": "2026-04-10T00:35:00",
                "a_share_relevance": "high",
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "analysis_blockers": [],
                "entities": [],
                "numeric_facts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__steel__42",
                    "cluster_status": "confirmed",
                    "primary_item_id": 42,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [42],
                    "member_source_ids": ["whitehouse_news"],
                    "latest_published_at": "2026-04-10T00:30:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": [],
                },
            },
        ]
    )
    market_snapshot_service = FakeMarketSnapshotService(
        {
            "analysis_date": "2026-04-10",
            "market_regimes": [
                {
                    "regime_id": "2026-04-10__technology_risk_on",
                    "regime_key": "technology_risk_on",
                    "triggered": True,
                    "direction": "bullish",
                    "strength": 2.1,
                    "confidence": "high",
                    "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                    "supporting_observations": [],
                    "suppressed_by": [],
                }
            ],
            "market_regime_evaluations": [
                {
                    "regime_id": "2026-04-10__technology_risk_on",
                    "regime_key": "technology_risk_on",
                    "triggered": True,
                    "direction": "bullish",
                    "strength": 2.1,
                    "confidence": "high",
                    "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                    "supporting_observations": [],
                    "suppressed_by": [],
                }
            ],
            "asset_board": {
                "analysis_date": "2026-04-10",
                "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.0}],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": 4.0},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 5.0},
                ],
                "rates_fx": [],
                "precious_metals": [],
                "energy": [],
                "industrial_metals": [],
            },
        }
    )
    service = HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )

    handoff = service.get_handoff(limit=20)

    assert handoff["market_regimes"][0]["regime_key"] == "technology_risk_on"
    assert handoff["mainlines"][0]["regime_ids"] == ["2026-04-10__technology_risk_on"]
    assert handoff["secondary_event_groups"][0]["cluster_id"] == "trade_policy__steel__42"
