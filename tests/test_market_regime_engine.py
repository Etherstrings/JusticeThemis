# -*- coding: utf-8 -*-
"""Tests for deterministic overnight market regime evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from app.db import Database
from app.repository import OvernightRepository
from app.services.market_snapshot import (
    MarketDataProviderDefinition,
    MarketInstrumentDefinition,
    UsMarketSnapshotService,
)


def _observation(
    *,
    symbol: str,
    bucket: str,
    change_pct: float,
    freshness_status: str = "fresh",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "bucket": bucket,
        "display_name": symbol,
        "provider_name": "test",
        "provider_symbol": symbol,
        "market_timestamp": "2026-04-09T20:00:00+00:00",
        "analysis_date": "2026-04-10",
        "market_date": "2026-04-09",
        "close": 100.0,
        "previous_close": 99.0,
        "change_value": 1.0,
        "change_pct": change_pct,
        "currency": "USD",
        "freshness_status": freshness_status,
        "provenance": {},
        "is_primary": True,
        "is_fallback": False,
    }


def _chart_payload(
    *,
    symbol: str,
    name: str,
    first_close: float,
    last_close: float,
    market_time: int,
    instrument_type: str,
    exchange_name: str = "SNP",
    exchange_timezone_name: str = "America/New_York",
    volume: int = 1000000,
) -> str:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "symbol": symbol,
                        "exchangeName": exchange_name,
                        "fullExchangeName": exchange_name,
                        "instrumentType": instrument_type,
                        "regularMarketTime": market_time,
                        "exchangeTimezoneName": exchange_timezone_name,
                        "regularMarketPrice": last_close,
                        "regularMarketDayHigh": max(first_close, last_close) + 1.0,
                        "regularMarketDayLow": min(first_close, last_close) - 1.0,
                        "regularMarketVolume": volume,
                        "longName": name,
                        "shortName": name,
                        "chartPreviousClose": first_close,
                        "priceHint": 2,
                    },
                    "timestamp": [market_time - 86400, market_time],
                    "indicators": {
                        "quote": [
                            {
                                "open": [first_close, first_close],
                                "close": [first_close, last_close],
                                "high": [first_close + 0.8, max(first_close, last_close) + 1.0],
                                "low": [first_close - 0.8, min(first_close, last_close) - 1.0],
                                "volume": [volume, volume],
                            }
                        ],
                    },
                }
            ],
            "error": None,
        }
    }
    return json.dumps(payload)


class RoutingMarketClient:
    def __init__(self, routes: dict[str, str]):
        self.routes = routes

    def fetch(self, url: str) -> str:
        for fragment, payload in self.routes.items():
            if fragment in url:
                return payload
        raise AssertionError(f"Unexpected market url: {url}")


def test_market_regime_engine_triggers_technology_and_china_proxy_strength() -> None:
    from app.services.market_regime_engine import MarketRegimeEngine

    report = MarketRegimeEngine().evaluate(
        analysis_date="2026-04-10",
        observations=[
            _observation(symbol="SOXX", bucket="sector", change_pct=4.8),
            _observation(symbol="XLK", bucket="sector", change_pct=2.3),
            _observation(symbol="^IXIC", bucket="index", change_pct=1.9),
            _observation(symbol="^VIX", bucket="sentiment", change_pct=-7.2),
            _observation(symbol="^TNX", bucket="rates_fx", change_pct=-1.6),
            _observation(symbol="KWEB", bucket="china_proxy", change_pct=3.5),
            _observation(symbol="FXI", bucket="china_proxy", change_pct=1.2),
            _observation(symbol="CNH=X", bucket="rates_fx", change_pct=-0.8),
        ],
    )

    by_key = {item["regime_key"]: item for item in report["market_regimes"]}
    assert by_key["technology_risk_on"]["confidence"] == "high"
    assert by_key["china_proxy_strength"]["triggered"] is True


def test_market_regime_engine_suppresses_rates_pressure_when_required_inputs_missing() -> None:
    from app.services.market_regime_engine import MarketRegimeEngine

    report = MarketRegimeEngine().evaluate(
        analysis_date="2026-04-10",
        observations=[
            _observation(symbol="DX-Y.NYB", bucket="rates_fx", change_pct=0.7),
        ],
    )

    by_key = {item["regime_key"]: item for item in report["market_regime_evaluations"]}
    assert by_key["rates_pressure"]["triggered"] is False
    assert "missing_required_observations" in by_key["rates_pressure"]["suppressed_by"]


def test_market_regime_engine_downgrades_safe_haven_flow_on_conflicting_indexes() -> None:
    from app.services.market_regime_engine import MarketRegimeEngine

    report = MarketRegimeEngine().evaluate(
        analysis_date="2026-04-10",
        observations=[
            _observation(symbol="GC=F", bucket="precious_metals", change_pct=1.5),
            _observation(symbol="SI=F", bucket="precious_metals", change_pct=2.1),
            _observation(symbol="^VIX", bucket="sentiment", change_pct=6.5),
            _observation(symbol="^GSPC", bucket="index", change_pct=1.2),
            _observation(symbol="^IXIC", bucket="index", change_pct=1.4),
        ],
    )

    by_key = {item["regime_key"]: item for item in report["market_regimes"]}
    assert by_key["safe_haven_flow"]["triggered"] is True
    assert by_key["safe_haven_flow"]["confidence"] == "medium"
    assert "conflicting_observations" in by_key["safe_haven_flow"]["suppressed_by"]


def test_market_regime_engine_triggers_energy_inflation_impulse() -> None:
    from app.services.market_regime_engine import MarketRegimeEngine

    report = MarketRegimeEngine().evaluate(
        analysis_date="2026-04-10",
        observations=[
            _observation(symbol="CL=F", bucket="energy", change_pct=3.6),
            _observation(symbol="BZ=F", bucket="energy", change_pct=3.2),
            _observation(symbol="NG=F", bucket="energy", change_pct=4.1),
            _observation(symbol="XLE", bucket="sector", change_pct=2.2),
        ],
    )

    by_key = {item["regime_key"]: item for item in report["market_regimes"]}
    assert by_key["energy_inflation_impulse"]["triggered"] is True
    assert by_key["energy_inflation_impulse"]["confidence"] == "high"


def test_market_snapshot_refresh_includes_market_regimes_and_evaluations() -> None:
    market_close = int(datetime(2026, 4, 9, 20, 0, tzinfo=timezone.utc).timestamp())
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_market_regime_snapshot.db"))
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "%5EIXIC": _chart_payload(
                        symbol="^IXIC",
                        name="NASDAQ Composite",
                        first_close=17600.0,
                        last_close=17920.0,
                        market_time=market_close,
                        instrument_type="INDEX",
                    ),
                    "XLK?": _chart_payload(
                        symbol="XLK",
                        name="Technology Select Sector SPDR Fund",
                        first_close=200.0,
                        last_close=206.0,
                        market_time=market_close,
                        instrument_type="ETF",
                    ),
                    "SOXX?": _chart_payload(
                        symbol="SOXX",
                        name="iShares Semiconductor ETF",
                        first_close=250.0,
                        last_close=260.0,
                        market_time=market_close,
                        instrument_type="ETF",
                    ),
                    "%5EVIX": _chart_payload(
                        symbol="^VIX",
                        name="CBOE Volatility Index",
                        first_close=18.0,
                        last_close=16.5,
                        market_time=market_close,
                        instrument_type="INDEX",
                        exchange_name="CBOE",
                    ),
                    "%5ETNX": _chart_payload(
                        symbol="^TNX",
                        name="10Y Treasury Yield",
                        first_close=4.35,
                        last_close=4.20,
                        market_time=market_close,
                        instrument_type="INDEX",
                    ),
                }
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Yahoo Finance Chart",
                    source_url="https://finance.yahoo.com/",
                    chart_url_template="https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d",
                ),
            ),
            instruments=(
                MarketInstrumentDefinition(symbol="^IXIC", display_name="纳指综指", bucket="index", priority=100),
                MarketInstrumentDefinition(symbol="XLK", display_name="科技板块", bucket="sector", priority=99),
                MarketInstrumentDefinition(symbol="SOXX", display_name="半导体板块", bucket="sector", priority=98),
                MarketInstrumentDefinition(symbol="^VIX", display_name="VIX", bucket="sentiment", priority=97),
                MarketInstrumentDefinition(symbol="^TNX", display_name="美国10年期国债收益率", bucket="rates_fx", priority=96),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

    assert "market_regimes" in snapshot
    assert "market_regime_evaluations" in snapshot
    assert any(item["regime_key"] == "technology_risk_on" for item in snapshot["market_regimes"])
