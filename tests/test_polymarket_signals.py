# -*- coding: utf-8 -*-
"""Tests for Polymarket client normalization and signal building."""

from __future__ import annotations

import json

from app.services.polymarket_client import (
    OrderBook,
    OrderLevel,
    OutcomeQuote,
    PolymarketClient,
    PolymarketEvent,
    PolymarketMarket,
)
from app.services.polymarket_signals import PolymarketSignalDefinition, PolymarketSignalService


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, params: dict[str, object] | None = None, timeout: float, headers: dict[str, str]) -> FakeResponse:
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers})
        if url.endswith("/events"):
            return FakeResponse(
                [
                    {
                        "id": "event-1",
                        "slug": "fed-june-decision",
                        "title": "Fed June Decision",
                        "active": True,
                        "closed": False,
                        "liquidity": "300000",
                        "volume": "500000",
                        "volume24hr": "90000",
                        "openInterest": "110000",
                        "markets": [
                            {
                                "id": "market-old",
                                "slug": "fed-june-old",
                                "question": "Old series",
                                "conditionId": "cond-old",
                                "active": False,
                                "closed": True,
                                "volume": "1000000",
                                "volume24hr": "1000",
                                "liquidity": "1000",
                                "outcomes": json.dumps(["Yes", "No"]),
                                "outcomePrices": json.dumps(["0.20", "0.80"]),
                                "clobTokenIds": json.dumps(["old-yes", "old-no"]),
                            },
                            {
                                "id": "market-live",
                                "slug": "fed-june-live",
                                "question": "Will the Fed cut by June?",
                                "conditionId": "cond-live",
                                "active": True,
                                "closed": False,
                                "acceptingOrders": True,
                                "volume": "450000",
                                "volume24hr": "88000",
                                "liquidity": "220000",
                                "bestBid": "0.61",
                                "bestAsk": "0.63",
                                "lastTradePrice": "0.62",
                                "eventSlug": "fed-june-decision",
                                "eventTitle": "Fed June Decision",
                                "outcomes": json.dumps(["Yes", "No"]),
                                "outcomePrices": json.dumps(["0.62", "0.38"]),
                                "clobTokenIds": json.dumps(["yes-token", "no-token"]),
                            },
                        ],
                    }
                ]
            )
        if url.endswith("/book"):
            return FakeResponse(
                {
                    "market": "market-live",
                    "asset_id": "yes-token",
                    "timestamp": 1710000000000,
                    "tick_size": "0.01",
                    "min_order_size": "5",
                    "last_trade_price": "0.62",
                    "bids": [{"price": "0.61", "size": "1200"}],
                    "asks": [{"price": "0.63", "size": "950"}],
                }
            )
        if url.endswith("/midpoint"):
            return FakeResponse({"mid": "0.62"})
        raise AssertionError(f"unexpected url: {url}")


class FakePolymarketSignalClient:
    def __init__(self) -> None:
        self.requested_event_slugs: list[str] = []
        self.requested_token_ids: list[str] = []

    def get_event_by_slug(self, slug: str) -> PolymarketEvent | None:
        self.requested_event_slugs.append(slug)
        return PolymarketEvent(
            id="event-1",
            slug=slug,
            title="Fed June Decision",
            description=None,
            active=True,
            closed=False,
            start_date=None,
            end_date="2026-06-18T18:00:00Z",
            liquidity=300000.0,
            volume=500000.0,
            volume_24hr=90000.0,
            open_interest=110000.0,
            markets=(
                PolymarketMarket(
                    id="market-live",
                    slug="fed-june-live",
                    question="Will the Fed cut by June?",
                    condition_id="cond-live",
                    active=True,
                    closed=False,
                    archived=False,
                    accepting_orders=True,
                    start_date=None,
                    end_date="2026-06-18T18:00:00Z",
                    volume=450000.0,
                    volume_24hr=88000.0,
                    liquidity=220000.0,
                    open_interest=110000.0,
                    best_bid=0.61,
                    best_ask=0.63,
                    last_trade_price=0.62,
                    event_slug=slug,
                    event_title="Fed June Decision",
                    outcomes=(
                        OutcomeQuote(name="Yes", probability=0.62, token_id="yes-token"),
                        OutcomeQuote(name="No", probability=0.38, token_id="no-token"),
                    ),
                ),
            ),
        )

    def get_order_book(self, *, token_id: str) -> OrderBook:
        self.requested_token_ids.append(token_id)
        return OrderBook(
            market_id="market-live",
            token_id=token_id,
            timestamp_ms=1710000000000,
            tick_size=0.01,
            min_order_size=5.0,
            last_trade_price=0.62,
            bids=(OrderLevel(price=0.61, size=1200.0),),
            asks=(OrderLevel(price=0.63, size=950.0),),
        )

    def get_midpoint(self, *, token_id: str) -> float | None:
        self.requested_token_ids.append(f"mid:{token_id}")
        return 0.62


def test_polymarket_client_parses_event_and_primary_market_like_digital_oracle() -> None:
    client = PolymarketClient(session=FakeSession())

    event = client.get_event_by_slug("fed-june-decision")

    assert event is not None
    assert event.slug == "fed-june-decision"
    assert len(event.markets) == 2
    primary_market = event.primary_market()
    assert primary_market is not None
    assert primary_market.slug == "fed-june-live"
    assert primary_market.yes_probability == 0.62
    assert primary_market.midpoint == 0.62


def test_polymarket_signal_service_builds_signal_with_order_book_context() -> None:
    client = FakePolymarketSignalClient()
    service = PolymarketSignalService(
        client=client,
        definitions=[
            PolymarketSignalDefinition(
                signal_key="fed_cut_june",
                label="6月前降息预期",
                event_slug="fed-june-decision",
                market_question_contains="cut by june",
                bucket="macro_rates",
                outcome="Yes",
            )
        ],
    )

    payload = service.collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
        previous_snapshot={
            "prediction_markets": {
                "signals": [
                    {"signal_key": "fed_cut_june", "probability": 58.0}
                ]
            }
        },
    )

    assert payload["status"] == "ready"
    assert payload["signal_count"] == 1
    assert client.requested_event_slugs == ["fed-june-decision"]
    signal = payload["signals"][0]
    assert signal["signal_key"] == "fed_cut_june"
    assert signal["probability"] == 62.0
    assert signal["market_implied_probability"] == 62.0
    assert signal["midpoint_probability"] == 62.0
    assert signal["best_bid_probability"] == 61.0
    assert signal["best_ask_probability"] == 63.0
    assert signal["spread_pct_points"] == 2.0
    assert signal["delta_pct_points"] == 4.0
    assert signal["price_source"] == "orderbook_midpoint"
    assert signal["order_book"]["best_bid"] == 61.0
    assert signal["source_url"] == "https://polymarket.com/event/fed-june-decision"


def test_polymarket_signal_service_returns_unconfigured_when_no_definitions() -> None:
    payload = PolymarketSignalService(client=FakePolymarketSignalClient(), definitions=[]).collect(
        analysis_date="2026-04-09",
        market_date="2026-04-08",
    )

    assert payload["status"] == "unconfigured"
    assert payload["signal_count"] == 0
