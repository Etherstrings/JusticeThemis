# -*- coding: utf-8 -*-
"""Tests for release-boundary and first-run readiness documentation."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_root_readmes_publish_release_verdict_and_user_cohorts() -> None:
    english = _read_text(REPO_ROOT / "README.md")
    chinese = _read_text(REPO_ROOT / "README.zh.md")

    assert "Release Verdict" in english
    assert "technical self-hosted user" in english
    assert "general end user" in english
    assert "BLS official pages currently return 403" in english

    assert "发布结论" in chinese
    assert "技术型自托管用户" in chinese
    assert "泛用户" in chinese
    assert "BLS 官方页面当前会返回 403" in chinese


def test_release_boundary_verdict_doc_records_first_run_gate_and_failures() -> None:
    verdict_doc = _read_text(
        REPO_ROOT / "docs" / "technical" / "2026-04-16-user-release-boundary-and-first-run-verdict.md"
    )

    assert "2026-04-16" in verdict_doc
    assert "Supported user cohort" in verdict_doc
    assert "Unsupported user cohort" in verdict_doc
    assert "uv run pytest tests/test_market_snapshot.py tests/test_daily_analysis.py tests/test_pipeline_ops.py tests/test_pipeline_runner.py tests/test_backend_live_run_evidence.py tests/test_report_preview.py" in verdict_doc
    assert ".venv/bin/python -m app.backend_live_run_evidence --analysis-date 2026-04-16" in verdict_doc
    assert "Degraded-but-acceptable first-run states" in verdict_doc
    assert "Primary failure modes" in verdict_doc
    assert "BLS official pages currently return 403" in verdict_doc


def test_root_readmes_document_standalone_frontend_preview_path() -> None:
    english = _read_text(REPO_ROOT / "README.md")
    chinese = _read_text(REPO_ROOT / "README.zh.md")

    assert "pnpm install --dir frontend" in english
    assert "pnpm --dir frontend dev" in english
    assert "VITE_API_BASE_URL" in english
    assert "built-in `/ui` operator panel remains a compatibility surface" in english

    assert "pnpm install --dir frontend" in chinese
    assert "pnpm --dir frontend dev" in chinese
    assert "VITE_API_BASE_URL" in chinese
    assert "内置 `/ui` operator 面板保留为兼容性 surface" in chinese
