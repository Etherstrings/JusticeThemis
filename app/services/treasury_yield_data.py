# -*- coding: utf-8 -*-
"""Official Treasury yield-curve adapter for the 10Y U.S. Treasury yield."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests


_TREASURY_YIELD_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "TextView?type=daily_treasury_yield_curve"
)
_TREASURY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class TreasuryYieldRow:
    market_date: str
    close: float


class TreasuryYieldClient:
    """Fetch official Treasury 10Y yield rows and normalize them into chart payloads."""

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
        if str(provider_symbol).strip() != "^TNX":
            raise RuntimeError(f"Treasury yield client does not support {provider_symbol}")

        rows = self._fetch_recent_rows()
        timestamps = [_treasury_close_timestamp(row.market_date) for row in rows]
        closes = [row.close for row in rows]
        quote_row = {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [0 for _ in closes],
        }
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "currency": "USD",
                                "symbol": "^TNX",
                                "exchangeName": "U.S. Treasury",
                                "fullExchangeName": "U.S. Treasury",
                                "instrumentType": "INDEX",
                                "regularMarketTime": timestamps[-1],
                                "exchangeTimezoneName": "America/New_York",
                                "regularMarketPrice": closes[-1],
                                "chartPreviousClose": closes[-2],
                                "priceHint": 3,
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
            },
            ensure_ascii=True,
        )

    def _fetch_recent_rows(self) -> list[TreasuryYieldRow]:
        rows: list[TreasuryYieldRow] = []
        seen_dates: set[str] = set()
        for year in self._candidate_years():
            response = self.session.get(
                self._request_url_for_year(year),
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            response.raise_for_status()
            response.encoding = response.encoding or response.apparent_encoding or "utf-8"

            soup = BeautifulSoup(response.text, "lxml")
            for table_row in soup.select("table tbody tr"):
                market_date = _extract_market_date(table_row)
                close = _extract_ten_year_close(table_row)
                if market_date is None or close is None or market_date in seen_dates:
                    continue
                rows.append(TreasuryYieldRow(market_date=market_date, close=close))
                seen_dates.add(market_date)
            if len(rows) >= 2:
                break

        if len(rows) < 2:
            raise RuntimeError("Treasury yield page did not expose two valid 10Y rows")
        sorted_rows = sorted(rows, key=lambda row: row.market_date)
        return sorted_rows[-2:]

    def _candidate_years(self) -> list[int]:
        current_year = self.now_fn().astimezone(_TREASURY_TZ).year
        return [current_year, current_year - 1]

    def _request_url_for_year(self, year: int) -> str:
        return f"{_TREASURY_YIELD_URL}&field_tdr_date_value={int(year)}"


def _extract_market_date(table_row: object) -> str | None:
    time_node = getattr(table_row, "select_one", lambda _selector: None)("td.views-field-field-tdr-date time")
    if time_node is not None:
        raw_datetime = str(time_node.get("datetime") or "").strip()
        if raw_datetime:
            return raw_datetime[:10]

    cell = getattr(table_row, "select_one", lambda _selector: None)("td.views-field-field-tdr-date")
    raw_text = cell.get_text(" ", strip=True) if cell is not None else ""
    if not raw_text:
        return None
    return datetime.strptime(raw_text, "%m/%d/%Y").date().isoformat()


def _extract_ten_year_close(table_row: object) -> float | None:
    cell = getattr(table_row, "select_one", lambda _selector: None)(
        "td.views-field-field-bc-10year, td[headers='view-field-bc-10year-table-column']"
    )
    raw_text = cell.get_text(" ", strip=True) if cell is not None else ""
    if not raw_text or raw_text.upper() == "N/A":
        return None
    return float(raw_text)


def _treasury_close_timestamp(market_date: str) -> int:
    market_dt = datetime.fromisoformat(market_date).replace(hour=15, minute=30, tzinfo=_TREASURY_TZ)
    return int(market_dt.astimezone(timezone.utc).timestamp())
