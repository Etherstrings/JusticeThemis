# -*- coding: utf-8 -*-
"""Tests for market provider routing and observation normalization."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from app.db import Database
from app.repository import OvernightRepository
from app.services.market_snapshot import (
    DEFAULT_US_MARKET_INSTRUMENTS,
    MarketDataProviderDefinition,
    MarketInstrumentDefinition,
    UsMarketSnapshotService,
)


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
                        "adjclose": [{"adjclose": [first_close, last_close]}],
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


def test_market_provider_router_is_bucket_aware() -> None:
    from app.services.market_data_router import ordered_provider_routes

    providers = (
        MarketDataProviderDefinition(
            name="iFinD History",
            source_url="https://quantapi.51ifind.com/",
            chart_url_template="ifind://history/{symbol}",
        ),
        MarketDataProviderDefinition(
            name="Treasury Yield Curve",
            source_url="https://home.treasury.gov/",
            chart_url_template="treasury://yieldcurve/{symbol}",
        ),
        MarketDataProviderDefinition(
            name="Yahoo Finance Chart",
            source_url="https://finance.yahoo.com/",
            chart_url_template="https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
        ),
    )
    treasury_instrument = MarketInstrumentDefinition(
        symbol="^TNX",
        display_name="美国10年期国债收益率",
        bucket="rates_fx",
        priority=90,
        provider_symbol_overrides=(("Treasury Yield Curve", "^TNX"),),
    )
    sector_instrument = MarketInstrumentDefinition(
        symbol="XLK",
        display_name="科技板块",
        bucket="sector",
        priority=80,
        provider_symbol_overrides=(("iFinD History", "XLK.P"),),
    )

    treasury_routes = ordered_provider_routes(instrument=treasury_instrument, providers=providers)
    sector_routes = ordered_provider_routes(instrument=sector_instrument, providers=providers)

    assert [route.provider_name for route in treasury_routes] == [
        "Treasury Yield Curve",
        "Yahoo Finance Chart",
    ]
    assert [route.provider_name for route in sector_routes] == [
        "iFinD History",
        "Yahoo Finance Chart",
    ]
    assert treasury_routes[0].provider_symbol == "^TNX"
    assert sector_routes[0].provider_symbol == "XLK.P"


def test_default_market_instruments_include_first_pass_china_proxies() -> None:
    symbols = {instrument.symbol for instrument in DEFAULT_US_MARKET_INSTRUMENTS}

    assert "KWEB" in symbols
    assert "FXI" in symbols


def test_normalize_market_observation_payload() -> None:
    from app.services.market_data_router import build_market_observation_payload

    payload = build_market_observation_payload(
        capture_run_id=7,
        session_name="us_close",
        snapshot={
            "analysis_date": "2026-04-10",
            "market_date": "2026-04-09",
            "symbol": "SOXX",
            "display_name": "半导体板块",
            "provider_name": "iFinD History",
            "provider_symbol": "SOXX.O",
            "bucket": "sector",
            "market_time": "2026-04-09T20:00:00+00:00",
            "close": 220.5,
            "previous_close": 215.0,
            "change": 5.5,
            "change_pct": 2.5581,
            "currency": "USD",
            "provider_url": "https://quantapi.51ifind.com/",
            "quote_url": "https://quantapi.51ifind.com/",
            "instrument_type": "ETF",
            "exchange_name": "NASDAQ",
            "exchange_timezone_name": "America/New_York",
        },
    )

    assert payload["capture_run_id"] == 7
    assert payload["symbol"] == "SOXX"
    assert payload["provider_name"] == "iFinD History"
    assert payload["provider_symbol"] == "SOXX.O"
    assert payload["change_value"] == 5.5
    assert payload["change_pct"] == 2.5581
    assert payload["freshness_status"] == "fresh"
    assert payload["provenance"]["quote_url"] == "https://quantapi.51ifind.com/"


def test_market_snapshot_refresh_persists_capture_run_and_observations() -> None:
    market_close = int(datetime(2026, 4, 9, 20, 0, tzinfo=timezone.utc).timestamp())
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_market_snapshot_observations.db"))
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "ifind://history/IXIC.GI": _chart_payload(
                        symbol="IXIC.GI",
                        name="NASDAQ Composite",
                        first_close=17600.0,
                        last_close=17720.0,
                        market_time=market_close,
                        instrument_type="INDEX",
                    ),
                    "ifind://history/KWEB.P": _chart_payload(
                        symbol="KWEB.P",
                        name="KraneShares CSI China Internet ETF",
                        first_close=29.0,
                        last_close=30.2,
                        market_time=market_close,
                        instrument_type="ETF",
                    ),
                }
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="iFinD History",
                    source_url="https://quantapi.51ifind.com/",
                    chart_url_template="ifind://history/{symbol}",
                    quote_url_template="https://quantapi.51ifind.com/",
                ),
            ),
            instruments=(
                MarketInstrumentDefinition(
                    symbol="^IXIC",
                    display_name="纳指综指",
                    bucket="index",
                    priority=100,
                    provider_symbol_overrides=(("iFinD History", "IXIC.GI"),),
                ),
                MarketInstrumentDefinition(
                    symbol="KWEB",
                    display_name="中国互联网ETF",
                    bucket="china_proxy",
                    priority=88,
                    provider_symbol_overrides=(("iFinD History", "KWEB.P"),),
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()
        runs = repo.list_market_capture_runs(analysis_date="2026-04-10", session_name="us_close")
        observations = repo.list_market_observations(analysis_date="2026-04-10", session_name="us_close")

    assert snapshot["capture_run_id"] == runs[0]["id"]
    assert len(runs) == 1
    assert runs[0]["provider_hits"] == {"iFinD History": 2}
    assert [item["symbol"] for item in observations] == ["KWEB", "^IXIC"]
    assert all(item["capture_run_id"] == runs[0]["id"] for item in observations)
