# -*- coding: utf-8 -*-
"""Tests for iFinD-backed market snapshot provider integration."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from app.db import Database
from app.repository import OvernightRepository
from app.services.ifind_market_data import IFindHistoryClient
from app.services.market_snapshot import (
    MarketDataProviderDefinition,
    MarketInstrumentDefinition,
    UsMarketSnapshotService,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict[str, object]:
        return dict(self._payload)


class FakeIFindSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object], dict[str, str]]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(("POST", url, dict(json), dict(headers)))
        if url.endswith("/get_access_token"):
            return FakeResponse(
                {
                    "data": {
                        "access_token": "access-token-demo",
                        "expires_in": 3600,
                    }
                }
            )
        if url.endswith("/cmd_history_quotation"):
            return FakeResponse(
                {
                    "errorcode": 0,
                    "errmsg": "",
                    "tables": [
                        {
                            "thscode": "IXIC.GI",
                            "time": ["2026-04-07", "2026-04-08"],
                            "table": {
                                "open": [17500.0, 17610.0],
                                "high": [17650.0, 17750.0],
                                "low": [17480.0, 17590.0],
                                "close": [17600.0, 17720.0],
                                "volume": [1000000.0, 1200000.0],
                            },
                        }
                    ],
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")


class RoutingFetchClient:
    def __init__(self, routes: dict[str, str]) -> None:
        self.routes = routes

    def fetch(self, url: str) -> str:
        for fragment, payload in self.routes.items():
            if fragment in url:
                return payload
        raise AssertionError(f"Unexpected market url: {url}")


def test_ifind_history_client_transforms_history_payload_to_chart_json() -> None:
    session = FakeIFindSession()
    client = IFindHistoryClient(
        refresh_token="refresh-token-demo",
        session=session,
        now=lambda: datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(client.fetch_chart("IXIC.GI", start_date="2026-04-07", end_date="2026-04-08"))
    result = payload["chart"]["result"][0]

    assert result["meta"]["symbol"] == "IXIC.GI"
    assert result["meta"]["chartPreviousClose"] == 17600.0
    assert result["timestamp"] == [1775592000, 1775678400]
    assert result["indicators"]["quote"][0]["close"] == [17600.0, 17720.0]
    assert session.calls[0][1].endswith("/get_access_token")
    assert session.calls[1][1].endswith("/cmd_history_quotation")
    assert session.calls[1][2]["codes"] == "IXIC.GI"
    assert session.calls[1][2]["indicators"] == "open,high,low,close,volume"


def test_market_snapshot_service_uses_ifind_provider_symbol_override() -> None:
    chart_payload = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "symbol": "SPY.P",
                            "exchangeName": "NYSEARCA",
                            "fullExchangeName": "NYSE Arca",
                            "instrumentType": "ETF",
                            "regularMarketTime": 1744142400,
                            "exchangeTimezoneName": "America/New_York",
                            "chartPreviousClose": 500.0,
                        },
                        "timestamp": [1744056000, 1744142400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [500.0, 505.0],
                                    "high": [506.0, 511.0],
                                    "low": [499.0, 504.0],
                                    "close": [500.0, 510.0],
                                    "volume": [1000000, 1200000],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_ifind_market_snapshot_override.db")
        repo = OvernightRepository(database)
        service = UsMarketSnapshotService(
            repo=repo,
            http_client=RoutingFetchClient({"ifind://history/SPY.P": chart_payload}),
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
                    symbol="^GSPC",
                    display_name="标普500",
                    bucket="index",
                    priority=100,
                    provider_symbol_overrides=(("iFinD History", "SPY.P"),),
                ),
            ),
        )

        snapshot = service.refresh_us_close_snapshot()

        assert snapshot["indexes"][0]["symbol"] == "^GSPC"
        assert snapshot["indexes"][0]["provider_name"] == "iFinD History"
        assert snapshot["indexes"][0]["close"] == 510.0
        assert snapshot["source_name"] == "iFinD History"


def test_market_snapshot_service_prefers_ifind_provider_when_refresh_token_present(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("IFIND_REFRESH_TOKEN", "refresh-token-demo")
        database = Database(Path(temp_dir) / "test_ifind_market_provider_order.db")
        repo = OvernightRepository(database)

        service = UsMarketSnapshotService(repo=repo)

        assert service.providers[0].name == "iFinD History"
