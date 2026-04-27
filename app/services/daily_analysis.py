# -*- coding: utf-8 -*-
"""Generate and cache fixed daily analysis reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from app.repository import OvernightRepository
from app.services.current_window import filter_current_window_items
from app.services.mainline_engine import MainlineEngine
from app.services.daily_analysis_provider import DailyAnalysisProvider, RuleBasedDailyAnalysisProvider
from app.services.result_first_reports import build_result_first_reports
from app.services.source_capture import OvernightSourceCaptureService
from app.services.ticker_enrichment import TickerEnrichmentService


class MarketSnapshotProvider(Protocol):
    def get_daily_snapshot(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        """Return one persisted market snapshot for the requested analysis date."""


class TickerEnrichmentProvider(Protocol):
    def collect(
        self,
        *,
        analysis_date: str,
        session_name: str,
        access_tier: str,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        stock_calls: list[dict[str, Any]],
        explicit_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """Collect optional ticker enrichments."""


class DailyAnalysisService:
    def __init__(
        self,
        *,
        repo: OvernightRepository,
        capture_service: OvernightSourceCaptureService,
        provider: DailyAnalysisProvider | None = None,
        market_snapshot_service: MarketSnapshotProvider | None = None,
        ticker_enrichment_service: TickerEnrichmentProvider | None = None,
    ) -> None:
        self.repo = repo
        self.capture_service = capture_service
        self.provider = provider or RuleBasedDailyAnalysisProvider()
        self.market_snapshot_service = market_snapshot_service
        self.ticker_enrichment_service = ticker_enrichment_service or TickerEnrichmentService(repo=repo)
        self.mainline_engine = MainlineEngine()

    def generate_daily_reports(
        self,
        *,
        analysis_date: str | None = None,
        recent_limit: int = 200,
    ) -> dict[str, Any]:
        resolved_date = self._resolve_analysis_date(analysis_date)
        market_snapshot = (
            self.market_snapshot_service.get_daily_snapshot(analysis_date=resolved_date)
            if self.market_snapshot_service is not None
            else None
        )
        items = self._items_for_analysis_dates(
            self.capture_service.list_recent_items(limit=recent_limit).get("items", []),
            analysis_dates=self._news_window_dates(
                analysis_date=resolved_date,
                market_snapshot=market_snapshot,
            ),
        )
        mainline_context = self._build_mainline_context(items=items, market_snapshot=market_snapshot)
        mainlines = list(mainline_context.get("mainlines", []) or [])
        mainline_coverage = dict(mainline_context.get("coverage_state", {}) or {})
        market_context = dict(mainline_context.get("market_context", {}) or {})
        reports: list[dict[str, Any]] = []
        input_item_ids = [int(item.get("item_id", 0) or 0) for item in items]
        for access_tier in ("free", "premium"):
            report = self.provider.generate_report(
                analysis_date=resolved_date,
                access_tier=access_tier,
                items=items,
                market_snapshot=market_snapshot,
                mainlines=mainlines,
                mainline_coverage=mainline_coverage,
                market_context=market_context,
            )
            report["market_regimes"] = list(mainline_context.get("market_regimes", []) or [])
            report["secondary_event_groups"] = list(mainline_context.get("secondary_event_groups", []) or [])
            report["mainline_coverage"] = dict(report.get("mainline_coverage", {}) or mainline_coverage)
            report["market_context"] = dict(report.get("market_context", {}) or market_context)
            report["ticker_enrichments"] = []
            report["enrichment_summary"] = {
                "status": "skipped",
                "attempted_symbol_count": 0,
                "error_count": 0,
            }
            if access_tier == "premium":
                enrichment_result = self.ticker_enrichment_service.collect(
                    analysis_date=resolved_date,
                    session_name="daily_analysis",
                    access_tier=access_tier,
                    mainlines=list(report.get("mainlines", []) or []),
                    market_regimes=list(report.get("market_regimes", []) or []),
                    stock_calls=list(report.get("stock_calls", []) or []),
                    explicit_symbols=[],
                )
                report["ticker_enrichments"] = list(enrichment_result.get("records", []) or [])
                report["enrichment_summary"] = {
                    "status": str(enrichment_result.get("status", "")).strip() or "skipped",
                    "attempted_symbol_count": int(enrichment_result.get("attempted_symbol_count", 0) or 0),
                    "error_count": int(enrichment_result.get("error_count", 0) or 0),
                    "trigger_reason": str(enrichment_result.get("trigger_reason", "")).strip(),
                }
            report["product_view"] = self._build_product_view(report)
            stored = self.repo.create_daily_analysis_report(
                analysis_date=resolved_date,
                access_tier=access_tier,
                provider_name=self.provider.name,
                provider_model=str(self.provider.model or ""),
                input_item_ids=input_item_ids,
                report=report,
            )
            reports.append(self._decorate_report(stored))
        return {
            "analysis_date": resolved_date,
            "reports": reports,
        }

    def _build_mainline_context(
        self,
        *,
        items: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        market_context = self._market_context_from_snapshot(market_snapshot)
        if not isinstance(market_snapshot, dict):
            return {
                "market_regimes": [],
                "mainlines": [],
                "secondary_event_groups": [],
                "coverage_state": {
                    "status": "unavailable",
                    "market_data_status": str(market_context.get("market_data_status", "missing")).strip() or "missing",
                    "suppression_reasons": ["market_snapshot_missing"],
                    "secondary_group_count": 0,
                },
                "market_context": market_context,
            }
        market_board = market_snapshot.get("asset_board")
        if not isinstance(market_board, dict):
            market_board = market_snapshot
        if not isinstance(market_board, dict):
            return {
                "market_regimes": [],
                "mainlines": [],
                "secondary_event_groups": [],
                "coverage_state": {
                    "status": "unavailable",
                    "market_data_status": str(market_context.get("market_data_status", "missing")).strip() or "missing",
                    "suppression_reasons": ["market_board_missing"],
                    "secondary_group_count": 0,
                },
                "market_context": market_context,
            }

        event_groups = self._build_event_groups(items)
        market_regimes = list(market_snapshot.get("market_regimes", []) or [])
        market_regime_evaluations = list(market_snapshot.get("market_regime_evaluations", []) or [])
        if market_regimes or market_regime_evaluations:
            result = self.mainline_engine.build_result(
                market_board=market_board,
                market_regimes=market_regimes,
                market_regime_evaluations=market_regime_evaluations,
                event_groups=event_groups,
            )
            mainlines = list(result.get("mainlines", []) or [])
            secondary_event_groups = list(result.get("secondary_event_groups", []) or [])
            return {
                "market_regimes": market_regimes,
                "mainlines": mainlines,
                "secondary_event_groups": secondary_event_groups,
                "coverage_state": self._coverage_state(
                    market_context=market_context,
                    market_regimes=market_regimes,
                    mainlines=mainlines,
                    event_groups=event_groups,
                    secondary_event_groups=secondary_event_groups,
                ),
                "market_context": market_context,
            }

        grouped: dict[str, dict[str, Any]] = {}
        for item in items:
            event_cluster = dict(item.get("event_cluster", {}) or {})
            cluster_id = str(event_cluster.get("cluster_id", "")).strip()
            if not cluster_id:
                continue
            if cluster_id not in grouped:
                grouped[cluster_id] = {
                    "event_id": cluster_id,
                    "event_status": str(event_cluster.get("cluster_status", "")).strip(),
                    "official_source_count": int(event_cluster.get("official_source_count", 0) or 0),
                    "source_count": int(event_cluster.get("source_count", 0) or 0),
                    "topic_tags": list(event_cluster.get("topic_tags", []) or []),
                    "affected_assets": [],
                    "key_facts": list(event_cluster.get("fact_signatures", []) or []),
                }
            grouped[cluster_id]["affected_assets"].extend(self._item_affected_assets(item))

        events = []
        for event in grouped.values():
            event["affected_assets"] = list(dict.fromkeys(event["affected_assets"]))
            events.append(event)
        if not events:
            secondary_event_groups: list[dict[str, Any]] = []
            return {
                "market_regimes": [],
                "mainlines": [],
                "secondary_event_groups": secondary_event_groups,
                "coverage_state": self._coverage_state(
                    market_context=market_context,
                    market_regimes=[],
                    mainlines=[],
                    event_groups=[],
                    secondary_event_groups=secondary_event_groups,
                ),
                "market_context": market_context,
            }
        mainlines = self.mainline_engine.build(market_board=market_board, events=events)
        secondary_event_groups = []
        return {
            "market_regimes": [],
            "mainlines": mainlines,
            "secondary_event_groups": secondary_event_groups,
            "coverage_state": self._coverage_state(
                market_context=market_context,
                market_regimes=[],
                mainlines=mainlines,
                event_groups=event_groups,
                secondary_event_groups=secondary_event_groups,
            ),
            "market_context": market_context,
        }

    def _build_event_groups(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for item in items:
            event_cluster = dict(item.get("event_cluster", {}) or {})
            cluster_id = str(event_cluster.get("cluster_id", "")).strip()
            if not cluster_id:
                continue
            if cluster_id not in grouped:
                grouped[cluster_id] = {
                    "cluster_id": cluster_id,
                    "cluster_status": str(event_cluster.get("cluster_status", "")).strip(),
                    "official_source_count": int(event_cluster.get("official_source_count", 0) or 0),
                    "source_count": int(event_cluster.get("source_count", 0) or 0),
                    "topic_tags": list(event_cluster.get("topic_tags", []) or []),
                    "headline": str(item.get("title", "")).strip(),
                    "primary_source_name": str(item.get("source_name", "")).strip(),
                    "item_ids": [],
                }
            grouped[cluster_id]["item_ids"].append(int(item.get("item_id", 0) or 0))
        return list(grouped.values())

    def _item_affected_assets(self, item: dict[str, Any]) -> list[str]:
        affected_assets: list[str] = []
        for implication in list(item.get("market_implications", []) or []):
            direction = str(implication.get("direction", "")).strip()
            if direction:
                affected_assets.append(direction)
        for field in ("beneficiary_directions", "pressured_directions", "price_up_signals"):
            for direction in list(item.get(field, []) or []):
                candidate = str(direction).strip()
                if candidate:
                    affected_assets.append(candidate)
        return affected_assets

    def _market_context_from_snapshot(self, market_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(market_snapshot, dict):
            return {
                "capture_status": "missing",
                "market_data_status": "missing",
                "missing_symbols": [],
                "core_missing_symbols": [],
                "captured_instrument_count": 0,
            }
        capture_summary = dict(market_snapshot.get("capture_summary", {}) or {})
        capture_status = str(capture_summary.get("capture_status", "")).strip() or "complete"
        missing_symbols = [str(symbol).strip() for symbol in list(capture_summary.get("missing_symbols", []) or []) if str(symbol).strip()]
        core_missing_symbols = [
            str(symbol).strip()
            for symbol in list(capture_summary.get("core_missing_symbols", []) or [])
            if str(symbol).strip()
        ]
        market_data_status = "complete"
        if capture_status == "partial" or core_missing_symbols:
            market_data_status = "partial"
        elif capture_status in {"missing", "error"}:
            market_data_status = "missing"
        return {
            "capture_status": capture_status,
            "market_data_status": market_data_status,
            "missing_symbols": missing_symbols,
            "core_missing_symbols": core_missing_symbols,
            "captured_instrument_count": int(capture_summary.get("captured_instrument_count", 0) or 0),
        }

    def _coverage_state(
        self,
        *,
        market_context: dict[str, Any],
        market_regimes: list[dict[str, Any]],
        mainlines: list[dict[str, Any]],
        event_groups: list[dict[str, Any]],
        secondary_event_groups: list[dict[str, Any]],
    ) -> dict[str, Any]:
        suppression_reasons: list[str] = []
        market_data_status = str(market_context.get("market_data_status", "missing")).strip() or "missing"
        if list(market_context.get("core_missing_symbols", []) or []):
            suppression_reasons.append("core_market_gap")
        if market_data_status == "missing":
            suppression_reasons.append("market_snapshot_missing")
        if not market_regimes:
            suppression_reasons.append("no_triggered_regime")
        if event_groups and not mainlines:
            suppression_reasons.append("no_linked_event_group")
        if not event_groups:
            suppression_reasons.append("no_relevant_event_group")

        if mainlines or market_regimes:
            status = "confirmed"
        elif market_data_status != "complete" or secondary_event_groups or event_groups:
            status = "degraded"
        else:
            status = "unavailable"

        return {
            "status": status,
            "market_data_status": market_data_status,
            "suppression_reasons": list(dict.fromkeys(suppression_reasons)),
            "secondary_group_count": len(secondary_event_groups),
        }

    def get_daily_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        resolved_date = self._resolve_analysis_date(analysis_date)
        if version is not None:
            report = self.repo.get_daily_analysis_report_version(
                analysis_date=resolved_date,
                access_tier=access_tier,
                version=version,
            )
            return self._decorate_report(report)
        report = self.repo.get_latest_daily_analysis_report(
            analysis_date=resolved_date,
            access_tier=access_tier,
        )
        return self._decorate_report(report)

    def get_product_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        report = self.get_daily_report(
            analysis_date=analysis_date,
            access_tier=access_tier,
            version=version,
        )
        if report is None:
            return None
        return {
            "analysis_date": report["analysis_date"],
            "access_tier": report["access_tier"],
            "report_version": report["version"],
            "provider": dict(report.get("provider", {}) or {}),
            "summary": dict(report.get("summary", {}) or {}),
            "product_view": dict(report.get("product_view", {}) or {}),
        }

    def get_group_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        report = self.get_daily_report(
            analysis_date=analysis_date,
            access_tier=access_tier,
            version=version,
        )
        if report is None:
            return None
        return dict(report.get("group_report", {}) or {})

    def get_desk_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        report = self.get_daily_report(
            analysis_date=analysis_date,
            access_tier=access_tier,
            version=version,
        )
        if report is None:
            return None
        return dict(report.get("desk_report", {}) or {})

    def list_report_versions(self, *, analysis_date: str | None = None, access_tier: str = "free") -> dict[str, Any]:
        resolved_date = self._resolve_analysis_date(analysis_date)
        versions = self.repo.list_daily_analysis_report_versions(
            analysis_date=resolved_date,
            access_tier=access_tier,
        )
        return {
            "analysis_date": resolved_date,
            "access_tier": access_tier,
            "versions": versions,
        }

    def get_prompt_bundle(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        report = self.get_daily_report(analysis_date=analysis_date, access_tier=access_tier, version=version)
        if report is None:
            return None
        source_audit_pack = self._build_source_audit_pack(report)

        system_prompt = (
            "你是一名严谨的 A 股晨报分析员。必须优先引用 supporting_items 和 direction_calls 中已经给出的事实与证据。"
            " 不要编造来源，不要把媒体猜测写成确定结论。"
        )
        if access_tier == "free":
            system_prompt += " 不要输出具体个股买卖建议，只能输出方向、受益/承压/涨价链、置信度和待确认项。"
        else:
            system_prompt += " 可以输出具体个股映射，但必须说明映射依据、置信度和风险，不得伪装成确定收益承诺。"

        user_prompt = (
            f"请基于 {report['analysis_date']} 的固定日报缓存生成最终中文晨报。"
            f"\n\nsummary:\n{report['summary']}"
            f"\n\nproduct_view:\n{report.get('product_view', {})}"
            f"\n\nmarket_snapshot:\n{report.get('market_snapshot', {})}"
            f"\n\nnarratives:\n{report.get('narratives', {})}"
            f"\n\ndirection_calls:\n{report.get('direction_calls', [])}"
            f"\n\nstock_calls:\n{report.get('stock_calls', []) if access_tier == 'premium' else []}"
            f"\n\nrisk_watchpoints:\n{report.get('risk_watchpoints', [])}"
            f"\n\nsupporting_items:\n{report.get('supporting_items', [])}"
            f"\n\nsource_audit_pack:\n{source_audit_pack}"
            "\n\n输出必须先给总判断，再给方向结论，再给证据和待确认项。"
        )

        return {
            "analysis_date": report["analysis_date"],
            "access_tier": report["access_tier"],
            "report_version": report["version"],
            "provider_target": "external_llm_ready",
            "input_item_ids": list(report.get("input_item_ids", [])),
            "source_audit_pack": source_audit_pack,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

    def _decorate_report(self, report: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(report, dict):
            return None
        decorated = dict(report)
        decorated["product_view"] = self._build_product_view(decorated)
        decorated.update(
            build_result_first_reports(
                decorated,
                source_audit_pack=self._build_source_audit_pack(decorated),
            )
        )
        return decorated

    def _build_product_view(self, report: dict[str, Any]) -> dict[str, Any]:
        analysis_date = str(report.get("analysis_date", "")).strip()
        summary = dict(report.get("summary", {}) or {})
        narratives = dict(report.get("narratives", {}) or {})
        market_snapshot = dict(report.get("market_snapshot", {}) or {})
        market_context = dict(report.get("market_context", {}) or {})
        mainline_coverage = dict(report.get("mainline_coverage", {}) or {})
        direction_calls = [
            dict(item or {})
            for item in list(report.get("direction_calls", []) or [])
            if isinstance(item, dict)
        ]
        stock_calls = [
            dict(item or {})
            for item in list(report.get("stock_calls", []) or [])
            if isinstance(item, dict)
        ]
        supporting_items = [
            dict(item or {})
            for item in list(report.get("supporting_items", []) or [])
            if isinstance(item, dict)
        ]
        headline_news = [
            dict(item or {})
            for item in list(report.get("headline_news", []) or [])
            if isinstance(item, dict)
        ]
        event_drivers = [
            dict(item or {})
            for item in list(report.get("event_drivers", []) or [])
            if isinstance(item, dict)
        ]
        risk_watchpoints = [
            str(item).strip()
            for item in list(report.get("risk_watchpoints", []) or [])
            if str(item).strip()
        ]
        market_date = str(market_snapshot.get("market_date", "")).strip() or analysis_date
        source_audit_pack = self._build_source_audit_pack(report)
        external_market_signals = dict(market_snapshot.get("external_market_signals", {}) or {})

        return {
            "at_a_glance": {
                "headline": str(summary.get("headline", "")).strip(),
                "confidence": str(summary.get("confidence", "")).strip() or "medium",
                "analysis_date": analysis_date,
                "market_date": market_date,
                "news_window_dates": list(dict.fromkeys(date for date in [market_date, analysis_date] if date)),
                "window_label": (
                    f"美股市场日 {market_date} 收盘 -> 中国分析日 {analysis_date}"
                    if market_date and analysis_date
                    else analysis_date or market_date
                ),
                "market_data_status": str(market_context.get("market_data_status", "")).strip() or "unknown",
                "mainline_status": str(mainline_coverage.get("status", "")).strip() or "unknown",
                "event_group_count": int(source_audit_pack.get("event_group_count", 0) or 0),
                "included_item_count": int(source_audit_pack.get("included_item_count", 0) or 0),
            },
            "market_judgment": {
                "market_view": str(narratives.get("market_view", "")).strip(),
                "policy_view": str(narratives.get("policy_view", "")).strip(),
                "sector_view": str(narratives.get("sector_view", "")).strip(),
                "risk_view": str(narratives.get("risk_view", "")).strip(),
                "execution_view": str(narratives.get("execution_view", "")).strip(),
            },
            "sector_judgments": self._product_sector_judgments(direction_calls),
            "stock_judgments": self._product_stock_judgments(direction_calls, stock_calls),
            "evidence_chain": self._product_evidence_chain(
                event_drivers=event_drivers,
                headline_news=headline_news,
                supporting_items=supporting_items,
            ),
            "follow_up_panel": self._product_follow_up_panel(
                risk_watchpoints=risk_watchpoints,
                direction_calls=direction_calls,
                supporting_items=supporting_items,
                market_context=market_context,
                mainline_coverage=mainline_coverage,
                external_market_signals=external_market_signals,
            ),
            "external_signal_panel": self._product_external_signal_panel(market_snapshot),
            "evidence_summary": {
                "included_item_count": int(source_audit_pack.get("included_item_count", 0) or 0),
                "event_group_count": int(source_audit_pack.get("event_group_count", 0) or 0),
                "official_item_count": len(list(source_audit_pack.get("official_item_ids", []) or [])),
                "omitted_input_item_count": int(source_audit_pack.get("omitted_input_item_count", 0) or 0),
            },
        }

    def _product_sector_judgments(self, direction_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        signal_type_labels = {
            "beneficiary": "受益方向",
            "pressured": "承压方向",
            "price_up": "涨价链",
        }
        return [
            {
                "direction": str(call.get("direction", "")).strip(),
                "signal_type": str(call.get("signal_type", "")).strip(),
                "signal_type_label": signal_type_labels.get(str(call.get("signal_type", "")).strip(), ""),
                "stance": str(call.get("stance", "")).strip(),
                "confidence": str(call.get("confidence", "")).strip(),
                "rationale": str(call.get("rationale", "")).strip(),
                "event_cluster_count": int(call.get("event_cluster_count", 0) or 0),
                "source_mix": dict(call.get("source_mix", {}) or {}),
                "supporting_titles": list(call.get("supporting_titles", []) or []),
                "evidence_points": list(call.get("evidence_points", []) or []),
                "follow_up_checks": list(call.get("follow_up_checks", []) or []),
                "evidence_mainline_ids": list(call.get("evidence_mainline_ids", []) or []),
                "evidence_regime_ids": list(call.get("evidence_regime_ids", []) or []),
            }
            for call in direction_calls[:8]
        ]

    def _product_stock_judgments(
        self,
        direction_calls: list[dict[str, Any]],
        stock_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        direction_lookup = {
            str(call.get("direction", "")).strip(): dict(call)
            for call in direction_calls
            if str(call.get("direction", "")).strip()
        }
        results: list[dict[str, Any]] = []
        for call in stock_calls[:12]:
            direction = str(call.get("direction", "")).strip()
            linked_direction = direction_lookup.get(direction, {})
            results.append(
                {
                    "ticker": str(call.get("ticker", "")).strip(),
                    "name": str(call.get("name", "")).strip(),
                    "direction": direction,
                    "stance": str(call.get("stance", "")).strip(),
                    "confidence": str(call.get("confidence", "")).strip(),
                    "action": str(call.get("action", "")).strip(),
                    "action_label": str(call.get("action_label", "")).strip(),
                    "mapping_basis": str(call.get("mapping_basis", "")).strip(),
                    "reason": str(call.get("reason", "")).strip(),
                    "linked_mainline_ids": list(call.get("linked_mainline_ids", []) or []),
                    "linked_regime_ids": list(call.get("linked_regime_ids", []) or []),
                    "evidence_points": list(linked_direction.get("evidence_points", []) or []),
                    "follow_up_checks": list(linked_direction.get("follow_up_checks", []) or []),
                }
            )
        return results

    def _product_evidence_chain(
        self,
        *,
        event_drivers: list[dict[str, Any]],
        headline_news: list[dict[str, Any]],
        supporting_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if event_drivers:
            return [
                {
                    "source_name": str(item.get("source_name", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "brief": str(item.get("user_brief_cn", "")).strip(),
                    "why_it_matters": str(item.get("why_it_matters_cn", "")).strip(),
                    "detail_facts": list(item.get("detail_facts", []) or []),
                    "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                }
                for item in event_drivers[:4]
            ]
        if headline_news:
            return [
                {
                    "source_name": str(item.get("source_name", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "brief": str(item.get("user_brief_cn", "")).strip() or str(item.get("llm_ready_brief", "")).strip(),
                    "why_it_matters": str(item.get("why_it_matters_cn", "")).strip(),
                    "detail_facts": list(item.get("evidence_points", []) or []),
                    "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                }
                for item in headline_news[:4]
            ]
        return [
            {
                "source_name": str(item.get("source_name", "")).strip(),
                "title": str(item.get("title", "")).strip(),
                "brief": str(item.get("llm_ready_brief", "")).strip() or str(item.get("impact_summary", "")).strip(),
                "why_it_matters": str(item.get("impact_summary", "")).strip(),
                "detail_facts": list(item.get("evidence_points", []) or []),
                "coverage_tier": str(item.get("coverage_tier", "")).strip(),
            }
            for item in supporting_items[:4]
        ]

    def _product_follow_up_panel(
        self,
        *,
        risk_watchpoints: list[str],
        direction_calls: list[dict[str, Any]],
        supporting_items: list[dict[str, Any]],
        market_context: dict[str, Any],
        mainline_coverage: dict[str, Any],
        external_market_signals: dict[str, Any],
    ) -> dict[str, Any]:
        follow_up_checks: list[str] = []
        for value in risk_watchpoints:
            if value not in follow_up_checks:
                follow_up_checks.append(value)
        for call in direction_calls:
            for value in list(call.get("follow_up_checks", []) or []):
                candidate = str(value).strip()
                if candidate and candidate not in follow_up_checks:
                    follow_up_checks.append(candidate)
        for item in supporting_items:
            for value in list(item.get("follow_up_checks", []) or []):
                candidate = str(value).strip()
                if candidate and candidate not in follow_up_checks:
                    follow_up_checks.append(candidate)

        data_gaps: list[str] = []
        core_missing_symbols = [
            str(symbol).strip()
            for symbol in list(market_context.get("core_missing_symbols", []) or [])
            if str(symbol).strip()
        ]
        if core_missing_symbols:
            data_gaps.append(f"市场快照核心缺口：{', '.join(core_missing_symbols)}")
        if str(mainline_coverage.get("status", "")).strip() == "degraded":
            data_gaps.append("市场主线仍处于降级确认状态。")
        provider_statuses = dict(external_market_signals.get("provider_statuses", {}) or {})
        for provider_name, status in provider_statuses.items():
            normalized_status = str(status).strip()
            if normalized_status and normalized_status != "ready":
                data_gaps.append(f"外部信号源 {provider_name} 当前状态 {normalized_status}")

        return {
            "risk_watchpoints": risk_watchpoints[:8],
            "follow_up_checks": follow_up_checks[:12],
            "data_gaps": data_gaps,
        }

    def _product_external_signal_panel(self, market_snapshot: dict[str, Any]) -> dict[str, Any]:
        external_market_signals = dict(market_snapshot.get("external_market_signals", {}) or {})
        prediction_markets = dict(market_snapshot.get("prediction_markets", {}) or {})
        kalshi_signals = dict(market_snapshot.get("kalshi_signals", {}) or {})
        fedwatch_signals = dict(market_snapshot.get("fedwatch_signals", {}) or {})
        cftc_signals = dict(market_snapshot.get("cftc_signals", {}) or {})
        return {
            "headline": str(external_market_signals.get("headline", "")).strip(),
            "provider_statuses": dict(external_market_signals.get("provider_statuses", {}) or {}),
            "provider_count": int(external_market_signals.get("provider_count", 0) or 0),
            "ready_provider_count": int(external_market_signals.get("ready_provider_count", 0) or 0),
            "providers": {
                "polymarket": {
                    "status": str(prediction_markets.get("status", "")).strip(),
                    "headline": str(prediction_markets.get("headline", "")).strip(),
                    "signal_count": int(prediction_markets.get("signal_count", 0) or 0),
                },
                "kalshi": {
                    "status": str(kalshi_signals.get("status", "")).strip(),
                    "headline": str(kalshi_signals.get("headline", "")).strip(),
                    "signal_count": int(kalshi_signals.get("signal_count", 0) or 0),
                },
                "cme_fedwatch": {
                    "status": str(fedwatch_signals.get("status", "")).strip(),
                    "headline": str(fedwatch_signals.get("headline", "")).strip(),
                    "meeting_count": int(fedwatch_signals.get("meeting_count", 0) or 0),
                },
                "cftc": {
                    "status": str(cftc_signals.get("status", "")).strip(),
                    "headline": str(cftc_signals.get("headline", "")).strip(),
                    "signal_count": int(cftc_signals.get("signal_count", 0) or 0),
                },
            },
        }

    def _resolve_analysis_date(self, analysis_date: str | None) -> str:
        candidate = str(analysis_date or "").strip()
        if candidate:
            return candidate
        return datetime.now().date().isoformat()

    def _news_window_dates(
        self,
        *,
        analysis_date: str,
        market_snapshot: dict[str, Any] | None,
    ) -> list[str]:
        dates = [str(analysis_date or "").strip()]
        market_date = str(dict(market_snapshot or {}).get("market_date", "")).strip()
        if market_date and market_date not in dates:
            dates.append(market_date)
        followthrough_date = self._next_calendar_date(str(analysis_date or "").strip())
        if followthrough_date and followthrough_date not in dates:
            dates.append(followthrough_date)
        return [date for date in dates if date]

    def _next_calendar_date(self, analysis_date: str) -> str:
        candidate = str(analysis_date or "").strip()
        if not candidate:
            return ""
        try:
            parsed = datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return ""
        return (parsed + timedelta(days=1)).date().isoformat()

    def _build_source_audit_pack(self, report: dict[str, Any]) -> dict[str, Any]:
        supporting_items = list(report.get("supporting_items", []) or [])
        input_item_ids = [int(item_id) for item_id in list(report.get("input_item_ids", []) or [])]
        grouped: dict[str, dict[str, Any]] = {}
        order: list[str] = []

        for item in supporting_items:
            item_id = int(item.get("item_id", 0) or 0)
            event_cluster = dict(item.get("event_cluster", {}) or {})
            cluster_id = str(event_cluster.get("cluster_id", "")).strip() or f"item_{item_id}"
            if cluster_id not in grouped:
                grouped[cluster_id] = {
                    "cluster_id": cluster_id,
                    "cluster_status": str(event_cluster.get("cluster_status", "")).strip() or "single_source",
                    "primary_item_id": int(event_cluster.get("primary_item_id", 0) or item_id),
                    "item_count": int(event_cluster.get("item_count", 0) or 0),
                    "source_count": int(event_cluster.get("source_count", 0) or 0),
                    "official_source_count": int(event_cluster.get("official_source_count", 0) or 0),
                    "member_item_ids": list(event_cluster.get("member_item_ids", []) or []),
                    "member_source_ids": list(event_cluster.get("member_source_ids", []) or []),
                    "latest_published_at": event_cluster.get("latest_published_at"),
                    "topic_tags": list(event_cluster.get("topic_tags", []) or []),
                    "fact_signatures": list(event_cluster.get("fact_signatures", []) or []),
                    "included_item_ids": [],
                    "items": [],
                }
                order.append(cluster_id)
            group = grouped[cluster_id]
            group["included_item_ids"].append(item_id)
            group["items"].append(
                {
                    "item_id": item_id,
                    "source_id": str(item.get("source_id", "")).strip(),
                    "source_name": str(item.get("source_name", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "signal_score": int(item.get("signal_score", 0) or 0),
                    "analysis_status": str(item.get("analysis_status", "")).strip(),
                    "analysis_confidence": str(item.get("analysis_confidence", "")).strip(),
                    "impact_summary": str(item.get("impact_summary", "")).strip(),
                    "llm_ready_brief": str(item.get("llm_ready_brief", "")).strip(),
                    "evidence_points": list(item.get("evidence_points", []) or []),
                    "follow_up_checks": list(item.get("follow_up_checks", []) or []),
                }
            )

        event_groups = [grouped[cluster_id] for cluster_id in order]
        for group in event_groups:
            primary_item_id = int(group.get("primary_item_id", 0) or 0)
            group["items"].sort(
                key=lambda item: (
                    0 if int(item.get("item_id", 0) or 0) == primary_item_id else 1,
                    -int(item.get("signal_score", 0) or 0),
                    int(item.get("item_id", 0) or 0),
                )
            )
            group["included_item_ids"] = list(dict.fromkeys(int(item_id) for item_id in group["included_item_ids"]))
            group["included_item_count"] = len(group["included_item_ids"])
            if not group["item_count"]:
                group["item_count"] = group["included_item_count"]
            if not group["source_count"]:
                group["source_count"] = len(
                    {
                        str(item.get("source_id", "")).strip()
                        for item in group["items"]
                        if str(item.get("source_id", "")).strip()
                    }
                )
        event_groups.sort(
            key=lambda group: (
                -max((int(item.get("signal_score", 0) or 0) for item in group["items"]), default=0),
                int(group.get("primary_item_id", 0) or 0),
            )
        )

        return {
            "included_item_count": len(supporting_items),
            "input_item_count": len(input_item_ids),
            "omitted_input_item_count": max(0, len(input_item_ids) - len(supporting_items)),
            "event_group_count": len(event_groups),
            "official_item_ids": [
                int(item.get("item_id", 0) or 0)
                for item in supporting_items
                if str(item.get("coverage_tier", "")).strip() in {"official_policy", "official_data"}
            ],
            "supporting_items": supporting_items,
            "event_groups": event_groups,
            "field_priority": [
                "signal_score",
                "signal_score_breakdown",
                "source_capture_confidence",
                "cross_source_confirmation",
                "fact_conflicts",
                "event_cluster",
                "llm_ready_brief",
                "evidence_points",
                "follow_up_checks",
                "impact_summary",
            ],
        }

    def _items_for_analysis_date(self, items: list[dict[str, Any]], *, analysis_date: str) -> list[dict[str, Any]]:
        return self._items_for_analysis_dates(items, analysis_dates=[analysis_date])

    def _items_for_analysis_dates(self, items: list[dict[str, Any]], *, analysis_dates: list[str]) -> list[dict[str, Any]]:
        candidate_dates = [str(date).strip() for date in analysis_dates if str(date).strip()]
        filtered = [
            item
            for item in items
            if any(self._matches_analysis_date(item, analysis_date=analysis_date) for analysis_date in candidate_dates)
        ]
        filtered = filter_current_window_items(filtered)
        filtered.sort(
            key=lambda item: (
                str(item.get("analysis_status", "")) != "ready",
                str(item.get("coverage_tier", "")) == "editorial_media",
                -int(item.get("priority", 0) or 0),
                -int(item.get("item_id", 0) or 0),
            )
        )
        return filtered

    def _matches_analysis_date(self, item: dict[str, Any], *, analysis_date: str) -> bool:
        created_at = str(item.get("created_at", "") or "").strip()
        published_at = str(item.get("published_at", "") or "").strip()
        return created_at.startswith(analysis_date) or published_at.startswith(analysis_date)
