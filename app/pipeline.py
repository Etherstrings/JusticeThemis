# -*- coding: utf-8 -*-
"""CLI entrypoint for the fixed overnight pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence

from app.db import Database
from app.runtime_config import (
    DEFAULT_ENV_FILE_PATHS,
    ENRICHMENT_PROVIDER_ENV_NAMES,
    MARKET_PROVIDER_ENV_NAMES,
    SEARCH_PROVIDER_ENV_NAMES,
    load_runtime_environment as load_runtime_env_defaults,
)
from app.repository import OvernightRepository
from app.runtime_defaults import (
    DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
    DEFAULT_CAPTURE_MAX_SOURCES,
    DEFAULT_CAPTURE_RECENT_LIMIT,
)
from app.services.daily_analysis import DailyAnalysisService
from app.services.handoff import HandoffService
from app.services.market_snapshot import UsMarketSnapshotService
from app.services.mmu_handoff import MMUHandoffService
from app.services.pipeline_artifacts import PipelineArtifactService
from app.services.pipeline_blueprint import PipelineBlueprintService
from app.services.pipeline_delivery import PipelineDeliveryService
from app.services.pipeline_health import PipelineHealthService
from app.services.pipeline_markdown import (
    render_daily_report_markdown,
    render_pipeline_blueprint_markdown,
    render_pipeline_summary_markdown,
)
from app.services.pipeline_runner import OvernightPipelineService
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry

PIPELINE_ENV_NAMES: tuple[str, ...] = (
    SEARCH_PROVIDER_ENV_NAMES
    + MARKET_PROVIDER_ENV_NAMES
    + ENRICHMENT_PROVIDER_ENV_NAMES
    + (
        "OVERNIGHT_PREMIUM_API_KEY",
        "OVERNIGHT_ADMIN_API_KEY",
        "OVERNIGHT_ALLOW_UNSAFE_ADMIN",
    )
)


@dataclass(frozen=True)
class RuntimeServices:
    capture_service: OvernightSourceCaptureService
    market_snapshot_service: UsMarketSnapshotService
    daily_analysis_service: DailyAnalysisService
    handoff_service: HandoffService
    mmu_handoff_service: MMUHandoffService
    pipeline_blueprint_service: PipelineBlueprintService
    artifact_service: PipelineArtifactService
    delivery_service: PipelineDeliveryService
    pipeline_service: OvernightPipelineService


def load_runtime_environment(*, env_file_paths: Sequence[str | Path] | None = None) -> dict[str, str]:
    return load_runtime_env_defaults(
        env_file_paths=env_file_paths or DEFAULT_ENV_FILE_PATHS,
        env_names=PIPELINE_ENV_NAMES,
    )


def build_runtime_services(*, db_path: str | Path | None = None) -> RuntimeServices:
    database = Database(path=db_path)
    repo = OvernightRepository(database)
    capture_service = OvernightSourceCaptureService(
        repo=repo,
        registry=build_default_source_registry(),
    )
    market_snapshot_service = UsMarketSnapshotService(repo=repo)
    handoff_service = HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )
    daily_analysis_service = DailyAnalysisService(
        repo=repo,
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )
    mmu_handoff_service = MMUHandoffService()
    pipeline_blueprint_service = PipelineBlueprintService(
        registry=build_default_source_registry(include_disabled=True),
    )
    artifact_service = PipelineArtifactService(
        daily_analysis_service=daily_analysis_service,
        handoff_service=handoff_service,
        mmu_handoff_service=mmu_handoff_service,
    )
    delivery_service = PipelineDeliveryService()
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
        pipeline_blueprint_service=pipeline_blueprint_service,
        artifact_service=artifact_service,
        delivery_service=delivery_service,
        pipeline_service=pipeline_service,
    )


def build_pipeline_service(*, db_path: str | Path | None = None) -> OvernightPipelineService:
    return build_runtime_services(db_path=db_path).pipeline_service


def resolve_health_exit_code(health: dict[str, object], *, fail_on_health_status: str = "") -> int:
    threshold = str(fail_on_health_status or "").strip().lower()
    status = str(dict(health or {}).get("status", "")).strip().lower()
    if threshold == "warn" and status in {"warn", "fail"}:
        return 2
    if threshold == "fail" and status == "fail":
        return 2
    return 0


def _write_json(path: str | Path, payload: dict[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _artifact_manifest_entry(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_type": str(artifact.get("artifact_type", "")).strip(),
        "content_type": str(artifact.get("content_type", "")).strip(),
        "path": str(artifact.get("path", "")).strip(),
        "filename_hint": str(artifact.get("filename_hint", "")).strip(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed overnight news + market + daily-analysis pipeline.")
    parser.add_argument("--analysis-date", default="", help="Optional fixed analysis date in YYYY-MM-DD.")
    parser.add_argument("--db-path", default="", help="Optional SQLite path override.")
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
        help="Max persisted items per source.",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=DEFAULT_CAPTURE_MAX_SOURCES,
        help="Max sources to refresh in this run.",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=DEFAULT_CAPTURE_RECENT_LIMIT,
        help="Recent-item window size for the capture summary.",
    )
    parser.add_argument("--skip-market-snapshot", action="store_true", help="Skip U.S. close market snapshot refresh.")
    parser.add_argument("--skip-daily-analysis", action="store_true", help="Skip fixed daily report generation.")
    parser.add_argument("--output-path", default="", help="Optional JSON summary artifact path.")
    parser.add_argument("--summary-markdown-path", default="", help="Optional Markdown summary artifact path.")
    parser.add_argument("--daily-free-markdown-path", default="", help="Optional Markdown export path for the free daily report.")
    parser.add_argument("--daily-premium-markdown-path", default="", help="Optional Markdown export path for the premium daily report.")
    parser.add_argument("--blueprint-json-path", default="", help="Optional JSON export path for the pipeline blueprint.")
    parser.add_argument("--blueprint-markdown-path", default="", help="Optional Markdown export path for the pipeline blueprint.")
    parser.add_argument("--daily-free-prompt-path", default="", help="Optional JSON export path for the free prompt bundle.")
    parser.add_argument("--daily-premium-prompt-path", default="", help="Optional JSON export path for the premium prompt bundle.")
    parser.add_argument("--mmu-handoff-path", default="", help="Optional JSON export path for the staged MMU handoff bundle.")
    parser.add_argument("--delivery-webhook-url", default="", help="Optional webhook URL for summary + artifact delivery.")
    parser.add_argument("--delivery-timeout-seconds", type=float, default=10.0, help="Webhook timeout in seconds.")
    parser.add_argument(
        "--fail-on-health-status",
        choices=("fail", "warn"),
        default="",
        help="Return exit code 2 when the health status reaches this threshold.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    include_market_snapshot = not bool(args.skip_market_snapshot)
    include_daily_analysis = not bool(args.skip_daily_analysis)

    load_runtime_environment()
    runtime = build_runtime_services(db_path=args.db_path or None)
    summary = runtime.pipeline_service.run(
        analysis_date=args.analysis_date or None,
        limit_per_source=max(1, int(args.limit_per_source)),
        max_sources=max(1, int(args.max_sources)),
        recent_limit=max(1, int(args.recent_limit)),
        include_market_snapshot=include_market_snapshot,
        include_daily_analysis=include_daily_analysis,
        output_path=None,
    )
    health = PipelineHealthService().evaluate(summary)
    summary["health"] = health
    analysis_date = str(summary.get("analysis_date", "")).strip() or None
    blueprint = runtime.pipeline_blueprint_service.build(
        max_sources=max(1, int(args.max_sources)),
        limit_per_source=max(1, int(args.limit_per_source)),
        recent_limit=max(1, int(args.recent_limit)),
    )
    summary["collection_plan"] = {
        "enabled_source_count": int(dict(blueprint.get("source_summary", {}) or {}).get("enabled_source_count", 0) or 0),
        "disabled_source_count": int(dict(blueprint.get("source_summary", {}) or {}).get("disabled_source_count", 0) or 0),
        "default_source_budget": int(dict(blueprint.get("budget", {}) or {}).get("default_source_budget", 0) or 0),
        "default_item_budget": int(dict(blueprint.get("budget", {}) or {}).get("default_item_budget", 0) or 0),
    }

    artifact_records: list[dict[str, object]] = []

    if args.blueprint_json_path:
        artifact_records.append(
            {
                "artifact_type": "pipeline_blueprint_json",
                "content_type": "application/json",
                "path": args.blueprint_json_path,
                "filename_hint": Path(args.blueprint_json_path).name,
                "payload": blueprint,
            }
        )
    if args.blueprint_markdown_path:
        artifact_records.append(
            {
                "artifact_type": "pipeline_blueprint_markdown",
                "content_type": "text/markdown",
                "path": args.blueprint_markdown_path,
                "filename_hint": Path(args.blueprint_markdown_path).name,
                "payload": render_pipeline_blueprint_markdown(blueprint),
            }
        )

    if args.summary_markdown_path:
        artifact_records.append(
            {
                "artifact_type": "pipeline_summary_markdown",
                "content_type": "text/markdown",
                "path": args.summary_markdown_path,
                "filename_hint": Path(args.summary_markdown_path).name,
                "payload": render_pipeline_summary_markdown(summary, health=health),
            }
        )

    if include_daily_analysis and args.daily_free_markdown_path:
        report = runtime.daily_analysis_service.get_daily_report(
            analysis_date=analysis_date,
            access_tier="free",
        )
        if report is None:
            raise RuntimeError("Free daily analysis report not found for markdown export")
        artifact_records.append(
            {
                "artifact_type": "daily_free_markdown",
                "content_type": "text/markdown",
                "path": args.daily_free_markdown_path,
                "filename_hint": Path(args.daily_free_markdown_path).name,
                "payload": render_daily_report_markdown(report),
            }
        )
    if include_daily_analysis and args.daily_premium_markdown_path:
        report = runtime.daily_analysis_service.get_daily_report(
            analysis_date=analysis_date,
            access_tier="premium",
        )
        if report is None:
            raise RuntimeError("Premium daily analysis report not found for markdown export")
        artifact_records.append(
            {
                "artifact_type": "daily_premium_markdown",
                "content_type": "text/markdown",
                "path": args.daily_premium_markdown_path,
                "filename_hint": Path(args.daily_premium_markdown_path).name,
                "payload": render_daily_report_markdown(report),
            }
        )

    want_prompt_artifacts = include_daily_analysis and bool(args.daily_free_prompt_path or args.daily_premium_prompt_path)
    want_mmu_artifact = include_daily_analysis and include_market_snapshot and bool(args.mmu_handoff_path)
    if want_prompt_artifacts or want_mmu_artifact:
        exported_json_artifacts = runtime.artifact_service.build(
            analysis_date=analysis_date or "",
            item_limit=8,
            include_daily_analysis_artifacts=want_prompt_artifacts,
            include_mmu_handoff=want_mmu_artifact,
        )
        artifact_path_map = {
            "daily_free_prompt": args.daily_free_prompt_path,
            "daily_premium_prompt": args.daily_premium_prompt_path,
            "mmu_handoff": args.mmu_handoff_path,
        }
        for artifact in exported_json_artifacts:
            artifact_type = str(artifact.get("artifact_type", "")).strip()
            target_path = str(artifact_path_map.get(artifact_type, "")).strip()
            record = dict(artifact)
            record["path"] = target_path
            artifact_records.append(record)

    summary["artifacts"] = [_artifact_manifest_entry(artifact) for artifact in artifact_records]

    for artifact in artifact_records:
        target_path = str(artifact.get("path", "")).strip()
        if not target_path:
            continue
        if str(artifact.get("content_type", "")).strip() == "application/json":
            payload = artifact.get("payload")
            if not isinstance(payload, dict):
                raise RuntimeError(f"JSON artifact payload must be dict: {artifact.get('artifact_type')}")
            _write_json(target_path, payload)
        else:
            _write_text(target_path, str(artifact.get("payload", "")))

    delivery_result: dict[str, object] = {"status": "skipped"}
    if str(args.delivery_webhook_url).strip():
        try:
            delivery_result = runtime.delivery_service.deliver_webhook(
                webhook_url=str(args.delivery_webhook_url).strip(),
                summary=summary,
                health=health,
                blueprint=blueprint,
                artifacts=artifact_records,
                timeout=max(1.0, float(args.delivery_timeout_seconds)),
            )
        except Exception as exc:
            delivery_result = {
                "status": "fail",
                "webhook_url": str(args.delivery_webhook_url).strip(),
                "error": str(exc),
            }
    summary["delivery"] = delivery_result

    if args.output_path:
        _write_json(args.output_path, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return resolve_health_exit_code(health, fail_on_health_status=args.fail_on_health_status)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
