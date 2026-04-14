# -*- coding: utf-8 -*-
"""Tests for bilingual README parity and publication guidance."""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parent.parent
PARITY_PATTERN = re.compile(r"<!--\s*readme-parity:([a-z0-9-]+)\s*-->")
EXPECTED_PARITY_IDS = [
    "what-it-does",
    "runtime-contract",
    "legacy-compatibility-mapping",
    "environment-variables",
    "current-output-layers",
    "local-startup",
    "canonical-upstream-and-sync",
    "repository-hygiene",
    "source-owned-paths",
    "generated-local-artifacts",
    "verification-baseline",
    "auth-surfaces",
    "smoke-check",
    "container-startup",
    "rollback-notes",
    "disabled-source-invariants",
    "self-hosted-acceptance-criteria",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parity_ids(path: Path) -> list[str]:
    return PARITY_PATTERN.findall(_read_text(path))


def test_root_readme_language_pair_exposes_links_and_role_labels() -> None:
    english = _read_text(REPO_ROOT / "README.md")
    chinese_path = REPO_ROOT / "README.zh.md"

    assert chinese_path.exists()

    chinese = _read_text(chinese_path)
    assert english.startswith("# JusticeThemis")
    assert "[中文](README.zh.md)" in english
    assert "default bootstrap entrypoint" in english

    assert chinese.startswith("# JusticeThemis")
    assert "[English](README.md)" in chinese
    assert "中文 bootstrap companion" in chinese


def test_bilingual_readme_documents_share_parity_markers_and_bootstrap_invariants() -> None:
    english_path = REPO_ROOT / "README.md"
    chinese_path = REPO_ROOT / "README.zh.md"

    assert _parity_ids(english_path) == EXPECTED_PARITY_IDS
    assert _parity_ids(chinese_path) == EXPECTED_PARITY_IDS

    english = _read_text(english_path)
    chinese = _read_text(chinese_path)

    for shared_expected in (
        "JusticeThemis",
        "Etherstrings/JusticeThemis",
        "uv run pytest -q",
        "uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
    ):
        assert shared_expected in english
        assert shared_expected in chinese

    assert "isolated Git-backed convergence workspace" in english
    assert "独立的 Git-backed convergence workspace" in chinese


def test_convergence_docs_require_the_readme_pair_for_publication() -> None:
    audit = _read_text(
        REPO_ROOT / "docs" / "technical" / "2026-04-14-remote-repository-convergence.md"
    )
    summary = _read_text(
        REPO_ROOT / "docs" / "technical" / "2026-04-14-convergence-review-summary.md"
    )

    assert "README.zh.md" in audit
    assert "README.md" in audit
    assert "README.zh.md" in summary
    assert "README.md" in summary
    assert "both root README files" in summary
