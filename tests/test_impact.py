# -*- coding: utf-8 -*-
"""Tests for deterministic impact outlines."""

from __future__ import annotations

from app.services.impact import build_impact_outline


def test_build_impact_outline_for_trade_supply_chain_signal() -> None:
    outline = build_impact_outline(
        source_id="ustr_press_releases",
        title="USTR announces tariff adjustment for semiconductor supply chain imports",
        summary=(
            "The release details a new tariff framework for semiconductors, critical minerals, "
            "and related supply chain imports."
        ),
        relevance_label="high",
    )

    assert "自主可控半导体链" in outline.beneficiary_directions
    assert "对美出口链" in outline.pressured_directions
    assert "进口芯片/关键零部件" in outline.price_up_signals
    assert any("税率" in item for item in outline.follow_up_checks)


def test_build_impact_outline_for_energy_shock_signal() -> None:
    outline = build_impact_outline(
        source_id="ap_business",
        title="Asian shares rise as oil prices surge on Strait of Hormuz shipping risk",
        summary="Oil prices surged and shipping risk through the Strait of Hormuz remained elevated.",
        relevance_label="high",
    )

    assert "油气开采" in outline.beneficiary_directions
    assert "航空与燃油敏感运输链" in outline.pressured_directions
    assert "原油/燃料油" in outline.price_up_signals


def test_build_impact_outline_for_generic_policy_signal_stays_cautious() -> None:
    outline = build_impact_outline(
        source_id="whitehouse_news",
        title="Statement from the White House",
        summary="The White House announced a coordinated policy update with agency partners.",
        relevance_label="medium",
    )

    assert outline.beneficiary_directions == ()
    assert outline.pressured_directions == ()
    assert outline.price_up_signals == ()
    assert any("细则" in item or "执行" in item for item in outline.follow_up_checks)


def test_build_impact_outline_for_fed_enforcement_item_does_not_force_rates_trade() -> None:
    outline = build_impact_outline(
        source_id="fed_news",
        title="Federal Reserve Board issues enforcement action with former employee of United Bank",
        summary="The action concerns embezzlement of bank funds and an enforcement order.",
        relevance_label="high",
    )

    assert outline.beneficiary_directions == ()
    assert "尚不足以直接下受益或涨价结论" in outline.impact_summary


def test_build_impact_outline_for_pharma_trade_item_avoids_chip_specific_mapping() -> None:
    outline = build_impact_outline(
        source_id="ustr_press_releases",
        title="Successful Conclusion of the United States–United Kingdom Arrangement on Pharmaceutical Pricing",
        summary="The arrangement addresses pharmaceutical pricing, patient access, and supply chain resilience.",
        relevance_label="high",
    )

    assert "自主可控半导体链" not in outline.beneficiary_directions
    assert "进口芯片/关键零部件" not in outline.price_up_signals


def test_build_impact_outline_for_trade_data_item_uses_data_follow_up() -> None:
    outline = build_impact_outline(
        source_id="census_economic_indicators",
        title="U.S. International Trade in Goods and Services",
        summary="The trade deficit in goods and services widened as imports increased more than exports.",
        relevance_label="high",
    )

    assert "外需与贸易景气验证" in outline.impact_summary
    assert any("分项" in item for item in outline.follow_up_checks)


def test_build_impact_outline_for_trade_data_does_not_force_energy_shock_from_generic_logistics_wording() -> None:
    outline = build_impact_outline(
        source_id="census_economic_indicators",
        title="U.S. trade data shows exports rose 12% as imports stabilized",
        summary=(
            "The latest Census release showed trade conditions improved as exports rose 12% and "
            "inventories stabilized, giving an official read on external demand and shipping activity."
        ),
        relevance_label="high",
    )

    assert "油气与航运扰动可能向成本线传导" not in outline.impact_summary
    assert "原油/燃料油" not in outline.price_up_signals
