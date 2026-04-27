# -*- coding: utf-8 -*-
"""Tests for the standalone frontend workspace contract."""

from __future__ import annotations

from pathlib import Path
import json


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"


def test_frontend_workspace_manifest_and_scripts_exist() -> None:
    package_path = FRONTEND_ROOT / "package.json"

    assert package_path.exists()

    package = json.loads(package_path.read_text(encoding="utf-8"))

    assert package["name"] == "justice-themis-frontend"
    assert package["private"] is True
    assert package["scripts"]["dev"] == "vite"
    assert package["scripts"]["build"] == "tsc -b && vite build"
    assert package["scripts"]["preview"] == "vite preview"
    assert "react" in package["dependencies"]
    assert "vite" in package["devDependencies"]
    assert "typescript" in package["devDependencies"]


def test_frontend_workspace_includes_env_example_and_app_shell() -> None:
    env_example = FRONTEND_ROOT / ".env.example"
    main_entry = FRONTEND_ROOT / "src" / "main.tsx"
    app_shell = FRONTEND_ROOT / "src" / "App.tsx"

    assert env_example.exists()
    assert "VITE_API_BASE_URL=http://127.0.0.1:8000" in env_example.read_text(encoding="utf-8")

    assert main_entry.exists()
    assert app_shell.exists()

    app_text = app_shell.read_text(encoding="utf-8")
    assert "Dashboard" in app_text
    assert "News" in app_text
    assert "Analysis" in app_text


def test_frontend_workspace_uses_centralized_api_and_vite_proxy() -> None:
    client_path = FRONTEND_ROOT / "src" / "lib" / "api.ts"
    vite_config_path = FRONTEND_ROOT / "vite.config.ts"

    assert client_path.exists()
    assert vite_config_path.exists()

    client_text = client_path.read_text(encoding="utf-8")
    vite_text = vite_config_path.read_text(encoding="utf-8")

    assert "VITE_API_BASE_URL" in client_text
    assert "X-Admin-Access-Key" in client_text
    assert "X-Premium-Access-Key" in client_text
    assert "fetchHealthz" in client_text
    assert "fetchReadyz" in client_text
    assert "target: 'http://127.0.0.1:8000'" in vite_text or 'target: "http://127.0.0.1:8000"' in vite_text


def test_frontend_workspace_exposes_complete_dashboard_news_and_analysis_sections() -> None:
    app_text = (FRONTEND_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")

    for expected in (
        "Health + Readiness",
        "Operator Evidence",
        "Coverage Matrix",
        "Direction Calls",
        "Headline News",
        "Stock Calls",
        "Narrative Views",
    ):
        assert expected in app_text


def test_gitignore_excludes_frontend_node_modules() -> None:
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "frontend/node_modules/" in gitignore_text
