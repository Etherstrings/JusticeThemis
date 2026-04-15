# -*- coding: utf-8 -*-
"""Tests for pipeline health evaluation and markdown exports."""

from __future__ import annotations

from app.pipeline import resolve_health_exit_code
from app.services.pipeline_health import PipelineHealthService
from app.services.pipeline_markdown import render_daily_report_markdown, render_pipeline_summary_markdown


def _healthy_summary() -> dict[str, object]:
    return {
        "status": "ok",
        "analysis_date": "2026-04-10",
        "capture": {
            "status": "ok",
            "collected_sources": 6,
            "collected_items": 12,
            "recent_total": 20,
        },
        "market_snapshot": {
            "status": "ok",
            "analysis_date": "2026-04-10",
            "market_date": "2026-04-09",
            "source_name": "iFinD History, Treasury Yield Curve",
            "headline": "纳指综指 +0.83%；风险状态 risk_on。",
            "capture_status": "complete",
            "captured_instrument_count": 23,
            "missing_symbols": [],
        },
        "daily_analysis": {
            "status": "ok",
            "analysis_date": "2026-04-10",
            "report_count": 2,
            "report_tiers": ["free", "premium"],
        },
        "recent_preview": [
            {
                "item_id": 11,
                "source_name": "White House News",
                "title": "Fact Sheet: Trade Policy Update",
                "analysis_status": "ready",
            }
        ],
    }


def test_pipeline_health_service_returns_ok_for_complete_run() -> None:
    service = PipelineHealthService()

    health = service.evaluate(_healthy_summary())

    assert health["status"] == "ok"
    assert health["blocking_issues"] == []
    assert health["warnings"] == []


def test_pipeline_health_service_returns_fail_for_partial_market_and_missing_reports() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["market_snapshot"] = {
        "status": "ok",
        "capture_status": "partial",
        "captured_instrument_count": 1,
        "missing_symbols": ["^GSPC", "^IXIC"],
        "source_name": "Treasury Yield Curve",
    }
    summary["daily_analysis"] = {
        "status": "ok",
        "report_count": 1,
        "report_tiers": ["free"],
    }

    health = service.evaluate(summary)

    assert health["status"] == "fail"
    assert any("market snapshot is partial" in issue for issue in health["blocking_issues"])
    assert any("daily analysis report count is below expected" in issue for issue in health["blocking_issues"])


def test_pipeline_health_service_returns_warn_for_thin_capture() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["capture"] = {
        "status": "ok",
        "collected_sources": 2,
        "collected_items": 3,
        "recent_total": 3,
    }

    health = service.evaluate(summary)

    assert health["status"] == "warn"
    assert health["blocking_issues"] == []
    assert any("capture volume looks thin" in issue for issue in health["warnings"])


def test_pipeline_health_service_allows_zero_new_items_when_recent_window_exists() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["capture"] = {
        "status": "ok",
        "collected_sources": 6,
        "collected_items": 0,
        "recent_total": 12,
    }

    health = service.evaluate(summary)

    assert health["status"] == "warn"
    assert health["blocking_issues"] == []
    assert any("no new items" in issue for issue in health["warnings"])


def test_pipeline_health_service_does_not_warn_for_low_new_item_delta_when_recent_window_is_healthy() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["capture"] = {
        "status": "ok",
        "collected_sources": 29,
        "collected_items": 2,
        "recent_total": 20,
    }

    health = service.evaluate(summary)

    assert health["status"] == "ok"
    assert health["blocking_issues"] == []
    assert "capture volume looks thin" not in health["warnings"]


def test_pipeline_health_service_warns_when_mission_critical_source_is_cooling_down() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["capture"]["source_diagnostics"] = [
        {
            "source_id": "bls_news_releases",
            "source_name": "BLS News Releases",
            "status": "cooldown",
            "is_mission_critical": True,
            "cooldown_until": "2026-04-10T07:00:00+00:00",
        }
    ]

    health = service.evaluate(summary)

    assert health["status"] == "warn"
    assert any("mission critical source cooling down" in issue for issue in health["warnings"])


