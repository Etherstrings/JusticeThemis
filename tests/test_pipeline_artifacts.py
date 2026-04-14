# -*- coding: utf-8 -*-
"""Tests for prompt/MMU artifact export helpers."""

from __future__ import annotations

from app.services.pipeline_artifacts import PipelineArtifactService


class FakeDailyAnalysisProvider:
    def __init__(self) -> None:
        self.report_calls: list[dict[str, object]] = []

    def get_prompt_bundle(self, *, analysis_date: str | None = None, access_tier: str = "free", version: int | None = None):
        return {
            "analysis_date": analysis_date or "2026-04-10",
            "access_tier": access_tier,
            "messages": [
                {"role": "system", "content": f"{access_tier}-system"},
                {"role": "user", "content": f"{access_tier}-user"},
            ],
        }

    def get_daily_report(self, *, analysis_date: str | None = None, access_tier: str = "free", version: int | None = None):
        self.report_calls.append(
            {
                "analysis_date": analysis_date,
                "access_tier": access_tier,
                "version": version,
            }
        )
        return {
            "analysis_date": analysis_date or "2026-04-10",
            "access_tier": access_tier,
            "summary": f"{access_tier} summary",
        }


class FakeHandoffProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_handoff(self, *, limit: int = 20, analysis_date: str | None = None):
        self.calls.append({"limit": limit, "analysis_date": analysis_date})
        return {
            "analysis_date": "2026-04-10",
            "market_snapshot": {"analysis_date": "2026-04-10", "asset_board": {}},
            "items": [{"item_id": 1, "source_name": "White House News", "title": "Fact Sheet"}],
            "event_groups": [],
            "mainlines": [],
        }


class FakeMMUHandoffProvider:
    def build_bundle(self, *, handoff, analysis_report=None, item_limit: int = 8, access_tier: str = "free"):
        return {
            "analysis_date": "2026-04-10",
            "access_tier": access_tier,
            "single_item_understanding": [{"handoff_type": "single_item_understanding"}],
            "event_consolidation": [],
            "market_attribution": {"handoff_type": "market_attribution"},
            "premium_recommendation": {"handoff_type": "premium_recommendation"},
            "input_report": analysis_report,
            "input_limit": item_limit,
        }


def test_pipeline_artifact_service_builds_prompt_and_mmu_payloads() -> None:
    handoff_provider = FakeHandoffProvider()
    daily_analysis_provider = FakeDailyAnalysisProvider()
    service = PipelineArtifactService(
        daily_analysis_service=daily_analysis_provider,
        handoff_service=handoff_provider,
        mmu_handoff_service=FakeMMUHandoffProvider(),
    )

    artifacts = service.build(analysis_date="2026-04-10", item_limit=6)

    assert [artifact["artifact_type"] for artifact in artifacts] == [
        "daily_free_prompt",
        "daily_premium_prompt",
        "mmu_handoff",
    ]
    assert artifacts[0]["content_type"] == "application/json"
    assert artifacts[0]["payload"]["access_tier"] == "free"
    assert artifacts[1]["payload"]["access_tier"] == "premium"
    assert artifacts[2]["payload"]["market_attribution"]["handoff_type"] == "market_attribution"
    assert artifacts[2]["payload"]["input_limit"] == 6
    assert daily_analysis_provider.report_calls[-1]["access_tier"] == "premium"
    assert handoff_provider.calls == [{"limit": 20, "analysis_date": "2026-04-10"}]
