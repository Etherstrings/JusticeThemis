# -*- coding: utf-8 -*-
"""Tests for Kalshi, CME FedWatch and CFTC signal services."""

from __future__ import annotations

import requests

from app.services.cftc_cot import CFTCCOTSignalService
from app.services.cme_fedwatch import CMEFedWatchSignalService
from app.services.kalshi_client import KalshiClient, KalshiEvent, KalshiMarket, KalshiOrderBook, KalshiOrderLevel
from app.services.kalshi_signals import KalshiSignalDefinition, KalshiSignalService


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class _FedWatchSession:
    def get(self, url: str, *, timeout: float, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        assert "fed-funds-target.json" in url
        return _FakeResponse(
            {
                "meetings": [
                    {
                        "meetingDate": "2026-06-17",
                        "currentTarget": "425-450",
                        "probabilities": {
                            "400-425": 35.0,
                            "425-450": 60.0,
                            "450-475": 5.0,
                        },
                    }
                ]
            }
        )


class _ForbiddenResponse:
    status_code = 403


class _BlockedFedWatchSession:
    def get(self, url: str, *, timeout: float, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        assert "fed-funds-target.json" in url
        response = _ForbiddenResponse()
        raise requests.HTTPError(
            "403 Client Error: Forbidden for url: https://www.cmegroup.com/services/fed-funds-target/fed-funds-target.json",
            response=response,
        )


class _CftcSession:
    def get(self, url: str, *, params: dict[str, object], timeout: float, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        assert "72hh-3qpy.json" in url
        assert "$where" in params
        return _FakeResponse(
            [
                {
                    "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
                    "report_date_as_yyyy_mm_dd": "2026-04-07T00:00:00.000",
                    "m_money_positions_long_all": "120000",
                    "m_money_positions_short_all": "45000",
                    "prod_merc_positions_long_all": "38000",
                    "prod_merc_positions_short_all": "90000",
                    "open_interest_all": "520000",
                }
            ]
        )


class _KalshiClient:
    def __init__(self) -> None:
        self.requested_event_tickers: list[str] = []
        self.requested_orderbooks: list[str] = []

    def get_event(self, event_ticker: str) -> KalshiEvent:
        self.requested_event_tickers.append(event_ticker)
        return KalshiEvent(
            event_ticker=event_ticker,
            series_ticker="KX",
            title="US Recession",
            subtitle=None,
            category="Economy",
            strike_date=None,
            mutually_exclusive=None,
            available_on_brokers=None,
            markets=(
                KalshiMarket(
                    ticker="KXREC-2026",
                    event_ticker=event_ticker,
                    status="open",
                    market_type="binary",
                    title="Will the US enter recession in 2026?",
                    subtitle=None,
                    yes_sub_title=None,
                    no_sub_title=None,
                    yes_bid=0.41,
                    yes_ask=0.45,
                    no_bid=0.55,
                    no_ask=0.59,
                    last_price=0.43,
                    volume=120000.0,
                    volume_24h=15000.0,
                    open_interest=34000.0,
                    liquidity=9500.0,
                    strike_type=None,
                    floor_strike=None,
                    open_time=None,
                    close_time="2026-12-31T23:59:59Z",
                    expiration_time="2026-12-31T23:59:59Z",
                    rules_primary="Resolution rules",
                    rules_secondary=None,
                ),
            ),
        )

    def get_order_book(self, ticker: str) -> KalshiOrderBook:
        self.requested_orderbooks.append(ticker)
        return KalshiOrderBook(
            market_ticker=ticker,
            yes_bids=(KalshiOrderLevel(price=0.41, size=1000.0),),
            no_bids=(KalshiOrderLevel(price=0.55, size=1200.0),),
        )


class _KalshiSession:
    def get(self, url: str, *, params: dict[str, object] | None = None, timeout: float, headers: dict[str, str]) -> _FakeResponse:
        del params, timeout, headers
        assert "/markets" in url
        return _FakeResponse(
            {
                "markets": [
                    {
                        "ticker": "LIVE-1",
                        "event_ticker": "EVENT-1",
                        "status": "active",
                        "market_type": "binary",
                        "title": "Live market",
                        "yes_bid_dollars": "0.12",
                        "yes_ask_dollars": "0.18",
                        "last_price_dollars": "0.15",
                        "volume_fp": "123.45",
                        "volume_24h_fp": "67.89",
                        "open_interest_fp": "456.00",
                        "liquidity_dollars": "789.00",
                    }
                ]
            }
        )


def test_kalshi_client_parses_live_dollar_fields() -> None:
    client = KalshiClient(session=_KalshiSession())

    markets = client.list_markets(params={"limit": 1, "status": "open"})

    assert len(markets) == 1
    market = markets[0]
    assert market.yes_bid == 0.12
    assert market.yes_ask == 0.18
    assert market.midpoint == 0.15
    assert market.last_price == 0.15
    assert market.volume == 123.45
    assert market.volume_24h == 67.89
    assert market.open_interest == 456.0
    assert market.liquidity == 789.0


def test_kalshi_signal_service_builds_midpoint_signal() -> None:
    service = KalshiSignalService(
        client=_KalshiClient(),
        definitions=[
            KalshiSignalDefinition(
                signal_key="us_recession",
                label="美国衰退概率",
                event_ticker="KXRECSSNBER-26",
                title_contains="recession",
                bucket="macro_growth",
            )
        ],
    )

    payload = service.collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
        previous_snapshot={"kalshi_signals": {"signals": [{"signal_key": "us_recession", "probability": 39.0}]}},
    )

    assert payload["status"] == "ready"
    assert payload["signal_count"] == 1
    signal = payload["signals"][0]
    assert signal["probability"] == 43.0
    assert signal["delta_pct_points"] == 4.0
    assert signal["yes_bid_probability"] == 41.0
    assert signal["yes_ask_probability"] == 45.0
    assert signal["source_url"] == "https://kalshi.com/events/KXRECSSNBER-26"


def test_cme_fedwatch_signal_service_serializes_next_meeting() -> None:
    payload = CMEFedWatchSignalService(session=_FedWatchSession()).collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
    )

    assert payload["status"] == "ready"
    assert payload["meeting_count"] == 1
    meeting = payload["meetings"][0]
    assert meeting["meeting_date"] == "2026-06-17"
    assert meeting["cut_probability"] == 35.0
    assert meeting["hold_probability"] == 60.0
    assert meeting["hike_probability"] == 5.0


def test_cme_fedwatch_signal_service_classifies_source_block() -> None:
    payload = CMEFedWatchSignalService(session=_BlockedFedWatchSession()).collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
    )

    assert payload["status"] == "source_restricted"
    assert payload["status_reason"] == "source_blocked"
    assert "403 Client Error" in payload["error"]


def test_cftc_signal_service_builds_positioning_signal() -> None:
    payload = CFTCCOTSignalService(session=_CftcSession()).collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
        previous_snapshot={"cftc_signals": {"signals": [{"signal_key": "gold_cot", "managed_money_net": 70000}]}},
    )

    assert payload["status"] == "ready"
    assert payload["signal_count"] >= 1
    gold_signal = next(item for item in payload["signals"] if item["signal_key"] == "gold_cot")
    assert gold_signal["managed_money_net"] == 75000
    assert gold_signal["managed_money_net_change"] == 5000
    assert gold_signal["bias"] == "long"
    assert gold_signal["producer_long"] == 38000
    assert gold_signal["producer_short"] == 90000
    assert gold_signal["producer_net"] == -52000
