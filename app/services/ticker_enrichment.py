# -*- coding: utf-8 -*-
"""Optional ticker enrichment for premium and regime-driven contexts."""

from __future__ import annotations

import os
import re
from typing import Any, Protocol

import requests

from app.repository import OvernightRepository


class TickerEnrichmentProvider(Protocol):
    name: str

    def is_configured(self) -> bool:
        """Return whether the provider has enough configuration to run."""

    def supports_symbol(self, symbol: str) -> bool:
        """Return whether the provider can enrich the requested symbol."""

    def fetch_symbol_context(self, *, symbol: str) -> dict[str, Any]:
        """Fetch one symbol-level context payload."""


class AlphaVantageTickerEnrichmentProvider:
    name = "Alpha Vantage"
    ENV_NAMES = ("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY")
    BASE_URL = "https://www.alphavantage.co/query"
    _SUPPORTED_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")
    _DISALLOWED_SUFFIXES = (".SH", ".SZ", ".HK")

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.sessions.Session | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.session = session or requests.Session()
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def is_configured(self) -> bool:
        return bool(self._resolved_api_key())

    def supports_symbol(self, symbol: str) -> bool:
        normalized = str(symbol or "").strip().upper()
        if not normalized or normalized.startswith("^") or "=" in normalized:
            return False
        if normalized.endswith(self._DISALLOWED_SUFFIXES):
            return False
        return bool(self._SUPPORTED_PATTERN.fullmatch(normalized))

    def fetch_symbol_context(self, *, symbol: str) -> dict[str, Any]:
        api_key = self._resolved_api_key()
        if not api_key:
            raise RuntimeError("Alpha Vantage API key is not configured")
        normalized = str(symbol or "").strip().upper()
        quote = self._query(function="GLOBAL_QUOTE", symbol=normalized, api_key=api_key)
        overview = self._query(function="OVERVIEW", symbol=normalized, api_key=api_key)
        return {
            "provider": self.name,
            "symbol": normalized,
            "quote": quote,
            "profile": overview,
        }

    def _query(self, *, function: str, symbol: str, api_key: str) -> dict[str, Any]:
        response = self.session.get(
            self.BASE_URL,
            params={"function": function, "symbol": symbol, "apikey": api_key},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = dict(response.json() or {})
        if payload.get("Error Message"):
            raise RuntimeError(str(payload["Error Message"]))
        if payload.get("Information"):
            raise RuntimeError(str(payload["Information"]))
        if payload.get("Note"):
            raise RuntimeError(str(payload["Note"]))
        return payload

    def _resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        for env_name in self.ENV_NAMES:
            candidate = str(os.environ.get(env_name, "")).strip()
            if candidate:
                return candidate
        return ""


def build_default_ticker_enrichment_providers() -> list[TickerEnrichmentProvider]:
    return [AlphaVantageTickerEnrichmentProvider()]


class TickerEnrichmentService:
    def __init__(
        self,
        *,
        repo: OvernightRepository,
        providers: list[TickerEnrichmentProvider] | None = None,
    ) -> None:
        self.repo = repo
        self.providers = list(providers or build_default_ticker_enrichment_providers())

    def collect(
        self,
        *,
        analysis_date: str,
        session_name: str,
        access_tier: str,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        stock_calls: list[dict[str, Any]],
        explicit_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        plan = self.build_plan(
            access_tier=access_tier,
            mainlines=mainlines,
            market_regimes=market_regimes,
            stock_calls=stock_calls,
            explicit_symbols=explicit_symbols,
        )
        symbols = list(plan.get("symbols", []) or [])
        if not symbols:
            return {
                "status": "skipped",
                "trigger_reason": str(plan.get("trigger_reason", "")).strip(),
                "records": [],
                "attempted_symbol_count": 0,
                "error_count": 0,
            }

        records: list[dict[str, Any]] = []
        error_count = 0
        trigger_reason = str(plan.get("trigger_reason", "")).strip() or "ticker_enrichment"
        for symbol in symbols:
            provider = self._provider_for_symbol(symbol)
            if provider is None:
                continue
            try:
                payload = provider.fetch_symbol_context(symbol=symbol)
                record = self.repo.create_ticker_enrichment_record(
                    analysis_date=analysis_date,
                    session_name=session_name,
                    symbol=symbol,
                    provider_name=provider.name,
                    record_type="symbol_context",
                    trigger_reason=trigger_reason,
                    status="ready",
                    payload=payload,
                )
            except Exception as exc:
                error_count += 1
                record = self.repo.create_ticker_enrichment_record(
                    analysis_date=analysis_date,
                    session_name=session_name,
                    symbol=symbol,
                    provider_name=provider.name,
                    record_type="symbol_context",
                    trigger_reason=trigger_reason,
                    status="error",
                    payload={"error": str(exc)},
                )
            records.append(record)

        if not records:
            status = "skipped"
        elif error_count > 0:
            status = "degraded"
        else:
            status = "ok"
        return {
            "status": status,
            "trigger_reason": trigger_reason,
            "records": records,
            "attempted_symbol_count": len(records),
            "error_count": error_count,
        }

    def build_plan(
        self,
        *,
        access_tier: str,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        stock_calls: list[dict[str, Any]],
        explicit_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_explicit = [
            str(symbol).strip().upper()
            for symbol in list(explicit_symbols or [])
            if str(symbol).strip()
        ]
        trigger_reason = ""
        candidate_symbols: list[str] = []

        if normalized_explicit:
            trigger_reason = "explicit_symbol_request"
            candidate_symbols.extend(normalized_explicit)
        elif str(access_tier or "").strip() == "premium":
            trigger_reason = "premium_market_context"
            candidate_symbols.extend(self._mainline_symbols(mainlines))
            candidate_symbols.extend(self._regime_symbols(market_regimes))
            candidate_symbols.extend(
                str(call.get("ticker", "")).strip().upper()
                for call in list(stock_calls or [])
                if str(call.get("ticker", "")).strip()
            )
        elif mainlines:
            trigger_reason = "mainline_market_context"
            candidate_symbols.extend(self._mainline_symbols(mainlines))
        elif market_regimes:
            trigger_reason = "regime_market_context"
            candidate_symbols.extend(self._regime_symbols(market_regimes))

        supported_symbols = [
            symbol
            for symbol in dict.fromkeys(candidate_symbols)
            if self._provider_for_symbol(symbol) is not None
        ]
        return {
            "trigger_reason": trigger_reason,
            "symbols": supported_symbols[:6],
        }

    def _mainline_symbols(self, mainlines: list[dict[str, Any]]) -> list[str]:
        symbols: list[str] = []
        for mainline in list(mainlines or []):
            for symbol in list(mainline.get("affected_assets", []) or []):
                candidate = str(symbol).strip().upper()
                if candidate:
                    symbols.append(candidate)
        return symbols

    def _regime_symbols(self, market_regimes: list[dict[str, Any]]) -> list[str]:
        symbols: list[str] = []
        for regime in list(market_regimes or []):
            for symbol in list(regime.get("driving_symbols", []) or []):
                candidate = str(symbol).strip().upper()
                if candidate:
                    symbols.append(candidate)
        return symbols

    def _provider_for_symbol(self, symbol: str) -> TickerEnrichmentProvider | None:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return None
        for provider in self.providers:
            if provider.is_configured() and provider.supports_symbol(normalized):
                return provider
        return None
