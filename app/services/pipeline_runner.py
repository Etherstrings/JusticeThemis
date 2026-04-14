# -*- coding: utf-8 -*-
"""End-to-end fixed pipeline runner for overnight capture and analysis."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Protocol

from app.runtime_defaults import (
    DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
    DEFAULT_CAPTURE_MAX_SOURCES,
    DEFAULT_CAPTURE_RECENT_LIMIT,
)


class CapturePipelineProvider(Protocol):
    def refresh(
        self,
        *,
        limit_per_source: int = 2,
        max_sources: int = 6,
        recent_limit: int = 12,
    ) -> dict[str, object]:
        """Refresh source items and return recent items."""


class MarketSnapshotPipelineProvider(Protocol):
    def refresh_us_close_snapshot(self) -> dict[str, object]:
        """Refresh one U.S. close market snapshot."""


class DailyAnalysisPipelineProvider(Protocol):
    def generate_daily_reports(
        self,
        *,
        analysis_date: str | None = None,
        recent_limit: int = 200,
    ) -> dict[str, object]:
        """Generate cached fixed daily reports."""


class OvernightPipelineService:
    def __init__(
        self,
        *,
        capture_service: CapturePipelineProvider,
        market_snapshot_service: MarketSnapshotPipelineProvider,
        daily_analysis_service: DailyAnalysisPipelineProvider,
    ) -> None:
        self.capture_service = capture_service
        self.market_snapshot_service = market_snapshot_service
        self.daily_analysis_service = daily_analysis_service

    def run(
        self,
        *,
        analysis_date: str | None = None,
        limit_per_source: int = DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
        max_sources: int = DEFAULT_CAPTURE_MAX_SOURCES,
        recent_limit: int = DEFAULT_CAPTURE_RECENT_LIMIT,
        include_market_snapshot: bool = True,
        include_daily_analysis: bool = True,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        requested_analysis_date = str(analysis_date or "").strip()

        capture_result = self.capture_service.refresh(
            limit_per_source=limit_per_source,
            max_sources=max_sources,
            recent_limit=recent_limit,
        )
        resolved_analysis_date = str(
            requested_analysis_date
            or self._first_non_empty(
                self._item_analysis_date_preview(capture_result),
                self._snapshot_analysis_date_preview(capture_result),
                started_at.date().isoformat(),
            )
        ).strip()

        market_snapshot_summary = self._skipped_step_summary()
        if include_market_snapshot:
            snapshot = self.market_snapshot_service.refresh_us_close_snapshot()
            market_snapshot_summary = {
                "status": "ok",
                "analysis_date": str(snapshot.get("analysis_date", "")).strip(),
                "market_date": str(snapshot.get("market_date", "")).strip(),
                "source_name": str(snapshot.get("source_name", "")).strip(),
                "headline": str(snapshot.get("headline", "")).strip(),
                "capture_status": str(dict(snapshot.get("capture_summary", {}) or {}).get("capture_status", "")).strip(),
                "captured_instrument_count": int(
                    dict(snapshot.get("capture_summary", {}) or {}).get("captured_instrument_count", 0) or 0
                ),
                "missing_symbols": list(dict(snapshot.get("capture_summary", {}) or {}).get("missing_symbols", []) or []),
                "provider_hits": dict(dict(snapshot.get("capture_summary", {}) or {}).get("provider_hits", {}) or {}),
                "core_missing_symbols": list(dict(snapshot.get("capture_summary", {}) or {}).get("core_missing_symbols", []) or []),
                "supporting_missing_symbols": list(
                    dict(snapshot.get("capture_summary", {}) or {}).get("supporting_missing_symbols", []) or []
                ),
                "optional_missing_symbols": list(
                    dict(snapshot.get("capture_summary", {}) or {}).get("optional_missing_symbols", []) or []
                ),
                "freshness_status_counts": dict(
                    dict(snapshot.get("capture_summary", {}) or {}).get("freshness_status_counts", {}) or {}
                ),
            }
            if market_snapshot_summary["analysis_date"] and not requested_analysis_date:
                resolved_analysis_date = market_snapshot_summary["analysis_date"]

        daily_analysis_summary = self._skipped_step_summary()
        if include_daily_analysis:
            report_result = self.daily_analysis_service.generate_daily_reports(
                analysis_date=resolved_analysis_date,
                recent_limit=200,
            )
            reports = list(report_result.get("reports", []) or [])
            daily_analysis_summary = {
                "status": "ok",
                "analysis_date": str(report_result.get("analysis_date", "")).strip() or resolved_analysis_date,
                "report_count": len(reports),
                "report_tiers": [
                    str(report.get("access_tier", "")).strip()
                    for report in reports
                    if str(report.get("access_tier", "")).strip()
                ],
            }
            premium_report = next(
                (
                    report
                    for report in reports
                    if str(report.get("access_tier", "")).strip() == "premium"
                ),
                {},
            )
            enrichment_summary = dict(dict(premium_report).get("enrichment_summary", {}) or {})
            daily_analysis_summary["ticker_enrichment_status"] = str(enrichment_summary.get("status", "")).strip() or "skipped"
            daily_analysis_summary["ticker_enrichment_attempted_symbol_count"] = int(
                enrichment_summary.get("attempted_symbol_count", 0) or 0
            )
            daily_analysis_summary["ticker_enrichment_error_count"] = int(
                enrichment_summary.get("error_count", 0) or 0
            )

        finished_at = datetime.now(timezone.utc)
        summary = {
            "status": "ok",
            "analysis_date": resolved_analysis_date,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "capture": {
                "status": "ok",
                "collected_sources": int(capture_result.get("collected_sources", 0) or 0),
                "collected_items": int(capture_result.get("collected_items", 0) or 0),
                "recent_total": int(capture_result.get("total", 0) or 0),
                "source_diagnostics": list(capture_result.get("source_diagnostics", []) or []),
            },
            "market_snapshot": market_snapshot_summary,
            "daily_analysis": daily_analysis_summary,
            "recent_preview": self._recent_preview(capture_result),
        }

        if output_path is not None:
            self._write_summary(output_path=output_path, summary=summary)

        return summary

    def _recent_preview(self, capture_result: dict[str, object]) -> list[dict[str, object]]:
        preview: list[dict[str, object]] = []
        for item in list(capture_result.get("items", []) or [])[:10]:
            if not isinstance(item, dict):
                continue
            preview.append(
                {
                    "item_id": int(item.get("item_id", 0) or 0),
                    "source_id": str(item.get("source_id", "")).strip(),
                    "source_name": str(item.get("source_name", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "analysis_status": str(item.get("analysis_status", "")).strip(),
                }
            )
        return preview

    def _item_analysis_date_preview(self, capture_result: dict[str, object]) -> str:
        for item in list(capture_result.get("items", []) or []):
            if not isinstance(item, dict):
                continue
            published_at = str(item.get("published_at", "")).strip()
            if len(published_at) >= 10:
                return published_at[:10]
        return ""

    def _snapshot_analysis_date_preview(self, capture_result: dict[str, object]) -> str:
        return str(capture_result.get("analysis_date", "")).strip()

    def _skipped_step_summary(self) -> dict[str, object]:
        return {"status": "skipped"}

    def _write_summary(self, *, output_path: str | Path, summary: dict[str, Any]) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _first_non_empty(self, *values: str) -> str:
        for value in values:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
        return ""
