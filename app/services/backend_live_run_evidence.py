# -*- coding: utf-8 -*-
"""Backend-only live run workflow and Chinese-first evidence writer."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.services.pipeline_health import PipelineHealthService
from app.services.pipeline_markdown import render_daily_report_markdown, render_pipeline_summary_markdown


class BackendLiveRunEvidenceService:
    def __init__(
        self,
        *,
        capture_service: object,
        market_snapshot_service: object,
        daily_analysis_service: object,
    ) -> None:
        self.capture_service = capture_service
        self.market_snapshot_service = market_snapshot_service
        self.daily_analysis_service = daily_analysis_service

    def run(
        self,
        *,
        analysis_date: str,
        output_dir: str | Path,
        db_path: str | Path,
        limit_per_source: int = 2,
        max_sources: int = 24,
        recent_limit: int = 20,
        include_market_snapshot: bool = True,
        include_daily_analysis: bool = True,
    ) -> dict[str, Any]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        database_path = Path(db_path)

        started_at = datetime.now(timezone.utc)
        requested_analysis_date = str(analysis_date or "").strip() or started_at.date().isoformat()
        resolved_analysis_date = requested_analysis_date

        capture_result: dict[str, object] = {}
        recent_preview: list[dict[str, object]] = []
        try:
            capture_result = self.capture_service.refresh(
                limit_per_source=max(1, int(limit_per_source)),
                max_sources=max(1, int(max_sources)),
                recent_limit=max(1, int(recent_limit)),
            )
            recent_preview = self._recent_preview(capture_result)
            capture_summary = {
                "status": "ok",
                "collected_sources": int(capture_result.get("collected_sources", 0) or 0),
                "collected_items": int(capture_result.get("collected_items", 0) or 0),
                "recent_total": int(capture_result.get("total", 0) or 0),
                "source_diagnostics": list(capture_result.get("source_diagnostics", []) or []),
            }
        except Exception as exc:
            capture_summary = {
                "status": "error",
                "error": str(exc),
                "collected_sources": 0,
                "collected_items": 0,
                "recent_total": 0,
                "source_diagnostics": [],
            }

        market_snapshot_summary = {"status": "skipped"}
        if include_market_snapshot:
            try:
                snapshot = self.market_snapshot_service.refresh_us_close_snapshot()
                capture_summary_payload = dict(snapshot.get("capture_summary", {}) or {})
                market_snapshot_summary = {
                    "status": "ok",
                    "analysis_date": str(snapshot.get("analysis_date", "")).strip(),
                    "market_date": str(snapshot.get("market_date", "")).strip(),
                    "source_name": str(snapshot.get("source_name", "")).strip(),
                    "headline": str(snapshot.get("headline", "")).strip(),
                    "capture_status": str(capture_summary_payload.get("capture_status", "")).strip(),
                    "captured_instrument_count": int(capture_summary_payload.get("captured_instrument_count", 0) or 0),
                    "missing_symbols": list(capture_summary_payload.get("missing_symbols", []) or []),
                    "provider_hits": dict(capture_summary_payload.get("provider_hits", {}) or {}),
                    "core_missing_symbols": list(capture_summary_payload.get("core_missing_symbols", []) or []),
                    "supporting_missing_symbols": list(capture_summary_payload.get("supporting_missing_symbols", []) or []),
                    "optional_missing_symbols": list(capture_summary_payload.get("optional_missing_symbols", []) or []),
                    "freshness_status_counts": dict(capture_summary_payload.get("freshness_status_counts", {}) or {}),
                }
            except Exception as exc:
                market_snapshot_summary = {
                    "status": "error",
                    "error": str(exc),
                    "capture_status": "",
                    "captured_instrument_count": 0,
                    "missing_symbols": [],
                    "provider_hits": {},
                    "core_missing_symbols": [],
                    "supporting_missing_symbols": [],
                    "optional_missing_symbols": [],
                    "freshness_status_counts": {},
                }

        daily_analysis_summary = {"status": "skipped"}
        if include_daily_analysis:
            try:
                report_result = self.daily_analysis_service.generate_daily_reports(
                    analysis_date=resolved_analysis_date,
                    recent_limit=200,
                )
                reports = [
                    report
                    for report in list(report_result.get("reports", []) or [])
                    if isinstance(report, dict)
                ]
                premium_report = next(
                    (
                        report
                        for report in reports
                        if str(report.get("access_tier", "")).strip() == "premium"
                    ),
                    {},
                )
                enrichment_summary = dict(dict(premium_report).get("enrichment_summary", {}) or {})
                daily_analysis_summary = {
                    "status": "ok",
                    "analysis_date": str(report_result.get("analysis_date", "")).strip() or resolved_analysis_date,
                    "report_count": len(reports),
                    "report_tiers": [
                        str(report.get("access_tier", "")).strip()
                        for report in reports
                        if str(report.get("access_tier", "")).strip()
                    ],
                    "ticker_enrichment_status": str(enrichment_summary.get("status", "")).strip() or "skipped",
                    "ticker_enrichment_attempted_symbol_count": int(
                        enrichment_summary.get("attempted_symbol_count", 0) or 0
                    ),
                    "ticker_enrichment_error_count": int(enrichment_summary.get("error_count", 0) or 0),
                }
            except Exception as exc:
                daily_analysis_summary = {
                    "status": "error",
                    "error": str(exc),
                    "analysis_date": resolved_analysis_date,
                    "report_count": 0,
                    "report_tiers": [],
                    "ticker_enrichment_status": "error",
                    "ticker_enrichment_attempted_symbol_count": 0,
                    "ticker_enrichment_error_count": 0,
                }

        finished_at = datetime.now(timezone.utc)
        summary: dict[str, Any] = {
            "status": "ok",
            "analysis_date": resolved_analysis_date,
            "requested_analysis_date": requested_analysis_date,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "capture": capture_summary,
            "market_snapshot": market_snapshot_summary,
            "daily_analysis": daily_analysis_summary,
            "recent_preview": recent_preview,
        }

        health = PipelineHealthService().evaluate(summary)
        summary["health"] = health

        artifacts: list[dict[str, str]] = [
            {
                "artifact_type": "pipeline_summary_json",
                "content_type": "application/json",
                "path": str(target_dir / "pipeline-summary.json"),
            },
            {
                "artifact_type": "pipeline_summary_markdown",
                "content_type": "text/markdown",
                "path": str(target_dir / "pipeline-summary.md"),
            },
        ]

        daily_reports: dict[str, dict[str, object]] = {}
        if str(daily_analysis_summary.get("status", "")).strip() == "ok":
            for access_tier in ("free", "premium"):
                report = self._get_daily_report(analysis_date=resolved_analysis_date, access_tier=access_tier)
                if report is None:
                    continue
                daily_reports[access_tier] = report
                artifacts.append(
                    {
                        "artifact_type": f"daily_{access_tier}_markdown",
                        "content_type": "text/markdown",
                        "path": str(target_dir / f"daily-{access_tier}.md"),
                    }
                )

        artifacts.extend(
            [
                {
                    "artifact_type": "evidence_markdown",
                    "content_type": "text/markdown",
                    "path": str(target_dir / "readhub-backend-live-run-evidence.zh.md"),
                },
                {
                    "artifact_type": "artifact_manifest_json",
                    "content_type": "application/json",
                    "path": str(target_dir / "artifact-manifest.json"),
                },
            ]
        )
        summary["artifacts"] = artifacts

        readhub_items = self._readhub_items(
            analysis_date=resolved_analysis_date,
            capture_result=capture_result,
        )

        self._write_json(target_dir / "pipeline-summary.json", summary)
        self._write_text(
            target_dir / "pipeline-summary.md",
            render_pipeline_summary_markdown(summary, health=health),
        )
        for access_tier, report in daily_reports.items():
            self._write_text(
                target_dir / f"daily-{access_tier}.md",
                render_daily_report_markdown(report),
            )

        evidence_markdown = self._render_evidence_markdown(
            summary=summary,
            health=health,
            artifacts=artifacts,
            readhub_items=readhub_items,
            db_path=database_path,
        )
        self._write_text(target_dir / "readhub-backend-live-run-evidence.zh.md", evidence_markdown)

        manifest = {
            "analysis_date": resolved_analysis_date,
            "db_path": str(database_path),
            "artifacts": artifacts,
        }
        self._write_json(target_dir / "artifact-manifest.json", manifest)
        return {
            "summary": summary,
            "health": health,
            "artifacts": artifacts,
            "evidence_path": str(target_dir / "readhub-backend-live-run-evidence.zh.md"),
            "manifest_path": str(target_dir / "artifact-manifest.json"),
        }

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

    def _readhub_items(
        self,
        *,
        analysis_date: str,
        capture_result: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        preview_items = self._filter_source_items(
            list(dict(capture_result or {}).get("items", []) or []),
            source_id="readhub_daily_digest",
        )
        list_recent_items = getattr(self.capture_service, "list_recent_items", None)
        if not callable(list_recent_items):
            return preview_items
        recent_payload = list_recent_items(limit=200)
        recent_items = self._filter_source_items(
            list(dict(recent_payload or {}).get("items", []) or []),
            source_id="readhub_daily_digest",
        )
        if recent_items:
            return self._merge_source_items(primary=recent_items, secondary=preview_items)
        if analysis_date:
            dated_payload = list_recent_items(limit=200, analysis_date=analysis_date)
            dated_items = self._filter_source_items(
                list(dict(dated_payload or {}).get("items", []) or []),
                source_id="readhub_daily_digest",
            )
            if dated_items:
                return self._merge_source_items(primary=dated_items, secondary=preview_items)
        return preview_items

    def _filter_source_items(self, items: list[object], *, source_id: str) -> list[dict[str, object]]:
        return [
            dict(item)
            for item in items
            if isinstance(item, dict) and str(item.get("source_id", "")).strip() == source_id
        ]

    def _merge_source_items(
        self,
        *,
        primary: list[dict[str, object]],
        secondary: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        merged: list[dict[str, object]] = []
        seen_keys: set[tuple[int, str, str]] = set()
        for item in [*primary, *secondary]:
            item_id = int(item.get("item_id", 0) or 0)
            canonical_url = str(item.get("canonical_url", "")).strip()
            title = str(item.get("title", "")).strip()
            key = (item_id, canonical_url, title)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(item)
        return merged

    def _get_daily_report(self, *, analysis_date: str, access_tier: str) -> dict[str, object] | None:
        get_daily_report = getattr(self.daily_analysis_service, "get_daily_report", None)
        if not callable(get_daily_report):
            return None
        report = get_daily_report(
            analysis_date=analysis_date,
            access_tier=access_tier,
        )
        return report if isinstance(report, dict) else None

    def _render_evidence_markdown(
        self,
        *,
        summary: dict[str, Any],
        health: dict[str, Any],
        artifacts: list[dict[str, str]],
        readhub_items: list[dict[str, object]],
        db_path: Path,
    ) -> str:
        lines = [
            f"# Readhub 后端真实运行证据（{str(summary.get('analysis_date', '')).strip()}）",
            "",
            "## 一、运行元信息",
            "",
            f"- 请求分析日期：`{str(summary.get('requested_analysis_date', '')).strip()}`",
            f"- 实际分析日期：`{str(summary.get('analysis_date', '')).strip()}`",
            f"- 运行开始时间：`{str(summary.get('started_at', '')).strip()}`",
            f"- 运行结束时间：`{str(summary.get('finished_at', '')).strip()}`",
            f"- 隔离数据库路径：`{str(db_path)}`",
            "",
            "## 二、后端阶段结果",
            "",
            f"- Capture 状态：`{str(dict(summary.get('capture', {}) or {}).get('status', '')).strip()}`",
            f"- Capture 新增条数：`{int(dict(summary.get('capture', {}) or {}).get('collected_items', 0) or 0)}`",
            f"- Capture 命中 source 数：`{int(dict(summary.get('capture', {}) or {}).get('collected_sources', 0) or 0)}`",
            f"- Market Snapshot 状态：`{str(dict(summary.get('market_snapshot', {}) or {}).get('status', '')).strip()}`",
            f"- Daily Analysis 状态：`{str(dict(summary.get('daily_analysis', {}) or {}).get('status', '')).strip()}`",
            f"- Daily Analysis 报告数：`{int(dict(summary.get('daily_analysis', {}) or {}).get('report_count', 0) or 0)}`",
            "",
            "## 三、Readhub 实际效果",
            "",
            f"- Readhub 命中条数：`{len(readhub_items)}`",
        ]

        if readhub_items:
            for item in readhub_items[:5]:
                source_context = dict(item.get("source_context", {}) or {})
                daily_context = dict(source_context.get("daily", {}) or {})
                topic_context = dict(source_context.get("topic", {}) or {})
                lines.append(
                    f"- Rank `{daily_context.get('rank', '')}` | Issue `{daily_context.get('issue_date', '')}` | "
                    f"{str(item.get('title', '')).strip()} | {str(item.get('canonical_url', '')).strip()}"
                )
                tags = [str(tag).strip() for tag in list(topic_context.get("tags", []) or []) if str(tag).strip()]
                news_links = [
                    dict(link)
                    for link in list(topic_context.get("news_links", []) or [])
                    if isinstance(link, dict)
                ]
                if tags:
                    lines.append(f"  tags: {', '.join(tags[:6])}")
                if news_links:
                    first_link = news_links[0]
                    lines.append(
                        f"  sample_link: {str(first_link.get('site_name', '')).strip()} | "
                        f"{str(first_link.get('url', '')).strip()}"
                    )
        else:
            lines.append("- 本轮没有在 recent window 中看到 Readhub 命中。")

        lines.extend(["", "## 四、生成产物", ""])
        for artifact in artifacts:
            lines.append(
                f"- {str(artifact.get('artifact_type', '')).strip()} | "
                f"`{str(artifact.get('path', '')).strip()}`"
            )

        lines.extend(["", "## 五、失败与警告", ""])
        blocking_issues = [str(issue).strip() for issue in list(health.get("blocking_issues", []) or []) if str(issue).strip()]
        warnings = [str(issue).strip() for issue in list(health.get("warnings", []) or []) if str(issue).strip()]
        if not blocking_issues and not warnings:
            lines.append("- 无。")
        for issue in blocking_issues:
            lines.append(f"- blocking: {issue}")
        for issue in warnings:
            lines.append(f"- warning: {issue}")

        capture_errors = [
            str(error).strip()
            for diagnostic in list(dict(summary.get("capture", {}) or {}).get("source_diagnostics", []) or [])
            if isinstance(diagnostic, dict)
            for error in list(diagnostic.get("errors", []) or [])
            if str(error).strip()
        ]
        stage_errors = [
            str(dict(summary.get("market_snapshot", {}) or {}).get("error", "")).strip(),
            str(dict(summary.get("daily_analysis", {}) or {}).get("error", "")).strip(),
            str(dict(summary.get("capture", {}) or {}).get("error", "")).strip(),
        ]
        for error in capture_errors + [error for error in stage_errors if error]:
            lines.append(f"- detail: {error}")

        return "\n".join(lines).strip() + "\n"

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
