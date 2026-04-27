# -*- coding: utf-8 -*-
"""Tests for persisted U.S. market snapshot capture and daily-analysis integration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import requests
import pytest

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.asset_board import AssetBoardService
from app.services.market_snapshot import (
    DEFAULT_US_MARKET_INSTRUMENTS,
    MarketDataProviderDefinition,
    MarketInstrumentDefinition,
    MarketRequestsHttpClient,
    UsMarketSnapshotService,
    _provider_symbol_for,
)
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate


class RoutingMarketClient:
    def __init__(self, routes: dict[str, str]):
        self.routes = routes

    def fetch(self, url: str) -> str:
        for fragment, payload in self.routes.items():
            if fragment in url:
                return payload
        raise AssertionError(f"Unexpected market url: {url}")


class _FakeHttpResponse:
    def __init__(self, *, text: str = "", status_code: int = 200) -> None:
        self._text = text
        self.status_code = status_code
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    @property
    def text(self) -> str:
        return self._text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class _Always429Session:
    def __init__(self) -> None:
        self.call_count = 0

    def get(self, _url: str, *, timeout: int, headers: dict[str, str]) -> _FakeHttpResponse:
        del timeout, headers
        self.call_count += 1
        return _FakeHttpResponse(status_code=429)


class StaticPredictionMarketService:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def collect(
        self,
        *,
        analysis_date: str,
        market_date: str,
        previous_snapshot: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "analysis_date": analysis_date,
                "market_date": market_date,
                "previous_snapshot": previous_snapshot,
            }
        )
        return self.payload


class StaticSignalService:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def collect(
        self,
        *,
        analysis_date: str,
        market_date: str,
        previous_snapshot: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "analysis_date": analysis_date,
                "market_date": market_date,
                "previous_snapshot": previous_snapshot,
            }
        )
        return self.payload


def _admin_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
    monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
    return {"X-Admin-Access-Key": "secret-admin"}


def test_default_market_snapshot_maps_aluminum_to_ifind_dbb_proxy() -> None:
    ali_instrument = next(item for item in DEFAULT_US_MARKET_INSTRUMENTS if item.symbol == "ALI=F")

    assert _provider_symbol_for(ali_instrument, "iFinD History") == "DBB.P"


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


def test_market_requests_http_client_uses_urllib_fallback_for_yahoo_429() -> None:
    session = _Always429Session()
    fallback_calls: list[str] = []
    market_close = int(datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc).timestamp())
    payload = _chart_payload(
        symbol="ALI=F",
        name="Aluminum",
        first_close=2400.0,
        last_close=2424.0,
        market_time=market_close,
        instrument_type="FUTURE",
        exchange_name="CMX",
    )
    client = MarketRequestsHttpClient(
        session=session,
        retry_attempts=1,
        backoff_seconds=0.0,
        sleep_fn=lambda _seconds: None,
        urllib_fetcher=lambda url, _headers, _timeout: fallback_calls.append(url) or payload,
    )

    result = client.fetch("https://query2.finance.yahoo.com/v8/finance/chart/ALI%3DF?range=5d&interval=1d")

    assert json.loads(result)["chart"]["result"][0]["meta"]["symbol"] == "ALI=F"
    assert session.call_count == 1
    assert fallback_calls == ["https://query2.finance.yahoo.com/v8/finance/chart/ALI%3DF?range=5d&interval=1d"]


def test_market_requests_http_client_uses_curl_fallback_when_urllib_fails() -> None:
    session = _Always429Session()
    fallback_calls: list[str] = []
    market_close = int(datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc).timestamp())
    payload = _chart_payload(
        symbol="^TNX",
        name="10Y Treasury Yield",
        first_close=4.25,
        last_close=4.10,
        market_time=market_close,
        instrument_type="INDEX",
        exchange_name="CGI",
    )
    client = MarketRequestsHttpClient(
        session=session,
        retry_attempts=1,
        backoff_seconds=0.0,
        sleep_fn=lambda _seconds: None,
        urllib_fetcher=lambda _url, _headers, _timeout: (_ for _ in ()).throw(RuntimeError("urllib blocked")),
        curl_fetcher=lambda url, _headers, _timeout: fallback_calls.append(url) or payload,
    )

    result = client.fetch("https://query2.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5d&interval=1d")

    assert json.loads(result)["chart"]["result"][0]["meta"]["symbol"] == "^TNX"
    assert session.call_count == 1
    assert fallback_calls == ["https://query2.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5d&interval=1d"]


def test_market_requests_http_client_rejects_plaintext_curl_fallback_body() -> None:
    session = _Always429Session()
    client = MarketRequestsHttpClient(
        session=session,
        retry_attempts=1,
        backoff_seconds=0.0,
        sleep_fn=lambda _seconds: None,
        urllib_fetcher=lambda _url, _headers, _timeout: (_ for _ in ()).throw(RuntimeError("urllib blocked")),
        curl_fetcher=lambda _url, _headers, _timeout: "Too Many Requests\r\n",
    )

    try:
        client.fetch("https://query2.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d")
    except requests.HTTPError as exc:
        assert exc.response is not None
        assert exc.response.status_code == 429
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected HTTPError when curl fallback only returns plaintext 429 body")


def test_market_snapshot_service_uses_treasury_provider_for_tnx_when_available() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "treasury-provider.db"))
        market_close = int(datetime(2026, 4, 8, 19, 30, tzinfo=timezone.utc).timestamp())
        client = RoutingMarketClient(
            {
                "treasury://yieldcurve/%5ETNX": _chart_payload(
                    symbol="^TNX",
                    name="10Y Treasury Yield",
                    first_close=4.32,
                    last_close=4.26,
                    market_time=market_close,
                    instrument_type="INDEX",
                    exchange_name="U.S. Treasury",
                    volume=0,
                )
            }
        )
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=client,
            instruments=(
                MarketInstrumentDefinition(
                    symbol="^TNX",
                    display_name="美国10年期国债收益率",
                    bucket="rates_fx",
                    priority=90,
                    provider_symbol_overrides=(("Treasury Yield Curve", "^TNX"),),
                ),
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Treasury Yield Curve",
                    source_url="https://home.treasury.gov/",
                    chart_url_template="treasury://yieldcurve/{symbol}",
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

    assert snapshot["rates_fx"][0]["provider_name"] == "Treasury Yield Curve"
    assert snapshot["rates_fx"][0]["close"] == 4.26
    assert snapshot["capture_summary"]["missing_symbols"] == []


def test_market_snapshot_service_uses_stooq_provider_when_yahoo_payload_is_invalid() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "stooq-provider.db"))
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "query2.finance.yahoo.com": "Too Many Requests\r\n",
                    "stooq.com/q/l/": "Symbol,Date,Time,Open,High,Low,Close,Volume\r\n^SPX,2026-04-14,23:00:00,6910.2,6969.42,6905.17,6967.38,3046739431\r\n",
                }
            ),
            instruments=(
                MarketInstrumentDefinition(
                    symbol="^GSPC",
                    display_name="标普500",
                    bucket="index",
                    priority=100,
                    provider_symbol_overrides=(("Stooq Quotes", "^spx"),),
                ),
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Yahoo Finance Chart",
                    source_url="https://finance.yahoo.com/",
                    chart_url_template="https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d&includePrePost=false",
                ),
                MarketDataProviderDefinition(
                    name="Stooq Quotes",
                    source_url="https://stooq.com/",
                    chart_url_template="https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv",
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

    assert snapshot["indexes"][0]["provider_name"] == "Stooq Quotes"
    assert snapshot["indexes"][0]["close"] == 6967.38
    assert snapshot["capture_summary"]["missing_symbols"] == []


def test_market_snapshot_service_uses_stooq_prev_close_when_detail_page_is_available() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "stooq-prev-close.db"))
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "stooq.com/q/l/": "Symbol,Date,Time,Open,High,Low,Close,Volume\r\n^SPX,2026-04-14,23:00:00,6910.2,6969.42,6905.17,6967.38,3046739431\r\n",
                    "stooq.com/q/?s=": "<html><body><span id=aq_^spx_p>6936.00</span><span id=aq_^spx_rr1>+0.45%</span></body></html>",
                }
            ),
            instruments=(
                MarketInstrumentDefinition(
                    symbol="^GSPC",
                    display_name="标普500",
                    bucket="index",
                    priority=100,
                    provider_symbol_overrides=(("Stooq Quotes", "^spx"),),
                ),
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Stooq Quotes",
                    source_url="https://stooq.com/",
                    chart_url_template="https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv",
                    quote_url_template="https://stooq.com/q/?s={symbol}",
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

    quote = snapshot["indexes"][0]
    expected_change = 6967.38 - 6936.00
    expected_change_pct = (expected_change / 6936.00) * 100.0
    assert quote["provider_name"] == "Stooq Quotes"
    assert quote["previous_close"] == pytest.approx(6936.00)
    assert quote["change"] == pytest.approx(expected_change)
    assert quote["change_pct"] == pytest.approx(expected_change_pct)
    assert quote["change_pct_text"] == f"{expected_change_pct:+.2f}%"


def test_market_snapshot_service_inverts_stooq_cnyusd_quote_for_usdcnh() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "stooq-cnh.db"))
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "stooq.com/q/l/": "Symbol,Date,Time,Open,High,Low,Close,Volume\r\nCNYUSD,2026-04-15,12:00:56,0.14684,0.146873,0.146612,0.146667,\r\n",
                }
            ),
            instruments=(
                MarketInstrumentDefinition(
                    symbol="CNH=X",
                    display_name="美元/离岸人民币",
                    bucket="rates_fx",
                    priority=100,
                    provider_symbol_overrides=(("Stooq Quotes", "cnyusd"),),
                ),
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Stooq Quotes",
                    source_url="https://stooq.com/",
                    chart_url_template="https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv",
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

    quote = snapshot["rates_fx"][0]
    assert quote["provider_name"] == "Stooq Quotes"
    assert quote["provider_symbol"] == "cnyusd"
    assert quote["close"] == pytest.approx(1 / 0.146667, rel=1e-6)


def _seed_item(
    repo: OvernightRepository,
    *,
    source_id: str,
    url: str,
    title: str,
    summary: str,
    published_at: str,
    created_at: str,
) -> int:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url=url,
            candidate_title=title,
            candidate_summary=summary,
            candidate_excerpt_source="body_selector:main",
            candidate_published_at=published_at,
            candidate_published_at_source="html:meta_article_published_time",
        )
    )
    raw_id = repo.create_raw_record(
        source_id=source_id,
        fetch_mode="test_seed",
        payload_hash=f"{source_id}:{published_at}:{title}",
    )
    stored = repo.persist_source_item(replace(normalized, raw_id=raw_id))
    repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
    repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
    with repo.db.connect() as connection:
        connection.execute(
            "UPDATE overnight_source_items SET created_at = ? WHERE id = ?",
            (created_at, stored.id),
        )
    return stored.id


def _build_market_service(repo: OvernightRepository) -> UsMarketSnapshotService:
    market_close = int(datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc).timestamp())
    routes = {
        "%5EGSPC": _chart_payload(
            symbol="^GSPC",
            name="S&P 500",
            first_close=5000.0,
            last_close=5100.0,
            market_time=market_close,
            instrument_type="INDEX",
        ),
        "%5EIXIC": _chart_payload(
            symbol="^IXIC",
            name="NASDAQ Composite",
            first_close=16000.0,
            last_close=16320.0,
            market_time=market_close,
            instrument_type="INDEX",
        ),
        "%5EVIX": _chart_payload(
            symbol="^VIX",
            name="CBOE Volatility Index",
            first_close=20.0,
            last_close=18.0,
            market_time=market_close,
            instrument_type="INDEX",
            exchange_name="CBOE",
            exchange_timezone_name="America/Chicago",
            volume=0,
        ),
        "XLK?": _chart_payload(
            symbol="XLK",
            name="Technology Select Sector SPDR Fund",
            first_close=200.0,
            last_close=208.0,
            market_time=market_close,
            instrument_type="ETF",
        ),
        "XLE?": _chart_payload(
            symbol="XLE",
            name="Energy Select Sector SPDR Fund",
            first_close=95.0,
            last_close=94.0,
            market_time=market_close,
            instrument_type="ETF",
        ),
    }
    return UsMarketSnapshotService(
        repo=repo,
        http_client=RoutingMarketClient(routes),
        instruments=(
            MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            MarketInstrumentDefinition(symbol="^IXIC", display_name="纳指综指", bucket="index", priority=95),
            MarketInstrumentDefinition(symbol="^VIX", display_name="VIX", bucket="sentiment", priority=90),
            MarketInstrumentDefinition(symbol="XLK", display_name="科技板块", bucket="sector", priority=80),
            MarketInstrumentDefinition(symbol="XLE", display_name="能源板块", bucket="sector", priority=78),
        ),
    )


def _build_cross_asset_market_service(repo: OvernightRepository) -> UsMarketSnapshotService:
    market_close = int(datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc).timestamp())
    routes = {
        "%5EGSPC": _chart_payload(
            symbol="^GSPC",
            name="S&P 500",
            first_close=5000.0,
            last_close=5100.0,
            market_time=market_close,
            instrument_type="INDEX",
        ),
        "%5EIXIC": _chart_payload(
            symbol="^IXIC",
            name="NASDAQ Composite",
            first_close=16000.0,
            last_close=16480.0,
            market_time=market_close,
            instrument_type="INDEX",
        ),
        "%5EVIX": _chart_payload(
            symbol="^VIX",
            name="CBOE Volatility Index",
            first_close=20.0,
            last_close=17.6,
            market_time=market_close,
            instrument_type="INDEX",
            exchange_name="CBOE",
            exchange_timezone_name="America/Chicago",
            volume=0,
        ),
        "XLK?": _chart_payload(
            symbol="XLK",
            name="Technology Select Sector SPDR Fund",
            first_close=200.0,
            last_close=210.0,
            market_time=market_close,
            instrument_type="ETF",
        ),
        "SOXX?": _chart_payload(
            symbol="SOXX",
            name="iShares Semiconductor ETF",
            first_close=250.0,
            last_close=265.0,
            market_time=market_close,
            instrument_type="ETF",
        ),
        "XLE?": _chart_payload(
            symbol="XLE",
            name="Energy Select Sector SPDR Fund",
            first_close=95.0,
            last_close=92.0,
            market_time=market_close,
            instrument_type="ETF",
        ),
        "%5ETNX": _chart_payload(
            symbol="^TNX",
            name="CBOE 10 Year Treasury Note Yield Index",
            first_close=4.40,
            last_close=4.20,
            market_time=market_close,
            instrument_type="INDEX",
            exchange_name="CBOE",
        ),
        "DX-Y.NYB": _chart_payload(
            symbol="DX-Y.NYB",
            name="US Dollar Index",
            first_close=104.0,
            last_close=103.0,
            market_time=market_close,
            instrument_type="INDEX",
            exchange_name="ICE",
        ),
        "CNH%3DX": _chart_payload(
            symbol="CNH=X",
            name="USD/CNH",
            first_close=7.29,
            last_close=7.24,
            market_time=market_close,
            instrument_type="CURRENCY",
            exchange_name="CCY",
        ),
        "GC%3DF": _chart_payload(
            symbol="GC=F",
            name="Gold",
            first_close=2320.0,
            last_close=2348.0,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="COMEX",
        ),
        "SI%3DF": _chart_payload(
            symbol="SI=F",
            name="Silver",
            first_close=26.0,
            last_close=26.5,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="COMEX",
        ),
        "CL%3DF": _chart_payload(
            symbol="CL=F",
            name="WTI Crude Oil",
            first_close=82.0,
            last_close=78.0,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="NYMEX",
        ),
        "BZ%3DF": _chart_payload(
            symbol="BZ=F",
            name="Brent Crude Oil",
            first_close=85.0,
            last_close=81.5,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="ICE",
        ),
        "NG%3DF": _chart_payload(
            symbol="NG=F",
            name="Natural Gas",
            first_close=2.40,
            last_close=2.28,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="NYMEX",
        ),
        "HG%3DF": _chart_payload(
            symbol="HG=F",
            name="Copper",
            first_close=4.00,
            last_close=4.12,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="COMEX",
        ),
        "ALI%3DF": _chart_payload(
            symbol="ALI=F",
            name="Aluminum",
            first_close=112.0,
            last_close=113.2,
            market_time=market_close,
            instrument_type="FUTURE",
            exchange_name="LME",
        ),
    }
    return UsMarketSnapshotService(
        repo=repo,
        http_client=RoutingMarketClient(routes),
        instruments=(
            MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            MarketInstrumentDefinition(symbol="^IXIC", display_name="纳指综指", bucket="index", priority=98),
            MarketInstrumentDefinition(symbol="^VIX", display_name="VIX", bucket="sentiment", priority=97),
            MarketInstrumentDefinition(symbol="XLK", display_name="科技板块", bucket="sector", priority=95),
            MarketInstrumentDefinition(symbol="SOXX", display_name="半导体板块", bucket="sector", priority=94),
            MarketInstrumentDefinition(symbol="XLE", display_name="能源板块", bucket="sector", priority=93),
            MarketInstrumentDefinition(symbol="^TNX", display_name="美国10年期国债收益率", bucket="rates_fx", priority=90),
            MarketInstrumentDefinition(symbol="DX-Y.NYB", display_name="美元指数", bucket="rates_fx", priority=89),
            MarketInstrumentDefinition(symbol="CNH=X", display_name="美元/离岸人民币", bucket="rates_fx", priority=88),
            MarketInstrumentDefinition(symbol="GC=F", display_name="黄金", bucket="precious_metals", priority=86),
            MarketInstrumentDefinition(symbol="SI=F", display_name="白银", bucket="precious_metals", priority=85),
            MarketInstrumentDefinition(symbol="CL=F", display_name="WTI原油", bucket="energy", priority=84),
            MarketInstrumentDefinition(symbol="BZ=F", display_name="布伦特原油", bucket="energy", priority=83),
            MarketInstrumentDefinition(symbol="NG=F", display_name="天然气", bucket="energy", priority=82),
            MarketInstrumentDefinition(symbol="HG=F", display_name="铜", bucket="industrial_metals", priority=80),
            MarketInstrumentDefinition(symbol="ALI=F", display_name="铝", bucket="industrial_metals", priority=79),
        ),
    )


def test_us_market_snapshot_service_refreshes_and_persists_us_close_snapshot() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_service.db")
        repo = OvernightRepository(database)
        service = _build_market_service(repo)

        snapshot = service.refresh_us_close_snapshot()
        stored = service.get_daily_snapshot(analysis_date="2026-04-07")

        assert snapshot["analysis_date"] == "2026-04-07"
        assert snapshot["market_date"] == "2026-04-06"
        assert stored is not None
        assert len(snapshot["indexes"]) == 2
        assert len(snapshot["sectors"]) == 2
        assert round(snapshot["indexes"][0]["change_pct"], 2) == 2.0
        assert round(snapshot["indexes"][1]["change_pct"], 2) == 2.0
        assert snapshot["indexes"][0]["close_text"] == "5,100.00"
        assert snapshot["indexes"][0]["change_text"] == "+100.00"
        assert snapshot["indexes"][0]["change_pct_text"] == "+2.00%"
        assert snapshot["indexes"][0]["change_direction"] == "up"
        assert snapshot["indexes"][0]["volume_text"] == "1,000,000"
        assert snapshot["indexes"][0]["market_time_local"].startswith("2026-04-06T16:00:00")
        assert snapshot["indexes"][0]["analysis_time_shanghai"].startswith("2026-04-07T04:00:00")
        assert snapshot["risk_signals"]["risk_mode"] == "risk_on"
        assert snapshot["risk_signals"]["strongest_sector"]["symbol"] == "XLK"
        assert snapshot["risk_signals"]["weakest_sector"]["symbol"] == "XLE"
        assert snapshot["risk_signals"]["volatility_proxy"]["symbol"] == "^VIX"
        assert snapshot["capture_summary"]["capture_status"] == "complete"
        assert snapshot["capture_summary"]["expected_instrument_count"] == 5
        assert snapshot["capture_summary"]["captured_instrument_count"] == 5
        assert snapshot["capture_summary"]["missing_symbols"] == []


def test_market_snapshot_api_and_daily_analysis_include_snapshot_context(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        database = Database(Path(temp_dir) / "test_market_snapshot_api.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/rates-update",
            title="Federal Reserve says inflation remains sticky",
            summary=(
                "Federal Reserve officials said inflation remained sticky and rates may stay restrictive "
                "while markets reassess duration-sensitive assets."
            ),
            published_at="2026-04-07T01:00:00+00:00",
            created_at="2026-04-07 09:01:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        market_service = _build_market_service(repo)
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                market_snapshot_service=market_service,
            )
        )

        refresh_response = client.post("/api/v1/market/us/refresh", headers=admin_headers)
        daily_snapshot_response = client.get("/api/v1/market/us/daily", params={"analysis_date": "2026-04-07"})
        generate_response = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )
        prompt_response = client.get("/api/v1/analysis/daily/prompt", params={"analysis_date": "2026-04-07", "tier": "free"})

        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["analysis_date"] == "2026-04-07"
        assert refresh_payload["risk_signals"]["risk_mode"] == "risk_on"

        assert daily_snapshot_response.status_code == 200
        assert daily_snapshot_response.json()["market_date"] == "2026-04-06"

        assert generate_response.status_code == 200
        free_report = generate_response.json()["reports"][0]
        assert free_report["market_snapshot"]["analysis_date"] == "2026-04-07"
        assert free_report["market_snapshot"]["risk_signals"]["risk_mode"] == "risk_on"
        assert "标普500" in free_report["narratives"]["market_view"]
        assert "VIX" in free_report["narratives"]["market_view"]

        assert prompt_response.status_code == 200
        assert "market_snapshot" in prompt_response.json()["messages"][1]["content"]


def test_market_snapshot_marks_partial_capture_and_exposes_missing_symbols() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_partial.db")
        repo = OvernightRepository(database)
        market_close = int(datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc).timestamp())
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "%5EGSPC": _chart_payload(
                        symbol="^GSPC",
                        name="S&P 500",
                        first_close=5000.0,
                        last_close=5100.0,
                        market_time=market_close,
                        instrument_type="INDEX",
                    )
                }
            ),
            instruments=(
                MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
                MarketInstrumentDefinition(symbol="XLK", display_name="科技板块", bucket="sector", priority=80),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

        assert snapshot["capture_summary"]["capture_status"] == "partial"
        assert snapshot["capture_summary"]["expected_instrument_count"] == 2
        assert snapshot["capture_summary"]["captured_instrument_count"] == 1
        assert snapshot["capture_summary"]["missing_instrument_count"] == 1
        assert snapshot["capture_summary"]["missing_symbols"] == ["XLK"]
        assert snapshot["capture_summary"]["captured_symbols"] == ["^GSPC"]


def test_market_snapshot_uses_timestamp_of_last_valid_close_not_stale_regular_market_time() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_last_valid_close_date.db")
        repo = OvernightRepository(database)
        friday_close = int(datetime(2026, 4, 3, 20, 0, tzinfo=timezone.utc).timestamp())
        monday_meta_time = int(datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc).timestamp())
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "symbol": "^GSPC",
                            "exchangeName": "SNP",
                            "fullExchangeName": "SNP",
                            "instrumentType": "INDEX",
                            "regularMarketTime": monday_meta_time,
                            "exchangeTimezoneName": "America/New_York",
                            "chartPreviousClose": 4900.0,
                        },
                        "timestamp": [friday_close, monday_meta_time],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [4900.0, None],
                                    "close": [5000.0, None],
                                    "high": [5010.0, None],
                                    "low": [4890.0, None],
                                    "volume": [1000000, None],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient({"%5EGSPC": json.dumps(payload)}),
            instruments=(
                MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

        assert snapshot["market_date"] == "2026-04-03"
        assert snapshot["analysis_date"] == "2026-04-04"
        assert snapshot["indexes"][0]["market_time_local"].startswith("2026-04-03T16:00:00")
        assert snapshot["indexes"][0]["analysis_time_shanghai"].startswith("2026-04-04T04:00:00")


def test_market_snapshot_service_emits_cross_asset_groups_and_asset_board() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_cross_asset.db")
        repo = OvernightRepository(database)
        service = _build_cross_asset_market_service(repo)

        snapshot = service.refresh_us_close_snapshot()

        assert [item["symbol"] for item in snapshot["rates_fx"]] == ["^TNX", "DX-Y.NYB", "CNH=X"]
        assert [item["symbol"] for item in snapshot["precious_metals"]] == ["GC=F", "SI=F"]
        assert [item["symbol"] for item in snapshot["energy"]] == ["CL=F", "BZ=F", "NG=F"]
        assert [item["symbol"] for item in snapshot["industrial_metals"]] == ["HG=F", "ALI=F"]

        futures_by_code = {
            item["future_code"]: item
            for item in snapshot["china_mapped_futures"]
        }
        assert len(futures_by_code) == 8
        assert futures_by_code["methanol"]["watch_direction"] == "down"
        assert futures_by_code["pta"]["watch_direction"] == "down"
        assert futures_by_code["lithium_carbonate"]["watch_direction"] == "up"
        assert futures_by_code["industrial_silicon"]["watch_direction"] == "up"
        assert futures_by_code["methanol"]["driver_symbols"] == ["CL=F", "BZ=F", "NG=F"]

        asset_board = snapshot["asset_board"]
        assert asset_board["analysis_date"] == "2026-04-07"
        assert asset_board["market_date"] == "2026-04-06"
        assert asset_board["key_moves"]["strongest_move"]["symbol"] == "SOXX"
        assert asset_board["key_moves"]["weakest_move"]["symbol"] == "CL=F"
        assert asset_board["risk_signals"]["risk_mode"] == "risk_on"
        assert asset_board["headline"].startswith("纳指综指 +3.00%")


def test_market_snapshot_service_falls_back_to_second_provider_when_primary_fails() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_provider_fallback.db")
        repo = OvernightRepository(database)
        market_close = int(datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc).timestamp())
        payload = _chart_payload(
            symbol="^GSPC",
            name="S&P 500",
            first_close=5000.0,
            last_close=5100.0,
            market_time=market_close,
            instrument_type="INDEX",
        )
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "backup.example/%5EGSPC": payload,
                }
            ),
            providers=(
                MarketDataProviderDefinition(
                    name="Primary Provider",
                    source_url="https://primary.example/",
                    chart_url_template="https://primary.example/{symbol}",
                ),
                MarketDataProviderDefinition(
                    name="Backup Provider",
                    source_url="https://backup.example/",
                    chart_url_template="https://backup.example/{symbol}",
                ),
            ),
            instruments=(
                MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

        assert snapshot["source_name"] == "Backup Provider"
        assert snapshot["source_url"] == "https://backup.example/"
        assert snapshot["indexes"][0]["provider_name"] == "Backup Provider"
        assert snapshot["indexes"][0]["provider_url"] == "https://backup.example/"


def test_market_snapshot_service_embeds_prediction_market_payload() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_polymarket.db")
        repo = OvernightRepository(database)
        market_close = int(datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc).timestamp())
        prediction_service = StaticPredictionMarketService(
            {
                "provider_name": "Polymarket",
                "status": "ready",
                "signal_count": 1,
                "signals": [
                    {
                        "signal_key": "fed_path",
                        "label": "美联储路径",
                        "probability": 63.0,
                        "delta_pct_points": 4.0,
                    }
                ],
            }
        )
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "%5EGSPC": _chart_payload(
                        symbol="^GSPC",
                        name="S&P 500",
                        first_close=5000.0,
                        last_close=5100.0,
                        market_time=market_close,
                        instrument_type="INDEX",
                    )
                }
            ),
            instruments=(
                MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            ),
            prediction_market_service=prediction_service,
        )

        snapshot = service.refresh_us_close_snapshot()

    assert snapshot["prediction_markets"]["provider_name"] == "Polymarket"
    assert snapshot["prediction_markets"]["signal_count"] == 1
    assert snapshot["prediction_markets"]["signals"][0]["signal_key"] == "fed_path"
    assert prediction_service.calls[0]["analysis_date"] == "2026-04-09"


def test_market_snapshot_service_embeds_external_signal_layers() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_market_snapshot_external_signals.db")
        repo = OvernightRepository(database)
        market_close = int(datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc).timestamp())
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingMarketClient(
                {
                    "%5EGSPC": _chart_payload(
                        symbol="^GSPC",
                        name="S&P 500",
                        first_close=5000.0,
                        last_close=5100.0,
                        market_time=market_close,
                        instrument_type="INDEX",
                    )
                }
            ),
            instruments=(
                MarketInstrumentDefinition(symbol="^GSPC", display_name="标普500", bucket="index", priority=100),
            ),
            prediction_market_service=StaticPredictionMarketService({"status": "ready", "headline": "Polymarket headline", "signals": [], "signal_count": 0}),
            kalshi_signal_service=StaticSignalService({"status": "ready", "headline": "Kalshi headline", "signals": [], "signal_count": 0}),
            fedwatch_signal_service=StaticSignalService({"status": "ready", "headline": "FedWatch headline", "meetings": [], "meeting_count": 0}),
            cftc_signal_service=StaticSignalService({"status": "ready", "headline": "CFTC headline", "signals": [], "signal_count": 0}),
        )

        snapshot = service.refresh_us_close_snapshot()

    assert snapshot["kalshi_signals"]["status"] == "ready"
    assert snapshot["fedwatch_signals"]["status"] == "ready"
    assert snapshot["cftc_signals"]["status"] == "ready"
    assert snapshot["external_market_signals"]["ready_provider_count"] == 4
    assert "Polymarket headline" in snapshot["external_market_signals"]["headline"]
