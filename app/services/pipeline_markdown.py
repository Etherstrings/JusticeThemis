# -*- coding: utf-8 -*-
"""Markdown exporters for pipeline summaries and fixed daily reports."""

from __future__ import annotations

from typing import Any


def render_pipeline_summary_markdown(summary: dict[str, Any], *, health: dict[str, Any] | None = None) -> str:
    capture = dict(summary.get("capture", {}) or {})
    market_snapshot = dict(summary.get("market_snapshot", {}) or {})
    daily_analysis = dict(summary.get("daily_analysis", {}) or {})
    health = dict(health or {})

    lines = [
        "# JusticeThemis Pipeline Summary",
        "",
        f"- Analysis Date: {str(summary.get('analysis_date', '')).strip()}",
        f"- Health Status: {str(health.get('status', 'unknown')).strip() or 'unknown'}",
        f"- Duration Seconds: {summary.get('duration_seconds', '')}",
        "",
        "## Capture",
        "",
        f"- Collected Sources: {int(capture.get('collected_sources', 0) or 0)}",
        f"- Collected Items: {int(capture.get('collected_items', 0) or 0)}",
        f"- Recent Total: {int(capture.get('recent_total', 0) or 0)}",
        "",
        "## Market Snapshot",
        "",
        f"- Status: {str(market_snapshot.get('status', '')).strip()}",
        f"- Source: {str(market_snapshot.get('source_name', '')).strip()}",
        f"- Headline: {str(market_snapshot.get('headline', '')).strip()}",
        f"- Capture Status: {str(market_snapshot.get('capture_status', '')).strip()}",
        f"- Captured Instrument Count: {int(market_snapshot.get('captured_instrument_count', 0) or 0)}",
        "",
        "## Daily Analysis",
        "",
        f"- Status: {str(daily_analysis.get('status', '')).strip()}",
        f"- Report Count: {int(daily_analysis.get('report_count', 0) or 0)}",
        f"- Report Tiers: {', '.join(str(item).strip() for item in list(daily_analysis.get('report_tiers', []) or []) if str(item).strip())}",
        "",
    ]

    market_regimes = [
        item
        for item in list(daily_analysis.get("market_regimes", []) or [])
        if isinstance(item, dict)
    ]
    if market_regimes:
        lines.extend(["## Market Regimes", ""])
        for regime in market_regimes[:5]:
            lines.append(
                f"- {str(regime.get('regime_key', '')).strip()} | "
                f"confidence={str(regime.get('confidence', '')).strip()} | "
                f"strength={regime.get('strength', '')}"
            )
        lines.append("")

    confirmed_mainlines = [
        item
        for item in list(daily_analysis.get("mainlines", []) or [])
        if isinstance(item, dict)
    ]
    if confirmed_mainlines:
        lines.extend(["## Confirmed Mainlines", ""])
        for mainline in confirmed_mainlines[:5]:
            lines.append(
                f"- {str(mainline.get('headline', '')).strip()} | "
                f"bucket={str(mainline.get('mainline_bucket', '')).strip()} | "
                f"confidence={str(mainline.get('confidence', '')).strip()}"
            )
        lines.append("")

    secondary_event_groups = [
        item
        for item in list(daily_analysis.get("secondary_event_groups", []) or [])
        if isinstance(item, dict)
    ]
    if secondary_event_groups:
        lines.extend(["## Secondary Context", ""])
        for group in secondary_event_groups[:5]:
            lines.append(
                f"- {str(group.get('cluster_id', '')).strip()} | "
                f"{str(group.get('headline', '')).strip()} | "
                f"downgrade_reason={str(group.get('downgrade_reason', '')).strip()}"
            )
        lines.append("")

    lines.extend(["## Recent Preview", ""])

    preview_rows = list(summary.get("recent_preview", []) or [])
    if not preview_rows:
        lines.append("- No preview items.")
    else:
        for item in preview_rows[:10]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- [{int(item.get('item_id', 0) or 0)}] {str(item.get('source_name', '')).strip()} | "
                f"{str(item.get('analysis_status', '')).strip()} | {str(item.get('title', '')).strip()}"
            )

    source_diagnostics = [
        item
        for item in list(capture.get("source_diagnostics", []) or [])
        if isinstance(item, dict)
    ]
    if source_diagnostics:
        lines.extend(["", "## Source Diagnostics", ""])
        for diagnostic in source_diagnostics[:10]:
            lines.append(
                f"- {str(diagnostic.get('source_name', '')).strip() or str(diagnostic.get('source_id', '')).strip()} | "
                f"status={str(diagnostic.get('status', '')).strip()} | "
                f"errors={int(diagnostic.get('error_count', 0) or 0)} | "
                f"cooldown_until={str(diagnostic.get('cooldown_until', '')).strip() or 'none'}"
            )
            errors = [str(item).strip() for item in list(diagnostic.get("errors", []) or []) if str(item).strip()]
            if errors:
                lines.append(f"  latest_error: {errors[0]}")

    blocking_issues = list(health.get("blocking_issues", []) or [])
    warnings = list(health.get("warnings", []) or [])
    if blocking_issues:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {str(issue).strip()}" for issue in blocking_issues if str(issue).strip())
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {str(issue).strip()}" for issue in warnings if str(issue).strip())

    artifacts = list(summary.get("artifacts", []) or [])
    if artifacts:
        lines.extend(["", "## Artifacts", ""])
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            lines.append(
                f"- {str(artifact.get('artifact_type', '')).strip()} | "
                f"{str(artifact.get('content_type', '')).strip()} | "
                f"{str(artifact.get('path', '')).strip() or 'not_written'}"
            )

    return "\n".join(lines).strip() + "\n"


