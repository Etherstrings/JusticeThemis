# -*- coding: utf-8 -*-
"""Bucket-aware market provider routing and observation normalization."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote
from typing import Any


YAHOO_PROVIDER_NAME = "Yahoo Finance Chart"
IFIND_PROVIDER_NAME = "iFinD History"
TREASURY_PROVIDER_NAME = "Treasury Yield Curve"
STOOQ_PROVIDER_NAME = "Stooq Quotes"

_DEFAULT_PROVIDER_PRIORITY: tuple[str, ...] = (
    IFIND_PROVIDER_NAME,
    STOOQ_PROVIDER_NAME,
    YAHOO_PROVIDER_NAME,
    TREASURY_PROVIDER_NAME,
)
_BUCKET_PROVIDER_PRIORITY: dict[str, tuple[str, ...]] = {
    "index": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "sector": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "sentiment": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "rates_fx": (TREASURY_PROVIDER_NAME, IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "precious_metals": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "energy": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "industrial_metals": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
    "china_proxy": (IFIND_PROVIDER_NAME, STOOQ_PROVIDER_NAME, YAHOO_PROVIDER_NAME),
}


@dataclass(frozen=True)
class MarketProviderRoute:
    provider_name: str
    provider_symbol: str
    provider_url: str
    chart_url: str
    quote_url: str


def provider_symbol_for(instrument: Any, provider_name: str) -> str:
    normalized_provider = str(provider_name).strip().lower()
    for candidate_provider, provider_symbol in tuple(getattr(instrument, "provider_symbol_overrides", ()) or ()):
        if str(candidate_provider).strip().lower() == normalized_provider and str(provider_symbol).strip():
            return str(provider_symbol).strip()
    return str(getattr(instrument, "symbol", "")).strip()


def provider_applies_to(instrument: Any, provider_name: str) -> bool:
    normalized_provider = str(provider_name).strip().lower()
    if normalized_provider == YAHOO_PROVIDER_NAME.strip().lower():
        return True
    if normalized_provider not in {
        IFIND_PROVIDER_NAME.strip().lower(),
        TREASURY_PROVIDER_NAME.strip().lower(),
        STOOQ_PROVIDER_NAME.strip().lower(),
    }:
        return True
    return any(
        str(candidate_provider).strip().lower() == normalized_provider
        for candidate_provider, _provider_symbol in tuple(getattr(instrument, "provider_symbol_overrides", ()) or ())
    )


def ordered_provider_routes(
    *,
    instrument: Any,
    providers: tuple[Any, ...],
) -> tuple[MarketProviderRoute, ...]:
    bucket = str(getattr(instrument, "bucket", "")).strip()
    preferred_names = _BUCKET_PROVIDER_PRIORITY.get(bucket, _DEFAULT_PROVIDER_PRIORITY)
    providers_by_name = {
        str(provider.name).strip(): provider
        for provider in providers
        if str(getattr(provider, "name", "")).strip()
    }

    ordered_names: list[str] = [name for name in preferred_names if name in providers_by_name]
    for provider in providers:
        name = str(getattr(provider, "name", "")).strip()
        if name and name not in ordered_names:
            ordered_names.append(name)

    routes: list[MarketProviderRoute] = []
    for provider_name in ordered_names:
        provider = providers_by_name.get(provider_name)
        if provider is None or not provider_applies_to(instrument, provider_name):
            continue
        provider_symbol = provider_symbol_for(instrument, provider_name)
        quoted_symbol = quote(provider_symbol, safe="")
        quote_template = str(getattr(provider, "quote_url_template", "") or "").strip()
        routes.append(
            MarketProviderRoute(
                provider_name=provider_name,
                provider_symbol=provider_symbol,
                provider_url=str(getattr(provider, "source_url", "") or "").strip(),
                chart_url=str(getattr(provider, "chart_url_template", "") or "").format(symbol=quoted_symbol),
                quote_url=(
                    quote_template.format(symbol=quoted_symbol)
                    if quote_template
                    else f"{str(getattr(provider, 'source_url', '') or '').rstrip('/')}/quote/{quoted_symbol}"
                ),
            )
        )
    return tuple(routes)


def build_market_observation_payload(
    *,
    capture_run_id: int,
    session_name: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "capture_run_id": int(capture_run_id),
        "analysis_date": str(snapshot.get("analysis_date", "")).strip(),
        "market_date": str(snapshot.get("market_date", "")).strip(),
        "session_name": str(session_name).strip(),
        "symbol": str(snapshot.get("symbol", "")).strip(),
        "display_name": str(snapshot.get("display_name", "")).strip(),
        "provider_name": str(snapshot.get("provider_name", "")).strip(),
        "provider_symbol": str(snapshot.get("provider_symbol", "")).strip(),
        "bucket": str(snapshot.get("bucket", "")).strip(),
        "market_timestamp": str(snapshot.get("market_time", "")).strip() or None,
        "close": snapshot.get("close"),
        "previous_close": snapshot.get("previous_close"),
        "change_value": snapshot.get("change"),
        "change_pct": snapshot.get("change_pct"),
        "currency": str(snapshot.get("currency", "")).strip(),
        "freshness_status": _freshness_status(snapshot),
        "provenance": {
            "provider_url": str(snapshot.get("provider_url", "")).strip(),
            "quote_url": str(snapshot.get("quote_url", "")).strip(),
            "market_time_local": str(snapshot.get("market_time_local", "")).strip(),
            "analysis_time_shanghai": str(snapshot.get("analysis_time_shanghai", "")).strip(),
            "instrument_type": str(snapshot.get("instrument_type", "")).strip(),
            "exchange_name": str(snapshot.get("exchange_name", "")).strip(),
            "exchange_timezone_name": str(snapshot.get("exchange_timezone_name", "")).strip(),
        },
        "is_primary": bool(snapshot.get("is_primary_provider", True)),
        "is_fallback": bool(snapshot.get("is_fallback_provider", False)),
    }


def _freshness_status(snapshot: dict[str, Any]) -> str:
    if str(snapshot.get("market_time", "")).strip() and str(snapshot.get("analysis_date", "")).strip():
        return "fresh"
    return "unknown"