def test_pipeline_health_service_distinguishes_optional_market_and_enrichment_degradation() -> None:
    service = PipelineHealthService()
    summary = _healthy_summary()
    summary["market_snapshot"] = {
        "status": "ok",
        "capture_status": "partial",
        "captured_instrument_count": 20,
        "missing_symbols": ["GC=F"],
        "core_missing_symbols": [],
        "supporting_missing_symbols": ["GC=F"],
        "optional_missing_symbols": [],
        "provider_hits": {"iFinD History": 12, "Yahoo Finance Chart": 8},
    }
    summary["daily_analysis"] = {
        "status": "ok",
        "report_count": 2,
        "report_tiers": ["free", "premium"],
        "ticker_enrichment_status": "degraded",
        "ticker_enrichment_error_count": 1,
    }

    health = service.evaluate(summary)

    assert health["status"] == "warn"
    assert health["blocking_issues"] == []
    assert any("optional market coverage degraded" in issue for issue in health["warnings"])
    assert any("ticker enrichment degraded" in issue for issue in health["warnings"])


def test_render_pipeline_summary_markdown_includes_core_sections() -> None:
    markdown = render_pipeline_summary_markdown(_healthy_summary(), health={"status": "ok", "blocking_issues": [], "warnings": []})

    assert "# JusticeThemis Pipeline Summary" in markdown
    assert "2026-04-10" in markdown
    assert "iFinD History, Treasury Yield Curve" in markdown
    assert "Fact Sheet: Trade Policy Update" in markdown
    assert "Health Status: ok" in markdown


def test_render_pipeline_summary_markdown_includes_source_diagnostics() -> None:
    summary = _healthy_summary()
    summary["capture"]["source_diagnostics"] = [
        {
            "source_id": "bls_news_releases",
            "source_name": "BLS News Releases",
            "status": "cooldown",
            "error_count": 1,
            "cooldown_until": "2026-04-10T07:00:00+00:00",
            "errors": ["403 Client Error: Forbidden for url: https://www.bls.gov/bls/news-release/home.htm"],
        }
    ]

    markdown = render_pipeline_summary_markdown(summary, health={"status": "warn", "blocking_issues": [], "warnings": []})

    assert "## Source Diagnostics" in markdown
    assert "BLS News Releases" in markdown
    assert "cooldown" in markdown
    assert "2026-04-10T07:00:00+00:00" in markdown


def test_render_pipeline_summary_markdown_includes_regimes_and_secondary_context() -> None:
    summary = _healthy_summary()
    summary["daily_analysis"]["market_regimes"] = [
        {
            "regime_key": "technology_risk_on",
            "confidence": "high",
            "strength": 2.4,
        }
    ]
    summary["daily_analysis"]["mainlines"] = [
        {
            "headline": "科技/半导体主线走强",
            "mainline_bucket": "tech_semiconductor",
            "confidence": "high",
        }
    ]
    summary["daily_analysis"]["secondary_event_groups"] = [
        {
            "headline": "White House updates tariff language",
            "cluster_id": "trade_policy__steel__11",
            "downgrade_reason": "no_regime_match",
        }
    ]

    markdown = render_pipeline_summary_markdown(summary, health={"status": "ok", "blocking_issues": [], "warnings": []})

    assert "## Market Regimes" in markdown
    assert "technology_risk_on" in markdown
    assert "## Confirmed Mainlines" in markdown
    assert "科技/半导体主线走强" in markdown
    assert "## Secondary Context" in markdown
    assert "trade_policy__steel__11" in markdown


