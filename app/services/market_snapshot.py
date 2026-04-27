# -*- coding: utf-8 -*-
"""Persisted U.S. market-close snapshots for China-morning analysis."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import re
import shlex
import subprocess
import time
from typing import Any, Callable, Protocol
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import requests

from app.repository import OvernightRepository
from app.services.asset_board import AssetBoardService
from app.services.coinbase_market_data import CoinbaseCandlesClient
from app.services.cftc_cot import CFTCCOTSignalService
from app.services.cme_fedwatch import CMEFedWatchSignalService
from app.services.market_data_router import (
    COINBASE_PROVIDER_NAME,
    IFIND_PROVIDER_NAME,
    STOOQ_PROVIDER_NAME,
    TREASURY_PROVIDER_NAME,
    build_market_observation_payload,
    ordered_provider_routes,
    provider_applies_to,
    provider_symbol_for,
)
from app.services.ifind_market_data import IFindHistoryClient
from app.services.kalshi_signals import KalshiSignalService
from app.services.market_regime_engine import MarketRegimeEngine
from app.services.polymarket_signals import PolymarketSignalService
from app.services.treasury_yield_data import TreasuryYieldClient


logger = logging.getLogger(__name__)

_IFIND_PROVIDER_NAME = IFIND_PROVIDER_NAME
_TREASURY_PROVIDER_NAME = TREASURY_PROVIDER_NAME
_STOOQ_PROVIDER_NAME = STOOQ_PROVIDER_NAME
_COINBASE_PROVIDER_NAME = COINBASE_PROVIDER_NAME


class FetchingClient(Protocol):
    def fetch(self, url: str) -> str | bytes:
        """Fetch one payload and return its response body."""


@dataclass(frozen=True)
class MarketInstrumentDefinition:
    symbol: str
    display_name: str
    bucket: str
    priority: int
    provider_symbol_overrides: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MarketDataProviderDefinition:
    name: str
    source_url: str
    chart_url_template: str
    quote_url_template: str = ""


class MarketRequestsHttpClient:
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        retry_attempts: int = 3,
        backoff_seconds: float = 0.8,
        sleep_fn: Callable[[float], None] | None = None,
        urllib_fetcher: Callable[[str, dict[str, str], float], str] | None = None,
        curl_fetcher: Callable[[str, dict[str, str], float], str] | None = None,
        ifind_client: IFindHistoryClient | None = None,
        treasury_client: TreasuryYieldClient | None = None,
        coinbase_client: CoinbaseCandlesClient | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.retry_attempts = max(1, int(retry_attempts))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.sleep_fn = sleep_fn or time.sleep
        self._urllib_fetcher = urllib_fetcher or self._fetch_with_urllib
        self._curl_fetcher = curl_fetcher or self._fetch_with_curl
        self.ifind_client = ifind_client or IFindHistoryClient.from_environment()
        self.treasury_client = treasury_client or TreasuryYieldClient()
        self.coinbase_client = coinbase_client or CoinbaseCandlesClient()

    def fetch(self, url: str) -> str:
        if url.startswith("ifind://history/"):
            if self.ifind_client is None:
                raise RuntimeError("IFIND_REFRESH_TOKEN is required for iFinD history provider")
            provider_symbol = unquote(url.rsplit("/", 1)[-1].strip())
            if not provider_symbol:
                raise RuntimeError("iFinD history provider symbol is missing")
            return self.ifind_client.fetch_chart(provider_symbol)
        if url.startswith("treasury://yieldcurve/"):
            if self.treasury_client is None:
                raise RuntimeError("Treasury yield client is required for Treasury yield provider")
            provider_symbol = unquote(url.rsplit("/", 1)[-1].strip())
            if not provider_symbol:
                raise RuntimeError("Treasury yield provider symbol is missing")
            return self.treasury_client.fetch_chart(provider_symbol)
        if url.startswith("coinbase://candles/"):
            if self.coinbase_client is None:
                raise RuntimeError("Coinbase candle client is required for crypto provider")
            provider_symbol = unquote(url.rsplit("/", 1)[-1].strip())
            if not provider_symbol:
                raise RuntimeError("Coinbase provider symbol is missing")
            return self.coinbase_client.fetch_chart(provider_symbol)

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=12,
                    headers=headers,
                )
                response.raise_for_status()
                response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                return response.text
            except requests.HTTPError as exc:
                last_error = exc
                status_code = getattr(exc.response, "status_code", None)
                if status_code == 429:
                    fallback_payload = self._try_urllib_fallback(url=url, headers=headers, timeout=12.0)
                    if fallback_payload is None:
                        fallback_payload = self._try_curl_fallback(url=url, headers=headers, timeout=12.0)
                    if fallback_payload is not None:
                        return fallback_payload
                if status_code not in self.RETRYABLE_STATUS_CODES or attempt >= self.retry_attempts:
                    raise
            except (requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    fallback_payload = self._try_urllib_fallback(url=url, headers=headers, timeout=12.0)
                    if fallback_payload is None:
                        fallback_payload = self._try_curl_fallback(url=url, headers=headers, timeout=12.0)
                    if fallback_payload is not None:
                        return fallback_payload
                    raise

            if self.backoff_seconds > 0:
                self.sleep_fn(self.backoff_seconds * attempt)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Failed to fetch market snapshot payload")

    def _try_urllib_fallback(self, *, url: str, headers: dict[str, str], timeout: float) -> str | None:
        if not (_is_yahoo_chart_url(url) or _is_stooq_csv_url(url)):
            return None
        try:
            return self._urllib_fetcher(url, headers, timeout)
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("Fallback fetch failed for %s: %s", url, exc)
            return None

    def _try_curl_fallback(self, *, url: str, headers: dict[str, str], timeout: float) -> str | None:
        if not (_is_yahoo_chart_url(url) or _is_stooq_csv_url(url)):
            return None
        try:
            payload = self._curl_fetcher(url, headers, timeout)
            if _is_yahoo_chart_url(url) and not _looks_like_json_payload(payload):
                return None
            if _is_stooq_csv_url(url) and "," not in payload:
                return None
            return payload
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("Curl fallback failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _fetch_with_urllib(url: str, headers: dict[str, str], timeout: float) -> str:
        request = Request(url, headers={**headers, "Connection": "close"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
        return payload.decode("utf-8")

    @staticmethod
    def _fetch_with_curl(url: str, headers: dict[str, str], timeout: float) -> str:
        shell_executable = os.environ.get("SHELL", "/bin/sh").strip() or "/bin/sh"
        command = " ".join(
            [
                "curl",
                "--location",
                "--silent",
                "--show-error",
                "--max-time",
                shlex.quote(str(max(1, int(timeout)))),
                "-A",
                shlex.quote(headers.get("User-Agent", MarketRequestsHttpClient.USER_AGENT)),
                "-H",
                shlex.quote(f"Accept: {headers.get('Accept', '*/*')}"),
                "-H",
                shlex.quote(f"Accept-Language: {headers.get('Accept-Language', 'en-US,en;q=0.9')}"),
                shlex.quote(url),
            ]
        )
        completed = subprocess.run(
            [shell_executable, "-lc", command],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


_IFIND_PROVIDER_SYMBOL_OVERRIDES: dict[str, str] = {
    "^GSPC": "SPY.P",
    "^IXIC": "IXIC.GI",
    "^DJI": "DIA.P",
    "^RUT": "IWM.P",
    "^VIX": "VIX.GI",
    "XLK": "XLK.P",
    "SOXX": "SOXX.O",
    "XLF": "XLF.P",
    "XLE": "XLE.P",
    "XLI": "XLI.P",
    "XLV": "XLV.P",
    "XLY": "XLY.P",
    "XLP": "XLP.P",
    "DX-Y.NYB": "UUP.P",
    "CNH=X": "USDCNH.FX",
    "GC=F": "GLD.P",
    "SI=F": "SLV.P",
    "CL=F": "USO.P",
    "BZ=F": "BNO.P",
    "NG=F": "UNG.P",
    "HG=F": "CPER.P",
    "ALI=F": "DBB.P",
    "BDRY": "BDRY.P",
    "SEA": "SEA.P",
    "BOAT": "BOAT.P",
    "EEM": "EEM.P",
    "EFA": "EFA.P",
    "FEZ": "FEZ.P",
    "EWJ": "EWJ.P",
    "HYG": "HYG.P",
    "LQD": "LQD.P",
    "JNK": "JNK.P",
    "EMB": "EMB.P",
    "TLT": "TLT.O",
    "KWEB": "KWEB.P",
    "FXI": "FXI.P",
}
_TREASURY_PROVIDER_SYMBOL_OVERRIDES: dict[str, str] = {
    "^UST2Y": "^UST2Y",
    "^UST5Y": "^UST5Y",
    "^TNX": "^TNX",
    "^UST30Y": "^UST30Y",
}
_STOOQ_PROVIDER_SYMBOL_OVERRIDES: dict[str, str] = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
    "^RUT": "iwm.us",
    "^VIX": "vxx.us",
    "XLK": "xlk.us",
    "SOXX": "soxx.us",
    "XLF": "xlf.us",
    "XLE": "xle.us",
    "XLI": "xli.us",
    "XLV": "xlv.us",
    "XLY": "xly.us",
    "XLP": "xlp.us",
    "DX-Y.NYB": "dx.f",
    "CNH=X": "cnyusd",
    "GC=F": "gc.f",
    "SI=F": "si.f",
    "CL=F": "cl.f",
    "BZ=F": "cb.f",
    "NG=F": "ng.f",
    "HG=F": "hg.f",
    "ALI=F": "ah.f",
    "BDRY": "bdry.us",
    "SEA": "sea.us",
    "BOAT": "boat.us",
    "EEM": "eem.us",
    "EFA": "efa.us",
    "FEZ": "fez.us",
    "EWJ": "ewj.us",
    "HYG": "hyg.us",
    "LQD": "lqd.us",
    "JNK": "jnk.us",
    "EMB": "emb.us",
    "TLT": "tlt.us",
    "KWEB": "kweb.us",
    "FXI": "fxi.us",
}
_COINBASE_PROVIDER_SYMBOL_OVERRIDES: dict[str, str] = {
    "BTC-USD": "BTC-USD",
    "ETH-USD": "ETH-USD",
}


def _instrument(symbol: str, display_name: str, bucket: str, priority: int) -> MarketInstrumentDefinition:
    overrides: list[tuple[str, str]] = []
    ifind_symbol = _IFIND_PROVIDER_SYMBOL_OVERRIDES.get(symbol)
    treasury_symbol = _TREASURY_PROVIDER_SYMBOL_OVERRIDES.get(symbol)
    stooq_symbol = _STOOQ_PROVIDER_SYMBOL_OVERRIDES.get(symbol)
    coinbase_symbol = _COINBASE_PROVIDER_SYMBOL_OVERRIDES.get(symbol)
    if ifind_symbol:
        overrides.append((_IFIND_PROVIDER_NAME, ifind_symbol))
    if treasury_symbol:
        overrides.append((_TREASURY_PROVIDER_NAME, treasury_symbol))
    if stooq_symbol:
        overrides.append((_STOOQ_PROVIDER_NAME, stooq_symbol))
    if coinbase_symbol:
        overrides.append((_COINBASE_PROVIDER_NAME, coinbase_symbol))
    return MarketInstrumentDefinition(
        symbol=symbol,
        display_name=display_name,
        bucket=bucket,
        priority=priority,
        provider_symbol_overrides=tuple(overrides),
    )


DEFAULT_US_MARKET_INSTRUMENTS: tuple[MarketInstrumentDefinition, ...] = (
    _instrument("^GSPC", "标普500", "index", 100),
    _instrument("^IXIC", "纳指综指", "index", 98),
    _instrument("^DJI", "道指", "index", 96),
    _instrument("^RUT", "罗素2000", "index", 94),
    _instrument("^VIX", "VIX", "sentiment", 92),
    _instrument("XLK", "科技板块", "sector", 85),
    _instrument("SOXX", "半导体板块", "sector", 84),
    _instrument("XLF", "金融板块", "sector", 83),
    _instrument("XLE", "能源板块", "sector", 82),
    _instrument("XLI", "工业板块", "sector", 81),
    _instrument("XLV", "医疗板块", "sector", 80),
    _instrument("XLY", "可选消费板块", "sector", 79),
    _instrument("XLP", "必选消费板块", "sector", 78),
    _instrument("^UST2Y", "美国2年期国债收益率", "rates_fx", 77),
    _instrument("^UST5Y", "美国5年期国债收益率", "rates_fx", 76),
    _instrument("^TNX", "美国10年期国债收益率", "rates_fx", 75),
    _instrument("^UST30Y", "美国30年期国债收益率", "rates_fx", 74),
    _instrument("DX-Y.NYB", "美元指数", "rates_fx", 73),
    _instrument("CNH=X", "美元/离岸人民币", "rates_fx", 72),
    _instrument("GC=F", "黄金", "precious_metals", 72),
    _instrument("SI=F", "白银", "precious_metals", 71),
    _instrument("TLT", "长期美债ETF", "duration", 71),
    _instrument("HYG", "高收益债ETF", "credit", 70),
    _instrument("LQD", "投资级债ETF", "credit", 69),
    _instrument("JNK", "垃圾债ETF", "credit", 68),
    _instrument("EMB", "新兴市场债ETF", "credit", 67),
    _instrument("KWEB", "中国互联网ETF", "china_proxy", 70),
    _instrument("FXI", "中国大型股ETF", "china_proxy", 69),
    _instrument("CL=F", "WTI原油", "energy", 70),
    _instrument("BZ=F", "布伦特原油", "energy", 68),
    _instrument("NG=F", "天然气", "energy", 67),
    _instrument("HG=F", "铜", "industrial_metals", 66),
    _instrument("ALI=F", "铝", "industrial_metals", 65),
    _instrument("BDRY", "干散货ETF", "shipping", 64),
    _instrument("SEA", "全球航运ETF", "shipping", 63),
    _instrument("BOAT", "航运产业ETF", "shipping", 62),
    _instrument("EEM", "新兴市场ETF", "global_equity", 61),
    _instrument("EFA", "发达市场ETF", "global_equity", 60),
    _instrument("FEZ", "欧元区ETF", "global_equity", 59),
    _instrument("EWJ", "日本ETF", "global_equity", 58),
    _instrument("BTC-USD", "比特币", "crypto", 57),
    _instrument("ETH-USD", "以太坊", "crypto", 56),
)

_YAHOO_MARKET_DATA_PROVIDER = MarketDataProviderDefinition(
    name="Yahoo Finance Chart",
    source_url="https://finance.yahoo.com/",
    chart_url_template=(
        "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?range=5d&interval=1d&includePrePost=false"
    ),
)
_IFIND_MARKET_DATA_PROVIDER = MarketDataProviderDefinition(
    name=_IFIND_PROVIDER_NAME,
    source_url="https://quantapi.51ifind.com/",
    chart_url_template="ifind://history/{symbol}",
    quote_url_template="https://quantapi.51ifind.com/",
)
_TREASURY_MARKET_DATA_PROVIDER = MarketDataProviderDefinition(
    name=_TREASURY_PROVIDER_NAME,
    source_url="https://home.treasury.gov/",
    chart_url_template="treasury://yieldcurve/{symbol}",
    quote_url_template="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
)
_STOOQ_MARKET_DATA_PROVIDER = MarketDataProviderDefinition(
    name=_STOOQ_PROVIDER_NAME,
    source_url="https://stooq.com/",
    chart_url_template="https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv",
    quote_url_template="https://stooq.com/q/?s={symbol}",
)
_COINBASE_MARKET_DATA_PROVIDER = MarketDataProviderDefinition(
    name=_COINBASE_PROVIDER_NAME,
    source_url="https://exchange.coinbase.com/",
    chart_url_template="coinbase://candles/{symbol}",
    quote_url_template="https://exchange.coinbase.com/trade/{symbol}",
)

DEFAULT_MARKET_DATA_PROVIDERS: tuple[MarketDataProviderDefinition, ...] = (
    _COINBASE_MARKET_DATA_PROVIDER,
    _TREASURY_MARKET_DATA_PROVIDER,
    _STOOQ_MARKET_DATA_PROVIDER,
    _YAHOO_MARKET_DATA_PROVIDER,
)


def _build_default_market_data_providers() -> tuple[MarketDataProviderDefinition, ...]:
    if os.environ.get("IFIND_REFRESH_TOKEN", "").strip():
        return (
            _IFIND_MARKET_DATA_PROVIDER,
            _COINBASE_MARKET_DATA_PROVIDER,
            _TREASURY_MARKET_DATA_PROVIDER,
            _STOOQ_MARKET_DATA_PROVIDER,
            _YAHOO_MARKET_DATA_PROVIDER,
        )
    return DEFAULT_MARKET_DATA_PROVIDERS


def _provider_symbol_for(instrument: MarketInstrumentDefinition, provider_name: str) -> str:
    return provider_symbol_for(instrument, provider_name)


def _provider_applies_to(instrument: MarketInstrumentDefinition, provider_name: str) -> bool:
    return provider_applies_to(instrument, provider_name)


def _is_yahoo_chart_url(url: str) -> bool:
    lowered = str(url).strip().lower()
    return "finance.yahoo.com/v8/finance/chart/" in lowered


def _is_stooq_csv_url(url: str) -> bool:
    lowered = str(url).strip().lower()
    return "stooq.com/q/l/" in lowered


class UsMarketSnapshotService:
    SESSION_NAME = "us_close"
    ANALYSIS_TIMEZONE = ZoneInfo("Asia/Shanghai")

    def __init__(
        self,
        *,
        repo: OvernightRepository,
        http_client: FetchingClient | None = None,
        instruments: tuple[MarketInstrumentDefinition, ...] | None = None,
        asset_board_service: AssetBoardService | None = None,
        providers: tuple[MarketDataProviderDefinition, ...] | None = None,
        regime_engine: MarketRegimeEngine | None = None,
        prediction_market_service: PolymarketSignalService | None = None,
        kalshi_signal_service: KalshiSignalService | None = None,
        fedwatch_signal_service: CMEFedWatchSignalService | None = None,
        cftc_signal_service: CFTCCOTSignalService | None = None,
    ) -> None:
        self.repo = repo
        self.http_client = http_client or MarketRequestsHttpClient()
        self.instruments = tuple(instruments or DEFAULT_US_MARKET_INSTRUMENTS)
        self.asset_board_service = asset_board_service or AssetBoardService()
        default_providers = _build_default_market_data_providers() if http_client is None else DEFAULT_MARKET_DATA_PROVIDERS
        self.providers = tuple(providers or default_providers)
        self.regime_engine = regime_engine or MarketRegimeEngine()
        self.prediction_market_service = prediction_market_service or PolymarketSignalService.from_environment()
        self.kalshi_signal_service = kalshi_signal_service or KalshiSignalService.from_environment()
        self.fedwatch_signal_service = fedwatch_signal_service or CMEFedWatchSignalService.from_environment()
        self.cftc_signal_service = cftc_signal_service or CFTCCOTSignalService.from_environment()

    def refresh_us_close_snapshot(self) -> dict[str, Any]:
        snapshots: list[dict[str, Any]] = []
        captured_symbols: list[str] = []
        failed_instruments: list[dict[str, str]] = []
        for instrument in sorted(self.instruments, key=lambda item: item.priority, reverse=True):
            try:
                snapshots.append(self._fetch_instrument_snapshot(instrument))
                captured_symbols.append(instrument.symbol)
            except Exception as exc:
                logger.warning("Failed to fetch U.S. market snapshot for %s: %s", instrument.symbol, exc)
                failed_instruments.append(
                    {
                        "symbol": instrument.symbol,
                        "display_name": instrument.display_name,
                        "reason": str(exc),
                    }
                )

        if not snapshots:
            raise RuntimeError("No market instruments were captured")

        analysis_date = str(snapshots[0]["analysis_date"])
        market_date = str(snapshots[0]["market_date"])
        previous_snapshot = self.repo.get_latest_market_snapshot(session_name=self.SESSION_NAME)
        provider_hits: dict[str, int] = {}
        for item in snapshots:
            provider_name = str(item.get("provider_name", "")).strip()
            if provider_name:
                provider_hits[provider_name] = provider_hits.get(provider_name, 0) + 1
        capture_summary = self._build_capture_summary(
            captured_symbols=captured_symbols,
            snapshots=snapshots,
            failed_instruments=failed_instruments,
        )
        capture_run = self.repo.create_market_capture_run(
            analysis_date=analysis_date,
            market_date=market_date,
            session_name=self.SESSION_NAME,
            status="completed" if not capture_summary["missing_symbols"] else "partial",
            source_name="; ".join(sorted(provider_hits)) if provider_hits else "",
            provider_hits=provider_hits,
            missing_symbols=list(capture_summary["missing_symbols"]),
            diagnostics=list(failed_instruments),
        )
        observation_payloads: list[dict[str, Any]] = []
        for item in snapshots:
            observation_payload = build_market_observation_payload(
                capture_run_id=int(capture_run["id"]),
                session_name=self.SESSION_NAME,
                snapshot=item,
            )
            self.repo.upsert_market_observation(
                **observation_payload
            )
            observation_payloads.append(observation_payload)
        indexes = [item for item in snapshots if item["bucket"] == "index"]
        sectors = [item for item in snapshots if item["bucket"] == "sector"]
        sentiment = [item for item in snapshots if item["bucket"] == "sentiment"]
        rates_fx = [item for item in snapshots if item["bucket"] == "rates_fx"]
        precious_metals = [item for item in snapshots if item["bucket"] == "precious_metals"]
        energy = [item for item in snapshots if item["bucket"] == "energy"]
        industrial_metals = [item for item in snapshots if item["bucket"] == "industrial_metals"]
        shipping = [item for item in snapshots if item["bucket"] == "shipping"]
        global_equities = [item for item in snapshots if item["bucket"] == "global_equity"]
        crypto = [item for item in snapshots if item["bucket"] == "crypto"]
        credit = [item for item in snapshots if item["bucket"] == "credit"]
        duration = [item for item in snapshots if item["bucket"] == "duration"]
        china_proxies = [item for item in snapshots if item["bucket"] == "china_proxy"]
        risk_signals = self._build_risk_signals(indexes=indexes, sectors=sectors, sentiment=sentiment)
        asset_board = self.asset_board_service.build(
            analysis_date=analysis_date,
            market_date=market_date,
            indexes=indexes,
            sectors=sectors,
            sentiment=sentiment,
            rates_fx=rates_fx,
            precious_metals=precious_metals,
            energy=energy,
            industrial_metals=industrial_metals,
            shipping=shipping,
            global_equities=global_equities,
            crypto=crypto,
            credit=credit,
            duration=duration,
            china_proxies=china_proxies,
            risk_signals=risk_signals,
        )
        source_names = list(dict.fromkeys(str(item.get("provider_name", "")).strip() for item in snapshots if str(item.get("provider_name", "")).strip()))
        source_urls = list(dict.fromkeys(str(item.get("provider_url", "")).strip() for item in snapshots if str(item.get("provider_url", "")).strip()))
        source_name = source_names[0] if len(source_names) == 1 else ", ".join(source_names)
        source_url = source_urls[0] if len(source_urls) == 1 else ", ".join(source_urls)
        regime_report = self.regime_engine.evaluate(
            analysis_date=analysis_date,
            observations=observation_payloads,
        )
        prediction_markets = self.prediction_market_service.collect(
            analysis_date=analysis_date,
            market_date=market_date,
            previous_snapshot=previous_snapshot,
        )
        kalshi_signals = self.kalshi_signal_service.collect(
            analysis_date=analysis_date,
            market_date=market_date,
            previous_snapshot=previous_snapshot,
        )
        fedwatch_signals = self.fedwatch_signal_service.collect(
            analysis_date=analysis_date,
            market_date=market_date,
            previous_snapshot=previous_snapshot,
        )
        fedwatch_signals = self._fedwatch_or_prediction_fallback(
            fedwatch_signals=fedwatch_signals,
            prediction_markets=prediction_markets,
            analysis_date=analysis_date,
            market_date=market_date,
        )
        cftc_signals = self.cftc_signal_service.collect(
            analysis_date=analysis_date,
            market_date=market_date,
            previous_snapshot=previous_snapshot,
        )
        external_signal_headlines = [
            str(payload.get("headline", "")).strip()
            for payload in (prediction_markets, kalshi_signals, fedwatch_signals, cftc_signals)
            if isinstance(payload, dict) and str(payload.get("headline", "")).strip()
        ]

        snapshot = {
            "analysis_date": analysis_date,
            "market_date": market_date,
            "session_name": self.SESSION_NAME,
            "capture_run_id": int(capture_run["id"]),
            "source_name": source_name,
            "source_url": source_url,
            "headline": asset_board["headline"],
            "capture_summary": {
                **capture_summary,
                "capture_run_id": int(capture_run["id"]),
                "provider_hits": dict(provider_hits),
            },
            "indexes": indexes,
            "sectors": sectors,
            "sentiment": sentiment,
            "rates_fx": rates_fx,
            "precious_metals": precious_metals,
            "energy": energy,
            "industrial_metals": industrial_metals,
            "shipping": shipping,
            "global_equities": global_equities,
            "crypto": crypto,
            "credit": credit,
            "duration": duration,
            "china_proxies": china_proxies,
            "china_mapped_futures": asset_board["china_mapped_futures"],
            "asset_board": asset_board,
            "risk_signals": risk_signals,
            "market_regimes": list(regime_report.get("market_regimes", [])),
            "market_regime_evaluations": list(regime_report.get("market_regime_evaluations", [])),
            "prediction_markets": prediction_markets,
            "kalshi_signals": kalshi_signals,
            "fedwatch_signals": fedwatch_signals,
            "cftc_signals": cftc_signals,
            "external_market_signals": {
                "headline": "；".join(external_signal_headlines[:3]),
                "provider_statuses": {
                    "polymarket": str(dict(prediction_markets).get("status", "")).strip(),
                    "kalshi": str(dict(kalshi_signals).get("status", "")).strip(),
                    "cme_fedwatch": str(dict(fedwatch_signals).get("status", "")).strip(),
                    "cftc": str(dict(cftc_signals).get("status", "")).strip(),
                },
                "provider_count": 4,
                "ready_provider_count": sum(
                    1
                    for payload in (prediction_markets, kalshi_signals, fedwatch_signals, cftc_signals)
                    if str(dict(payload).get("status", "")).strip() == "ready"
                ),
            },
        }
        return self.repo.upsert_market_snapshot(
            analysis_date=analysis_date,
            market_date=market_date,
            session_name=self.SESSION_NAME,
            source_name=source_name,
            source_url=source_url,
            snapshot=snapshot,
        )

    def _build_capture_summary(
        self,
        *,
        captured_symbols: list[str],
        snapshots: list[dict[str, Any]],
        failed_instruments: list[dict[str, str]],
    ) -> dict[str, Any]:
        expected_symbols = [instrument.symbol for instrument in self.instruments]
        missing_symbols = [symbol for symbol in expected_symbols if symbol not in captured_symbols]
        instrument_by_symbol = {instrument.symbol: instrument for instrument in self.instruments}
        core_missing_symbols = [
            symbol
            for symbol in missing_symbols
            if self._instrument_importance_tier(instrument_by_symbol.get(symbol)) == "P0"
        ]
        supporting_missing_symbols = [
            symbol
            for symbol in missing_symbols
            if self._instrument_importance_tier(instrument_by_symbol.get(symbol)) == "P1"
        ]
        optional_missing_symbols = [
            symbol
            for symbol in missing_symbols
            if self._instrument_importance_tier(instrument_by_symbol.get(symbol)) == "P2"
        ]
        freshness_status_counts: dict[str, int] = {}
        for item in snapshots:
            freshness_status = str(item.get("freshness_status", "")).strip() or "unknown"
            freshness_status_counts[freshness_status] = freshness_status_counts.get(freshness_status, 0) + 1
        return {
            "capture_status": "complete" if not missing_symbols else "partial",
            "expected_instrument_count": len(expected_symbols),
            "captured_instrument_count": len(captured_symbols),
            "missing_instrument_count": len(missing_symbols),
            "captured_symbols": list(captured_symbols),
            "missing_symbols": missing_symbols,
            "core_missing_symbols": core_missing_symbols,
            "supporting_missing_symbols": supporting_missing_symbols,
            "optional_missing_symbols": optional_missing_symbols,
            "freshness_status_counts": freshness_status_counts,
            "failed_instruments": failed_instruments,
        }

    def _instrument_importance_tier(self, instrument: MarketInstrumentDefinition | None) -> str:
        if instrument is None:
            return "P2"
        if instrument.bucket in {"index", "sector", "sentiment", "rates_fx"}:
            return "P0"
        if instrument.bucket in {"precious_metals", "energy", "industrial_metals", "shipping", "global_equity", "crypto", "china_proxy", "credit", "duration"}:
            return "P1"
        return "P2"

    def get_daily_snapshot(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        candidate = str(analysis_date or "").strip()
        if candidate:
            return self.repo.get_market_snapshot(analysis_date=candidate, session_name=self.SESSION_NAME)
        return self.repo.get_latest_market_snapshot(session_name=self.SESSION_NAME)

    def get_external_signals(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        snapshot = self.get_daily_snapshot(analysis_date=analysis_date)
        if snapshot is None:
            return None
        return {
            "analysis_date": snapshot.get("analysis_date"),
            "market_date": snapshot.get("market_date"),
            "session_name": snapshot.get("session_name"),
            "source_name": snapshot.get("source_name"),
            "source_url": snapshot.get("source_url"),
            "external_market_signals": dict(snapshot.get("external_market_signals", {}) or {}),
            "prediction_markets": dict(snapshot.get("prediction_markets", {}) or {}),
            "kalshi_signals": dict(snapshot.get("kalshi_signals", {}) or {}),
            "fedwatch_signals": dict(snapshot.get("fedwatch_signals", {}) or {}),
            "cftc_signals": dict(snapshot.get("cftc_signals", {}) or {}),
        }

    def _fetch_instrument_snapshot(self, instrument: MarketInstrumentDefinition) -> dict[str, Any]:
        last_error: Exception | None = None
        routes = ordered_provider_routes(instrument=instrument, providers=self.providers)
        for route in routes:
            try:
                payload = _fetch_payload(self.http_client, route.chart_url)
                if route.provider_name == _STOOQ_PROVIDER_NAME:
                    return self._parse_stooq_snapshot(
                        instrument=instrument,
                        route=route,
                        payload=payload,
                        is_primary_provider=route == routes[0],
                    )
                parsed = json.loads(payload)
                result = list(parsed.get("chart", {}).get("result", []) or [])
                if not result:
                    raise ValueError(f"Empty chart result for {instrument.symbol}")

                chart = result[0]
                meta = dict(chart.get("meta", {}) or {})
                timestamps = list(chart.get("timestamp", []) or [])
                quote_rows = list(chart.get("indicators", {}).get("quote", []) or [])
                if not timestamps or not quote_rows:
                    raise ValueError(f"Incomplete chart payload for {instrument.symbol}")
                quote_row = dict(quote_rows[0] or {})
                latest_index = _latest_valid_index(quote_row.get("close", []))
                close = _number_or_none(quote_row.get("close", []), latest_index)
                if close is None:
                    raise ValueError(f"No close data for {instrument.symbol}")

                previous_close = _number_or_none(quote_row.get("close", []), latest_index - 1)
                if previous_close is None:
                    previous_close = _to_float(meta.get("chartPreviousClose"))

                latest_valid_timestamp = timestamps[latest_index] if latest_index < len(timestamps) else None
                regular_market_time = int(latest_valid_timestamp or meta.get("regularMarketTime") or timestamps[latest_index])
                exchange_timezone_name = str(meta.get("exchangeTimezoneName") or "America/New_York")
                try:
                    market_timezone = ZoneInfo(exchange_timezone_name)
                except Exception:
                    market_timezone = timezone.utc
                market_dt_utc = datetime.fromtimestamp(regular_market_time, tz=timezone.utc)
                market_dt_local = market_dt_utc.astimezone(market_timezone)
                analysis_dt_local = market_dt_utc.astimezone(self.ANALYSIS_TIMEZONE)
                change = close - previous_close if previous_close is not None else None
                change_pct = ((change / previous_close) * 100.0) if (change is not None and previous_close) else None

                return {
                    "symbol": instrument.symbol,
                    "display_name": instrument.display_name,
                    "bucket": instrument.bucket,
                    "priority": instrument.priority,
                    "provider_name": route.provider_name,
                    "provider_symbol": route.provider_symbol,
                    "provider_url": route.provider_url,
                    "quote_url": route.quote_url,
                    "market_time": market_dt_utc.isoformat(timespec="seconds"),
                    "market_time_local": market_dt_local.isoformat(timespec="seconds"),
                    "analysis_time_shanghai": analysis_dt_local.isoformat(timespec="seconds"),
                    "market_date": market_dt_local.date().isoformat(),
                    "analysis_date": analysis_dt_local.date().isoformat(),
                    "instrument_type": str(meta.get("instrumentType") or ""),
                    "exchange_name": str(meta.get("fullExchangeName") or meta.get("exchangeName") or ""),
                    "exchange_timezone_name": exchange_timezone_name,
                    "currency": str(meta.get("currency") or "USD"),
                    "close": close,
                    "close_text": _format_number(close),
                    "previous_close": previous_close,
                    "previous_close_text": _format_number(previous_close),
                    "change": change,
                    "change_text": _format_signed_number(change),
                    "change_pct": change_pct,
                    "change_pct_text": _format_signed_percent(change_pct),
                    "change_direction": _change_direction(change),
                    "day_high": _number_or_none(quote_row.get("high", []), latest_index) or _to_float(meta.get("regularMarketDayHigh")),
                    "day_low": _number_or_none(quote_row.get("low", []), latest_index) or _to_float(meta.get("regularMarketDayLow")),
                    "volume": int(_number_or_none(quote_row.get("volume", []), latest_index) or _to_float(meta.get("regularMarketVolume")) or 0),
                    "volume_text": _format_integer(_number_or_none(quote_row.get("volume", []), latest_index) or _to_float(meta.get("regularMarketVolume")) or 0),
                    "is_primary_provider": route == routes[0],
                    "is_fallback_provider": route != routes[0],
                }
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"No market data providers configured for {instrument.symbol}")

    def _parse_stooq_snapshot(
        self,
        *,
        instrument: MarketInstrumentDefinition,
        route: object,
        payload: str,
        is_primary_provider: bool,
    ) -> dict[str, Any]:
        rows = list(csv.DictReader(str(payload or "").splitlines()))
        if not rows:
            raise ValueError(f"Empty stooq payload for {instrument.symbol}")
        row = rows[0]
        close = _stooq_numeric(row.get("Close"))
        if close is None:
            raise ValueError(f"No close data for {instrument.symbol}")

        open_value = _stooq_numeric(row.get("Open"))
        high = _stooq_numeric(row.get("High"))
        low = _stooq_numeric(row.get("Low"))
        volume = int(_stooq_numeric(row.get("Volume")) or 0)
        market_date = str(row.get("Date", "")).strip()
        if not market_date or market_date == "N/D":
            raise ValueError(f"No market date for {instrument.symbol}")
        market_time_value = str(row.get("Time", "")).strip()
        market_time = market_time_value if market_time_value and market_time_value != "N/D" else "00:00:00"
        analysis_date = _stooq_analysis_date(market_date=market_date, bucket=instrument.bucket)
        previous_close = self._fetch_stooq_previous_close(provider_symbol=str(route.provider_symbol).strip())
        if str(route.provider_symbol).strip().lower() == "cnyusd":
            open_value, high, low, close = _invert_fx_quote(
                open_value=open_value,
                high=high,
                low=low,
                close=close,
            )
            previous_close = _invert_numeric(previous_close)
        previous_close = previous_close if previous_close is not None else open_value
        change = close - previous_close if previous_close is not None else None
        change_pct = ((change / previous_close) * 100.0) if (change is not None and previous_close) else None
        market_timestamp = f"{market_date}T{market_time}+00:00"

        return {
            "symbol": instrument.symbol,
            "display_name": instrument.display_name,
            "bucket": instrument.bucket,
            "priority": instrument.priority,
            "provider_name": route.provider_name,
            "provider_symbol": route.provider_symbol,
            "provider_url": route.provider_url,
            "quote_url": route.quote_url,
            "market_time": market_timestamp,
            "market_time_local": market_timestamp,
            "analysis_time_shanghai": f"{analysis_date}T08:00:00+08:00",
            "market_date": market_date,
            "analysis_date": analysis_date,
            "instrument_type": _stooq_instrument_type(instrument.bucket),
            "exchange_name": "Stooq",
            "exchange_timezone_name": "UTC",
            "currency": "USD",
            "close": close,
            "close_text": _format_number(close),
            "previous_close": previous_close,
            "previous_close_text": _format_number(previous_close),
            "change": change,
            "change_text": _format_signed_number(change),
            "change_pct": change_pct,
            "change_pct_text": _format_signed_percent(change_pct),
            "change_direction": _change_direction(change),
            "day_high": high,
            "day_low": low,
            "volume": volume,
            "volume_text": _format_integer(volume),
            "is_primary_provider": is_primary_provider,
            "is_fallback_provider": not is_primary_provider,
        }

    def _fetch_stooq_previous_close(self, *, provider_symbol: str) -> float | None:
        normalized_symbol = str(provider_symbol).strip().lower()
        if not normalized_symbol:
            return None
        try:
            payload = _fetch_payload(
                self.http_client,
                f"https://stooq.com/q/?s={quote(normalized_symbol, safe='')}",
            )
        except Exception:
            return None
        return _parse_stooq_previous_close(payload, provider_symbol=normalized_symbol)

    def _build_risk_signals(
        self,
        *,
        indexes: list[dict[str, Any]],
        sectors: list[dict[str, Any]],
        sentiment: list[dict[str, Any]],
    ) -> dict[str, Any]:
        vix = next((item for item in sentiment if item.get("symbol") == "^VIX"), sentiment[0] if sentiment else None)
        strongest_sector = _pick_extreme(sectors, reverse=True)
        weakest_sector = _pick_extreme(sectors, reverse=False)
        strongest_index = _pick_extreme(indexes, reverse=True)
        weakest_index = _pick_extreme(indexes, reverse=False)
        advancing_sector_count = sum(1 for item in sectors if (item.get("change_pct") or 0.0) > 0)
        declining_sector_count = sum(1 for item in sectors if (item.get("change_pct") or 0.0) < 0)
        positive_index_count = sum(1 for item in indexes if (item.get("change_pct") or 0.0) > 0)
        negative_index_count = sum(1 for item in indexes if (item.get("change_pct") or 0.0) < 0)

        risk_mode = "mixed"
        if positive_index_count >= max(1, len(indexes) - 1) and (vix is None or (vix.get("change_pct") or 0.0) < 0):
            risk_mode = "risk_on"
        elif negative_index_count >= max(1, len(indexes) - 1) and (vix is None or (vix.get("change_pct") or 0.0) > 0):
            risk_mode = "risk_off"

        return {
            "risk_mode": risk_mode,
            "advancing_sector_count": advancing_sector_count,
            "declining_sector_count": declining_sector_count,
            "positive_index_count": positive_index_count,
            "negative_index_count": negative_index_count,
            "strongest_sector": strongest_sector,
            "weakest_sector": weakest_sector,
            "strongest_index": strongest_index,
            "weakest_index": weakest_index,
            "volatility_proxy": vix,
        }

    def _fedwatch_or_prediction_fallback(
        self,
        *,
        fedwatch_signals: dict[str, Any],
        prediction_markets: dict[str, Any],
        analysis_date: str,
        market_date: str,
    ) -> dict[str, Any]:
        if str(dict(fedwatch_signals or {}).get("status", "")).strip() == "ready":
            return fedwatch_signals
        prediction_payload = dict(prediction_markets or {})
        signals = [
            dict(signal or {})
            for signal in list(prediction_payload.get("signals", []) or [])
            if isinstance(signal, dict) and "fed" in str(signal.get("signal_key", "")).strip().lower()
        ]
        if not signals:
            return fedwatch_signals
        signal = signals[0]
        label = str(signal.get("label", "")).strip() or "Fed利率预期"
        probability = signal.get("probability")
        probability_text = f"{float(probability):.1f}%" if probability is not None else "暂无概率"
        return {
            "provider_name": "FedWatch fallback",
            "provider_url": str(signal.get("source_url", "")).strip() or str(prediction_payload.get("provider_url", "")).strip(),
            "analysis_date": str(analysis_date or "").strip(),
            "market_date": str(market_date or "").strip(),
            "status": "ready",
            "status_reason": "polymarket_fallback",
            "headline": f"Polymarket利率预期：{label} {probability_text}",
            "meetings": [],
            "meeting_count": 0,
            "fallback_signal": signal,
            "fallback_provider": str(prediction_payload.get("provider_name", "")).strip() or "Polymarket",
        }


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def _looks_like_json_payload(payload: str) -> bool:
    candidate = str(payload or "").lstrip()
    return candidate.startswith("{") or candidate.startswith("[")


def _stooq_numeric(value: object) -> float | None:
    candidate = str(value or "").strip()
    if not candidate or candidate == "N/D":
        return None
    return _to_float(candidate)


def _parse_stooq_previous_close(payload: str, *, provider_symbol: str) -> float | None:
    normalized_symbol = str(provider_symbol).strip().lower()
    if not normalized_symbol:
        return None
    match = re.search(
        rf'id=(?:["\'])?aq_{re.escape(normalized_symbol)}_p(?:["\'])?[^>]*>\s*([^<\s]+)',
        str(payload or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return _stooq_numeric(match.group(1))


def _stooq_analysis_date(*, market_date: str, bucket: str) -> str:
    market_day = datetime.fromisoformat(f"{market_date}T00:00:00+00:00").date()
    if bucket in {"index", "sector", "sentiment", "china_proxy", "global_equity"}:
        return market_day.fromordinal(market_day.toordinal() + 1).isoformat()
    return market_day.isoformat()


def _stooq_instrument_type(bucket: str) -> str:
    mapping = {
        "index": "INDEX",
        "sector": "ETF",
        "sentiment": "INDEX",
        "rates_fx": "INDEX",
        "precious_metals": "FUTURE",
        "energy": "FUTURE",
        "industrial_metals": "FUTURE",
        "shipping": "ETF",
        "global_equity": "ETF",
        "crypto": "CRYPTOCURRENCY",
        "credit": "ETF",
        "duration": "ETF",
        "china_proxy": "ETF",
    }
    return mapping.get(str(bucket).strip(), "INDEX")


def _invert_fx_quote(
    *,
    open_value: float | None,
    high: float | None,
    low: float | None,
    close: float | None,
) -> tuple[float | None, float | None, float | None, float | None]:
    def invert(value: float | None) -> float | None:
        if value in (None, 0):
            return None
        return 1.0 / value

    return (
        invert(open_value),
        invert(low),
        invert(high),
        invert(close),
    )


def _invert_numeric(value: float | None) -> float | None:
    if value in (None, 0):
        return None
    return 1.0 / value


def _latest_valid_index(values: list[object]) -> int:
    for index in range(len(values) - 1, -1, -1):
        if _to_float(values[index]) is not None:
            return index
    raise ValueError("No valid time series values found")


def _number_or_none(values: list[object], index: int) -> float | None:
    if index < 0 or index >= len(values):
        return None
    return _to_float(values[index])


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{numeric:,.2f}"


def _format_signed_number(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{numeric:+,.2f}"


def _format_signed_percent(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{numeric:+.2f}%"


def _format_integer(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    return f"{int(round(numeric)):,}"


def _change_direction(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "unknown"
    if numeric > 0:
        return "up"
    if numeric < 0:
        return "down"
    return "flat"


def _pick_extreme(items: list[dict[str, Any]], *, reverse: bool) -> dict[str, Any] | None:
    if not items:
        return None
    return sorted(
        items,
        key=lambda item: (
            _to_float(item.get("change_pct")) if _to_float(item.get("change_pct")) is not None else float("-inf"),
            int(item.get("priority", 0) or 0),
        ),
        reverse=reverse,
    )[0]
