# -*- coding: utf-8 -*-
"""Tests for explicit overnight event construction."""

from __future__ import annotations

from app.services.event_engine import EventEngine


def _item(
    *,
    item_id: int,
    source_id: str,
    source_name: str,
    coverage_tier: str,
    source_authority: str,
    priority: int,
    published_at: str,
    title: str,
    summary: str,
    key_numbers: list[dict[str, object]],
    market_implications: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "source_id": source_id,
        "source_name": source_name,
        "coverage_tier": coverage_tier,
        "source_authority": source_authority,
        "priority": priority,
        "published_at": published_at,
        "published_at_precision": "datetime",
        "created_at": published_at,
        "title": title,
        "summary": summary,
        "impact_summary": "",
        "key_numbers": key_numbers,
        "market_implications": market_implications,
        "entities": [],
    }


def test_event_engine_builds_explicit_event_records_and_item_index() -> None:
    engine = EventEngine()
    items = [
        _item(
            item_id=101,
            source_id="whitehouse_news",
            source_name="White House News",
            coverage_tier="official_policy",
            source_authority="primary_official",
            priority=100,
            published_at="2026-04-07T01:30:00+00:00",
            title="White House says 25% tariff on steel imports remains in place",
            summary=(
                "The White House said the 25% tariff on steel imports remains in place while "
                "agencies review supply chains."
            ),
            key_numbers=[{"metric": "tariff_rate", "subject": "steel", "value_text": "25.0%"}],
            market_implications=[
                {"implication_type": "beneficiary", "direction": "进口替代制造链"},
                {"implication_type": "pressured", "direction": "对美出口链"},
            ],
        ),
        _item(
            item_id=102,
            source_id="ustr_press_releases",
            source_name="USTR Press Releases",
            coverage_tier="official_policy",
            source_authority="primary_official",
            priority=95,
            published_at="2026-04-07T01:50:00+00:00",
            title="USTR confirms 25% tariff on steel imports",
            summary=(
                "USTR confirmed the 25% tariff on steel imports remains in effect while "
                "agencies coordinate implementation."
            ),
            key_numbers=[{"metric": "tariff_rate", "subject": "steel", "value_text": "25.0%"}],
            market_implications=[
                {"implication_type": "beneficiary", "direction": "进口替代制造链"},
                {"implication_type": "pressured", "direction": "对美出口链"},
            ],
        ),
        _item(
            item_id=103,
            source_id="ap_business",
            source_name="AP Business",
            coverage_tier="editorial_media",
            source_authority="editorial_context",
            priority=70,
            published_at="2026-04-07T02:10:00+00:00",
            title="AP says tariff on steel imports could move to 15%",
            summary=(
                "AP reported discussion around a possible 15% tariff on steel imports, though "
                "officials have not confirmed any change to the current policy."
            ),
            key_numbers=[{"metric": "tariff_rate", "subject": "steel", "value_text": "15.0%"}],
            market_implications=[
                {"implication_type": "beneficiary", "direction": "进口替代制造链"},
                {"implication_type": "pressured", "direction": "对美出口链"},
            ],
        ),
        _item(
            item_id=201,
            source_id="fed_news",
            source_name="Federal Reserve News",
            coverage_tier="official_policy",
            source_authority="primary_official",
            priority=98,
            published_at="2026-04-07T02:20:00+00:00",
            title="Federal Reserve says rates may stay restrictive",
            summary=(
                "Federal Reserve officials said inflation remains elevated and rates may need "
                "to stay restrictive while markets assess the next FOMC path."
            ),
            key_numbers=[],
            market_implications=[
                {"implication_type": "pressured", "direction": "高估值成长链"},
            ],
        ),
    ]

    result = engine.build(items)

    assert len(result["events"]) == 2
    trade_event = next(event for event in result["events"] if event["event_id"].startswith("trade_policy"))
    assert trade_event["event_status"] == "conflicted"
    assert trade_event["primary_item_id"] == 101
    assert trade_event["supporting_item_ids"] == [102, 103]
    assert trade_event["official_source_count"] == 2
    assert trade_event["affected_assets"] == ["进口替代制造链", "对美出口链"]
    assert trade_event["key_facts"] == ["tariff_rate: 25.0% on steel", "tariff_rate: 15.0% on steel"]

    rates_event = next(event for event in result["events"] if event["event_id"].startswith("rates_macro"))
    assert rates_event["event_status"] == "single_source"
    assert rates_event["primary_item_id"] == 201
    assert rates_event["affected_assets"] == ["高估值成长链"]

    item_event_index = result["item_event_index"]
    assert item_event_index[101]["cluster_id"] == trade_event["event_id"]
    assert item_event_index[102]["cluster_status"] == "conflicted"
    assert item_event_index[201]["cluster_status"] == "single_source"


def test_event_engine_normalizes_mixed_time_formats_before_time_window_comparison() -> None:
    engine = EventEngine()
    items = [
        {
            "item_id": 301,
            "source_id": "bls_news_releases",
            "source_name": "BLS News Releases",
            "coverage_tier": "official_data",
            "source_authority": "primary_official",
            "priority": 90,
            "published_at": "Wed, 08 Apr 2026 17:47:47 GMT",
            "published_at_precision": "datetime",
            "created_at": "2026-04-09 01:00:00",
            "title": "State employment and unemployment summary keeps payroll trend in focus",
            "summary": "Labor data keeps payroll and unemployment trends in focus while rates expectations remain active.",
            "impact_summary": "",
            "key_numbers": [],
            "market_implications": [{"implication_type": "pressured", "direction": "高估值成长链"}],
            "entities": [],
        },
        {
            "item_id": 302,
            "source_id": "fed_news",
            "source_name": "Federal Reserve News",
            "coverage_tier": "official_policy",
            "source_authority": "primary_official",
            "priority": 98,
            "published_at": "2026-04-08T18:00:00+00:00",
            "published_at_precision": "datetime",
            "created_at": "2026-04-09T01:05:00",
            "title": "Federal Reserve says labor market keeps rate path in focus",
            "summary": "Federal Reserve officials said payroll and unemployment trends keep the rate path in focus.",
            "impact_summary": "",
            "key_numbers": [],
            "market_implications": [{"implication_type": "pressured", "direction": "高估值成长链"}],
            "entities": [],
        },
    ]

    result = engine.build(items)

    assert len(result["events"]) == 1
    assert result["item_event_index"][301]["cluster_id"] == result["events"][0]["event_id"]
