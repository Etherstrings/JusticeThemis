# -*- coding: utf-8 -*-
"""Tests for overnight market context and priority scoring."""

from __future__ import annotations

import os
import tempfile

import pytest

from src.config import Config
from src.overnight.normalizer import NumericFact
from src.overnight.market_context import MarketEvent, MarketSnapshot, build_market_link_set
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
        core_fact="USTR announced a 25% tariff action targeting imports from China.",
        title="USTR announces 25% tariff on selected Chinese imports",
        summary="Official trade action signals a broader escalation with China.",
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
                context="25% tariff on selected Chinese imports.",
                subject="imports",
            ),
        ),
    )


def test_trade_tariff_market_links_include_usdcnh_and_brent() -> None:
    link_set = build_market_link_set(_official_trade_shock())

    assert "USDCNH" in link_set.fx
    assert "Brent" in link_set.commodities
    assert "China" in link_set.regions
    assert "fx_repricing" in link_set.transmission_channels


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


def test_priority_engine_uses_morning_highlight_when_alert_threshold_is_higher() -> None:
    event = _official_trade_shock()
    link_set = build_market_link_set(event)

    result = PriorityEngine(
        p0_cutoff=95,
        p1_cutoff=60,
        alert_threshold="P0",
    ).score(event, link_set)

    assert result.priority == "P1"
    assert result.delivery_policy == "morning_brief_highlight"


def test_market_snapshot_repo_round_trip(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    event = _official_trade_shock()
    link_set = build_market_link_set(event)
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
        transmission_map={
            "trade_policy": ("import_costs", "supply_chain", "fx_repricing", "energy_demand")
        },
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
    assert snapshots[0].transmission_map["trade_policy"] == (
        "import_costs",
        "supply_chain",
        "fx_repricing",
        "energy_demand",
    )
