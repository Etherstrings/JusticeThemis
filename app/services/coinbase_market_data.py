# -*- coding: utf-8 -*-
"""Coinbase daily candle adapter for crypto spot pairs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable
from zoneinfo import ZoneInfo

import requests


_COINBASE_TZ = ZoneInfo("UTC")


class CoinbaseCandlesClient:
    """Fetch recent Coinbase daily candles and normalize them into chart payloads."""

    BASE_URL = "https://api.exchange.coinbase.com"
    SUPPORTED_SYMBOLS = frozenset({"BTC-USD", "ETH-USD"})

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        timeout: float = 20.0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def fetch_chart(self, provider_symbol: str) -> str:
        symbol = str(provider_symbol or "").strip().upper()
        if symbol not in self.SUPPORTED_SYMBOLS:
            raise RuntimeError(f"Coinbase candle client does not support {provider_symbol}")

        candles = self._fetch_recent_candles(symbol)
        timestamps = [int(datetime.fromtimestamp(int(row[0]), tz=_COINBASE_TZ).timestamp()) for row in candles]
        lows = [float(row[1]) for row in candles]
        highs = [float(row[2]) for row in candles]
        opens = [float(row[3]) for row in candles]
        closes = [float(row[4]) for row in candles]
        volumes = [float(row[5]) for row in candles]
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "currency": "USD",
                                "symbol": symbol,
                                "exchangeName": "Coinbase",
                                "fullExchangeName": "Coinbase Exchange",
                                "instrumentType": "CRYPTOCURRENCY",
                                "regularMarketTime": timestamps[-1],
                                "exchangeTimezoneName": "UTC",
                                "regularMarketPrice": closes[-1],
                                "chartPreviousClose": closes[-2],
                                "priceHint": 2,
                            },
                            "timestamp": timestamps,
                            "indicators": {
                                "quote": [
                                    {
                                        "open": opens,
                                        "high": highs,
                                        "low": lows,
                                        "close": closes,
                                        "volume": volumes,
                                    }
                                ],
                                "adjclose": [{"adjclose": closes}],
                            },
                        }
                    ],
                    "error": None,
                }
            },
            ensure_ascii=True,
        )

    def _fetch_recent_candles(self, symbol: str) -> list[list[float]]:
        response = self.session.get(
            f"{self.BASE_URL}/products/{symbol}/candles",
            params={"granularity": 86400},
            timeout=self.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "overnight-news-handoff/1.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("expected Coinbase candles payload to be a list")
        rows = [row for row in payload if isinstance(row, list) and len(row) >= 6]
        if len(rows) < 2:
            raise RuntimeError("Coinbase candles payload missing enough rows")
        rows.sort(key=lambda row: int(row[0]))
        return rows[-2:]
