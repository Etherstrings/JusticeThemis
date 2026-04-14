# -*- coding: utf-8 -*-
"""Tests for standalone runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

from app.runtime_config import DEFAULT_ENV_FILE_PATHS, PROJECT_ROOT, load_runtime_environment


def test_default_env_file_paths_are_project_local() -> None:
    assert DEFAULT_ENV_FILE_PATHS == (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / ".env.local",
    )
    assert all("JusticePlutus" not in str(path) for path in DEFAULT_ENV_FILE_PATHS)


def test_load_runtime_environment_prefers_process_env_over_files(tmp_path: Path, monkeypatch) -> None:
    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text("IFIND_REFRESH_TOKEN=file-base\nSERPAPI_API_KEYS=serp-base\n", encoding="utf-8")
    local_env.write_text("IFIND_REFRESH_TOKEN=file-local\nSERPAPI_API_KEYS=serp-local\n", encoding="utf-8")
    monkeypatch.setenv("IFIND_REFRESH_TOKEN", "process-token")
    monkeypatch.delenv("SERPAPI_API_KEYS", raising=False)

    loaded = load_runtime_environment(
        env_file_paths=(base_env, local_env),
        env_names=("IFIND_REFRESH_TOKEN", "SERPAPI_API_KEYS"),
    )

    assert loaded == {"SERPAPI_API_KEYS": "serp-local"}
    assert os.environ["IFIND_REFRESH_TOKEN"] == "process-token"
    assert os.environ["SERPAPI_API_KEYS"] == "serp-local"


def test_load_runtime_environment_uses_default_project_env_paths_when_no_paths_are_passed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    env_file.write_text("OVERNIGHT_PREMIUM_API_KEY=base-premium\n", encoding="utf-8")
    local_env.write_text("OVERNIGHT_PREMIUM_API_KEY=local-premium\n", encoding="utf-8")
    monkeypatch.setattr("app.runtime_config.DEFAULT_ENV_FILE_PATHS", (env_file, local_env))
    monkeypatch.delenv("OVERNIGHT_PREMIUM_API_KEY", raising=False)

    loaded = load_runtime_environment(env_names=("OVERNIGHT_PREMIUM_API_KEY",))

    assert loaded == {"OVERNIGHT_PREMIUM_API_KEY": "local-premium"}
    assert os.environ["OVERNIGHT_PREMIUM_API_KEY"] == "local-premium"
