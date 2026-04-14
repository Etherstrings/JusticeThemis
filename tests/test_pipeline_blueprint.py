# -*- coding: utf-8 -*-
"""Tests for pipeline blueprint planning and markdown rendering."""

from __future__ import annotations

from app.services.pipeline_blueprint import PipelineBlueprintService
from app.services.pipeline_markdown import render_pipeline_blueprint_markdown
from app.sources.registry import build_default_source_registry


def test_pipeline_blueprint_service_describes_default_flow_and_source_policy() -> None:
    service = PipelineBlueprintService(registry=build_default_source_registry())

    blueprint = service.build(max_sources=16, limit_per_source=4, recent_limit=40)

    assert blueprint["product_name"] == "JusticeThemis"
    assert blueprint["pipeline_name"] == "justice_themis"
    assert blueprint["run_window"]["timezone"] == "Asia/Shanghai"
    assert blueprint["source_summary"]["enabled_source_count"] >= 6
    assert blueprint["source_summary"]["disabled_source_count"] >= 2
    assert any(lane["lane_id"] == "official_policy" for lane in blueprint["source_lanes"])
    official_lane = next(lane for lane in blueprint["source_lanes"] if lane["lane_id"] == "official_policy")
    assert "whitehouse_news" in official_lane["source_ids"]
    assert official_lane["default_item_budget"] == official_lane["default_source_budget"] * 4
    official_data_lane = next(lane for lane in blueprint["source_lanes"] if lane["lane_id"] == "official_data")
    editorial_lane = next(lane for lane in blueprint["source_lanes"] if lane["lane_id"] == "editorial_media")
    assert "newyorkfed_news" in official_data_lane["source_ids"]
    assert "ecb_press" in official_data_lane["source_ids"]
    assert "iea_news" in official_data_lane["source_ids"]
    assert "kitco_news" in editorial_lane["source_ids"]
    assert "oilprice_world_news" in editorial_lane["source_ids"]
    assert "farmdoc_daily" in editorial_lane["source_ids"]
    assert "cnbc_markets" in editorial_lane["source_ids"]
    assert "cnbc_technology" in editorial_lane["source_ids"]
    assert "ap_world" in editorial_lane["source_ids"]
    assert "ap_financial_markets" in editorial_lane["source_ids"]
    disabled_ids = [item["source_id"] for item in blueprint["disabled_sources"]]
    assert "state_spokesperson_releases" in disabled_ids
    assert "dod_news_releases" in disabled_ids
    assert any(stage["stage_id"] == "fixed_daily_analysis" for stage in blueprint["processing_stages"])
    assert any(endpoint["path"] == "/api/v1/mmu/handoff" for endpoint in blueprint["entrypoints"]["api"])


def test_render_pipeline_blueprint_markdown_includes_entrypoints_and_lanes() -> None:
    service = PipelineBlueprintService(registry=build_default_source_registry())
    blueprint = service.build(max_sources=12, limit_per_source=3, recent_limit=24)

    markdown = render_pipeline_blueprint_markdown(blueprint)

    assert "# JusticeThemis Pipeline Blueprint" in markdown
    assert "- Product: JusticeThemis" in markdown
    assert "Asia/Shanghai" in markdown
    assert "official_policy" in markdown
    assert "/api/v1/pipeline/blueprint" in markdown
    assert "state_spokesperson_releases" in markdown
