# -*- coding: utf-8 -*-
"""Tests for staged MMU handoff payload builders."""

from __future__ import annotations

from app.services.mmu_handoff import MMUHandoffService


def test_mmu_handoff_service_builds_staged_payloads() -> None:
    service = MMUHandoffService()
    item = {
        "item_id": 101,
        "source_id": "fed_news",
        "source_name": "Federal Reserve News",
        "source_group": "official_policy",
        "coverage_tier": "official_policy",
        "published_at": "2026-04-08T14:00:00+00:00",
        "published_at_display": "2026-04-08 22:00 CST",
        "title": "Federal Reserve says rates may stay restrictive",
        "summary": "Officials said rates may need to stay restrictive while inflation remains elevated.",
        "canonical_url": "https://example.com/fed",
        "excerpt_source": "body_selector:main",
        "document_type": "press_release",
        "entities": [],
        "numeric_facts": [],
        "evidence_points": ["Rates may stay restrictive."],
        "source_capture_confidence": {"level": "high", "score": 91},
        "source_integrity": {"domain_status": "verified"},
        "key_numbers": [],
    }
    event_group = {
        "cluster_id": "rates_macro__rates__101",
        "cluster_status": "confirmed",
        "primary_item_id": 101,
        "item_ids": [101, 102],
        "items": [
            item,
            {
                "item_id": 102,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "coverage_tier": "editorial_media",
                "published_at_display": "2026-04-08 22:20 CST",
                "title": "Markets price lower yields after Fed remarks",
                "summary": "Media follow-up on lower yields and tech risk appetite.",
                "canonical_url": "https://example.com/ap",
                "key_numbers": [],
                "evidence_points": ["Treasury yields fell."],
            },
        ],
        "topic_tags": ["rates_macro"],
        "fact_signatures": [],
        "headline": "Federal Reserve says rates may stay restrictive",
        "primary_source_name": "Federal Reserve News",
    }
    market_board = {
        "headline": "纳指领涨，油价回落，收益率回落。",
        "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 3.0}],
        "sectors": [{"symbol": "XLK", "display_name": "科技板块", "change_pct": 5.0}],
        "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -4.5}],
        "precious_metals": [],
        "energy": [{"symbol": "CL=F", "display_name": "WTI原油", "change_pct": -4.8}],
        "industrial_metals": [],
        "china_mapped_futures": [{"future_code": "pta", "future_name": "PTA", "watch_direction": "down"}],
    }
    mainlines = [
        {
            "mainline_id": "rates_liquidity__2026-04-08",
            "headline": "利率流动性压力缓和",
            "mainline_bucket": "rates_liquidity",
            "importance_rank": 1,
            "linked_event_ids": ["rates_macro__rates__101"],
            "affected_assets": ["^TNX", "XLK"],
            "market_effect": "利率压力缓和",
            "confidence": "high",
        }
    ]
    china_mapping_context = {
        "sector_direction_map": [
            {
                "direction": "高估值成长链",
                "stance": "positive",
                "evidence_mainline_ids": ["rates_liquidity__2026-04-08"],
            }
        ],
        "commodity_direction_map": [
            {
                "commodity_direction": "PTA链观察偏空",
                "confidence": "medium",
                "evidence_mainline_ids": ["rates_liquidity__2026-04-08"],
            }
        ],
        "candidate_stock_pool": [
            {"ticker": "300308.SZ", "name": "中际旭创"},
        ],
    }

    item_payload = service.build_single_item_understanding(
        analysis_date="2026-04-08",
        item=item,
    )
    cluster_payload = service.build_event_consolidation(
        analysis_date="2026-04-08",
        event_group=event_group,
        mainline_bucket_hint="rates_liquidity",
    )
    attribution_payload = service.build_market_attribution(
        analysis_date="2026-04-08",
        market_board=market_board,
        mainlines=mainlines,
        event_groups=[event_group],
    )
    premium_payload = service.build_premium_recommendation(
        analysis_date="2026-04-08",
        market_attribution=attribution_payload,
        china_mapping_context=china_mapping_context,
    )

    assert item_payload["handoff_type"] == "single_item_understanding"
    assert item_payload["item"]["item_id"] == 101
    assert item_payload["instructions"]["must_not_give_investment_advice"] is True

    assert cluster_payload["handoff_type"] == "event_consolidation"
    assert cluster_payload["cluster_candidate"]["cluster_id"] == "rates_macro__rates__101"
    assert cluster_payload["cluster_candidate"]["mainline_bucket_hint"] == "rates_liquidity"
    assert cluster_payload["cluster_candidate"]["item_ids"] == [101, 102]

    assert attribution_payload["handoff_type"] == "market_attribution"
    assert attribution_payload["market_board"]["headline"] == "纳指领涨，油价回落，收益率回落。"
    assert attribution_payload["main_candidate_events"][0]["cluster_id"] == "rates_macro__rates__101"
    assert attribution_payload["main_candidate_events"][0]["mainline_bucket"] == "rates_liquidity"

    assert premium_payload["handoff_type"] == "premium_recommendation"
    assert premium_payload["market_attribution"]["mainlines"][0]["mainline_id"] == "rates_liquidity__2026-04-08"
    assert premium_payload["china_mapping_context"]["candidate_stock_pool"] == [
        {"ticker": "300308.SZ", "name": "中际旭创"}
    ]


