# -*- coding: utf-8 -*-
"""Tests for market capture-run, observation, and enrichment persistence."""

from __future__ import annotations

from pathlib import Path
import tempfile

from app.db import Database
from app.repository import OvernightRepository


def test_database_initializes_market_data_tables_idempotently() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_market_data_tables.db"
        Database(db_path)
        database = Database(db_path)

        with database.connect() as connection:
            tables = {
                str(row["name"])
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

    assert "overnight_market_capture_runs" in tables
    assert "overnight_market_observations" in tables
    assert "overnight_ticker_enrichment_records" in tables


def test_repository_round_trips_market_capture_runs_and_observations() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_market_capture_runs.db"))
        capture_run = repo.create_market_capture_run(
            analysis_date="2026-04-10",
            market_date="2026-04-09",
            session_name="us_close",
            status="completed",
            source_name="iFinD History",
            provider_hits={"iFinD History": 18, "Yahoo Finance": 2},
            missing_symbols=["^VIX"],
            diagnostics=[{"provider_name": "Yahoo Finance", "status": "fallback"}],
        )

        repo.upsert_market_observation(
            capture_run_id=int(capture_run["id"]),
            analysis_date="2026-04-10",
            market_date="2026-04-09",
            session_name="us_close",
            symbol="SOXX",
            display_name="半导体板块",
            provider_name="iFinD History",
            provider_symbol="SOXX.O",
            bucket="sector",
            market_timestamp="2026-04-09T20:00:00+00:00",
            close=220.5,
            previous_close=215.0,
            change_value=5.5,
            change_pct=2.5581,
            freshness_status="fresh",
            currency="USD",
            is_primary=True,
            is_fallback=False,
            provenance={"source_url": "ifind://history/SOXX.O"},
        )
        repo.upsert_market_observation(
            capture_run_id=int(capture_run["id"]),
            analysis_date="2026-04-10",
            market_date="2026-04-09",
            session_name="us_close",
            symbol="SOXX",
            display_name="半导体板块",
            provider_name="Yahoo Finance",
            provider_symbol="SOXX",
            bucket="sector",
            market_timestamp="2026-04-09T20:00:00+00:00",
            close=220.48,
            previous_close=215.0,
            change_value=5.48,
            change_pct=2.5488,
            freshness_status="fresh",
            currency="USD",
            is_primary=False,
            is_fallback=True,
            provenance={"source_url": "https://query2.finance.yahoo.com/v8/finance/chart/SOXX"},
        )

        runs = repo.list_market_capture_runs(analysis_date="2026-04-10", session_name="us_close")
        observations = repo.list_market_observations(analysis_date="2026-04-10", session_name="us_close")

    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["provider_hits"] == {"iFinD History": 18, "Yahoo Finance": 2}
    assert runs[0]["missing_symbols"] == ["^VIX"]

    assert [(item["symbol"], item["provider_name"]) for item in observations] == [
        ("SOXX", "Yahoo Finance"),
        ("SOXX", "iFinD History"),
    ]
    assert observations[0]["capture_run_id"] == capture_run["id"]
    assert observations[1]["capture_run_id"] == capture_run["id"]


def test_repository_round_trips_ticker_enrichment_records() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_ticker_enrichment_records.db"))
        record = repo.create_ticker_enrichment_record(
            analysis_date="2026-04-10",
            session_name="us_close",
            symbol="NVDA",
            provider_name="Finnhub",
            record_type="news",
            trigger_reason="regime:technology_risk_on",
            status="ready",
            payload={
                "headline_count": 3,
                "items": [{"title": "AI demand remains strong"}],
            },
        )

        records = repo.list_ticker_enrichment_records(
            analysis_date="2026-04-10",
            session_name="us_close",
            symbol="NVDA",
        )

    assert record["symbol"] == "NVDA"
    assert len(records) == 1
    assert records[0]["provider_name"] == "Finnhub"
    assert records[0]["record_type"] == "news"
    assert records[0]["trigger_reason"] == "regime:technology_risk_on"
