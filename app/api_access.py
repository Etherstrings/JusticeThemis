# -*- coding: utf-8 -*-
"""Access control and readiness helpers for the API surface."""

from __future__ import annotations

from dataclasses import dataclass
import os
import sqlite3
from typing import Any, Sequence

from fastapi import HTTPException

from app.db import Database
from app.product_identity import PRODUCT_NAME
from app.runtime_config import (
    ENRICHMENT_PROVIDER_ENV_NAMES,
    SEARCH_PROVIDER_ENV_NAMES,
    env_flag_enabled,
    list_existing_env_files,
)
from app.services.search_discovery import SearchDiscoveryService


@dataclass(frozen=True)
class AccessState:
    premium_configured: bool
    admin_configured: bool
    unsafe_admin_mode: bool


def current_access_state() -> AccessState:
    return AccessState(
        premium_configured=bool(str(os.environ.get("OVERNIGHT_PREMIUM_API_KEY", "")).strip()),
        admin_configured=bool(str(os.environ.get("OVERNIGHT_ADMIN_API_KEY", "")).strip()),
        unsafe_admin_mode=env_flag_enabled("OVERNIGHT_ALLOW_UNSAFE_ADMIN"),
    )


def require_premium_access(x_premium_access_key: str | None) -> None:
    expected_key = str(os.environ.get("OVERNIGHT_PREMIUM_API_KEY", "")).strip()
    if not expected_key or x_premium_access_key != expected_key:
        raise HTTPException(status_code=403, detail="Premium access key required")


def require_admin_access(x_admin_access_key: str | None) -> None:
    state = current_access_state()
    if state.unsafe_admin_mode:
        return
    expected_key = str(os.environ.get("OVERNIGHT_ADMIN_API_KEY", "")).strip()
    if not expected_key or x_admin_access_key != expected_key:
        raise HTTPException(status_code=403, detail="Admin access key required")


def build_readiness_report(
    *,
    database: Database,
    registry: Sequence[object],
) -> dict[str, Any]:
    state = current_access_state()
    database_status = _database_status(database)
    search_provider_count = len(SearchDiscoveryService.from_environment().providers)
    enabled_sources = [source for source in registry if bool(getattr(source, "is_enabled", False))]
    disabled_sources = [source for source in registry if not bool(getattr(source, "is_enabled", False))]

    return {
        "status": "ok" if database_status["status"] == "ok" else "fail",
        "service": PRODUCT_NAME,
        "database": database_status,
        "runtime": {
            "env_files": list_existing_env_files(),
        },
        "auth": {
            "premium_configured": state.premium_configured,
            "admin_configured": state.admin_configured,
            "unsafe_admin_mode": state.unsafe_admin_mode,
        },
        "features": {
            "market_snapshot": {
                "available": bool(str(os.environ.get("IFIND_REFRESH_TOKEN", "")).strip())
                or str(os.environ.get("POLYMARKET_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"},
                "ifind_configured": bool(str(os.environ.get("IFIND_REFRESH_TOKEN", "")).strip()),
                "polymarket_enabled": str(os.environ.get("POLYMARKET_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"},
                "polymarket_signal_configured": bool(str(os.environ.get("POLYMARKET_SIGNAL_CONFIG_JSON", "")).strip()),
                "kalshi_enabled": str(os.environ.get("KALSHI_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"},
                "kalshi_signal_configured": bool(str(os.environ.get("KALSHI_SIGNAL_CONFIG_JSON", "")).strip()),
                "cme_fedwatch_enabled": str(os.environ.get("CME_FEDWATCH_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"},
                "cftc_enabled": str(os.environ.get("CFTC_ENABLED", "true")).strip().lower() not in {"0", "false", "no", "off"},
                "cftc_signal_configured": bool(str(os.environ.get("CFTC_SIGNAL_CONFIG_JSON", "")).strip()),
                "configured_env_names": [
                    name
                    for name in (
                        "IFIND_REFRESH_TOKEN",
                        "POLYMARKET_ENABLED",
                        "POLYMARKET_SIGNAL_CONFIG_JSON",
                        "KALSHI_ENABLED",
                        "KALSHI_SIGNAL_CONFIG_JSON",
                        "CME_FEDWATCH_ENABLED",
                        "CFTC_ENABLED",
                        "CFTC_SIGNAL_CONFIG_JSON",
                    )
                    if str(os.environ.get(name, "")).strip()
                ],
            },
            "search_discovery": {
                "available": search_provider_count > 0,
                "provider_count": search_provider_count,
                "configured_env_names": [
                    name
                    for name in SEARCH_PROVIDER_ENV_NAMES
                    if str(os.environ.get(name, "")).strip()
                ],
            },
            "ticker_enrichment": {
                "available": any(str(os.environ.get(name, "")).strip() for name in ENRICHMENT_PROVIDER_ENV_NAMES),
                "provider_count": sum(1 for name in ENRICHMENT_PROVIDER_ENV_NAMES if str(os.environ.get(name, "")).strip()),
                "configured_env_names": [
                    name
                    for name in ENRICHMENT_PROVIDER_ENV_NAMES
                    if str(os.environ.get(name, "")).strip()
                ],
            },
        },
        "source_registry": {
            "enabled_source_count": len(enabled_sources),
            "disabled_source_count": len(disabled_sources),
            "mission_critical_source_count": sum(
                1 for source in enabled_sources if bool(getattr(source, "is_mission_critical", False))
            ),
        },
    }


def _database_status(database: Database) -> dict[str, Any]:
    try:
        with database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "path": str(database.path),
            "error": str(exc),
        }
    return {
        "status": "ok",
        "path": str(database.path),
    }