def test_mmu_handoff_bundle_exposes_market_regimes_and_secondary_event_groups() -> None:
    service = MMUHandoffService()
    handoff = {
        "analysis_date": "2026-04-08",
        "generated_at": "2026-04-08T09:00:00+08:00",
        "items": [],
        "event_groups": [],
        "market_regimes": [
            {
                "regime_id": "2026-04-08__technology_risk_on",
                "regime_key": "technology_risk_on",
                "triggered": True,
                "direction": "bullish",
                "strength": 2.1,
                "confidence": "high",
                "driving_symbols": ["SOXX", "XLK", "^IXIC"],
            }
        ],
        "secondary_event_groups": [
            {
                "cluster_id": "trade_policy__steel__42",
                "headline": "White House updates tariff language",
                "mainline_bucket_hint": "trade_export_control",
                "downgrade_reason": "no_regime_match",
            }
        ],
        "market_snapshot": {
            "analysis_date": "2026-04-08",
            "asset_board": {
                "headline": "纳指上涨，半导体领涨。",
                "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.0}],
                "sectors": [{"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 4.2}],
                "rates_fx": [],
                "precious_metals": [],
                "energy": [],
                "industrial_metals": [],
                "china_mapped_futures": [],
            },
        },
        "mainlines": [
            {
                "mainline_id": "tech_semiconductor__2026-04-08",
                "headline": "科技/半导体主线走强",
                "mainline_bucket": "tech_semiconductor",
                "linked_event_ids": [],
                "regime_ids": ["2026-04-08__technology_risk_on"],
                "confidence": "high",
            }
        ],
    }
    analysis_report = {
        "access_tier": "premium",
        "direction_calls": [],
        "stock_calls": [],
    }

    bundle = service.build_bundle(
        handoff=handoff,
        analysis_report=analysis_report,
        access_tier="premium",
    )

    assert bundle["market_regimes"][0]["regime_key"] == "technology_risk_on"
    assert bundle["secondary_event_groups"][0]["cluster_id"] == "trade_policy__steel__42"
    assert bundle["market_attribution"]["market_regimes"][0]["regime_key"] == "technology_risk_on"
    assert bundle["market_attribution"]["secondary_event_groups"][0]["downgrade_reason"] == "no_regime_match"
    assert bundle["premium_recommendation"]["market_regimes"][0]["regime_key"] == "technology_risk_on"
    assert bundle["premium_recommendation"]["secondary_event_groups"][0]["cluster_id"] == "trade_policy__steel__42"
