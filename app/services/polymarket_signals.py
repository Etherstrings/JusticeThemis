# -*- coding: utf-8 -*-
"""Normalize Polymarket prediction-market signals for market snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

from app.services.polymarket_client import OrderBook, PolymarketClient, PolymarketEventQuery, PolymarketMarket


logger = logging.getLogger(__name__)


def polymarket_enabled_from_env() -> bool:
    raw_value = str(os.environ.get("POLYMARKET_ENABLED", "true")).strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class PolymarketSignalDefinition:
    signal_key: str
    label: str
    bucket: str = ""
    event_slug: str = ""
    event_slug_contains: str = ""
    event_title_contains: str = ""
    market_slug: str = ""
    market_id: str = ""
    market_question_contains: str = ""
    outcome: str = "Yes"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PolymarketSignalDefinition":
        signal_key = str(payload.get("signal_key", "")).strip()
        label = str(payload.get("label", "")).strip()
        if not signal_key:
            raise ValueError("signal_key is required for Polymarket signal definitions")
        return cls(
            signal_key=signal_key,
            label=label or signal_key.replace("_", " ").strip() or signal_key,
            bucket=str(payload.get("bucket", "")).strip(),
            event_slug=str(payload.get("event_slug", "")).strip(),
            event_slug_contains=str(payload.get("event_slug_contains", "")).strip(),
            event_title_contains=str(payload.get("event_title_contains", "")).strip(),
            market_slug=str(payload.get("market_slug", "")).strip(),
            market_id=str(payload.get("market_id", "")).strip(),
            market_question_contains=str(payload.get("market_question_contains", "")).strip(),
            outcome=str(payload.get("outcome", "Yes")).strip() or "Yes",
        )


class PolymarketSignalService:
    PROVIDER_NAME = "Polymarket"
    PROVIDER_URL = "https://polymarket.com"
    ENV_NAME = "POLYMARKET_SIGNAL_CONFIG_JSON"
    DEFAULT_DEFINITIONS = [
        PolymarketSignalDefinition(
            signal_key="fed_hold_next_meeting",
            label="Fed按兵不动",
            bucket="rates",
            event_title_contains="Fed decision",
            market_question_contains="no change in fed interest rates",
            outcome="Yes",
        ),
        PolymarketSignalDefinition(
            signal_key="iran_ceasefire_extension",
            label="美伊停火延续",
            bucket="geopolitics",
            event_title_contains="Iran ceasefire",
            outcome="Yes",
        ),
        PolymarketSignalDefinition(
            signal_key="bitcoin_150k",
            label="比特币冲150k",
            bucket="crypto",
            event_title_contains="Bitcoin hit $150k",
            outcome="Yes",
        ),
    ]

    def __init__(
        self,
        *,
        client: PolymarketClient | None = None,
        definitions: list[PolymarketSignalDefinition] | None = None,
        enabled: bool = True,
    ) -> None:
        self.client = client or PolymarketClient()
        self.definitions = list(definitions or [])
        self.enabled = bool(enabled)

    @classmethod
    def from_environment(cls) -> "PolymarketSignalService":
        raw_config = str(os.environ.get(cls.ENV_NAME, "")).strip()
        definitions: list[PolymarketSignalDefinition] = list(cls.DEFAULT_DEFINITIONS)
        if raw_config:
            parsed = json.loads(raw_config)
            if not isinstance(parsed, list):
                raise ValueError(f"{cls.ENV_NAME} must be a JSON array")
            definitions = [PolymarketSignalDefinition.from_mapping(dict(item or {})) for item in parsed]
        return cls(
            definitions=definitions,
            enabled=polymarket_enabled_from_env(),
        )

    def collect(
        self,
        *,
        analysis_date: str,
        market_date: str,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        base_payload = {
            "provider_name": self.PROVIDER_NAME,
            "provider_url": self.PROVIDER_URL,
            "analysis_date": str(analysis_date or "").strip(),
            "market_date": str(market_date or "").strip(),
            "generated_at": generated_at,
            "signals": [],
            "signal_count": 0,
            "error_count": 0,
            "errors": [],
        }
        if not self.enabled:
            return {**base_payload, "status": "disabled", "status_reason": "disabled_by_env"}
        if not self.definitions:
            return {**base_payload, "status": "unconfigured", "status_reason": "missing_signal_definitions"}

        previous_probabilities = self._previous_probabilities(previous_snapshot)
        signals: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for definition in self.definitions:
            try:
                market = self._resolve_market(definition)
                signal = self._build_signal(
                    definition=definition,
                    market=market,
                    previous_probability=previous_probabilities.get(definition.signal_key),
                )
                signals.append(signal)
            except Exception as exc:
                logger.warning("Failed to resolve Polymarket signal %s: %s", definition.signal_key, exc)
                errors.append({"signal_key": definition.signal_key, "reason": str(exc)})

        return {
            **base_payload,
            "status": "ready" if signals else "error",
            "status_reason": "ok" if signals else "signal_resolution_failed",
            "signals": signals,
            "signal_count": len(signals),
            "error_count": len(errors),
            "errors": errors,
            "headline": self._headline(signals),
        }

    def _resolve_market(self, definition: PolymarketSignalDefinition) -> PolymarketMarket:
        if definition.market_slug:
            return self.client.get_market_by_slug(definition.market_slug)
        if definition.market_id:
            return self.client.get_market(definition.market_id)
        if definition.event_slug:
            event = self.client.get_event_by_slug(definition.event_slug)
            if event is None:
                raise RuntimeError(f"event not found: {definition.event_slug}")
            selected = self._select_market_from_event(
                markets=list(event.markets),
                definition=definition,
            )
            if selected is None:
                raise RuntimeError(f"no matching market found for event_slug={definition.event_slug}")
            return selected
        if definition.event_slug_contains or definition.event_title_contains:
            query = PolymarketEventQuery(
                limit=20,
                active=True,
                closed=False,
                order="volume_24hr",
                ascending=False,
                slug_contains=definition.event_slug_contains or None,
                title_contains=definition.event_title_contains or None,
            )
            events = self.client.list_events(query=query)
            if not events:
                raise RuntimeError("no matching event found")
            ranked_events = sorted(
                events,
                key=lambda event: (
                    int(event.active and not event.closed),
                    event.volume_24hr or 0.0,
                    event.volume or 0.0,
                    event.liquidity or 0.0,
                ),
                reverse=True,
            )
            for event in ranked_events:
                selected = self._select_market_from_event(
                    markets=list(event.markets),
                    definition=definition,
                )
                if selected is not None:
                    return selected
            raise RuntimeError("no matching market found in candidate events")
        raise ValueError("one of market_slug, market_id, or event_slug is required")

    def _select_market_from_event(
        self,
        *,
        markets: list[PolymarketMarket],
        definition: PolymarketSignalDefinition,
    ) -> PolymarketMarket | None:
        if definition.market_slug:
            for market in markets:
                if market.slug == definition.market_slug:
                    return market
        if definition.market_question_contains:
            needle = definition.market_question_contains.lower()
            for market in markets:
                if needle in market.question.lower():
                    return market
        if not markets:
            return None
        return max(
            markets,
            key=lambda market: (
                int(market.active and not market.closed and market.accepting_orders is not False),
                market.volume_24hr or 0.0,
                market.volume or 0.0,
                market.liquidity or 0.0,
            ),
        )

    def _build_signal(
        self,
        *,
        definition: PolymarketSignalDefinition,
        market: PolymarketMarket,
        previous_probability: float | None,
    ) -> dict[str, Any]:
        token_id = market.token_id_for(definition.outcome) or ""
        book = self._safe_order_book(token_id=token_id)
        market_probability = market.probability_for(definition.outcome)
        book_midpoint = None
        if book is not None and book.best_bid is not None and book.best_ask is not None:
            book_midpoint = (book.best_bid + book.best_ask) / 2.0
        elif token_id:
            book_midpoint = self.client.get_midpoint(token_id=token_id)
        signal_probability = book_midpoint if book_midpoint is not None else market_probability
        if signal_probability is None:
            raise RuntimeError("market probability is missing")
        probability_pct = round(signal_probability * 100.0, 2)
        previous_probability_pct = round(previous_probability * 100.0, 2) if previous_probability is not None else None
        delta_pct_points = (
            round(probability_pct - previous_probability_pct, 2)
            if previous_probability_pct is not None
            else None
        )
        best_bid_pct = round(book.best_bid * 100.0, 2) if book is not None and book.best_bid is not None else None
        best_ask_pct = round(book.best_ask * 100.0, 2) if book is not None and book.best_ask is not None else None
        spread_pct_points = (
            round((book.spread or 0.0) * 100.0, 2)
            if book is not None and book.spread is not None
            else None
        )
        market_probability_pct = round(market_probability * 100.0, 2) if market_probability is not None else None
        midpoint_probability_pct = round(book_midpoint * 100.0, 2) if book_midpoint is not None else None
        last_trade_probability_pct = (
            round(market.last_trade_price * 100.0, 2)
            if market.last_trade_price is not None
            else None
        )
        return {
            "signal_key": definition.signal_key,
            "label": definition.label,
            "bucket": definition.bucket,
            "status": "ready",
            "question": market.question,
            "event_title": market.event_title,
            "event_slug": market.event_slug,
            "market_slug": market.slug,
            "market_id": market.id,
            "condition_id": market.condition_id,
            "target_outcome": definition.outcome,
            "token_id": token_id or None,
            "probability": probability_pct,
            "previous_probability": previous_probability_pct,
            "delta_pct_points": delta_pct_points,
            "market_implied_probability": market_probability_pct,
            "midpoint_probability": midpoint_probability_pct,
            "best_bid_probability": best_bid_pct,
            "best_ask_probability": best_ask_pct,
            "spread_pct_points": spread_pct_points,
            "last_trade_probability": last_trade_probability_pct,
            "volume": market.volume,
            "volume_24hr": market.volume_24hr,
            "liquidity": market.liquidity,
            "open_interest": market.open_interest,
            "accepting_orders": market.accepting_orders,
            "active": market.active,
            "closed": market.closed,
            "archived": market.archived,
            "start_date": market.start_date,
            "end_date": market.end_date,
            "source_url": self._source_url(event_slug=market.event_slug, market_slug=market.slug),
            "order_book": self._serialize_order_book(book),
            "price_source": "orderbook_midpoint" if book_midpoint is not None else "market_outcome_price",
            "provenance": {
                "gamma_market_slug": market.slug,
                "gamma_market_id": market.id,
                "clob_token_id": token_id or None,
            },
        }

    def _safe_order_book(self, *, token_id: str) -> OrderBook | None:
        if not token_id:
            return None
        try:
            return self.client.get_order_book(token_id=token_id)
        except Exception as exc:
            logger.warning("Failed to fetch Polymarket order book for %s: %s", token_id, exc)
            return None

    def _serialize_order_book(self, book: OrderBook | None) -> dict[str, Any] | None:
        if book is None:
            return None
        return {
            "market_id": book.market_id,
            "token_id": book.token_id,
            "timestamp_ms": book.timestamp_ms,
            "tick_size": book.tick_size,
            "min_order_size": book.min_order_size,
            "last_trade_price": round(book.last_trade_price * 100.0, 2) if book.last_trade_price is not None else None,
            "best_bid": round(book.best_bid * 100.0, 2) if book.best_bid is not None else None,
            "best_ask": round(book.best_ask * 100.0, 2) if book.best_ask is not None else None,
            "spread_pct_points": round(book.spread * 100.0, 2) if book.spread is not None else None,
            "bid_levels": [
                {"price": round(level.price * 100.0, 2), "size": level.size}
                for level in list(book.bids)[:3]
            ],
            "ask_levels": [
                {"price": round(level.price * 100.0, 2), "size": level.size}
                for level in list(book.asks)[:3]
            ],
        }

    def _previous_probabilities(self, snapshot: dict[str, Any] | None) -> dict[str, float]:
        payload = dict(snapshot or {})
        prediction_markets = dict(payload.get("prediction_markets", {}) or {})
        signals = list(prediction_markets.get("signals", []) or [])
        probabilities: dict[str, float] = {}
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            signal_key = str(signal.get("signal_key", "")).strip()
            probability = self._to_float(signal.get("probability"))
            if signal_key and probability is not None:
                probabilities[signal_key] = probability / 100.0
        return probabilities

    def _headline(self, signals: list[dict[str, Any]]) -> str:
        ranked = sorted(
            [dict(item or {}) for item in signals if isinstance(item, dict)],
            key=lambda item: abs(float(item.get("delta_pct_points", 0.0) or 0.0)),
            reverse=True,
        )
        parts: list[str] = []
        for item in ranked[:2]:
            label = str(item.get("label", "")).strip() or str(item.get("question", "")).strip()
            probability = item.get("probability")
            if not label or probability is None:
                continue
            delta = item.get("delta_pct_points")
            delta_text = f" ({float(delta):+.1f}pct)" if delta is not None else ""
            parts.append(f"{label} {float(probability):.1f}%{delta_text}")
        return "；".join(parts)

    def _source_url(self, *, event_slug: str, market_slug: str) -> str:
        if event_slug:
            return f"{self.PROVIDER_URL}/event/{event_slug}"
        if market_slug:
            return f"{self.PROVIDER_URL}/event/{market_slug}"
        return self.PROVIDER_URL

    def _to_float(self, value: Any) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
