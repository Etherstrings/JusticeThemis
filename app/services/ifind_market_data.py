# -*- coding: utf-8 -*-
"""Minimal iFinD history adapter for overnight market snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests


_IFIND_BASE_URL = "https://quantapi.51ifind.com/api/v1"
_US_MARKET_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class IFindTokenBundle:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def is_stale(self, *, now: datetime) -> bool:
        return now >= self.expires_at


class IFindHistoryClient:
    """Fetch iFinD OHLCV history and normalize it into a Yahoo-like chart payload."""

    def __init__(
        self,
        *,
        refresh_token: str,
        base_url: str = _IFIND_BASE_URL,
        session: requests.sessions.Session | None = None,
        timeout: float = 20.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.refresh_token = str(refresh_token).strip()
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._cached_bundle: IFindTokenBundle | None = None

    @classmethod
    def from_environment(cls) -> "IFindHistoryClient | None":
        refresh_token = os.environ.get("IFIND_REFRESH_TOKEN", "").strip()
        if not refresh_token:
            return None
        return cls(refresh_token=refresh_token)

    def fetch_chart(
        self,
        provider_symbol: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        if not self.refresh_token:
            raise RuntimeError("IFIND_REFRESH_TOKEN is required for iFinD market history")

        end = end_date or self._now().astimezone(timezone.utc).date().isoformat()
        start = start_date or (date.fromisoformat(end) - timedelta(days=10)).isoformat()
        payload = self._post(
            "/cmd_history_quotation",
            {
                "codes": provider_symbol,
                "indicators": "open,high,low,close,volume",
                "startdate": start,
                "enddate": end,
            },
        )
        return json.dumps(self._build_chart_payload(provider_symbol=provider_symbol, payload=payload), ensure_ascii=True)

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        bundle = self._resolve_access_bundle()
        response = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "access_token": bundle.access_token,
                "ifindlang": "cn",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        errorcode = data.get("errorcode")
        if errorcode not in (None, 0, "0"):
            raise RuntimeError(str(data.get("errmsg") or f"iFinD request failed: {errorcode}"))
        return data

    def _resolve_access_bundle(self) -> IFindTokenBundle:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        if self._cached_bundle is not None and not self._cached_bundle.is_stale(now=now):
            return self._cached_bundle

        response = self.session.post(
            f"{self.base_url}/get_access_token",
            json={},
            headers={"refresh_token": self.refresh_token},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("iFinD auth response missing data object")
        access_token = str(data.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("iFinD auth response missing access_token")
        expires_in = _coerce_int(data.get("expires_in")) or 0
        expires_at = now + timedelta(seconds=max(expires_in - 30, 0))
        self._cached_bundle = IFindTokenBundle(
            access_token=access_token,
            refresh_token=self.refresh_token,
            expires_at=expires_at,
        )
        return self._cached_bundle

    def _build_chart_payload(self, *, provider_symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        tables = list(payload.get("tables", []) or [])
        if not tables:
            raise RuntimeError(f"iFinD history payload missing tables for {provider_symbol}")
        first_table = dict(tables[0] or {})
        times = list(first_table.get("time", []) or [])
        table = dict(first_table.get("table", {}) or {})
        closes = list(table.get("close", []) or [])
        if not times or not closes:
            raise RuntimeError(f"iFinD history payload incomplete for {provider_symbol}")

        timestamps = [_market_close_timestamp(candidate_date) for candidate_date in times]
        quote_row = {
            "open": list(table.get("open", []) or []),
            "high": list(table.get("high", []) or []),
            "low": list(table.get("low", []) or []),
            "close": closes,
            "volume": list(table.get("volume", []) or []),
        }
        latest_close = closes[-1]
        previous_close = closes[-2] if len(closes) >= 2 else closes[-1]
        return {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "symbol": provider_symbol,
                            "exchangeName": _infer_exchange_name(provider_symbol),
                            "fullExchangeName": _infer_exchange_name(provider_symbol),
                            "instrumentType": _infer_instrument_type(provider_symbol),
                            "regularMarketTime": timestamps[-1],
                            "exchangeTimezoneName": "America/New_York",
                            "regularMarketPrice": latest_close,
                            "chartPreviousClose": previous_close,
                            "priceHint": 2,
                        },
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [quote_row],
                            "adjclose": [{"adjclose": closes}],
                        },
                    }
                ],
                "error": None,
            }
        }


def _market_close_timestamp(candidate_date: object) -> int:
    market_date = date.fromisoformat(str(candidate_date))
    local_dt = datetime(
        market_date.year,
        market_date.month,
        market_date.day,
        16,
        0,
        0,
        tzinfo=_US_MARKET_TZ,
    )
    return int(local_dt.astimezone(timezone.utc).timestamp())


def _infer_exchange_name(provider_symbol: str) -> str:
    symbol = provider_symbol.upper()
    if symbol.endswith(".GI"):
        return "Global Index"
    if symbol.endswith(".FX"):
        return "FX"
    if symbol.endswith(".O"):
        return "NASDAQ"
    if symbol.endswith(".P"):
        return "NYSE Arca"
    return "iFinD"


def _infer_instrument_type(provider_symbol: str) -> str:
    symbol = provider_symbol.upper()
    if symbol.endswith(".GI"):
        return "INDEX"
    if symbol.endswith(".FX"):
        return "FOREX"
    if symbol.endswith(".P"):
        return "ETF"
    if symbol.endswith(".O"):
        return "EQUITY"
    return ""


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
