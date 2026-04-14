# -*- coding: utf-8 -*-
"""Tests for optional ticker enrichment services."""

from __future__ import annotations

from pathlib import Path
import tempfile

from app.db import Database
from app.repository import OvernightRepository
from app.services.ticker_enrichment import TickerEnrichmentService


class FakeTickerEnrichmentProvider:
    def __init__(
        self,
        *,
        name: str = "Fake Enrichment",
        supported_symbols: tuple[str, ...] = ("SOXX", "XLK"),
        configured: bool = True,
        fail_symbols: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.supported_symbols = set(supported_symbols)
        self.configured = configured
        self.fail_symbols = set(fail_symbols)
        self.calls: list[str] = []

    def is_configured(self) -> bool:
        return self.configured

    def supports_symbol(self, symbol: str) -> bool:
        return symbol in self.supported_symbols

    def fetch_symbol_context(self, *, symbol: str) -> dict[str, object]:
        self.calls.append(symbol)
        if symbol in self.fail_symbols:
            raise RuntimeError(f"provider failed for {symbol}")
        return {
            "profile": {"symbol": symbol, "name": f"Name {symbol}"},
            "quote": {"symbol": symbol, "price": 100.0},
        }


def test_ticker_enrichment_service_skips_when_no_trigger_is_present() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_enrichment_skip.db"))
        provider = FakeTickerEnrichmentProvider()
        service = TickerEnrichmentService(repo=repo, providers=[provider])

        result = service.collect(
            analysis_date="2026-04-10",
            session_name="daily_analysis",
            access_tier="free",
            mainlines=[],
            market_regimes=[],
            stock_calls=[],
        )

        assert result["status"] == "skipped"
        assert result["records"] == []
        assert provider.calls == []


def test_ticker_enrichment_service_persists_supported_symbols_for_premium_context() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_enrichment_premium.db"))
        provider = FakeTickerEnrichmentProvider()
        service = TickerEnrichmentService(repo=repo, providers=[provider])

        result = service.collect(
            analysis_date="2026-04-10",
            session_name="daily_analysis",
            access_tier="premium",
            mainlines=[
                {
                    "mainline_id": "tech_semiconductor__2026-04-10",
                    "affected_assets": ["SOXX", "^IXIC"],
                }
            ],
            market_regimes=[
                {
                    "regime_id": "2026-04-10__technology_risk_on",
                    "driving_symbols": ["XLK"],
                }
            ],
            stock_calls=[{"ticker": "688981.SH"}],
        )

        records = repo.list_ticker_enrichment_records(
            analysis_date="2026-04-10",
            session_name="daily_analysis",
        )

        assert result["status"] == "ok"
        assert result["attempted_symbol_count"] == 2
        assert {record["symbol"] for record in records} == {"SOXX", "XLK"}
        assert all(record["status"] == "ready" for record in records)
        assert provider.calls == ["SOXX", "XLK"]


def test_ticker_enrichment_service_is_non_blocking_when_provider_errors() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_enrichment_error.db"))
        provider = FakeTickerEnrichmentProvider(fail_symbols=("SOXX",))
        service = TickerEnrichmentService(repo=repo, providers=[provider])

        result = service.collect(
            analysis_date="2026-04-10",
            session_name="daily_analysis",
            access_tier="premium",
            mainlines=[
                {
                    "mainline_id": "tech_semiconductor__2026-04-10",
                    "affected_assets": ["SOXX"],
                }
            ],
            market_regimes=[],
            stock_calls=[],
        )

        records = repo.list_ticker_enrichment_records(
            analysis_date="2026-04-10",
            session_name="daily_analysis",
        )

        assert result["status"] == "degraded"
        assert result["error_count"] == 1
        assert records[0]["symbol"] == "SOXX"
        assert records[0]["status"] == "error"
