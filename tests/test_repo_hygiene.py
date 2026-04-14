# -*- coding: utf-8 -*-
"""Tests for repository hygiene and CI baseline artifacts."""

from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gitignore_excludes_local_generated_artifacts() -> None:
    gitignore = REPO_ROOT / ".gitignore"

    assert gitignore.exists()

    content = _read_text(gitignore)
    for expected in (
        ".venv/",
        ".pytest_cache/",
        "__pycache__/",
        "*.egg-info/",
        "data/",
        "output/",
        "*.log",
    ):
        assert expected in content


def test_dockerignore_excludes_generated_local_artifacts_from_build_context() -> None:
    dockerignore = REPO_ROOT / ".dockerignore"

    assert dockerignore.exists()

    content = _read_text(dockerignore)
    for expected in (
        ".venv/",
        ".pytest_cache/",
        "__pycache__/",
        "*.egg-info/",
        "data/",
        "output/",
    ):
        assert expected in content


def test_ci_workflow_runs_deterministic_pytest_baseline_without_optional_secrets() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"

    assert workflow.exists()

    content = _read_text(workflow)
    assert "push:" in content
    assert "pull_request:" in content
    assert "uv sync --dev" in content
    assert "uv run pytest -q" in content

    for forbidden in (
        "IFIND_REFRESH_TOKEN",
        "OVERNIGHT_ADMIN_API_KEY",
        "OVERNIGHT_PREMIUM_API_KEY",
    ):
        assert forbidden not in content


def test_readme_documents_repo_hygiene_boundaries_and_verification_command() -> None:
    readme = _read_text(REPO_ROOT / "README.md")

    assert "## Repository Hygiene" in readme
    assert "Source-owned paths" in readme
    assert "Generated local artifacts" in readme
    assert "`uv run pytest -q`" in readme
    assert ".gitignore" in readme
    assert ".dockerignore" in readme


def test_pyproject_declares_uv_dev_dependency_group_for_ci_baseline() -> None:
    payload = tomllib.loads(_read_text(REPO_ROOT / "pyproject.toml"))

    dev_group = payload["dependency-groups"]["dev"]

    assert "httpx>=0.28.0" in dev_group
    assert "pytest>=8.4.0" in dev_group