def test_render_daily_report_markdown_includes_direction_calls_and_stock_calls() -> None:
    report = {
        "analysis_date": "2026-04-10",
        "access_tier": "premium",
        "summary": "昨夜美股科技偏强，贸易与能源主线同步升温。",
        "direction_calls": [
            {
                "direction": "自主可控半导体链",
                "stance": "positive",
                "confidence": "high",
                "rationale": "白宫与 BIS 信号共同支撑。",
                "evidence_points": ["白宫发布半导体相关事实清单"],
            }
        ],
        "stock_calls": [
            {
                "ticker": "688981.SH",
                "name": "中芯国际",
                "action_label": "偏多关注",
                "reason": "方向映射到自主可控半导体链。",
            }
        ],
        "risk_watchpoints": ["关注关税细则是否扩大。"],
    }

    markdown = render_daily_report_markdown(report)

    assert "# JusticeThemis Daily Analysis Report" in markdown
    assert "昨夜美股科技偏强" in markdown
    assert "自主可控半导体链" in markdown
    assert "688981.SH" in markdown
    assert "关注关税细则是否扩大" in markdown


def test_render_daily_report_markdown_formats_structured_summary_dict() -> None:
    report = {
        "analysis_date": "2026-04-10",
        "access_tier": "free",
        "summary": {
            "headline": "偏多方向：进口替代制造链。",
            "core_view": "昨夜美股收盘后，贸易与制造政策主线较强。",
            "confidence": "high",
        },
        "direction_calls": [],
        "stock_calls": [],
        "risk_watchpoints": [],
    }

    markdown = render_daily_report_markdown(report)

    assert "偏多方向：进口替代制造链。" in markdown
    assert "昨夜美股收盘后，贸易与制造政策主线较强。" in markdown
    assert "Confidence: high" in markdown
    assert "{'headline':" not in markdown


def test_render_daily_report_markdown_includes_key_news_with_source_attribution() -> None:
    report = {
        "analysis_date": "2026-04-10",
        "access_tier": "free",
        "summary": "隔夜新闻主线偏向能源与贵金属。",
        "direction_calls": [],
        "stock_calls": [],
        "risk_watchpoints": [],
        "supporting_items": [
            {
                "item_id": 11,
                "source_name": "Kitco News",
                "title": "Gold extends three-week rally, but fragile ceasefire and inflation risks cap upside",
                "llm_ready_brief": "金价延续三周涨势，但通胀和地缘风险让上行空间受限。",
                "impact_summary": "贵金属避险逻辑延续。",
            },
            {
                "item_id": 12,
                "source_name": "Oilprice World News",
                "title": "Fervo Locks In 1.7 GW Turbine Supply as Geothermal Ambitions Accelerate",
                "llm_ready_brief": "",
                "impact_summary": "地热设备扩张强化能源投资主线。",
            },
        ],
    }

    markdown = render_daily_report_markdown(report)

    assert "## Key News" in markdown
    assert "Kitco News | Gold extends three-week rally" in markdown
    assert "金价延续三周涨势" in markdown
    assert "Oilprice World News | Fervo Locks In 1.7 GW Turbine Supply" in markdown
    assert "地热设备扩张强化能源投资主线" in markdown


def test_render_daily_report_markdown_prefers_user_brief_and_includes_mainline_coverage_note() -> None:
    report = {
        "analysis_date": "2026-04-10",
        "access_tier": "free",
        "summary": {
            "headline": "偏多方向：油服。",
            "core_view": "当前市场快照存在核心缺口，市场板块并不完整。 暂未确认市场主线，原因包括：核心市场板块缺口、未触发明确 regime。",
            "confidence": "medium",
        },
        "mainline_coverage": {
            "status": "degraded",
            "market_data_status": "partial",
            "suppression_reasons": ["core_market_gap", "no_triggered_regime"],
        },
        "direction_calls": [],
        "stock_calls": [],
        "risk_watchpoints": ["市场快照核心板块仍有缺口，需补齐后再确认主线强度。"],
        "headline_news": [
            {
                "item_id": 11,
                "source_name": "White House News",
                "title": "White House energy fact sheet",
                "user_brief_cn": "白宫强调海上能源扩产，继续支撑油服链。",
                "brief_source": "synthesized_cn",
                "llm_ready_brief": "item_id=11 | White House News | authority=primary_official",
                "impact_summary": "item_id=11 | White House News",
            }
        ],
    }

    markdown = render_daily_report_markdown(report)

    assert "白宫强调海上能源扩产" in markdown
    assert "item_id=11 | White House News | authority=primary_official" not in markdown
    assert "当前市场快照存在核心缺口" in markdown


