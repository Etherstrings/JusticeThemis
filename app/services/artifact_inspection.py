# -*- coding: utf-8 -*-
"""Offline helpers for inspecting or re-exporting result-first artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sqlite3

from app.pipeline import build_runtime_services
from app.services.pipeline_markdown import render_desk_report_markdown, render_group_report_markdown


def inspect_result_first_artifact_freshness(output_dir: Path) -> dict[str, Any]:
    group_path = output_dir / "group-report-premium.json"
    desk_path = output_dir / "desk-report-premium.json"

    if not group_path.exists() or not desk_path.exists():
        return {
            "status": "missing",
            "missing_paths": [str(path) for path in (group_path, desk_path) if not path.exists()],
            "checks": {},
        }

    group_payload = json.loads(group_path.read_text(encoding="utf-8"))
    desk_payload = json.loads(desk_path.read_text(encoding="utf-8"))
    checks = {
        "group_ignored_heat_matrix": bool(
            isinstance(group_payload.get("ignored_heat", {}), dict)
            and "message_misses" in group_payload.get("ignored_heat", {})
            and "asset_misses" in group_payload.get("ignored_heat", {})
        ),
        "desk_continuation_check": bool(desk_payload.get("continuation_check")),
        "desk_china_texture": bool(
            next(
                (
                    bucket.get("texture")
                    for bucket in desk_payload.get("result_data", {}).get("buckets", [])
                    if bucket.get("bucket_label") == "国内资产映射"
                ),
                {},
            )
        ),
    }
    return {
        "status": "fresh" if all(checks.values()) else "stale",
        "missing_paths": [],
        "checks": checks,
    }


def inspect_local_data_availability(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "status": "missing",
            "db_path": str(db_path),
            "latest_daily_analysis": [],
            "latest_market_snapshots": [],
            "latest_market_capture_runs": [],
        }

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    def _fetch(query: str) -> list[dict[str, Any]]:
        cur.execute(query)
        columns = [item[0] for item in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    payload = {
        "status": "ok",
        "db_path": str(db_path),
        "latest_daily_analysis": _fetch(
            "SELECT analysis_date, access_tier, version FROM overnight_daily_analysis_reports ORDER BY analysis_date DESC, access_tier LIMIT 10"
        ),
        "latest_market_snapshots": _fetch(
            "SELECT analysis_date, market_date, session_name FROM overnight_market_snapshots ORDER BY analysis_date DESC LIMIT 10"
        ),
        "latest_market_capture_runs": _fetch(
            "SELECT analysis_date, market_date, session_name, status FROM overnight_market_capture_runs ORDER BY analysis_date DESC LIMIT 10"
        ),
    }
    conn.close()
    return payload


def reexport_result_first_artifacts_from_db(
    *,
    db_path: Path,
    output_dir: Path,
    analysis_date: str,
    access_tiers: tuple[str, ...] = ("free", "premium"),
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "status": "missing",
            "db_path": str(db_path),
            "output_dir": str(output_dir),
            "analysis_date": str(analysis_date or "").strip(),
            "written_files": [],
            "reports": [],
        }

    runtime = build_runtime_services(db_path=db_path)
    service = runtime.daily_analysis_service
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    reports: list[dict[str, Any]] = []
    resolved_analysis_date = str(analysis_date or "").strip()

    for access_tier in access_tiers:
        report = service.get_daily_report(analysis_date=resolved_analysis_date, access_tier=access_tier)
        if not isinstance(report, dict) or not report:
            reports.append({"access_tier": access_tier, "status": "missing"})
            continue
        group_report = dict(report.get("group_report", {}) or {})
        desk_report = dict(report.get("desk_report", {}) or {})
        tier_files = {
            f"group-report-{access_tier}.json": group_report,
            f"desk-report-{access_tier}.json": desk_report,
            f"group-report-{access_tier}.md": render_group_report_markdown(report),
            f"desk-report-{access_tier}.md": render_desk_report_markdown(report),
        }
        for filename, payload in tier_files.items():
            path = output_dir / filename
            if filename.endswith(".json"):
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                path.write_text(str(payload), encoding="utf-8")
            written_files.append(str(path))
        reports.append(
            {
                "access_tier": access_tier,
                "status": "ok",
                "analysis_date": str(report.get("analysis_date", "")).strip(),
                "has_group_report": bool(group_report),
                "has_desk_report": bool(desk_report),
            }
        )
        if not resolved_analysis_date:
            resolved_analysis_date = str(report.get("analysis_date", "")).strip()

    return {
        "status": "ok" if any(item.get("status") == "ok" for item in reports) else "missing",
        "db_path": str(db_path),
        "output_dir": str(output_dir),
        "analysis_date": resolved_analysis_date,
        "written_files": written_files,
        "reports": reports,
        "freshness": inspect_result_first_artifact_freshness(output_dir),
    }
