# -*- coding: utf-8 -*-
"""Standalone runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
)
SEARCH_PROVIDER_ENV_NAMES: tuple[str, ...] = (
    "BOCHA_API_KEYS",
    "BOCHA_API_KEY",
    "TAVILY_API_KEYS",
    "TAVILY_API_KEY",
    "SERPAPI_API_KEYS",
    "SERPAPI_API_KEY",
    "BRAVE_API_KEYS",
    "BRAVE_API_KEY",
    "AIHUBMIX_API_KEYS",
    "AIHUBMIX_API_KEY",
    "AIHUBMIX_BASE_URL",
    "AIHUBMIX_SEARCH_MODEL",
)
MARKET_PROVIDER_ENV_NAMES: tuple[str, ...] = (
    "IFIND_REFRESH_TOKEN",
    "POLYMARKET_ENABLED",
    "POLYMARKET_SIGNAL_CONFIG_JSON",
    "KALSHI_ENABLED",
    "KALSHI_SIGNAL_CONFIG_JSON",
    "CME_FEDWATCH_ENABLED",
    "CFTC_ENABLED",
    "CFTC_SIGNAL_CONFIG_JSON",
)
ENRICHMENT_PROVIDER_ENV_NAMES: tuple[str, ...] = (
    "ALPHA_VANTAGE_API_KEY",
    "ALPHAVANTAGE_API_KEY",
)
AUTH_ENV_NAMES: tuple[str, ...] = (
    "OVERNIGHT_PREMIUM_API_KEY",
    "OVERNIGHT_ADMIN_API_KEY",
    "OVERNIGHT_ALLOW_UNSAFE_ADMIN",
    "OVERNIGHT_FRONTEND_ALLOWED_ORIGINS",
)
RUNTIME_ENV_NAMES: tuple[str, ...] = (
    SEARCH_PROVIDER_ENV_NAMES
    + MARKET_PROVIDER_ENV_NAMES
    + ENRICHMENT_PROVIDER_ENV_NAMES
    + AUTH_ENV_NAMES
)


def load_env_values_from_files(
    *,
    env_file_paths: Sequence[Path | str],
    env_names: Sequence[str],
) -> dict[str, str]:
    loaded: dict[str, str] = {}
    wanted_names = {str(name).strip() for name in env_names if str(name).strip()}
    for candidate_path in env_file_paths:
        path = Path(candidate_path).expanduser()
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            if key not in wanted_names or not value:
                continue
            loaded[key] = value
    return loaded


def load_runtime_environment(
    *,
    env_file_paths: Sequence[Path | str] | None = None,
    env_names: Sequence[str] = RUNTIME_ENV_NAMES,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    target_environ = environ or os.environ
    loaded = load_env_values_from_files(
        env_file_paths=env_file_paths or DEFAULT_ENV_FILE_PATHS,
        env_names=env_names,
    )
    applied: dict[str, str] = {}
    for key, value in loaded.items():
        if str(target_environ.get(key, "")).strip():
            continue
        target_environ[key] = value
        applied[key] = value
    return applied


def list_existing_env_files(env_file_paths: Sequence[Path | str] | None = None) -> list[str]:
    return [
        str(Path(candidate_path).expanduser())
        for candidate_path in (env_file_paths or DEFAULT_ENV_FILE_PATHS)
        if Path(candidate_path).expanduser().is_file()
    ]


def env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def list_frontend_allowed_origins() -> list[str]:
    defaults = [
        origin
        for port in range(5173, 5181)
        for origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
    ]
    configured = [
        origin.strip()
        for origin in str(os.environ.get("OVERNIGHT_FRONTEND_ALLOWED_ORIGINS", "")).split(",")
        if origin.strip()
    ]
    ordered: list[str] = []
    for origin in [*defaults, *configured]:
        if origin not in ordered:
            ordered.append(origin)
    return ordered


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = str(line).strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = _strip_inline_comment(raw_value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return key, value.strip()


def _strip_inline_comment(raw_value: str) -> str:
    in_single = False
    in_double = False
    output: list[str] = []
    previous = ""
    for character in raw_value:
        if character == "'" and not in_double:
            in_single = not in_single
        elif character == '"' and not in_single:
            in_double = not in_double
        elif character == "#" and not in_single and not in_double and previous.isspace():
            break
        output.append(character)
        previous = character
    return "".join(output)
