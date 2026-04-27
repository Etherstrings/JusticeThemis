# -*- coding: utf-8 -*-
"""Tests for offline exported artifact freshness inspection."""

from __future__ import annotations

import json
from pathlib import Path

from app.artifact_inspection import main
from app.services.artifact_inspection import (
    inspect_local_data_availability,
    inspect_result_first_artifact_freshness,
    reexport_result_first_artifacts_from_db,
)


def test_inspect_result_first_artifact_freshness_reports_missing_files(tmp_path: Path) -> None:
    result = inspect_result_first_artifact_freshness(tmp_path)

    assert result["status"] == "missing"
    assert len(result["missing_paths"]) == 2


def test_inspect_result_first_artifact_freshness_reports_stale_payloads(tmp_path: Path) -> None:
    group_payload = {
        "report_type": "group_report",
        "ignored_heat": {"title": "昨晚市场没认的消息", "entries": []},
    }
    desk_payload = {
        "report_type": "desk_report",
        "result_data": {"buckets": [{"bucket_label": "中国代理", "rows": []}]},
    }
    (tmp_path / "group-report-premium.json").write_text(json.dumps(group_payload, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "desk-report-premium.json").write_text(json.dumps(desk_payload, ensure_ascii=False), encoding="utf-8")

    result = inspect_result_first_artifact_freshness(tmp_path)

    assert result["status"] == "stale"
    assert result["checks"] == {
        "group_ignored_heat_matrix": False,
        "desk_continuation_check": False,
        "desk_china_texture": False,
    }


def test_artifact_inspection_cli_prints_json_summary(tmp_path: Path, capsys) -> None:
    exit_code = main(["--output-dir", str(tmp_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "missing"


def test_inspect_local_data_availability_reports_missing_db(tmp_path: Path) -> None:
    result = inspect_local_data_availability(tmp_path / "missing.db")

    assert result["status"] == "missing"
    assert result["latest_daily_analysis"] == []


def test_artifact_inspection_cli_supports_db_availability_mode(tmp_path: Path, capsys) -> None:
    exit_code = main(["--db-path", str(tmp_path / "missing.db")])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "missing"


def test_reexport_result_first_artifacts_from_db_reports_missing_db(tmp_path: Path) -> None:
    result = reexport_result_first_artifacts_from_db(
        db_path=tmp_path / "missing.db",
        output_dir=tmp_path / "artifacts",
        analysis_date="2026-04-24",
    )

    assert result["status"] == "missing"
    assert result["written_files"] == []


def test_artifact_inspection_cli_can_reexport_from_live_run_db(capsys) -> None:
    db_path = Path("data/live-runs/readhub-2026-04-23.db")
    if not db_path.exists():
        return

    tmp_output_dir = Path("output/test-artifact-reexport")
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--output-dir",
            str(tmp_output_dir),
            "--analysis-date",
            "2026-04-24",
            "--reexport-from-db",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["analysis_date"] == "2026-04-24"
    assert payload["freshness"]["status"] == "fresh"
    assert (tmp_output_dir / "group-report-premium.json").exists()
