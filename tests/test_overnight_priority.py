# -*- coding: utf-8 -*-
"""Tests for overnight market context and priority scoring."""

from __future__ import annotations

import os
import tempfile

import pytest

from src.config import Config
from src.overnight.normalizer import NumericFact
from src.overnight.market_context import (
    MarketEvent,
    MarketSnapshot,
    build_market_link_set,
    build_transmission_map,
)
from src.overnight.priority import PriorityEngine
from src.repositories.overnight_repo import OvernightRepository
from src.storage import DatabaseManager


@pytest.fixture()
def db_manager() -> DatabaseManager:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_overnight_priority.db")
    previous_db_path = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path

    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()

    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if previous_db_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_db_path
        temp_dir.cleanup()


def _official_trade_shock() -> MarketEvent:
    return MarketEvent(
        core_fact="USTR announced a 25% tariff action targeting steel imports from China.",
        title="USTR announces 25% tariff on Chinese steel imports",
        summary="Official trade action signals a broader escalation with China and industrial supply chains.",
        event_type="trade",
        event_subtype="tariff",
        source_id="ustr_press",
        source_class="policy",
        organization_type="official_policy",
        entities=("USTR", "China"),
        numeric_facts=(
            NumericFact(
                metric="tariff_rate",
                value=25.0,
                unit="percent",
                context="25% tariff on Chinese steel imports.",
                subject="steel",
            ),
        ),
        market_reaction_score=0.8,
    )


def test_trade_tariff_market_links_include_usdcnh_and_brent() -> None:
    link_set = build_market_link_set(_official_trade_shock())

    assert "USDCNH" in link_set.fx
    assert "Brent" in link_set.commodities
    assert "China" in link_set.regions
    assert "fx_repricing" in link_set.transmission_channels


def test_transmission_map_is_derived_from_event_and_link_set() -> None:
    event = _official_trade_shock()
    link_set = build_market_link_set(event)

    transmission_map = build_transmission_map(event, link_set)

    assert transmission_map["trade_policy"] == ("import_costs", "supply_chain")
    assert transmission_map["cross_border"] == ("fx_repricing",)
    assert transmission_map["commodities"] == ("energy_demand", "industrial_input_costs")


def test_china_non_trade_event_does_not_get_full_commodity_or_rates_basket() -> None:
    link_set = build_market_link_set(
        MarketEvent(
            core_fact="China's finance ministry published a routine budget update.",
            title="China issues routine fiscal update",
            summary="The update covered local budget execution and did not include trade actions.",
            event_type="macro",
            event_subtype="fiscal_update",
            entities=("China",),
        )
    )

    assert link_set.fx == ("USDCNH",)
    assert link_set.regions == ("China",)
    assert link_set.commodities == ()
    assert link_set.rates == ()
    assert "energy_demand" not in link_set.transmission_channels
    assert "industrial_input_costs" not in link_set.transmission_channels


def test_transmission_map_uses_sector_bucket_for_technology_supply_chain() -> None:
    event = MarketEvent(
        core_fact="The USTR proposed semiconductor export controls affecting China supply chains.",
        title="USTR targets semiconductor supply chain",
        summary="Chip restrictions could reshape technology supply chains.",
        event_type="trade",
        event_subtype="export_control",
        source_id="ustr_press",
        source_class="policy",
        organization_type="official_policy",
        entities=("USTR", "China"),
        numeric_facts=(
            NumericFact(
                metric="percentage",
                value=5.0,
                unit="percent",
                context="Semiconductor exposure estimate of 5%.",
                subject="semiconductor",
            ),
        ),
    )

    transmission_map = build_transmission_map(event, build_market_link_set(event))

    assert transmission_map["sectors"] == ("technology_supply_chain",)
    assert "commodities" not in transmission_map or "technology_supply_chain" not in transmission_map["commodities"]


