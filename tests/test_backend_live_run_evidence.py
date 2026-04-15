# -*- coding: utf-8 -*-
"""Tests for the backend-only live run evidence workflow."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.backend_live_run_evidence import BackendLiveRunEvidenceService


class FakeCaptureService:
    def __init__(self) -> None:
        self.refresh_calls: list[dict[str, int]] = []
        self.list_recent_calls: list[dict[str, object]] = []

    def refresh(self, *, limit_per_source: int, max_sources: int, recent_limit: int) -> dict[str, object]:
        self.refresh_calls.append(
            {
                "limit_per_source": limit_per_source,
                "max_sources": max_sources,
                "recent_limit": recent_limit,
            }
        )
        return {
            "collected_sources": 4,
            "collected_items": 6,
            "total": 6,
            "items": [
                {
                    "item_id": 201,
                    "source_id": "readhub_daily_digest",
                    "source_name": "Readhub Daily Digest",
                    "title": "OpenAI 内部备忘录曝光",
                    "analysis_status": "ready",
                }
            ],
            "source_diagnostics": [
                {
                    "source_id": "readhub_daily_digest",
                    "source_name": "Readhub Daily Digest",
                    "status": "ok",
                    "candidate_count": 2,
                    "selected_candidate_count": 2,
                    "persisted_count": 2,
                    "error_count": 1,
                    "errors": [
                        "legacy_alias_probe_failed: https://1.readhub.cn/daily | SSL connect error for url: https://1.readhub.cn/daily"
                    ],
                    "is_mission_critical": False,
                }
            ],
        }

    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, object]:
        self.list_recent_calls.append({"limit": limit, "analysis_date": analysis_date})
        return {
            "total": 2,
            "items": [
                {
                    "item_id": 201,
                    "source_id": "readhub_daily_digest",
                    "source_name": "Readhub Daily Digest",
                    "title": "OpenAI 内部备忘录曝光",
                    "canonical_url": "https://readhub.cn/topic/8sReadhubA",
                    "summary": "Readhub topic 页面摘要 A",
                    "analysis_status": "ready",
                    "source_context": {
                        "source_family": "readhub_daily",
                        "daily": {
                            "canonical_url": "https://readhub.cn/daily",
                            "issue_date": "2026-04-15",
                            "rank": 1,
                        },
                        "topic": {
                            "tags": ["AI", "大模型"],
                            "tracking": [
                                {
                                    "publish_date": "2026-04-14T03:00:00.000Z",
                                    "title": "OpenAI 内部备忘录曝光",
                                    "uid": "8sReadhubA",
                                }
                            ],
                            "similar_events": [
                                {
                                    "name": "历史对比事件",
                                    "time": "2024年4月",
                                    "events": [{"title": "背景", "content": "背景说明"}],
                                }
                            ],
                            "news_links": [
                                {
                                    "site_name": "36Kr",
                                    "title": "OpenAI 相关媒体报道",
                                    "url": "https://36kr.com/p/10001",
                                }
                            ],
                            "enrichment_status": "ok",
                        },
                    },
                },
                {
                    "item_id": 202,
                    "source_id": "whitehouse_news",
                    "source_name": "White House News",
                    "title": "Unrelated official item",
                    "canonical_url": "https://www.whitehouse.gov/news/example",
                    "summary": "Other captured source item",
                    "analysis_status": "review",
                    "source_context": {},
                },
            ],
        }


class FakeCaptureServiceWithReadhubWindowGap(FakeCaptureService):
    def refresh(self, *, limit_per_source: int, max_sources: int, recent_limit: int) -> dict[str, object]:
        self.refresh_calls.append(
            {
                "limit_per_source": limit_per_source,
                "max_sources": max_sources,
                "recent_limit": recent_limit,
            }
        )
        return {
            "collected_sources": 4,
            "collected_items": 6,
            "total": 1,
            "items": [
                {
                    "item_id": 301,
                    "source_id": "whitehouse_news",
                    "source_name": "White House News",
                    "title": "Unrelated preview item",
                    "analysis_status": "ready",
                }
            ],
            "source_diagnostics": [],
        }

    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, object]:
        self.list_recent_calls.append({"limit": limit, "analysis_date": analysis_date})
        if analysis_date:
            return {
                "total": 1,
                "items": [
                    {
                        "item_id": 301,
                        "source_id": "whitehouse_news",
                        "source_name": "White House News",
                        "title": "Unrelated preview item",
                        "canonical_url": "https://www.whitehouse.gov/news/example",
                        "summary": "Other captured source item",
                        "analysis_status": "review",
                        "source_context": {},
                    }
                ],
            }
        return {
            "total": 1,
            "items": [
                {
                    "item_id": 302,
                    "source_id": "readhub_daily_digest",
                    "source_name": "Readhub Daily Digest",
                    "title": "霍尔木兹大消息！刚刚，直线拉升！",
                    "canonical_url": "https://readhub.cn/topic/hormuz-302",
                    "summary": "Readhub topic 页面摘要 B",
                    "analysis_status": "ready",
                    "source_context": {
                        "source_family": "readhub_daily",
                        "daily": {
                            "canonical_url": "https://readhub.cn/daily",
                            "issue_date": "2026-04-15",
                            "rank": 2,
                        },
                        "topic": {
                            "tags": ["原油", "中东"],
                            "tracking": [
                                {
                                    "publish_date": "2026-04-15T07:00:00.000Z",
                                    "title": "霍尔木兹大消息！刚刚，直线拉升！",
                                    "uid": "hormuz-302",
                                }
                            ],
                            "news_links": [
                                {
                                    "site_name": "中国基金报",
                                    "title": "霍尔木兹大消息！刚刚，直线拉升！",
                                    "url": "https://example.com/hormuz-302",
                                }
                            ],
                            "enrichment_status": "ok",
                        },
                    },
                }
            ],
        }


class FailingMarketSnapshotService:
    def refresh_us_close_snapshot(self) -> dict[str, object]:
        raise RuntimeError("market snapshot provider timeout")


class FakeDailyAnalysisService:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []
        self.report_calls: list[dict[str, object]] = []

    def generate_daily_reports(self, *, analysis_date: str | None = None, recent_limit: int = 200) -> dict[str, object]:
        self.generate_calls.append({"analysis_date": analysis_date, "recent_limit": recent_limit})
        return {
            "analysis_date": analysis_date or "2026-04-15",
            "reports": [
                {"access_tier": "free", "version": 1},
                {"access_tier": "premium", "version": 1},
            ],
        }

    def get_daily_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, object]:
        self.report_calls.append(
            {
                "analysis_date": analysis_date,
                "access_tier": access_tier,
                "version": version,
            }
        )
        return {
            "analysis_date": analysis_date or "2026-04-15",
            "access_tier": access_tier,
            "summary": f"{access_tier} report summary",
            "direction_calls": [],
            "stock_calls": [],
            "risk_watchpoints": [],
        }


def test_backend_live_run_evidence_service_writes_chinese_first_evidence_pack_even_when_market_snapshot_fails(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "live-run"
    db_path = tmp_path / "readhub-live-run.db"
    service = BackendLiveRunEvidenceService(
        capture_service=FakeCaptureService(),
        market_snapshot_service=FailingMarketSnapshotService(),
        daily_analysis_service=FakeDailyAnalysisService(),
    )

    result = service.run(
        analysis_date="2026-04-15",
        output_dir=output_dir,
        db_path=db_path,
        limit_per_source=2,
        max_sources=30,
        recent_limit=20,
    )

    summary = dict(result["summary"])
    health = dict(result["health"])
    artifacts = list(result["artifacts"])
    evidence_path = output_dir / "readhub-backend-live-run-evidence.zh.md"
    manifest_path = output_dir / "artifact-manifest.json"
    summary_json_path = output_dir / "pipeline-summary.json"
    summary_md_path = output_dir / "pipeline-summary.md"
    free_report_path = output_dir / "daily-free.md"
    premium_report_path = output_dir / "daily-premium.md"

    assert summary["analysis_date"] == "2026-04-15"
    assert summary["capture"]["collected_items"] == 6
    assert summary["market_snapshot"]["status"] == "error"
    assert summary["market_snapshot"]["error"] == "market snapshot provider timeout"
    assert summary["daily_analysis"]["status"] == "ok"
    assert health["status"] == "fail"
    assert "market snapshot status is not ok" in health["blocking_issues"]

    assert summary_json_path.exists()
    assert summary_md_path.exists()
    assert free_report_path.exists()
    assert premium_report_path.exists()
    assert evidence_path.exists()
    assert manifest_path.exists()

    evidence_text = evidence_path.read_text(encoding="utf-8")
    assert "Readhub 后端真实运行证据" in evidence_text
    assert "2026-04-15" in evidence_text
    assert str(db_path) in evidence_text
    assert "OpenAI 内部备忘录曝光" in evidence_text
    assert "https://readhub.cn/topic/8sReadhubA" in evidence_text
    assert "legacy_alias_probe_failed" in evidence_text
    assert "market snapshot provider timeout" in evidence_text
    assert str(summary_json_path) in evidence_text
    assert str(free_report_path) in evidence_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["analysis_date"] == "2026-04-15"
    assert manifest["db_path"] == str(db_path)
    assert manifest["artifacts"] == artifacts
    assert any(item["artifact_type"] == "evidence_markdown" for item in artifacts)


def test_backend_live_run_evidence_service_uses_unfiltered_recent_items_when_analysis_window_misses_readhub(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "live-run"
    db_path = tmp_path / "readhub-live-run.db"
    capture_service = FakeCaptureServiceWithReadhubWindowGap()
    service = BackendLiveRunEvidenceService(
        capture_service=capture_service,
        market_snapshot_service=FailingMarketSnapshotService(),
        daily_analysis_service=FakeDailyAnalysisService(),
    )

    service.run(
        analysis_date="2026-04-16",
        output_dir=output_dir,
        db_path=db_path,
        limit_per_source=2,
        max_sources=30,
        recent_limit=20,
    )

    evidence_text = (output_dir / "readhub-backend-live-run-evidence.zh.md").read_text(encoding="utf-8")
    assert "Readhub 命中条数：`1`" in evidence_text
    assert "霍尔木兹大消息！刚刚，直线拉升！" in evidence_text
    assert "https://readhub.cn/topic/hormuz-302" in evidence_text
    assert {"limit": 200, "analysis_date": None} in capture_service.list_recent_calls