def render_pipeline_blueprint_markdown(blueprint: dict[str, Any]) -> str:
    lines = [
        "# JusticeThemis Pipeline Blueprint",
        "",
        f"- Product: {str(blueprint.get('product_name', '')).strip()}",
        f"- Objective: {str(blueprint.get('objective', '')).strip()}",
        f"- Timezone: {str(dict(blueprint.get('run_window', {}) or {}).get('timezone', '')).strip()}",
        f"- Target Read Time: {str(dict(blueprint.get('run_window', {}) or {}).get('target_read_time', '')).strip()}",
        "",
        "## Source Summary",
        "",
    ]

    source_summary = dict(blueprint.get("source_summary", {}) or {})
    lines.extend(
        [
            f"- Enabled Sources: {int(source_summary.get('enabled_source_count', 0) or 0)}",
            f"- Disabled Sources: {int(source_summary.get('disabled_source_count', 0) or 0)}",
            f"- Mission Critical Sources: {int(source_summary.get('mission_critical_source_count', 0) or 0)}",
            f"- Search Discovery Sources: {int(source_summary.get('search_discovery_source_count', 0) or 0)}",
            "",
            "## Source Lanes",
            "",
        ]
    )

    for lane in list(blueprint.get("source_lanes", []) or []):
        if not isinstance(lane, dict):
            continue
        lines.append(
            f"- {str(lane.get('lane_id', '')).strip()} | "
            f"{str(lane.get('title', '')).strip()} | "
            f"budget={lane.get('default_item_budget', lane.get('instrument_target_count', ''))}"
        )
        source_ids = [str(item).strip() for item in list(lane.get("source_ids", []) or []) if str(item).strip()]
        if source_ids:
            lines.append(f"  sources: {', '.join(source_ids)}")

    lines.extend(["", "## Processing Stages", ""])
    for stage in list(blueprint.get("processing_stages", []) or []):
        if not isinstance(stage, dict):
            continue
        lines.append(
            f"- {str(stage.get('stage_id', '')).strip()} | "
            f"{str(stage.get('title', '')).strip()} | "
            f"{str(stage.get('summary', '')).strip()}"
        )

    lines.extend(["", "## API Entrypoints", ""])
    for endpoint in list(dict(blueprint.get("entrypoints", {}) or {}).get("api", []) or []):
        if not isinstance(endpoint, dict):
            continue
        lines.append(f"- {str(endpoint.get('path', '')).strip()} | {str(endpoint.get('purpose', '')).strip()}")

    disabled_sources = list(blueprint.get("disabled_sources", []) or [])
    if disabled_sources:
        lines.extend(["", "## Disabled Sources", ""])
        for item in disabled_sources:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {str(item.get('source_id', '')).strip()} | "
                f"{str(item.get('disable_reason', '')).strip()}"
            )

    return "\n".join(lines).strip() + "\n"


