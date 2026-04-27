# -*- coding: utf-8 -*-
"""Public read-only Polymarket data access with normalized event/market models."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

import requests


@dataclass(frozen=True)
class OutcomeQuote:
    name: str
    probability: float | None
    token_id: str | None = None


@dataclass
class PolymarketMarket:
    id: str
    slug: str
    question: str
    condition_id: str
    active: bool
    closed: bool
    archived: bool
    accepting_orders: bool | None
    start_date: str | None
    end_date: str | None
    volume: float | None
    volume_24hr: float | None
    liquidity: float | None
    open_interest: float | None
    best_bid: float | None
    best_ask: float | None
    last_trade_price: float | None
    event_slug: str
    event_title: str
    outcomes: tuple[OutcomeQuote, ...]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def probability_for(self, outcome_name: str) -> float | None:
        target = str(outcome_name or "").strip().lower()
        for outcome in self.outcomes:
            if outcome.name.strip().lower() == target:
                return outcome.probability
        return None

    def token_id_for(self, outcome_name: str) -> str | None:
        target = str(outcome_name or "").strip().lower()
        for outcome in self.outcomes:
            if outcome.name.strip().lower() == target:
                return outcome.token_id
        return None

    @property
    def yes_probability(self) -> float | None:
        return self.probability_for("yes")

    @property
    def midpoint(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0


@dataclass
class PolymarketEvent:
    id: str
    slug: str
    title: str
    description: str | None
    active: bool
    closed: bool
    start_date: str | None
    end_date: str | None
    liquidity: float | None
    volume: float | None
    volume_24hr: float | None
    open_interest: float | None
    markets: tuple[PolymarketMarket, ...]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def primary_market(self) -> PolymarketMarket | None:
        if not self.markets:
            return None

        def rank(market: PolymarketMarket) -> tuple[int, float, float, float]:
            live_score = int(market.active and not market.closed and market.accepting_orders is not False)
            return (
                live_score,
                market.volume_24hr or 0.0,
                market.volume or 0.0,
                market.liquidity or 0.0,
            )

        return max(self.markets, key=rank)


@dataclass(frozen=True)
class OrderLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    market_id: str
    token_id: str
    timestamp_ms: int | None
    tick_size: float | None
    min_order_size: float | None
    last_trade_price: float | None
    bids: tuple[OrderLevel, ...]
    asks: tuple[OrderLevel, ...]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


@dataclass(frozen=True)
class PolymarketEventQuery:
    limit: int = 20
    offset: int = 0
    active: bool | None = True
    closed: bool | None = False
    order: str | None = "volume_24hr"
    ascending: bool = False
    slug: str | None = None
    slug_contains: str | None = None
    title_contains: str | None = None
    tag_slug: str | None = None
    tag_id: int | None = None


class PolymarketClient:
    GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_BASE_URL = "https://clob.polymarket.com"
    DEFAULT_TIMEOUT_SECONDS = 10.0
    USER_AGENT = "overnight-news-handoff/1.0"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        gamma_base_url: str = GAMMA_BASE_URL,
        clob_base_url: str = CLOB_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session or requests.Session()
        self.gamma_base_url = str(gamma_base_url).rstrip("/")
        self.clob_base_url = str(clob_base_url).rstrip("/")
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def get_market(self, market_id: str | int) -> PolymarketMarket:
        payload = self._get_json(self.gamma_base_url, f"/markets/{market_id}")
        if not isinstance(payload, dict):
            raise RuntimeError("expected market payload to be an object")
        return self._parse_market(payload)

    def get_market_by_slug(self, slug: str) -> PolymarketMarket:
        payload = self._get_json(self.gamma_base_url, f"/markets/slug/{slug}")
        if not isinstance(payload, dict):
            raise RuntimeError("expected market payload to be an object")
        return self._parse_market(payload)

    def list_markets(self, *, params: dict[str, object] | None = None) -> list[PolymarketMarket]:
        payload = self._get_json(self.gamma_base_url, "/markets", params=params or {})
        if not isinstance(payload, list):
            raise RuntimeError("expected markets payload to be a list")
        return [self._parse_market(dict(item or {})) for item in payload if isinstance(item, Mapping)]

    def list_events(self, *, query: PolymarketEventQuery | None = None) -> list[PolymarketEvent]:
        resolved_query = query or PolymarketEventQuery()
        payload = self._get_json(
            self.gamma_base_url,
            "/events",
            params={
                "limit": resolved_query.limit,
                "offset": resolved_query.offset,
                "active": resolved_query.active,
                "closed": resolved_query.closed,
                "order": self._normalize_event_order(resolved_query.order),
                "ascending": resolved_query.ascending,
                "slug": resolved_query.slug,
                "tag_slug": resolved_query.tag_slug or resolved_query.slug_contains,
                "tag_id": resolved_query.tag_id,
            },
        )
        if not isinstance(payload, list):
            raise RuntimeError("expected events payload to be a list")
        events = [self._parse_event(dict(item or {})) for item in payload if isinstance(item, Mapping)]
        if resolved_query.slug_contains:
            needle = resolved_query.slug_contains.strip().lower()
            events = [
                event for event in events
                if needle in event.slug.lower() or needle in event.title.lower()
            ]
        if resolved_query.title_contains:
            needle = resolved_query.title_contains.strip().lower()
            events = [event for event in events if needle in event.title.lower()]
        return events

    def get_event_by_slug(self, slug: str) -> PolymarketEvent | None:
        payload = self._get_json(self.gamma_base_url, "/events", params={"slug": slug})
        if isinstance(payload, list):
            if not payload:
                return None
            first = payload[0]
            if not isinstance(first, Mapping):
                raise RuntimeError("expected event payload row to be an object")
            return self._parse_event(dict(first))
        if isinstance(payload, dict):
            return self._parse_event(payload)
        raise RuntimeError("expected event payload to be a list or object")

    def get_order_book(self, *, token_id: str) -> OrderBook:
        payload = self._get_json(self.clob_base_url, "/book", params={"token_id": token_id})
        if not isinstance(payload, dict):
            raise RuntimeError("expected order book payload to be an object")
        return self._parse_order_book(payload)

    def get_midpoint(self, *, token_id: str) -> float | None:
        payload = self._get_json(self.clob_base_url, "/midpoint", params={"token_id": token_id})
        if not isinstance(payload, dict):
            return None
        midpoint = payload.get("mid") or payload.get("midpoint")
        return self._to_float(midpoint)

    def _parse_event(self, raw_event: Mapping[str, Any]) -> PolymarketEvent:
        raw_markets = raw_event.get("markets")
        markets: tuple[PolymarketMarket, ...] = ()
        if isinstance(raw_markets, list):
            parsed_markets: list[PolymarketMarket] = []
            for item in raw_markets:
                if isinstance(item, Mapping):
                    parsed_markets.append(
                        self._parse_market(
                            dict(item),
                            fallback_event_slug=str(raw_event.get("slug", "")).strip(),
                            fallback_event_title=str(raw_event.get("title", "")).strip(),
                        )
                    )
            markets = tuple(parsed_markets)
        return PolymarketEvent(
            id=str(raw_event.get("id", "")).strip(),
            slug=str(raw_event.get("slug", "")).strip(),
            title=str(raw_event.get("title", "")).strip(),
            description=raw_event.get("description") if isinstance(raw_event.get("description"), str) else None,
            active=self._truthy(raw_event.get("active")),
            closed=self._truthy(raw_event.get("closed")),
            start_date=self._string_or_none(raw_event.get("startDate") or raw_event.get("start_date")),
            end_date=self._string_or_none(raw_event.get("endDate") or raw_event.get("end_date")),
            liquidity=self._to_float(raw_event.get("liquidity")),
            volume=self._to_float(raw_event.get("volume")),
            volume_24hr=self._to_float(raw_event.get("volume24hr") or raw_event.get("volume_24hr")),
            open_interest=self._to_float(raw_event.get("openInterest") or raw_event.get("open_interest")),
            markets=markets,
            raw=raw_event,
        )

    def _parse_market(
        self,
        raw_market: Mapping[str, Any],
        *,
        fallback_event_slug: str = "",
        fallback_event_title: str = "",
    ) -> PolymarketMarket:
        outcomes = self._json_list(raw_market.get("outcomes"), field_name="outcomes")
        prices = self._json_list(raw_market.get("outcomePrices"), field_name="outcomePrices")
        token_ids = self._json_list(raw_market.get("clobTokenIds"), field_name="clobTokenIds")
        normalized_outcomes: list[OutcomeQuote] = []
        size = max(len(outcomes), len(prices), len(token_ids))
        for index in range(size):
            outcome_name = str(outcomes[index]).strip() if index < len(outcomes) else f"Outcome {index + 1}"
            probability = self._to_float(prices[index]) if index < len(prices) else None
            token_id = str(token_ids[index]).strip() if index < len(token_ids) else None
            normalized_outcomes.append(
                OutcomeQuote(
                    name=outcome_name,
                    probability=probability,
                    token_id=token_id,
                )
            )
        return PolymarketMarket(
            id=str(raw_market.get("id", "")).strip(),
            slug=str(raw_market.get("slug", "")).strip(),
            question=str(raw_market.get("question", "")).strip(),
            condition_id=str(raw_market.get("conditionId", "") or raw_market.get("condition_id", "")).strip(),
            active=self._truthy(raw_market.get("active")),
            closed=self._truthy(raw_market.get("closed")),
            archived=self._truthy(raw_market.get("archived")),
            accepting_orders=raw_market.get("acceptingOrders") if isinstance(raw_market.get("acceptingOrders"), bool) else None,
            start_date=self._string_or_none(raw_market.get("startDate") or raw_market.get("start_date")),
            end_date=self._string_or_none(raw_market.get("endDate") or raw_market.get("end_date")),
            volume=self._to_float(raw_market.get("volumeNum") or raw_market.get("volume")),
            volume_24hr=self._to_float(raw_market.get("volume24hr") or raw_market.get("volume24hrClob") or raw_market.get("volume_24hr")),
            liquidity=self._to_float(raw_market.get("liquidityNum") or raw_market.get("liquidity")),
            open_interest=self._to_float(raw_market.get("openInterest") or raw_market.get("open_interest")),
            best_bid=self._to_float(raw_market.get("bestBid") or raw_market.get("best_bid")),
            best_ask=self._to_float(raw_market.get("bestAsk") or raw_market.get("best_ask")),
            last_trade_price=self._to_float(raw_market.get("lastTradePrice") or raw_market.get("last_trade_price")),
            event_slug=str(raw_market.get("eventSlug", "") or raw_market.get("event_slug", "")).strip() or fallback_event_slug,
            event_title=str(raw_market.get("eventTitle", "") or raw_market.get("event_title", "")).strip() or fallback_event_title,
            outcomes=tuple(normalized_outcomes),
            raw=raw_market,
        )

    def _parse_order_book(self, raw_book: Mapping[str, Any]) -> OrderBook:
        bids = self._parse_order_levels(raw_book.get("bids"), reverse=True)
        asks = self._parse_order_levels(raw_book.get("asks"), reverse=False)
        return OrderBook(
            market_id=str(raw_book.get("market", "")).strip(),
            token_id=str(raw_book.get("asset_id", "")).strip(),
            timestamp_ms=self._to_int(raw_book.get("timestamp")),
            tick_size=self._to_float(raw_book.get("tick_size")),
            min_order_size=self._to_float(raw_book.get("min_order_size")),
            last_trade_price=self._to_float(raw_book.get("last_trade_price")),
            bids=tuple(bids),
            asks=tuple(asks),
            raw=raw_book,
        )

    def _parse_order_levels(self, raw_levels: object, *, reverse: bool) -> list[OrderLevel]:
        if raw_levels is None:
            return []
        if not isinstance(raw_levels, list):
            raise RuntimeError("order book levels must be a list")
        parsed_levels: list[OrderLevel] = []
        for level in raw_levels:
            if not isinstance(level, Mapping):
                raise RuntimeError("order book entries must be objects")
            price = self._to_float(level.get("price"))
            size = self._to_float(level.get("size"))
            if price is None or size is None:
                continue
            parsed_levels.append(OrderLevel(price=price, size=size))
        return sorted(parsed_levels, key=lambda item: item.price, reverse=reverse)

    def _get_json(
        self,
        base_url: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
    ) -> Any:
        response = self.session.get(
            f"{base_url}{path}",
            params=params or None,
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": self.USER_AGENT,
            },
        )
        response.raise_for_status()
        return response.json()

    def _json_list(self, value: object, *, field_name: str) -> list[object]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid {field_name}: {text}") from exc
            if isinstance(decoded, list):
                return decoded
        raise RuntimeError(f"unexpected {field_name} type")

    def _normalize_event_order(self, order: str | None) -> str | None:
        if order is None:
            return None
        aliases = {
            "volume_24hr": "volume24hr",
            "start_date": "startDate",
            "end_date": "endDate",
            "closed_time": "closedTime",
        }
        return aliases.get(order, order)

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _string_or_none(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    def _to_float(self, value: Any) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