def test_priority_engine_promotes_official_trade_shock_and_alerts_at_night() -> None:
    event = _official_trade_shock()
    link_set = build_market_link_set(event)

    result = PriorityEngine(
        p0_cutoff=85,
        p1_cutoff=60,
        alert_threshold="P1",
    ).score(event, link_set)

    assert result.priority in {"P0", "P1"}
    assert result.score >= 60
    assert result.delivery_policy == "night_alert_and_brief"
    assert result.score_breakdown["officiality"] > 0
    assert result.score_breakdown["market_breadth"] > 0
    assert result.score_breakdown["market_reaction"] > 0


def test_priority_engine_handles_missing_market_reaction_score_safely() -> None:
    result = PriorityEngine(
        p0_cutoff=85,
        p1_cutoff=60,
        alert_threshold="P1",
    ).score(
        MarketEvent(
            core_fact="Official tariff note omitted reaction data.",
            title="USTR tariff note",
            summary="No market reaction field was populated.",
            event_type="trade",
            event_subtype="tariff",
            source_id="ustr_press",
            source_class="policy",
            organization_type="official_policy",
            entities=("USTR",),
            market_reaction_score=None,  # type: ignore[arg-type]
        )
    )

    assert result.score_breakdown["market_reaction"] == 0


def test_priority_engine_scores_market_reaction_boundary_deterministically() -> None:
    result = PriorityEngine(
        p0_cutoff=85,
        p1_cutoff=60,
        alert_threshold="P1",
    ).score(
        MarketEvent(
            core_fact="Trade shock with measured market reaction.",
            title="Trade shock reaction",
            summary="Boundary input is used to verify deterministic scoring.",
            event_type="trade",
            event_subtype="tariff",
            source_id="ustr_press",
            source_class="policy",
            organization_type="official_policy",
            entities=("USTR", "China"),
            market_reaction_score=0.85,
        )
    )

    assert result.score_breakdown["market_reaction"] == 9


def test_priority_engine_uses_morning_highlight_when_alert_threshold_is_higher() -> None:
    event = _official_trade_shock()
    link_set = build_market_link_set(event)

    result = PriorityEngine(
        p0_cutoff=105,
        p1_cutoff=60,
        alert_threshold="P0",
    ).score(event, link_set)

    assert result.priority == "P1"
    assert result.delivery_policy == "morning_brief_highlight"


def test_priority_engine_keeps_delivery_policy_inside_intermediate_layer() -> None:
    result = PriorityEngine(
        p0_cutoff=95,
        p1_cutoff=70,
        alert_threshold="P0",
    ).score(
        MarketEvent(
            core_fact="Industry publication noted a tentative tariff discussion.",
            title="Tariff discussion remains tentative",
            summary="No official confirmation or broad market linkage yet.",
            event_type="trade",
            event_subtype="tariff",
            market_reaction_score=0.1,
        )
    )

    assert result.delivery_policy == "morning_brief_highlight"
    assert result.delivery_policy in {"night_alert_and_brief", "morning_brief_highlight"}


def test_market_snapshot_repo_round_trip(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    event = _official_trade_shock()
    link_set = build_market_link_set(event)
    transmission_map = build_transmission_map(event, link_set)
    cluster_id = repo.upsert_event_cluster(
        core_fact=event.core_fact,
        event_type=event.event_type,
        event_subtype=event.event_subtype,
    )
    snapshot = MarketSnapshot(
        event_key=event.core_fact,
        event_type=event.event_type,
        event_subtype=event.event_subtype,
        link_set=link_set,
        transmission_map=transmission_map,
        rationale=(
            "official_ustr_source",
            "china_trade_shock",
        ),
    )

    snapshot_id = repo.save_market_snapshot(snapshot, cluster_id=cluster_id)
    snapshots = repo.list_market_snapshots(event_key=event.core_fact)

    assert snapshot_id > 0
    assert len(snapshots) == 1
    assert snapshots[0].id == snapshot_id
    assert snapshots[0].cluster_id == cluster_id
    assert "USDCNH" in snapshots[0].link_set.fx
    assert snapshots[0].transmission_map == transmission_map
