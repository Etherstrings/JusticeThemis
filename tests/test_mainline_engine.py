# -*- coding: utf-8 -*-
"""Tests for result-first overnight mainline ranking."""

from __future__ import annotations

from app.services.mainline_engine import MainlineEngine


def _asset(symbol: str, display_name: str, change_pct: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "display_name": display_name,
        "change_pct": change_pct,
        "change_pct_text": f"{change_pct:+.2f}%",
        "change_direction": "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
    }


def test_mainline_engine_ranks_result_first_mainlines_from_market_board_and_events() -> None:
    engine = MainlineEngine()
    market_board = {
        "analysis_date": "2026-04-07",
        "indexes": [
            _asset("^GSPC", "标普500", 2.0),
            _asset("^IXIC", "纳指综指", 3.0),
        ],
        "sectors": [
            _asset("XLK", "科技板块", 5.0),
            _asset("SOXX", "半导体板块", 6.0),
            _asset("XLE", "能源板块", -3.0),
        ],
        "rates_fx": [
            _asset("^TNX", "美国10年期国债收益率", -4.5),
            _asset("DX-Y.NYB", "美元指数", -0.8),
        ],
        "precious_metals": [
            _asset("GC=F", "黄金", 1.2),
        ],
        "energy": [
            _asset("CL=F", "WTI原油", -4.9),
            _asset("BZ=F", "布伦特原油", -4.2),
        ],
        "industrial_metals": [
            _asset("HG=F", "铜", 1.1),
        ],
        "risk_signals": {
            "risk_mode": "risk_on",
        },
    }
    events = [
        {
            "event_id": "tech_001",
            "event_status": "confirmed",
            "official_source_count": 1,
            "source_count": 2,
            "topic_tags": ["semiconductor_supply_chain"],
            "affected_assets": ["SOXX", "XLK"],
            "key_facts": ["BIS eased timing on one semiconductor restriction update."],
        },
        {
            "event_id": "tech_media_001",
            "event_status": "confirmed",
            "official_source_count": 0,
            "source_count": 1,
            "topic_tags": ["semiconductor_supply_chain"],
            "affected_assets": ["SOXX"],
            "key_facts": ["Media said chip shares led the rally."],
        },
        {
            "event_id": "energy_001",
            "event_status": "confirmed",
            "official_source_count": 2,
            "source_count": 3,
            "topic_tags": ["energy_shipping"],
            "affected_assets": ["CL=F", "BZ=F"],
            "key_facts": ["Oil prices fell after shipping risk eased."],
        },
        {
            "event_id": "rates_001",
            "event_status": "confirmed",
            "official_source_count": 1,
            "source_count": 1,
            "topic_tags": ["rates_macro"],
            "affected_assets": ["^TNX", "DX-Y.NYB"],
            "key_facts": ["Treasury yields eased overnight."],
        },
        {
            "event_id": "no_asset_link_001",
            "event_status": "confirmed",
            "official_source_count": 2,
            "source_count": 2,
            "topic_tags": ["trade_policy"],
            "affected_assets": [],
            "key_facts": ["A ceremonial trade statement had no new measures."],
        },
    ]

    mainlines = engine.build(market_board=market_board, events=events)

    assert [mainline["mainline_bucket"] for mainline in mainlines] == [
        "tech_semiconductor",
        "geopolitics_energy",
        "rates_liquidity",
    ]

    tech_mainline = mainlines[0]
    assert tech_mainline["primary_event_id"] == "tech_001"
    assert tech_mainline["linked_event_ids"] == ["tech_001", "tech_media_001"]
    assert tech_mainline["market_effect"] == "科技偏多"
    assert tech_mainline["confidence"] == "high"

    energy_mainline = mainlines[1]
    assert energy_mainline["linked_event_ids"] == ["energy_001"]
    assert energy_mainline["market_effect"] == "能源压力缓和"

    rates_mainline = mainlines[2]
    assert rates_mainline["linked_event_ids"] == ["rates_001"]
    assert rates_mainline["market_effect"] == "利率压力缓和"

    assert all("no_asset_link_001" not in mainline["linked_event_ids"] for mainline in mainlines)


def test_mainline_engine_builds_regime_led_mainlines_and_secondary_context() -> None:
    engine = MainlineEngine()
    market_board = {
        "analysis_date": "2026-04-10",
        "indexes": [_asset("^IXIC", "纳指综指", 2.4)],
        "sectors": [
            _asset("XLK", "科技板块", 4.1),
            _asset("SOXX", "半导体板块", 5.2),
        ],
        "rates_fx": [_asset("^TNX", "美国10年期国债收益率", -1.4)],
        "precious_metals": [],
        "energy": [],
        "industrial_metals": [],
    }
    result = engine.build_result(
        market_board=market_board,
        market_regimes=[
            {
                "regime_id": "2026-04-10__technology_risk_on",
                "regime_key": "technology_risk_on",
                "triggered": True,
                "direction": "bullish",
                "strength": 2.4,
                "confidence": "high",
                "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                "supporting_observations": [],
                "suppressed_by": [],
            }
        ],
        market_regime_evaluations=[
            {
                "regime_id": "2026-04-10__technology_risk_on",
                "regime_key": "technology_risk_on",
                "triggered": True,
                "direction": "bullish",
                "strength": 2.4,
                "confidence": "high",
                "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                "supporting_observations": [],
                "suppressed_by": [],
            },
            {
                "regime_id": "2026-04-10__trade_export_control",
                "regime_key": "trade_export_control",
                "triggered": False,
                "direction": "neutral",
                "strength": 0.0,
                "confidence": "low",
                "driving_symbols": [],
                "supporting_observations": [],
                "suppressed_by": ["no_regime_match"],
            },
        ],
        event_groups=[
            {
                "cluster_id": "semiconductor_supply_chain__guidance__31",
                "cluster_status": "confirmed",
                "official_source_count": 1,
                "source_count": 2,
                "topic_tags": ["semiconductor_supply_chain"],
                "headline": "BIS updates semiconductor export guidance",
                "primary_source_name": "BIS News Updates",
                "items": [],
            },
            {
                "cluster_id": "trade_policy__steel__41",
                "cluster_status": "confirmed",
                "official_source_count": 2,
                "source_count": 2,
                "topic_tags": ["trade_policy"],
                "headline": "Tariff language changed again",
                "primary_source_name": "White House News",
                "items": [],
            },
        ],
    )

    assert [item["mainline_bucket"] for item in result["mainlines"]] == ["tech_semiconductor"]
    assert result["mainlines"][0]["regime_ids"] == ["2026-04-10__technology_risk_on"]
    assert result["mainlines"][0]["linked_event_ids"] == ["semiconductor_supply_chain__guidance__31"]
    assert result["secondary_event_groups"][0]["cluster_id"] == "trade_policy__steel__41"
    assert result["secondary_event_groups"][0]["downgrade_reason"] == "no_regime_match"
