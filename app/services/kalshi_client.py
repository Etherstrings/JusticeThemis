# -*- coding: utf-8 -*-
"""Public read-only Kalshi market data access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import requests


@dataclass
class KalshiMarket:
    ticker: str
    event_ticker: str
    status: str
    market_type: str
    title: str
    subtitle: str | None
    yes_sub_title: str | None
    no_sub_title: str | None
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    last_price: float | None
    volume: float | None
    volume_24h: float | None
    open_interest: float | None
    liquidity: float | None
    strike_type: str | None
    floor_strike: float | None
    open_time: str | None
    close_time: str | None
    expiration_time: str | None
    rules_primary: str | None
    rules_secondary: str | None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def midpoint(self) -> float | None:
        if self.yes_bid is None or self.yes_ask is None:
            return None
        return (self.yes_bid + self.yes_ask) / 2.0

    @property
    def yes_probability(self) -> float | None:
        return self.midpoint if self.midpoint is not None else self.last_price


@dataclass
class KalshiEvent:
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str | None
    category: str | None
    strike_date: str | None
    mutually_exclusive: bool | None
    available_on_brokers: bool | None
    markets: tuple[KalshiMarket, ...]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def most_active_market(self) -> KalshiMarket | None:
        if not self.markets:
            return None
        return max(
            self.markets,
            key=lambda market: (
                market.volume_24h or 0.0,
                market.volume or 0.0,
                market.open_interest or 0.0,
            ),
        )


@dataclass(frozen=True)
class KalshiOrderLevel:
    price: float
    size: float


@dataclass
class KalshiOrderBook:
    market_ticker: str
    yes_bids: tuple[KalshiOrderLevel, ...]
    no_bids: tuple[KalshiOrderLevel, ...]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def best_yes_bid(self) -> float | None:
        return self.yes_bids[0].price if self.yes_bids else None

    @property
    def best_no_bid(self) -> float | None:
        return self.no_bids[0].price if self.no_bids else None

    @property
    def best_yes_ask(self) -> float | None:
        if self.best_no_bid is None:
            return None
        return 1.0 - self.best_no_bid

    @property
    def yes_spread(self) -> float | None:
        if self.best_yes_bid is None or self.best_yes_ask is None:
            return None
        return self.best_yes_ask - self.best_yes_bid

    @property
    def midpoint(self) -> float | None:
        if self.best_yes_bid is None or self.best_yes_ask is None:
            return None
        return (self.best_yes_bid + self.best_yes_ask) / 2.0


class KalshiClient:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    DEFAULT_TIMEOUT_SECONDS = 10.0
    USER_AGENT = "overnight-news-handoff/1.0"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        base_url: str = BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session or requests.Session()
        self.base_url = str(base_url).rstrip("/")
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def get_market(self, ticker: str) -> KalshiMarket:
        payload = self._get_json(f"/markets/{ticker}")
        market = payload.get("market") if isinstance(payload, Mapping) else None
        if not isinstance(market, Mapping):
            raise RuntimeError("expected Kalshi payload.market to be an object")
        return self._parse_market(market)

    def list_markets(self, *, params: dict[str, object] | None = None) -> list[KalshiMarket]:
        payload = self._get_json("/markets", params=params or {})
        markets = payload.get("markets") if isinstance(payload, Mapping) else None
        if not isinstance(markets, list):
            raise RuntimeError("expected Kalshi payload.markets to be a list")
        return [self._parse_market(item) for item in markets if isinstance(item, Mapping)]

    def get_event(self, event_ticker: str) -> KalshiEvent:
        payload = self._get_json(f"/events/{event_ticker}")
        raw_event = payload.get("event") if isinstance(payload, Mapping) else None
        raw_markets = payload.get("markets") if isinstance(payload, Mapping) else None
        if not isinstance(raw_event, Mapping) or not isinstance(raw_markets, list):
            raise RuntimeError("expected Kalshi event payload")
        return KalshiEvent(
            event_ticker=str(raw_event.get("event_ticker", "")).strip(),
            series_ticker=str(raw_event.get("series_ticker", "")).strip(),
            title=str(raw_event.get("title", "")).strip(),
            subtitle=self._string_or_none(raw_event.get("sub_title")),
            category=self._string_or_none(raw_event.get("category")),
            strike_date=self._string_or_none(raw_event.get("strike_date")),
            mutually_exclusive=bool(raw_event.get("mutually_exclusive")) if raw_event.get("mutually_exclusive") is not None else None,
            available_on_brokers=bool(raw_event.get("available_on_brokers")) if raw_event.get("available_on_brokers") is not None else None,
            markets=tuple(self._parse_market(item) for item in raw_markets if isinstance(item, Mapping)),
            raw=raw_event,
        )

    def get_order_book(self, ticker: str, *, depth: int = 10) -> KalshiOrderBook:
        payload = self._get_json(f"/markets/{ticker}/orderbook", params={"depth": depth})
        if not isinstance(payload, Mapping):
            raise RuntimeError("expected Kalshi orderbook payload")
        orderbook_fp = payload.get("orderbook_fp")
        orderbook = payload.get("orderbook")
        if isinstance(orderbook_fp, Mapping):
            yes_levels = self._parse_orderbook_side(orderbook_fp.get("yes_dollars"))
            no_levels = self._parse_orderbook_side(orderbook_fp.get("no_dollars"))
        elif isinstance(orderbook, Mapping):
            yes_levels = self._parse_orderbook_side(orderbook.get("yes_dollars") or orderbook.get("yes"), cents_fallback=True)
            no_levels = self._parse_orderbook_side(orderbook.get("no_dollars") or orderbook.get("no"), cents_fallback=True)
        else:
            raise RuntimeError("expected Kalshi orderbook or orderbook_fp payload")
        return KalshiOrderBook(
            market_ticker=ticker,
            yes_bids=yes_levels,
            no_bids=no_levels,
            raw=payload,
        )

    def _parse_market(self, raw: Mapping[str, Any]) -> KalshiMarket:
        return KalshiMarket(
            ticker=str(raw.get("ticker", "")).strip(),
            event_ticker=str(raw.get("event_ticker", "")).strip(),
            status=str(raw.get("status", "")).strip(),
            market_type=str(raw.get("market_type", "")).strip(),
            title=str(raw.get("title", "")).strip(),
            subtitle=self._string_or_none(raw.get("subtitle")),
            yes_sub_title=self._string_or_none(raw.get("yes_sub_title")),
            no_sub_title=self._string_or_none(raw.get("no_sub_title")),
            yes_bid=self._probability_from_fields(raw, "yes_bid"),
            yes_ask=self._probability_from_fields(raw, "yes_ask"),
            no_bid=self._probability_from_fields(raw, "no_bid"),
            no_ask=self._probability_from_fields(raw, "no_ask"),
            last_price=self._probability_from_fields(raw, "last_price"),
            volume=self._to_float(raw.get("volume")) or self._to_float(raw.get("volume_fp")),
            volume_24h=self._to_float(raw.get("volume_24h")) or self._to_float(raw.get("volume_24h_fp")),
            open_interest=self._to_float(raw.get("open_interest")) or self._to_float(raw.get("open_interest_fp")),
            liquidity=self._to_float(raw.get("liquidity")) or self._to_float(raw.get("liquidity_dollars")),
            strike_type=self._string_or_none(raw.get("strike_type")),
            floor_strike=self._to_float(raw.get("floor_strike")),
            open_time=self._string_or_none(raw.get("open_time")),
            close_time=self._string_or_none(raw.get("close_time")),
            expiration_time=self._string_or_none(raw.get("expiration_time")),
            rules_primary=self._string_or_none(raw.get("rules_primary")),
            rules_secondary=self._string_or_none(raw.get("rules_secondary")),
            raw=raw,
        )

    def _parse_orderbook_side(
        self,
        raw_levels: object,
        *,
        cents_fallback: bool = False,
    ) -> tuple[KalshiOrderLevel, ...]:
        if raw_levels is None:
            return ()
        if not isinstance(raw_levels, list):
            raise RuntimeError("expected Kalshi orderbook side to be a list")
        levels: list[KalshiOrderLevel] = []
        for raw_level in raw_levels:
            if not isinstance(raw_level, (list, tuple)) or len(raw_level) < 2:
                raise RuntimeError("expected Kalshi orderbook level with price and size")
            price_raw, size_raw = raw_level[0], raw_level[1]
            price = (float(price_raw) / 100.0) if cents_fallback and isinstance(price_raw, (int, float)) else self._to_float(price_raw)
            size = self._to_float(size_raw)
            if price is None or size is None:
                continue
            levels.append(KalshiOrderLevel(price=price, size=size))
        return tuple(sorted(levels, key=lambda level: level.price, reverse=True))

    def _get_json(self, path: str, *, params: dict[str, object] | None = None) -> Any:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params or None,
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": self.USER_AGENT,
            },
        )
        response.raise_for_status()
        return response.json()

    def _cent_probability(self, value: object) -> float | None:
        raw = self._to_float(value)
        if raw is None:
            return None
        return raw / 100.0

    def _probability_from_fields(self, raw: Mapping[str, Any], base_name: str) -> float | None:
        direct_dollars = self._to_float(raw.get(f"{base_name}_dollars"))
        if direct_dollars is not None:
            return direct_dollars
        return self._cent_probability(raw.get(base_name))

    def _to_float(self, value: object) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _string_or_none(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None
