# -*- coding: utf-8 -*-
"""Health evaluation for the fixed overnight pipeline."""

from __future__ import annotations

from typing import Any


class PipelineHealthService:
    def evaluate(self, summary: dict[str, Any]) -> dict[str, Any]:
        blocking_issues: list[str] = []
        warnings: list[str] = []

        capture = dict(summary.get("capture", {}) or {})
        market_snapshot = dict(summary.get("market_snapshot", {}) or {})
        daily_analysis = dict(summary.get("daily_analysis", {}) or {})

        if str(summary.get("status", "")).strip() != "ok":
            blocking_issues.append("pipeline status is not ok")

        collected_items = int(capture.get("collected_items", 0) or 0)
        collected_sources = int(capture.get("collected_sources", 0) or 0)
        recent_total = int(capture.get("recent_total", 0) or 0)
        source_diagnostics = list(capture.get("source_diagnostics", []) or [])
        if collected_items <= 0:
            if recent_total > 0 and collected_sources > 0:
                warnings.append("capture produced no new items but reused an existing recent window")
            else:
                blocking_issues.append("capture collected zero items")
        else:
            rerun_healthy_recent_window = collected_items < 5 and collected_sources >= 10 and recent_total >= 10
            if collected_sources < 3 or recent_total < 5 or (collected_items < 5 and not rerun_healthy_recent_window):
                warnings.append("capture volume looks thin")
        for source_diagnostic in source_diagnostics:
            if not isinstance(source_diagnostic, dict):
                continue
            if not bool(source_diagnostic.get("is_mission_critical")):
                continue
            status = str(source_diagnostic.get("status", "")).strip()
            source_name = str(source_diagnostic.get("source_name", "")).strip() or str(source_diagnostic.get("source_id", "")).strip()
            if status == "cooldown":
                warnings.append(f"mission critical source cooling down: {source_name}")
            elif status == "error":
                warnings.append(f"mission critical source errored during refresh: {source_name}")

        market_status = str(market_snapshot.get("status", "")).strip()
        if market_status and market_status != "skipped":
            if market_status != "ok":
                blocking_issues.append("market snapshot status is not ok")
            core_missing_symbols = list(market_snapshot.get("core_missing_symbols", []) or [])
            supporting_missing_symbols = list(market_snapshot.get("supporting_missing_symbols", []) or [])
            optional_missing_symbols = list(market_snapshot.get("optional_missing_symbols", []) or [])
            missing_symbols = list(market_snapshot.get("missing_symbols", []) or [])
            capture_status = str(market_snapshot.get("capture_status", "")).strip()
            if capture_status == "partial":
                if core_missing_symbols:
                    blocking_issues.append("market snapshot is partial with core-board gaps")
                elif supporting_missing_symbols or optional_missing_symbols:
                    warnings.append("optional market coverage degraded")
                elif missing_symbols:
                    blocking_issues.append("market snapshot is partial")
            if missing_symbols and not (supporting_missing_symbols or optional_missing_symbols):
                warnings.append("market snapshot has missing symbols")

        analysis_status = str(daily_analysis.get("status", "")).strip()
        if analysis_status and analysis_status != "skipped":
            if analysis_status != "ok":
                blocking_issues.append("daily analysis status is not ok")
            if int(daily_analysis.get("report_count", 0) or 0) < 2:
                blocking_issues.append("daily analysis report count is below expected")
            ticker_enrichment_status = str(daily_analysis.get("ticker_enrichment_status", "")).strip()
            if ticker_enrichment_status in {"degraded", "error"}:
                warnings.append("ticker enrichment degraded")

        status = "ok"
        if blocking_issues:
            status = "fail"
        elif warnings:
            status = "warn"

        return {
            "status": status,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
        }