def test_render_daily_report_markdown_includes_detailed_market_moves_and_driver_chain_sections() -> None:
    report = {
        "analysis_date": "2026-04-15",
        "access_tier": "premium",
        "summary": {
            "headline": "偏多方向：油服；承压方向：化工下游成本敏感链。",
            "core_view": "国际油价盘中拉升，市场正在重新交易霍尔木兹风险。",
            "confidence": "medium",
        },
        "market_move_brief": {
            "headline": "布伦特原油 +1.60%；WTI原油 +1.50%；黄金 -0.40%；美国10年期国债收益率 +0.06%。",
            "cross_asset_moves": [
                {"label": "布伦特原油", "change_pct": "+1.60%", "bucket": "energy"},
                {"label": "WTI原油", "change_pct": "+1.50%", "bucket": "energy"},
                {"label": "黄金", "change_pct": "-0.40%", "bucket": "precious_metals"},
            ],
            "strongest_move": {"label": "布伦特原油", "change_pct": "+1.60%"},
            "weakest_move": {"label": "黄金", "change_pct": "-0.40%"},
            "china_futures_watch": [
                {
                    "future_name": "PTA",
                    "watch_direction": "up",
                    "driver_summary": "布伦特原油 +1.60%；WTI原油 +1.50%。",
                }
            ],
            "market_data_note": "当前市场板块数据不完整，部分板块仍需补齐。",
        },
        "event_drivers": [
            {
                "source_name": "White House News",
                "title": "Trump team weighs additional Middle East deployment",
                "user_brief_cn": "美方考虑进一步军事部署，霍尔木兹运输风险升温。",
                "why_it_matters_cn": "这会先推升原油与运输风险溢价。",
                "detail_facts": [
                    "Brent=+1.60%(盘中涨幅)",
                    "WTI=+1.50%(盘中涨幅)",
                    "ICE 布油盘中突破 96 美元/桶。",
                ],
            }
        ],
        "editorial_chain_cn": "市场先交易布伦特原油 +1.60%、WTI原油 +1.50%，随后需要用 White House News 的中东增兵消息解释价格动作，落到 A 股映射则先看油服，成本承压链关注化工下游成本敏感链。",
        "direction_calls": [],
        "stock_calls": [],
        "risk_watchpoints": ["确认霍尔木兹通行状态和增兵节奏。"],
        "headline_news": [],
    }

    markdown = render_daily_report_markdown(report)

    assert "## Market Moves" in markdown
    assert "布伦特原油 +1.60%" in markdown
    assert "最强异动" in markdown
    assert "PTA" in markdown
    assert "## Driver Chain" in markdown
    assert "White House News" in markdown
    assert "ICE 布油盘中突破 96 美元/桶" in markdown
    assert "市场先交易布伦特原油 +1.60%" in markdown


def test_resolve_health_exit_code_respects_warn_threshold() -> None:
    assert resolve_health_exit_code({"status": "ok"}, fail_on_health_status="warn") == 0
    assert resolve_health_exit_code({"status": "warn"}, fail_on_health_status="warn") == 2
    assert resolve_health_exit_code({"status": "fail"}, fail_on_health_status="warn") == 2
    assert resolve_health_exit_code({"status": "warn"}, fail_on_health_status="fail") == 0
    assert resolve_health_exit_code({"status": "fail"}, fail_on_health_status="fail") == 2
