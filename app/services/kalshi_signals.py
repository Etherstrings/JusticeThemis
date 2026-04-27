# -*- coding: utf-8 -*-
"""Normalize Kalshi event probabilities into market snapshot signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

from app.services.kalshi_client import KalshiClient, KalshiMarket


logger = logging.getLogger(__name__)


def kalshi_enabled_from_env() -> bool:
    raw_value = str(os.environ.get("KALSHI_ENABLED", "true")).strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class KalshiSignalDefinition:
    signal_key: str
    label: str
    bucket: str = ""
    event_ticker: str = ""
    market_ticker: str = ""
    title_contains: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "KalshiSignalDefinition":
        signal_key = str(payload.get("signal_key", "")).strip()
        label = str(payload.get("label", "")).strip()
        if not signal_key:
            raise ValueError("signal_key is required for Kalshi signal definitions")
        return cls(
            signal_key=signal_key,
            label=label or signal_key.replace("_", " ").strip() or signal_key,
            bucket=str(payload.get("bucket", "")).strip(),
            event_ticker=str(payload.get("event_ticker", "")).strip(),
            market_ticker=str(payload.get("market_ticker", "")).strip(),
            title_contains=str(payload.get("title_contains", "")).strip(),
        )


class KalshiSignalService:
    PROVIDER_NAME = "Kalshi"
    PROVIDER_URL = "https://kalshi.com"
    ENV_NAME = "KALSHI_SIGNAL_CONFIG_JSON"

    def __init__(
        self,
        *,
        client: KalshiClient | None = None,
        definitions: list[KalshiSignalDefinition] | None = None,
        enabled: bool = True,
    ) -> None:
        self.client = client or KalshiClient()
        self.definitions = list(definitions or [])
        self.enabled = bool(enabled)

    @classmethod
    def from_environment(cls) -> "KalshiSignalService":
        raw_config = str(os.environ.get(cls.ENV_NAME, "")).strip()
        definitions: list[KalshiSignalDefinition] = []
        if raw_config:
            parsed = json.loads(raw_config)
            if not isinstance(parsed, list):
                raise ValueError(f"{cls.ENV_NAME} must be a JSON array")
            definitions = [KalshiSignalDefinition.from_mapping(dict(item or {})) for item in parsed]
        return cls(definitions=definitions, enabled=kalshi_enabled_from_env())

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
                book = self._safe_order_book(market.ticker)
                signal = self._build_signal(
                    definition=definition,
                    market=market,
                    previous_probability=previous_probabilities.get(definition.signal_key),
                    orderbook=book,
                )
                signals.append(signal)
            except Exception as exc:
                logger.warning("Failed to resolve Kalshi signal %s: %s", definition.signal_key, exc)
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

    def _resolve_market(self, definition: KalshiSignalDefinition) -> KalshiMarket:
        if definition.market_ticker:
            return self.client.get_market(definition.market_ticker)
        if not definition.event_ticker:
            raise ValueError("event_ticker or market_ticker is required")
        event = self.client.get_event(definition.event_ticker)
        markets = list(event.markets)
        if definition.title_contains:
            needle = definition.title_contains.lower()
            markets = [market for market in markets if needle in market.title.lower()]
        if not markets:
            raise RuntimeError(f"no matching Kalshi market for {definition.event_ticker}")
        return max(
            markets,
            key=lambda market: (
                market.volume_24h or 0.0,
                market.volume or 0.0,
                market.open_interest or 0.0,
            ),
        )

    def _safe_order_book(self, ticker: str) -> dict[str, Any] | None:
        try:
            book = self.client.get_order_book(ticker)
        except Exception as exc:
            logger.warning("Failed to fetch Kalshi order book for %s: %s", ticker, exc)
            return None
        return {
            "best_yes_bid": round(book.best_yes_bid * 100.0, 2) if book.best_yes_bid is not None else None,
            "best_yes_ask": round(book.best_yes_ask * 100.0, 2) if book.best_yes_ask is not None else None,
            "yes_spread_pct_points": round(book.yes_spread * 100.0, 2) if book.yes_spread is not None else None,
            "midpoint_probability": round(book.midpoint * 100.0, 2) if book.midpoint is not None else None,
            "yes_levels": [{"price": round(level.price * 100.0, 2), "size": level.size} for level in list(book.yes_bids)[:3]],
            "no_levels": [{"price": round(level.price * 100.0, 2), "size": level.size} for level in list(book.no_bids)[:3]],
        }

    def _build_signal(
        self,
        *,
        definition: KalshiSignalDefinition,
        market: KalshiMarket,
        previous_probability: float | None,
        orderbook: dict[str, Any] | None,
    ) -> dict[str, Any]:
        probability = market.yes_probability
        if probability is None and orderbook is not None:
            midpoint_value = self._to_float(orderbook.get("midpoint_probability"))
            probability = midpoint_value / 100.0 if midpoint_value is not None else None
        if probability is None:
            raise RuntimeError("Kalshi market probability is missing")
        probability_pct = round(probability * 100.0, 2)
        previous_probability_pct = round(previous_probability * 100.0, 2) if previous_probability is not None else None
        delta_pct_points = (
            round(probability_pct - previous_probability_pct, 2)
            if previous_probability_pct is not None
            else None
        )
        return {
            "signal_key": definition.signal_key,
            "label": definition.label,
            "bucket": definition.bucket,
            "status": "ready",
            "market_ticker": market.ticker,
            "event_ticker": market.event_ticker,
            "question": market.title,
            "probability": probability_pct,
            "previous_probability": previous_probability_pct,
            "delta_pct_points": delta_pct_points,
            "yes_bid_probability": round(market.yes_bid * 100.0, 2) if market.yes_bid is not None else None,
            "yes_ask_probability": round(market.yes_ask * 100.0, 2) if market.yes_ask is not None else None,
            "midpoint_probability": round(market.midpoint * 100.0, 2) if market.midpoint is not None else None,
            "last_trade_probability": round(market.last_price * 100.0, 2) if market.last_price is not None else None,
            "volume": market.volume,
            "volume_24h": market.volume_24h,
            "open_interest": market.open_interest,
            "liquidity": market.liquidity,
            "close_time": market.close_time,
            "expiration_time": market.expiration_time,
            "rules_primary": market.rules_primary,
            "rules_secondary": market.rules_secondary,
            "source_url": f"{self.PROVIDER_URL}/events/{market.event_ticker}",
            "order_book": orderbook,
            "price_source": "midpoint" if market.midpoint is not None else "last_price",
        }

    def _previous_probabilities(self, snapshot: dict[str, Any] | None) -> dict[str, float]:
        payload = dict(snapshot or {})
        section = dict(payload.get("kalshi_signals", {}) or {})
        signals = list(section.get("signals", []) or [])
        previous: dict[str, float] = {}
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            signal_key = str(signal.get("signal_key", "")).strip()
            probability = self._to_float(signal.get("probability"))
            if signal_key and probability is not None:
                previous[signal_key] = probability / 100.0
        return previous

    def _headline(self, signals: list[dict[str, Any]]) -> str:
        ranked = sorted(signals, key=lambda item: abs(float(item.get("delta_pct_points", 0.0) or 0.0)), reverse=True)
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

    def _to_float(self, value: Any) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
