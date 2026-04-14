# -*- coding: utf-8 -*-
"""Tests for remote repository convergence audit and bootstrap guidance."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_documents_canonical_upstream_and_sync_prerequisites() -> None:
    readme = _read_text(REPO_ROOT / "README.md")

    assert "## Canonical Upstream And Sync" in readme
    assert "Etherstrings/JusticeThemis" in readme
    assert "isolated Git-backed convergence workspace" in readme
    assert "post-sync verification contract" in readme


def test_repository_convergence_audit_captures_remote_local_baselines_and_mapping() -> None:
    audit_path = REPO_ROOT / "docs" / "technical" / "2026-04-14-remote-repository-convergence.md"

    assert audit_path.exists()

    content = _read_text(audit_path)
    for expected in (
        "## Remote Baseline",
        "## Local Baseline",
        "## Structure Mapping",
        "## Blocking Risks",
        "## Readiness Gates",
    ):
        assert expected in content

    assert "f3362f92984c3035d79240b546f2780a64801e14" in content
    assert "not a git repository" in content


def test_convergence_review_summary_documents_branch_and_merge_path() -> None:
    summary_path = REPO_ROOT / "docs" / "technical" / "2026-04-14-convergence-review-summary.md"

    assert summary_path.exists()

    content = _read_text(summary_path)
    assert "codex/remote-repo-convergence" in content
    assert "merge-ready" in content
    assert "uv run pytest -q" in content
