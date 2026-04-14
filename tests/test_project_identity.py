# -*- coding: utf-8 -*-
"""Tests for package metadata and primary operator documentation identity."""

from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_uses_justice_themis_metadata_and_script_aliases() -> None:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    project = payload["project"]
    scripts = project["scripts"]

    assert project["name"] == "justice-themis"
    assert scripts["justice-themis-pipeline"] == "app.pipeline:main"
    assert scripts["justice-themis-launchd-template"] == "app.schedule_template:main"
    assert scripts["overnight-news-pipeline"] == "app.pipeline:main"


def test_readme_presents_justice_themis_and_legacy_runtime_mapping() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.startswith("# JusticeThemis")
    assert "Legacy compatibility mapping" in readme
    assert "`OVERNIGHT_*`" in readme