def render_daily_report_markdown(report: dict[str, Any]) -> str:
    direction_calls = list(report.get("direction_calls", []) or [])
    stock_calls = list(report.get("stock_calls", []) or [])
    risk_watchpoints = list(report.get("risk_watchpoints", []) or [])
    key_news_items = [
        item
        for item in list(report.get("headline_news", []) or report.get("supporting_items", []) or [])
        if isinstance(item, dict)
    ]

    lines = [
        "# JusticeThemis Daily Analysis Report",
        "",
        f"- Analysis Date: {str(report.get('analysis_date', '')).strip()}",
        f"- Access Tier: {str(report.get('access_tier', '')).strip()}",
        "",
        "## Summary",
        "",
        _render_report_summary(report.get("summary")) or "No summary available.",
        "",
        "## Direction Calls",
        "",
    ]

    if not direction_calls:
        lines.append("- No direction calls.")
    else:
        for call in direction_calls:
            if not isinstance(call, dict):
                continue
            lines.append(
                f"- {str(call.get('direction', '')).strip()} | "
                f"stance={str(call.get('stance', '')).strip()} | "
                f"confidence={str(call.get('confidence', '')).strip()}"
            )
            rationale = str(call.get("rationale", "")).strip()
            if rationale:
                lines.append(f"  rationale: {rationale}")
            evidence_points = [str(item).strip() for item in list(call.get("evidence_points", []) or []) if str(item).strip()]
            if evidence_points:
                lines.append(f"  evidence: {'；'.join(evidence_points[:3])}")

    lines.extend(["", "## Key News", ""])
    if not key_news_items:
        lines.append("- No key news.")
    else:
        for item in key_news_items[:8]:
            source_name = str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
            title = str(item.get("title", "")).strip()
            brief = _render_supporting_item_brief(item)
            lines.append(f"- {source_name} | {title}")
            if brief:
                lines.append(f"  brief: {brief}")

    lines.extend(["", "## Stock Calls", ""])
    if not stock_calls:
        lines.append("- No stock calls.")
    else:
        for call in stock_calls:
            if not isinstance(call, dict):
                continue
            lines.append(
                f"- {str(call.get('ticker', '')).strip()} {str(call.get('name', '')).strip()} | "
                f"{str(call.get('action_label', '')).strip()} | {str(call.get('reason', '')).strip()}"
            )

    lines.extend(["", "## Risk Watchpoints", ""])
    if not risk_watchpoints:
        lines.append("- No risk watchpoints.")
    else:
        lines.extend(f"- {str(item).strip()}" for item in risk_watchpoints if str(item).strip())

    return "\n".join(lines).strip() + "\n"


def _render_report_summary(summary: Any) -> str:
    if isinstance(summary, dict):
        headline = str(summary.get("headline", "")).strip()
        core_view = str(summary.get("core_view", "")).strip()
        confidence = str(summary.get("confidence", "")).strip()
        parts = [part for part in (headline, core_view) if part]
        if confidence:
            parts.append(f"Confidence: {confidence}")
        return "\n".join(parts).strip()
    return str(summary or "").strip()


def _render_supporting_item_brief(item: dict[str, Any]) -> str:
    for field in ("llm_ready_brief", "impact_summary"):
        candidate = str(item.get(field, "")).strip()
        if candidate:
            return candidate
    evidence_points = [str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip()]
    if evidence_points:
        return "；".join(evidence_points[:2])
    return ""
