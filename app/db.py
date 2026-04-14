# -*- coding: utf-8 -*-
"""SQLite bootstrap for the standalone overnight news handoff app."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS overnight_raw_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    fetch_mode TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_overnight_raw_records_source_id
    ON overnight_raw_records(source_id);

CREATE INDEX IF NOT EXISTS idx_overnight_raw_records_payload_hash
    ON overnight_raw_records(payload_hash);

CREATE TABLE IF NOT EXISTS overnight_source_refresh_state (
    source_id TEXT PRIMARY KEY,
    last_status TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    consecutive_failure_count INTEGER NOT NULL DEFAULT 0,
    cooldown_until TEXT,
    last_attempted_at TEXT,
    last_success_at TEXT,
    last_candidate_count INTEGER NOT NULL DEFAULT 0,
    last_selected_candidate_count INTEGER NOT NULL DEFAULT 0,
    last_persisted_count INTEGER NOT NULL DEFAULT 0,
    last_elapsed_seconds REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overnight_document_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_key TEXT NOT NULL UNIQUE,
    family_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overnight_source_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    excerpt_source TEXT NOT NULL DEFAULT '',
    capture_path TEXT NOT NULL DEFAULT 'direct',
    capture_provider TEXT NOT NULL DEFAULT '',
    article_fetch_status TEXT NOT NULL DEFAULT 'not_attempted',
    document_type TEXT NOT NULL,
    title_hash TEXT,
    body_hash TEXT,
    content_hash TEXT,
    published_at TEXT,
    published_at_source TEXT NOT NULL DEFAULT '',
    normalized_entities TEXT NOT NULL DEFAULT '[]',
    normalized_numeric_facts TEXT NOT NULL DEFAULT '[]',
    family_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(raw_id) REFERENCES overnight_raw_records(id),
    FOREIGN KEY(family_id) REFERENCES overnight_document_families(id)
);

CREATE INDEX IF NOT EXISTS idx_overnight_source_items_raw_id
    ON overnight_source_items(raw_id);

CREATE INDEX IF NOT EXISTS idx_overnight_source_items_canonical_url
    ON overnight_source_items(canonical_url);

CREATE INDEX IF NOT EXISTS idx_overnight_source_items_created_at
    ON overnight_source_items(created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_overnight_source_items_family_id
    ON overnight_source_items(family_id);

CREATE TABLE IF NOT EXISTS overnight_document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    title_hash TEXT NOT NULL,
    body_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(item_id) REFERENCES overnight_source_items(id),
    UNIQUE(item_id, title_hash, body_hash)
);

CREATE INDEX IF NOT EXISTS idx_overnight_document_versions_item_id
    ON overnight_document_versions(item_id);

CREATE TABLE IF NOT EXISTS overnight_market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    market_date TEXT NOT NULL,
    session_name TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analysis_date, session_name)
);

CREATE INDEX IF NOT EXISTS idx_overnight_market_snapshots_lookup
    ON overnight_market_snapshots(session_name, analysis_date DESC);

CREATE TABLE IF NOT EXISTS overnight_market_capture_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    market_date TEXT NOT NULL,
    session_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    source_name TEXT NOT NULL DEFAULT '',
    provider_hits_json TEXT NOT NULL DEFAULT '{}',
    missing_symbols_json TEXT NOT NULL DEFAULT '[]',
    diagnostics_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_overnight_market_capture_runs_lookup
    ON overnight_market_capture_runs(session_name, analysis_date DESC, id DESC);

CREATE TABLE IF NOT EXISTS overnight_market_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_run_id INTEGER NOT NULL,
    analysis_date TEXT NOT NULL,
    market_date TEXT NOT NULL,
    session_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    provider_name TEXT NOT NULL,
    provider_symbol TEXT NOT NULL DEFAULT '',
    bucket TEXT NOT NULL,
    market_timestamp TEXT,
    close REAL,
    previous_close REAL,
    change_value REAL,
    change_pct REAL,
    currency TEXT NOT NULL DEFAULT '',
    freshness_status TEXT NOT NULL DEFAULT '',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    is_primary INTEGER NOT NULL DEFAULT 0,
    is_fallback INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(capture_run_id) REFERENCES overnight_market_capture_runs(id) ON DELETE CASCADE,
    UNIQUE(capture_run_id, symbol, provider_name)
);

CREATE INDEX IF NOT EXISTS idx_overnight_market_observations_lookup
    ON overnight_market_observations(session_name, analysis_date DESC, symbol, provider_name);

CREATE INDEX IF NOT EXISTS idx_overnight_market_observations_capture_run_id
    ON overnight_market_observations(capture_run_id, id DESC);

CREATE TABLE IF NOT EXISTS overnight_ticker_enrichment_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    session_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    record_type TEXT NOT NULL,
    trigger_reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ready',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_overnight_ticker_enrichment_records_lookup
    ON overnight_ticker_enrichment_records(analysis_date, session_name, symbol, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS overnight_daily_analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    access_tier TEXT NOT NULL,
    version INTEGER NOT NULL,
    provider_name TEXT NOT NULL DEFAULT '',
    provider_model TEXT NOT NULL DEFAULT '',
    input_item_ids TEXT NOT NULL DEFAULT '[]',
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analysis_date, access_tier, version)
);

CREATE INDEX IF NOT EXISTS idx_overnight_daily_analysis_reports_lookup
    ON overnight_daily_analysis_reports(analysis_date, access_tier, version DESC);
"""

_REQUIRED_SOURCE_ITEM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("excerpt_source", "TEXT NOT NULL DEFAULT ''"),
    ("capture_path", "TEXT NOT NULL DEFAULT 'direct'"),
    ("capture_provider", "TEXT NOT NULL DEFAULT ''"),
    ("article_fetch_status", "TEXT NOT NULL DEFAULT 'not_attempted'"),
    ("published_at_source", "TEXT NOT NULL DEFAULT ''"),
)


class Database:
    """Small SQLite helper scoped to this standalone project."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = path or os.environ.get("OVERNIGHT_NEWS_DB_PATH") or "data/overnight-news-handoff.db"
        self.path = Path(configured_path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._ensure_required_columns(connection)

    def _ensure_required_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(overnight_source_items)").fetchall()
        }
        for column_name, column_definition in _REQUIRED_SOURCE_ITEM_COLUMNS:
            if column_name in existing_columns:
                continue
            connection.execute(
                f"ALTER TABLE overnight_source_items ADD COLUMN {column_name} {column_definition}"
            )
