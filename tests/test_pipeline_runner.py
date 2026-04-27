# -*- coding: utf-8 -*-
"""Tests for the end-to-end overnight pipeline runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.pipeline import RuntimeServices, load_runtime_environment, main
from app.services.pipeline_blueprint import PipelineBlueprintService
from app.services.pipeline_runner import OvernightPipelineService


class FakeCaptureService:
    def __init__(self) -> None:
        self.refresh_calls: list[dict[str, int]] = []

    def refresh(self, *, limit_per_source: int, max_sources: int, recent_limit: int) -> dict[str, object]:
        self.refresh_calls.append(
            {
                "limit_per_source": limit_per_source,
                "max_sources": max_sources,
                "recent_limit": recent_limit,
            }
        )
        return {
            "collected_sources": 6,
            "collected_items": 18,
            "total": 12,
            "items": [
                {
                    "item_id": 101,
                    "source_id": "whitehouse_news",
                    "source_name": "White House News",
                    "title": "White House fact sheet",
                    "analysis_status": "ready",
                },
                {
                    "item_id": 102,
                    "source_id": "ustr_press_releases",
                    "source_name": "USTR Press Releases",
                    "title": "USTR tariff statement",
                    "analysis_status": "review",
                },
            ],
            "source_diagnostics": [
                {
                    "source_id": "whitehouse_news",
                    "source_name": "White House News",
                    "status": "ok",
                    "candidate_count": 3,
                    "selected_candidate_count": 2,
                    "persisted_count": 2,
                    "errors": [],
                }
            ],
        }


class FakeMarketSnapshotService:
    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_us_close_snapshot(self) -> dict[str, object]:
        self.refresh_calls += 1
        return {
            "analysis_date": "2026-04-10",
            "market_date": "2026-04-09",
            "source_name": "iFinD History, Treasury Yield Curve",
            "headline": "纳指综指 +0.83%；风险状态 risk_on。",
            "capture_summary": {
                "capture_status": "complete",
                "captured_instrument_count": 23,
                "missing_symbols": [],
            },
        }


class FakeMismatchedMarketSnapshotService(FakeMarketSnapshotService):
    def refresh_us_close_snapshot(self) -> dict[str, object]:
        self.refresh_calls += 1
        return {
            "analysis_date": "2026-04-11",
            "market_date": "2026-04-10",
            "source_name": "Treasury Yield Curve",
            "headline": "美国10年期国债收益率 +0.00%；风险状态 mixed。",
            "capture_summary": {
                "capture_status": "partial",
                "captured_instrument_count": 1,
                "missing_symbols": ["^GSPC"],
            },
        }


class FakeDailyAnalysisService:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []
        self.report_calls: list[dict[str, object]] = []

    def generate_daily_reports(self, *, analysis_date: str | None = None, recent_limit: int = 200) -> dict[str, object]:
        self.generate_calls.append(
            {
                "analysis_date": analysis_date,
                "recent_limit": recent_limit,
            }
        )
        return {
            "analysis_date": analysis_date or "2026-04-10",
            "reports": [
                {"access_tier": "free", "version": 1},
                {"access_tier": "premium", "version": 1},
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
            "group_report": {
                "report_type": "group_report",
                "analysis_date": analysis_date or "2026-04-10",
                "access_tier": access_tier,
                "markdown": f"# 群发中长版\n\n- {access_tier} group report\n",
            },
            "desk_report": {
                "report_type": "desk_report",
                "analysis_date": analysis_date or "2026-04-10",
                "access_tier": access_tier,
                "markdown": f"# 内参长版\n\n- {access_tier} desk report\n",
            },
        }

    def get_prompt_bundle(self, *, analysis_date: str | None = None, access_tier: str = "free", version: int | None = None):
        return {"analysis_date": analysis_date or "2026-04-10", "access_tier": access_tier, "messages": []}


class FakeHandoffService:
    def get_handoff(self, *, limit: int = 20, analysis_date: str | None = None):
        return {
            "analysis_date": analysis_date or "2026-04-10",
            "market_snapshot": {"analysis_date": analysis_date or "2026-04-10", "asset_board": {}},
            "items": [],
            "event_groups": [],
            "mainlines": [],
        }


class FakeMMUHandoffService:
    def build_bundle(self, *, handoff, analysis_report=None, item_limit: int = 8, access_tier: str = "free"):
        return {"analysis_date": handoff.get("analysis_date"), "item_limit": item_limit, "access_tier": access_tier}


class TrackingArtifactService:
    def __init__(self, artifacts: list[dict[str, object]] | None = None) -> None:
        self.artifacts = artifacts or []
        self.calls: list[dict[str, object]] = []

    def build(
        self,
        *,
        analysis_date: str,
        item_limit: int = 8,
        include_daily_analysis_artifacts: bool = True,
        include_mmu_handoff: bool = True,
    ):
        self.calls.append(
            {
                "analysis_date": analysis_date,
                "item_limit": item_limit,
                "include_daily_analysis_artifacts": include_daily_analysis_artifacts,
                "include_mmu_handoff": include_mmu_handoff,
            }
        )
        return list(self.artifacts)


class FileCheckingDeliveryService:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.should_raise = should_raise
        self.calls: list[dict[str, object]] = []

    def deliver_webhook(self, *, webhook_url: str, summary, health, blueprint, artifacts, timeout: float = 10.0):
        self.calls.append({"webhook_url": webhook_url, "artifacts": artifacts, "timeout": timeout})
        for artifact in artifacts:
            path = str(artifact.get("path", "")).strip()
            if path:
                assert Path(path).exists(), f"artifact missing before delivery: {path}"
        if self.should_raise:
            raise RuntimeError("webhook boom")
        return {"status": "ok", "status_code": 202, "artifact_count": len(artifacts)}


def _runtime_services_for_cli(*, artifact_service, delivery_service) -> RuntimeServices:
    capture_service = FakeCaptureService()
    market_snapshot_service = FakeMarketSnapshotService()
    daily_analysis_service = FakeDailyAnalysisService()
    handoff_service = FakeHandoffService()
    mmu_handoff_service = FakeMMUHandoffService()
    pipeline_service = OvernightPipelineService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
    )
    return RuntimeServices(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
        handoff_service=handoff_service,
        mmu_handoff_service=mmu_handoff_service,
        pipeline_blueprint_service=PipelineBlueprintService(),
        artifact_service=artifact_service,
        delivery_service=delivery_service,
        pipeline_service=pipeline_service,
    )


def test_pipeline_service_runs_capture_market_and_analysis_and_writes_summary(tmp_path) -> None:
    capture_service = FakeCaptureService()
    market_snapshot_service = FakeMarketSnapshotService()
    daily_analysis_service = FakeDailyAnalysisService()
    output_path = tmp_path / "pipeline-summary.json"
    service = OvernightPipelineService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
    )

    summary = service.run(
        analysis_date="2026-04-10",
        limit_per_source=4,
        max_sources=16,
        recent_limit=40,
        output_path=output_path,
    )

    assert summary["status"] == "ok"
    assert summary["analysis_date"] == "2026-04-10"
    assert summary["capture"]["collected_sources"] == 6
    assert summary["capture"]["collected_items"] == 18
    assert summary["capture"]["source_diagnostics"][0]["source_id"] == "whitehouse_news"
    assert summary["market_snapshot"]["capture_status"] == "complete"
    assert summary["market_snapshot"]["captured_instrument_count"] == 23
    assert summary["daily_analysis"]["report_count"] == 2
    assert summary["daily_analysis"]["report_tiers"] == ["free", "premium"]
    assert summary["recent_preview"][0]["item_id"] == 101
    assert capture_service.refresh_calls == [
        {"limit_per_source": 4, "max_sources": 16, "recent_limit": 40}
    ]
    assert market_snapshot_service.refresh_calls == 1
    assert daily_analysis_service.generate_calls == [
        {"analysis_date": "2026-04-10", "recent_limit": 200}
    ]

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["status"] == "ok"
    assert written["market_snapshot"]["market_date"] == "2026-04-09"


def test_pipeline_service_can_skip_market_snapshot_and_daily_analysis() -> None:
    capture_service = FakeCaptureService()
    market_snapshot_service = FakeMarketSnapshotService()
    daily_analysis_service = FakeDailyAnalysisService()
    service = OvernightPipelineService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
    )

    summary = service.run(
        analysis_date="2026-04-10",
        include_market_snapshot=False,
        include_daily_analysis=False,
    )

    assert summary["status"] == "ok"
    assert summary["market_snapshot"]["status"] == "skipped"
    assert summary["daily_analysis"]["status"] == "skipped"
    assert market_snapshot_service.refresh_calls == 0
    assert daily_analysis_service.generate_calls == []


def test_pipeline_service_surfaces_market_and_enrichment_diagnostics_in_summary() -> None:
    capture_service = FakeCaptureService()

    class DiagnosticMarketSnapshotService(FakeMarketSnapshotService):
        def refresh_us_close_snapshot(self) -> dict[str, object]:
            self.refresh_calls += 1
            return {
                "analysis_date": "2026-04-10",
                "market_date": "2026-04-09",
                "source_name": "iFinD History, Yahoo Finance Chart",
                "headline": "科技偏强，贵金属缺失。",
                "capture_summary": {
                    "capture_status": "partial",
                    "captured_instrument_count": 20,
                    "missing_symbols": ["GC=F"],
                    "provider_hits": {"iFinD History": 12, "Yahoo Finance Chart": 8},
                    "core_missing_symbols": [],
                    "supporting_missing_symbols": ["GC=F"],
                    "optional_missing_symbols": [],
                    "freshness_status_counts": {"fresh": 20},
                },
            }

    class DiagnosticDailyAnalysisService(FakeDailyAnalysisService):
        def generate_daily_reports(self, *, analysis_date: str | None = None, recent_limit: int = 200) -> dict[str, object]:
            self.generate_calls.append(
                {
                    "analysis_date": analysis_date,
                    "recent_limit": recent_limit,
                }
            )
            return {
                "analysis_date": analysis_date or "2026-04-10",
                "reports": [
                    {"access_tier": "free", "version": 1, "ticker_enrichments": [], "enrichment_summary": {"status": "skipped"}},
                    {
                        "access_tier": "premium",
                        "version": 1,
                        "ticker_enrichments": [{"symbol": "SOXX"}],
                        "enrichment_summary": {
                            "status": "degraded",
                            "attempted_symbol_count": 2,
                            "error_count": 1,
                        },
                    },
                ],
            }

    market_snapshot_service = DiagnosticMarketSnapshotService()
    daily_analysis_service = DiagnosticDailyAnalysisService()
    service = OvernightPipelineService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
    )

    summary = service.run(analysis_date="2026-04-10")

    assert summary["market_snapshot"]["provider_hits"] == {"iFinD History": 12, "Yahoo Finance Chart": 8}
    assert summary["market_snapshot"]["supporting_missing_symbols"] == ["GC=F"]
    assert summary["market_snapshot"]["freshness_status_counts"] == {"fresh": 20}
    assert summary["daily_analysis"]["ticker_enrichment_status"] == "degraded"
    assert summary["daily_analysis"]["ticker_enrichment_attempted_symbol_count"] == 2
    assert summary["daily_analysis"]["ticker_enrichment_error_count"] == 1


def test_pipeline_service_preserves_explicit_analysis_date_when_snapshot_returns_other_date() -> None:
    capture_service = FakeCaptureService()
    market_snapshot_service = FakeMismatchedMarketSnapshotService()
    daily_analysis_service = FakeDailyAnalysisService()
    service = OvernightPipelineService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
        daily_analysis_service=daily_analysis_service,
    )

    summary = service.run(
        analysis_date="2026-04-10",
        include_market_snapshot=True,
        include_daily_analysis=True,
    )

    assert summary["analysis_date"] == "2026-04-10"
    assert summary["market_snapshot"]["analysis_date"] == "2026-04-11"
    assert daily_analysis_service.generate_calls == [
        {"analysis_date": "2026-04-10", "recent_limit": 200}
    ]


def test_load_runtime_environment_reads_env_files_and_sets_process_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "IFIND_REFRESH_TOKEN=test-refresh-token",
                "SERPAPI_API_KEYS=serp-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("IFIND_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEYS", raising=False)

    loaded = load_runtime_environment(env_file_paths=(env_file,))

    assert loaded["IFIND_REFRESH_TOKEN"] == "test-refresh-token"
    assert loaded["SERPAPI_API_KEYS"] == "serp-key"
    assert os.environ["IFIND_REFRESH_TOKEN"] == "test-refresh-token"
    assert os.environ["SERPAPI_API_KEYS"] == "serp-key"


def test_pipeline_cli_skip_flags_do_not_build_prompt_or_mmu_artifacts(tmp_path, monkeypatch) -> None:
    artifact_service = TrackingArtifactService(
        artifacts=[
            {"artifact_type": "daily_free_prompt", "content_type": "application/json", "filename_hint": "free.json", "payload": {"ok": True}},
            {"artifact_type": "mmu_handoff", "content_type": "application/json", "filename_hint": "mmu.json", "payload": {"ok": True}},
        ]
    )
    delivery_service = FileCheckingDeliveryService()
    runtime = _runtime_services_for_cli(artifact_service=artifact_service, delivery_service=delivery_service)
    monkeypatch.setattr("app.pipeline.load_runtime_environment", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.pipeline.build_runtime_services", lambda **kwargs: runtime)

    exit_code = main(
        [
            "--analysis-date",
            "2026-04-10",
            "--skip-market-snapshot",
            "--skip-daily-analysis",
            "--daily-free-prompt-path",
            str(tmp_path / "free.json"),
            "--mmu-handoff-path",
            str(tmp_path / "mmu.json"),
        ]
    )

    assert exit_code == 0
    assert artifact_service.calls == []
    assert not (tmp_path / "free.json").exists()
    assert not (tmp_path / "mmu.json").exists()


def test_pipeline_cli_writes_artifacts_before_webhook_delivery(tmp_path, monkeypatch) -> None:
    artifact_service = TrackingArtifactService(
        artifacts=[
            {
                "artifact_type": "daily_free_prompt",
                "content_type": "application/json",
                "filename_hint": "free.json",
                "payload": {"analysis_date": "2026-04-10"},
            }
        ]
    )
    delivery_service = FileCheckingDeliveryService()
    runtime = _runtime_services_for_cli(artifact_service=artifact_service, delivery_service=delivery_service)
    monkeypatch.setattr("app.pipeline.load_runtime_environment", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.pipeline.build_runtime_services", lambda **kwargs: runtime)

    exit_code = main(
        [
            "--analysis-date",
            "2026-04-10",
            "--daily-free-prompt-path",
            str(tmp_path / "free.json"),
            "--delivery-webhook-url",
            "https://example.com/hook",
            "--output-path",
            str(tmp_path / "summary.json"),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "free.json").exists()
    assert (tmp_path / "summary.json").exists()
    assert len(delivery_service.calls) == 1


def test_pipeline_cli_writes_result_first_report_exports(tmp_path, monkeypatch) -> None:
    artifact_service = TrackingArtifactService()
    delivery_service = FileCheckingDeliveryService()
    runtime = _runtime_services_for_cli(artifact_service=artifact_service, delivery_service=delivery_service)
    monkeypatch.setattr("app.pipeline.load_runtime_environment", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.pipeline.build_runtime_services", lambda **kwargs: runtime)

    summary_path = tmp_path / "summary.json"
    free_group_md = tmp_path / "group-free.md"
    premium_group_json = tmp_path / "group-premium.json"
    free_desk_json = tmp_path / "desk-free.json"
    premium_desk_md = tmp_path / "desk-premium.md"
    exit_code = main(
        [
            "--analysis-date",
            "2026-04-10",
            "--group-report-free-markdown-path",
            str(free_group_md),
            "--group-report-premium-json-path",
            str(premium_group_json),
            "--desk-report-free-json-path",
            str(free_desk_json),
            "--desk-report-premium-markdown-path",
            str(premium_desk_md),
            "--output-path",
            str(summary_path),
        ]
    )

    assert exit_code == 0
    assert free_group_md.exists()
    assert premium_group_json.exists()
    assert free_desk_json.exists()
    assert premium_desk_md.exists()
    assert "free group report" in free_group_md.read_text(encoding="utf-8")
    assert "premium desk report" in premium_desk_md.read_text(encoding="utf-8")

    premium_group_payload = json.loads(premium_group_json.read_text(encoding="utf-8"))
    free_desk_payload = json.loads(free_desk_json.read_text(encoding="utf-8"))
    assert premium_group_payload["report_type"] == "group_report"
    assert premium_group_payload["access_tier"] == "premium"
    assert free_desk_payload["report_type"] == "desk_report"
    assert free_desk_payload["access_tier"] == "free"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifact_types = {artifact["artifact_type"] for artifact in summary["artifacts"]}
    assert "group_report_free_markdown" in artifact_types
    assert "group_report_premium_json" in artifact_types
    assert "desk_report_free_json" in artifact_types
    assert "desk_report_premium_markdown" in artifact_types


def test_pipeline_cli_keeps_local_outputs_when_webhook_fails(tmp_path, monkeypatch) -> None:
    artifact_service = TrackingArtifactService(
        artifacts=[
            {
                "artifact_type": "daily_free_prompt",
                "content_type": "application/json",
                "filename_hint": "free.json",
                "payload": {"analysis_date": "2026-04-10"},
            }
        ]
    )
    delivery_service = FileCheckingDeliveryService(should_raise=True)
    runtime = _runtime_services_for_cli(artifact_service=artifact_service, delivery_service=delivery_service)
    monkeypatch.setattr("app.pipeline.load_runtime_environment", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.pipeline.build_runtime_services", lambda **kwargs: runtime)

    summary_path = tmp_path / "summary.json"
    prompt_path = tmp_path / "free.json"
    exit_code = main(
        [
            "--analysis-date",
            "2026-04-10",
            "--daily-free-prompt-path",
            str(prompt_path),
            "--delivery-webhook-url",
            "https://example.com/hook",
            "--output-path",
            str(summary_path),
        ]
    )

    assert exit_code == 0
    assert prompt_path.exists()
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["delivery"]["status"] == "fail"
    assert "webhook boom" in summary["delivery"]["error"]
