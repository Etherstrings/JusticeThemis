# -*- coding: utf-8 -*-
"""Tests for the browser-viewable daily report preview exporter."""

from __future__ import annotations

from pathlib import Path

from app.db import Database
from app.report_preview import main as report_preview_main
from app.repository import OvernightRepository
from app.services.report_preview import render_daily_report_preview_html


def test_render_daily_report_preview_html_surfaces_report_sections() -> None:
    html = render_daily_report_preview_html(
        {
            "analysis_date": "2026-04-15",
            "access_tier": "premium",
            "summary": {
                "headline": "偏多方向：油服；承压方向：化工下游成本敏感链。",
                "core_view": "本日报告基于 28 条输入生成。",
                "confidence": "high",
            },
            "narratives": {
                "market_view": "纳入了美股收盘快照。",
                "execution_view": "个股映射仍需回到 evidence_points 复核。",
            },
            "input_snapshot": {
                "item_count": 28,
                "official_count": 14,
                "editorial_count": 14,
                "event_cluster_count": 12,
                "market_snapshot_available": True,
                "analysis_status_counts": {"ready": 6, "review": 17, "background": 5},
            },
            "market_snapshot": {
                "headline": "美股收盘快照暂无主要指数摘要。",
            },
            "direction_calls": [
                {
                    "direction": "油服",
                    "stance": "positive",
                    "confidence": "high",
                    "rationale": "由能源主线支撑。",
                    "evidence_points": ["U.S. offshore oil production also set a new record."],
                }
            ],
            "supporting_items": [
                {
                    "item_id": 1,
                    "source_name": "White House News",
                    "title": "President Trump’s Powerful Leadership Highlights American Strength",
                    "llm_ready_brief": "白宫将能源主线放在高优先级位置。",
                    "evidence_points": ["U.S. offshore oil production also set a new record."],
                }
            ],
            "stock_calls": [
                {
                    "ticker": "600583.SH",
                    "name": "海油工程",
                    "action_label": "偏多关注",
                    "reason": "油服方向代表映射。",
                }
            ],
            "risk_watchpoints": ["确认协议条款、适用范围和执行时间。"],
            "mainlines": [{"headline": "能源主线强化", "mainline_bucket": "energy"}],
            "market_regimes": [{"regime_key": "energy_inflation", "confidence": "high"}],
        },
        source_markdown_path="output/live-runs/readhub-2026-04-15/daily-premium.md",
        generated_at="2026-04-15 15:03:00",
    )

    assert "<!doctype html>" in html
    assert "Daily Analysis" in html
    assert "偏多方向：油服；承压方向：化工下游成本敏感链。" in html
    assert "Direction Calls" in html
    assert "White House News" in html
    assert "600583.SH" in html
    assert "确认协议条款、适用范围和执行时间。" in html
    assert "output/live-runs/readhub-2026-04-15/daily-premium.md" in html


def test_report_preview_cli_exports_html_from_persisted_report(tmp_path: Path) -> None:
    database = Database(tmp_path / "report-preview.db")
    repo = OvernightRepository(database)
    repo.create_daily_analysis_report(
        analysis_date="2026-04-15",
        access_tier="premium",
        provider_name="rule_based",
        provider_model="",
        input_item_ids=[1, 2, 3],
        report={
            "summary": {
                "headline": "偏多方向：油服。",
                "core_view": "本日报告基于 3 条输入生成。",
                "confidence": "high",
            },
            "direction_calls": [],
            "stock_calls": [],
            "risk_watchpoints": ["确认税率、覆盖商品清单和生效日期。"],
            "supporting_items": [],
        },
    )

    output_path = tmp_path / "daily-premium.html"
    exit_code = report_preview_main(
        [
            "--analysis-date",
            "2026-04-15",
            "--tier",
            "premium",
            "--db-path",
            str(tmp_path / "report-preview.db"),
            "--output-path",
            str(output_path),
            "--source-markdown-path",
            "output/live-runs/readhub-2026-04-15/daily-premium.md",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    html = output_path.read_text(encoding="utf-8")
    assert "偏多方向：油服。" in html
    assert "Risk Watchpoints" in html
    assert "确认税率、覆盖商品清单和生效日期。" in html
