# -*- coding: utf-8 -*-
"""Repository for standalone overnight capture tables."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import sqlite3
from typing import Any

from app.db import Database
from app.ledger import StoredSourceItem
from app.normalizer import EntityMention, NormalizedSourceItem, NumericFact


class OvernightRepository:
    def __init__(self, database: Database | None = None) -> None:
        self.db = database or Database()

    def create_raw_record(self, source_id: str, fetch_mode: str, payload_hash: str) -> int:
        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO overnight_raw_records (source_id, fetch_mode, payload_hash)
                VALUES (?, ?, ?)
                """,
                (source_id, fetch_mode, payload_hash),
            )
            return int(cursor.lastrowid)

    def persist_source_item(self, item: NormalizedSourceItem) -> StoredSourceItem:
        if item.raw_id is None:
            raise ValueError("NormalizedSourceItem.raw_id is required for persistence")

        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO overnight_source_items (
                    raw_id,
                    canonical_url,
                    title,
                    summary,
                    excerpt_source,
                    capture_path,
                    capture_provider,
                    article_fetch_status,
                    document_type,
                    title_hash,
                    body_hash,
                    content_hash,
                    published_at,
                    published_at_source,
                    normalized_entities,
                    normalized_numeric_facts,
                    source_context_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.raw_id,
                    item.canonical_url,
                    item.title,
                    item.summary,
                    item.excerpt_source,
                    item.capture_path,
                    item.capture_provider,
                    item.article_fetch_status,
                    item.document_type,
                    item.title_hash,
                    item.body_hash,
                    item.content_hash,
                    item.published_at,
                    item.published_at_source,
                    json.dumps([asdict(entity) for entity in item.entities], ensure_ascii=True),
                    json.dumps([asdict(fact) for fact in item.numeric_facts], ensure_ascii=True),
                    json.dumps(item.source_context, ensure_ascii=True, sort_keys=True),
                ),
            )
            row = connection.execute(
                "SELECT * FROM overnight_source_items WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
            assert row is not None
            return self._to_stored_item(row)

    def assign_document_family(self, item_id: int, *, family_key: str, family_type: str) -> int:
        with self.db.connect() as connection:
            family = connection.execute(
                """
                SELECT * FROM overnight_document_families
                WHERE family_key = ?
                LIMIT 1
                """,
                (family_key,),
            ).fetchone()

            if family is None:
                cursor = connection.execute(
                    """
                    INSERT INTO overnight_document_families (family_key, family_type)
                    VALUES (?, ?)
                    """,
                    (family_key, family_type),
                )
                family_id = int(cursor.lastrowid)
            else:
                family_id = int(family["id"])

            connection.execute(
                """
                UPDATE overnight_source_items
                SET family_id = ?
                WHERE id = ?
                """,
                (family_id, item_id),
            )
            connection.execute(
                """
                UPDATE overnight_document_families
                SET family_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (family_type, family_id),
            )
            return family_id

    def attach_document_version(self, item_id: int, *, body_hash: str, title_hash: str) -> int:
        with self.db.connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM overnight_document_versions
                WHERE item_id = ? AND body_hash = ? AND title_hash = ?
                LIMIT 1
                """,
                (item_id, body_hash, title_hash),
            ).fetchone()
            if existing is not None:
                return int(existing["id"])

            cursor = connection.execute(
                """
                INSERT INTO overnight_document_versions (item_id, title_hash, body_hash)
                VALUES (?, ?, ?)
                """,
                (item_id, title_hash, body_hash),
            )
            return int(cursor.lastrowid)

    def list_source_items_by_family_key(self, family_key: str) -> list[StoredSourceItem]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    item.*,
                    family.family_key AS family_key,
                    family.family_type AS family_type,
                    family.id AS family_row_id,
                    version.id AS version_id
                FROM overnight_source_items AS item
                JOIN overnight_document_families AS family
                    ON item.family_id = family.id
                LEFT JOIN overnight_document_versions AS version
                    ON version.item_id = item.id
                WHERE family.family_key = ?
                ORDER BY item.created_at ASC, item.id ASC
                """,
                (family_key,),
            ).fetchall()
            return [self._to_stored_item(row) for row in rows]

    def list_latest_source_items_by_urls(self, urls: list[str]) -> dict[str, StoredSourceItem]:
        normalized_urls = [str(url).strip() for url in urls if str(url).strip()]
        if not normalized_urls:
            return {}

        placeholders = ", ".join("?" for _ in normalized_urls)
        query = f"""
            SELECT
                item.*,
                family.family_key AS family_key,
                family.family_type AS family_type,
                version.id AS version_id
            FROM overnight_source_items AS item
            LEFT JOIN overnight_document_families AS family
                ON item.family_id = family.id
            LEFT JOIN overnight_document_versions AS version
                ON version.item_id = item.id
            WHERE item.canonical_url IN ({placeholders})
            ORDER BY item.created_at DESC, item.id DESC
        """
        with self.db.connect() as connection:
            rows = connection.execute(query, normalized_urls).fetchall()

        latest_by_url: dict[str, StoredSourceItem] = {}
        for row in rows:
            canonical_url = str(row["canonical_url"]).strip()
            if not canonical_url or canonical_url in latest_by_url:
                continue
            latest_by_url[canonical_url] = self._to_stored_item(row)
        return latest_by_url

    def get_source_item_by_id(self, item_id: int) -> dict[str, object] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    item.*,
                    raw.source_id AS source_id,
                    raw.fetch_mode AS fetch_mode,
                    family.family_key AS family_key,
                    family.family_type AS family_type,
                    version.id AS version_id
                FROM overnight_source_items AS item
                JOIN overnight_raw_records AS raw
                    ON item.raw_id = raw.id
                LEFT JOIN overnight_document_families AS family
                    ON item.family_id = family.id
                LEFT JOIN overnight_document_versions AS version
                    ON version.item_id = item.id
                WHERE item.id = ?
                LIMIT 1
                """,
                (item_id,),
            ).fetchone()

        if row is None:
            return None
        return self._stored_item_payload(row)

    def list_recent_source_items(self, *, limit: int = 20, offset: int = 0) -> list[dict[str, object]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    item.*,
                    raw.source_id AS source_id,
                    raw.fetch_mode AS fetch_mode,
                    family.family_key AS family_key,
                    family.family_type AS family_type,
                    version.id AS version_id
                FROM overnight_source_items AS item
                JOIN overnight_raw_records AS raw
                    ON item.raw_id = raw.id
                LEFT JOIN overnight_document_families AS family
                    ON item.family_id = family.id
                LEFT JOIN overnight_document_versions AS version
                    ON version.item_id = item.id
                ORDER BY item.created_at DESC, item.id DESC
                LIMIT ?
                OFFSET ?
                """,
                (limit, max(0, offset)),
            ).fetchall()

        return [self._stored_item_payload(row) for row in rows]

    def list_source_items_for_analysis_date(self, *, analysis_date: str, limit: int = 20) -> list[dict[str, object]]:
        normalized_date = str(analysis_date or "").strip()
        if not normalized_date:
            return self.list_recent_source_items(limit=limit)

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    item.*,
                    raw.source_id AS source_id,
                    raw.fetch_mode AS fetch_mode,
                    family.family_key AS family_key,
                    family.family_type AS family_type,
                    version.id AS version_id
                FROM overnight_source_items AS item
                JOIN overnight_raw_records AS raw
                    ON item.raw_id = raw.id
                LEFT JOIN overnight_document_families AS family
                    ON item.family_id = family.id
                LEFT JOIN overnight_document_versions AS version
                    ON version.item_id = item.id
                WHERE item.created_at LIKE ? OR item.published_at LIKE ?
                ORDER BY item.created_at DESC, item.id DESC
                LIMIT ?
                """,
                (f"{normalized_date}%", f"{normalized_date}%", max(1, int(limit))),
            ).fetchall()

        return [self._stored_item_payload(row) for row in rows]

    def upsert_market_snapshot(
        self,
        *,
        analysis_date: str,
        market_date: str,
        session_name: str,
        source_name: str,
        source_url: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        snapshot_json = json.dumps(snapshot, ensure_ascii=True, sort_keys=True)
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO overnight_market_snapshots (
                    analysis_date,
                    market_date,
                    session_name,
                    source_name,
                    source_url,
                    snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(analysis_date, session_name) DO UPDATE SET
                    market_date = excluded.market_date,
                    source_name = excluded.source_name,
                    source_url = excluded.source_url,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    analysis_date,
                    market_date,
                    session_name,
                    source_name,
                    source_url,
                    snapshot_json,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_market_snapshots
                WHERE analysis_date = ? AND session_name = ?
                LIMIT 1
                """,
                (analysis_date, session_name),
            ).fetchone()

        assert row is not None
        return self._market_snapshot_payload(row)

    def create_market_capture_run(
        self,
        *,
        analysis_date: str,
        market_date: str,
        session_name: str,
        status: str = "running",
        source_name: str = "",
        provider_hits: dict[str, int] | None = None,
        missing_symbols: list[str] | None = None,
        diagnostics: list[dict[str, Any]] | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO overnight_market_capture_runs (
                    analysis_date,
                    market_date,
                    session_name,
                    status,
                    source_name,
                    provider_hits_json,
                    missing_symbols_json,
                    diagnostics_json,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
                """,
                (
                    analysis_date,
                    market_date,
                    session_name,
                    str(status or "").strip() or "running",
                    str(source_name or "").strip(),
                    json.dumps(dict(provider_hits or {}), ensure_ascii=True, sort_keys=True),
                    json.dumps(list(missing_symbols or []), ensure_ascii=True),
                    json.dumps(list(diagnostics or []), ensure_ascii=True),
                    str(started_at).strip() if started_at else None,
                    str(completed_at).strip() if completed_at else None,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_market_capture_runs
                WHERE id = ?
                LIMIT 1
                """,
                (int(cursor.lastrowid),),
            ).fetchone()

        assert row is not None
        return self._market_capture_run_payload(row)

    def list_market_capture_runs(
        self,
        *,
        analysis_date: str | None = None,
        session_name: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[object] = []
        if str(analysis_date or "").strip():
            conditions.append("analysis_date = ?")
            parameters.append(str(analysis_date).strip())
        if str(session_name or "").strip():
            conditions.append("session_name = ?")
            parameters.append(str(session_name).strip())

        query = """
            SELECT *
            FROM overnight_market_capture_runs
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY analysis_date DESC, id DESC LIMIT ?"
        parameters.append(max(1, int(limit)))

        with self.db.connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()

        return [self._market_capture_run_payload(row) for row in rows]

    def upsert_market_observation(
        self,
        *,
        capture_run_id: int,
        analysis_date: str,
        market_date: str,
        session_name: str,
        symbol: str,
        display_name: str,
        provider_name: str,
        provider_symbol: str,
        bucket: str,
        market_timestamp: str | None = None,
        close: float | None = None,
        previous_close: float | None = None,
        change_value: float | None = None,
        change_pct: float | None = None,
        currency: str = "",
        freshness_status: str = "",
        provenance: dict[str, Any] | None = None,
        is_primary: bool = False,
        is_fallback: bool = False,
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip()
        normalized_provider_name = str(provider_name or "").strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if not normalized_provider_name:
            raise ValueError("provider_name is required")

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO overnight_market_observations (
                    capture_run_id,
                    analysis_date,
                    market_date,
                    session_name,
                    symbol,
                    display_name,
                    provider_name,
                    provider_symbol,
                    bucket,
                    market_timestamp,
                    close,
                    previous_close,
                    change_value,
                    change_pct,
                    currency,
                    freshness_status,
                    provenance_json,
                    is_primary,
                    is_fallback
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capture_run_id, symbol, provider_name) DO UPDATE SET
                    analysis_date = excluded.analysis_date,
                    market_date = excluded.market_date,
                    session_name = excluded.session_name,
                    display_name = excluded.display_name,
                    provider_symbol = excluded.provider_symbol,
                    bucket = excluded.bucket,
                    market_timestamp = excluded.market_timestamp,
                    close = excluded.close,
                    previous_close = excluded.previous_close,
                    change_value = excluded.change_value,
                    change_pct = excluded.change_pct,
                    currency = excluded.currency,
                    freshness_status = excluded.freshness_status,
                    provenance_json = excluded.provenance_json,
                    is_primary = excluded.is_primary,
                    is_fallback = excluded.is_fallback,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    int(capture_run_id),
                    str(analysis_date or "").strip(),
                    str(market_date or "").strip(),
                    str(session_name or "").strip(),
                    normalized_symbol,
                    str(display_name or "").strip(),
                    normalized_provider_name,
                    str(provider_symbol or "").strip(),
                    str(bucket or "").strip(),
                    str(market_timestamp).strip() if market_timestamp else None,
                    float(close) if close is not None else None,
                    float(previous_close) if previous_close is not None else None,
                    float(change_value) if change_value is not None else None,
                    float(change_pct) if change_pct is not None else None,
                    str(currency or "").strip(),
                    str(freshness_status or "").strip(),
                    json.dumps(dict(provenance or {}), ensure_ascii=True, sort_keys=True),
                    1 if is_primary else 0,
                    1 if is_fallback else 0,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_market_observations
                WHERE capture_run_id = ? AND symbol = ? AND provider_name = ?
                LIMIT 1
                """,
                (int(capture_run_id), normalized_symbol, normalized_provider_name),
            ).fetchone()

        assert row is not None
        return self._market_observation_payload(row)

    def list_market_observations(
        self,
        *,
        analysis_date: str | None = None,
        session_name: str | None = None,
        capture_run_id: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[object] = []
        if capture_run_id is not None:
            conditions.append("capture_run_id = ?")
            parameters.append(int(capture_run_id))
        if str(analysis_date or "").strip():
            conditions.append("analysis_date = ?")
            parameters.append(str(analysis_date).strip())
        if str(session_name or "").strip():
            conditions.append("session_name = ?")
            parameters.append(str(session_name).strip())

        query = """
            SELECT *
            FROM overnight_market_observations
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(max(1, int(limit)))

        with self.db.connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()

        return [self._market_observation_payload(row) for row in rows]

    def create_ticker_enrichment_record(
        self,
        *,
        analysis_date: str,
        session_name: str,
        symbol: str,
        provider_name: str,
        record_type: str,
        trigger_reason: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO overnight_ticker_enrichment_records (
                    analysis_date,
                    session_name,
                    symbol,
                    provider_name,
                    record_type,
                    trigger_reason,
                    status,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(analysis_date or "").strip(),
                    str(session_name or "").strip(),
                    str(symbol or "").strip(),
                    str(provider_name or "").strip(),
                    str(record_type or "").strip(),
                    str(trigger_reason or "").strip(),
                    str(status or "").strip() or "ready",
                    json.dumps(dict(payload or {}), ensure_ascii=True, sort_keys=True),
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_ticker_enrichment_records
                WHERE id = ?
                LIMIT 1
                """,
                (int(cursor.lastrowid),),
            ).fetchone()

        assert row is not None
        return self._ticker_enrichment_payload(row)

    def list_ticker_enrichment_records(
        self,
        *,
        analysis_date: str | None = None,
        session_name: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[object] = []
        if str(analysis_date or "").strip():
            conditions.append("analysis_date = ?")
            parameters.append(str(analysis_date).strip())
        if str(session_name or "").strip():
            conditions.append("session_name = ?")
            parameters.append(str(session_name).strip())
        if str(symbol or "").strip():
            conditions.append("symbol = ?")
            parameters.append(str(symbol).strip())

        query = """
            SELECT *
            FROM overnight_ticker_enrichment_records
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(max(1, int(limit)))

        with self.db.connect() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()

        return [self._ticker_enrichment_payload(row) for row in rows]

    def get_market_snapshot(self, *, analysis_date: str, session_name: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM overnight_market_snapshots
                WHERE analysis_date = ? AND session_name = ?
                LIMIT 1
                """,
                (analysis_date, session_name),
            ).fetchone()

        if row is None:
            return None
        return self._market_snapshot_payload(row)

    def get_latest_market_snapshot(self, *, session_name: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM overnight_market_snapshots
                WHERE session_name = ?
                ORDER BY analysis_date DESC, id DESC
                LIMIT 1
                """,
                (session_name,),
            ).fetchone()

        if row is None:
            return None
        return self._market_snapshot_payload(row)

    def create_daily_analysis_report(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        provider_name: str,
        provider_model: str,
        input_item_ids: list[int],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            version_row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) AS max_version
                FROM overnight_daily_analysis_reports
                WHERE analysis_date = ? AND access_tier = ?
                """,
                (analysis_date, access_tier),
            ).fetchone()
            version = int(version_row["max_version"] or 0) + 1
            cursor = connection.execute(
                """
                INSERT INTO overnight_daily_analysis_reports (
                    analysis_date,
                    access_tier,
                    version,
                    provider_name,
                    provider_model,
                    input_item_ids,
                    report_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_date,
                    access_tier,
                    version,
                    provider_name,
                    provider_model,
                    json.dumps(input_item_ids, ensure_ascii=True),
                    json.dumps(report, ensure_ascii=True),
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_daily_analysis_reports
                WHERE id = ?
                LIMIT 1
                """,
                (int(cursor.lastrowid),),
            ).fetchone()

        assert row is not None
        return self._daily_analysis_payload(row)

    def get_latest_daily_analysis_report(self, *, analysis_date: str, access_tier: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM overnight_daily_analysis_reports
                WHERE analysis_date = ? AND access_tier = ?
                ORDER BY version DESC, id DESC
                LIMIT 1
                """,
                (analysis_date, access_tier),
            ).fetchone()

        if row is None:
            return None
        return self._daily_analysis_payload(row)

    def get_daily_analysis_report_version(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        version: int,
    ) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM overnight_daily_analysis_reports
                WHERE analysis_date = ? AND access_tier = ? AND version = ?
                LIMIT 1
                """,
                (analysis_date, access_tier, version),
            ).fetchone()

        if row is None:
            return None
        return self._daily_analysis_payload(row)

    def list_daily_analysis_report_versions(self, *, analysis_date: str, access_tier: str) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM overnight_daily_analysis_reports
                WHERE analysis_date = ? AND access_tier = ?
                ORDER BY version DESC, id DESC
                """,
                (analysis_date, access_tier),
            ).fetchall()

        return [self._daily_analysis_version_payload(row) for row in rows]

    def list_source_refresh_states(self, *, source_ids: list[str] | None = None) -> dict[str, dict[str, object]]:
        normalized_source_ids = [str(source_id).strip() for source_id in list(source_ids or []) if str(source_id).strip()]
        query = """
            SELECT *
            FROM overnight_source_refresh_state
        """
        parameters: tuple[object, ...] = ()
        if normalized_source_ids:
            placeholders = ", ".join("?" for _ in normalized_source_ids)
            query += f" WHERE source_id IN ({placeholders})"
            parameters = tuple(normalized_source_ids)
        query += " ORDER BY source_id ASC"

        with self.db.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return {
            str(row["source_id"]).strip(): self._source_refresh_state_payload(row)
            for row in rows
            if str(row["source_id"]).strip()
        }

    def upsert_source_refresh_state(
        self,
        *,
        source_id: str,
        last_status: str,
        last_error: str = "",
        consecutive_failure_count: int = 0,
        cooldown_until: str | None = None,
        last_attempted_at: str | None = None,
        last_success_at: str | None = None,
        last_candidate_count: int = 0,
        last_selected_candidate_count: int = 0,
        last_persisted_count: int = 0,
        last_elapsed_seconds: float = 0.0,
    ) -> dict[str, object]:
        normalized_source_id = str(source_id).strip()
        if not normalized_source_id:
            raise ValueError("source_id is required")

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO overnight_source_refresh_state (
                    source_id,
                    last_status,
                    last_error,
                    consecutive_failure_count,
                    cooldown_until,
                    last_attempted_at,
                    last_success_at,
                    last_candidate_count,
                    last_selected_candidate_count,
                    last_persisted_count,
                    last_elapsed_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_status = excluded.last_status,
                    last_error = excluded.last_error,
                    consecutive_failure_count = excluded.consecutive_failure_count,
                    cooldown_until = excluded.cooldown_until,
                    last_attempted_at = excluded.last_attempted_at,
                    last_success_at = excluded.last_success_at,
                    last_candidate_count = excluded.last_candidate_count,
                    last_selected_candidate_count = excluded.last_selected_candidate_count,
                    last_persisted_count = excluded.last_persisted_count,
                    last_elapsed_seconds = excluded.last_elapsed_seconds,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    normalized_source_id,
                    str(last_status or "").strip(),
                    str(last_error or "").strip(),
                    max(0, int(consecutive_failure_count)),
                    str(cooldown_until).strip() if cooldown_until else None,
                    str(last_attempted_at).strip() if last_attempted_at else None,
                    str(last_success_at).strip() if last_success_at else None,
                    max(0, int(last_candidate_count)),
                    max(0, int(last_selected_candidate_count)),
                    max(0, int(last_persisted_count)),
                    float(last_elapsed_seconds or 0.0),
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM overnight_source_refresh_state
                WHERE source_id = ?
                LIMIT 1
                """,
                (normalized_source_id,),
            ).fetchone()

        assert row is not None
        return self._source_refresh_state_payload(row)

    def _stored_item_payload(self, row: sqlite3.Row) -> dict[str, object]:
        stored_item = self._to_stored_item(row)
        return {
            "item_id": stored_item.id,
            "source_id": row["source_id"],
            "canonical_url": stored_item.canonical_url,
            "title": stored_item.title,
            "summary": stored_item.summary,
            "excerpt_source": stored_item.excerpt_source,
            "capture_path": stored_item.capture_path,
            "capture_provider": stored_item.capture_provider or None,
            "article_fetch_status": stored_item.article_fetch_status,
            "document_type": stored_item.document_type,
            "published_at": stored_item.published_at,
            "published_at_source": stored_item.published_at_source,
            "created_at": stored_item.created_at.isoformat(timespec="seconds")
            if stored_item.created_at
            else None,
            "entities": [asdict(entity) for entity in stored_item.entities],
            "numeric_facts": [asdict(fact) for fact in stored_item.numeric_facts],
            "source_context": dict(stored_item.source_context),
            "family_id": stored_item.family_id,
            "family_key": stored_item.family_key,
            "family_type": stored_item.family_type,
            "version_id": stored_item.version_id,
        }

    def _daily_analysis_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        report_json = str(row["report_json"] or "{}")
        input_item_ids_json = str(row["input_item_ids"] or "[]")
        report = json.loads(report_json)
        return {
            "analysis_date": str(row["analysis_date"]),
            "access_tier": str(row["access_tier"]),
            "version": int(row["version"]),
            "generated_at": str(row["created_at"]).replace(" ", "T"),
            "provider": {
                "name": str(row["provider_name"] or ""),
                "model": str(row["provider_model"] or "") or None,
            },
            "input_item_ids": [int(item) for item in json.loads(input_item_ids_json)],
            "input_fingerprint": self._stable_fingerprint(input_item_ids_json),
            "report_fingerprint": self._stable_fingerprint(report_json),
            **report,
        }

    def _daily_analysis_version_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        report_json = str(row["report_json"] or "{}")
        input_item_ids_json = str(row["input_item_ids"] or "[]")
        report = json.loads(report_json)
        summary = dict(report.get("summary", {}) or {})
        return {
            "analysis_date": str(row["analysis_date"]),
            "access_tier": str(row["access_tier"]),
            "version": int(row["version"]),
            "generated_at": str(row["created_at"]).replace(" ", "T"),
            "provider": {
                "name": str(row["provider_name"] or ""),
                "model": str(row["provider_model"] or "") or None,
            },
            "input_item_ids": [int(item) for item in json.loads(input_item_ids_json)],
            "input_fingerprint": self._stable_fingerprint(input_item_ids_json),
            "report_fingerprint": self._stable_fingerprint(report_json),
            "headline": str(summary.get("headline", "")).strip(),
            "confidence": str(summary.get("confidence", "")).strip(),
        }

    def _source_refresh_state_payload(self, row: sqlite3.Row) -> dict[str, object]:
        return {
            "source_id": str(row["source_id"]).strip(),
            "last_refresh_status": str(row["last_status"] or "").strip(),
            "last_error": str(row["last_error"] or "").strip() or None,
            "consecutive_failure_count": int(row["consecutive_failure_count"] or 0),
            "cooldown_until": str(row["cooldown_until"]).strip() if row["cooldown_until"] else None,
            "last_attempted_at": str(row["last_attempted_at"]).strip() if row["last_attempted_at"] else None,
            "last_success_at": str(row["last_success_at"]).strip() if row["last_success_at"] else None,
            "last_candidate_count": int(row["last_candidate_count"] or 0),
            "last_selected_candidate_count": int(row["last_selected_candidate_count"] or 0),
            "last_persisted_count": int(row["last_persisted_count"] or 0),
            "last_elapsed_seconds": round(float(row["last_elapsed_seconds"] or 0.0), 3),
            "updated_at": str(row["updated_at"]).replace(" ", "T") if row["updated_at"] else None,
        }

    def _market_capture_run_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "analysis_date": str(row["analysis_date"]).strip(),
            "market_date": str(row["market_date"]).strip(),
            "session_name": str(row["session_name"]).strip(),
            "status": str(row["status"] or "").strip(),
            "source_name": str(row["source_name"] or "").strip(),
            "provider_hits": json.loads(str(row["provider_hits_json"] or "{}")),
            "missing_symbols": list(json.loads(str(row["missing_symbols_json"] or "[]"))),
            "diagnostics": list(json.loads(str(row["diagnostics_json"] or "[]"))),
            "started_at": str(row["started_at"]).replace(" ", "T") if row["started_at"] else None,
            "completed_at": str(row["completed_at"]).replace(" ", "T") if row["completed_at"] else None,
            "created_at": str(row["created_at"]).replace(" ", "T") if row["created_at"] else None,
            "updated_at": str(row["updated_at"]).replace(" ", "T") if row["updated_at"] else None,
        }

    def _market_observation_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "capture_run_id": int(row["capture_run_id"]),
            "analysis_date": str(row["analysis_date"]).strip(),
            "market_date": str(row["market_date"]).strip(),
            "session_name": str(row["session_name"]).strip(),
            "symbol": str(row["symbol"]).strip(),
            "display_name": str(row["display_name"] or "").strip(),
            "provider_name": str(row["provider_name"]).strip(),
            "provider_symbol": str(row["provider_symbol"] or "").strip(),
            "bucket": str(row["bucket"] or "").strip(),
            "market_timestamp": str(row["market_timestamp"]).replace(" ", "T") if row["market_timestamp"] else None,
            "close": float(row["close"]) if row["close"] is not None else None,
            "previous_close": float(row["previous_close"]) if row["previous_close"] is not None else None,
            "change_value": float(row["change_value"]) if row["change_value"] is not None else None,
            "change_pct": float(row["change_pct"]) if row["change_pct"] is not None else None,
            "currency": str(row["currency"] or "").strip(),
            "freshness_status": str(row["freshness_status"] or "").strip(),
            "provenance": json.loads(str(row["provenance_json"] or "{}")),
            "is_primary": bool(int(row["is_primary"] or 0)),
            "is_fallback": bool(int(row["is_fallback"] or 0)),
            "created_at": str(row["created_at"]).replace(" ", "T") if row["created_at"] else None,
            "updated_at": str(row["updated_at"]).replace(" ", "T") if row["updated_at"] else None,
        }

    def _ticker_enrichment_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "analysis_date": str(row["analysis_date"]).strip(),
            "session_name": str(row["session_name"]).strip(),
            "symbol": str(row["symbol"]).strip(),
            "provider_name": str(row["provider_name"]).strip(),
            "record_type": str(row["record_type"]).strip(),
            "trigger_reason": str(row["trigger_reason"] or "").strip(),
            "status": str(row["status"] or "").strip(),
            "payload": json.loads(str(row["payload_json"] or "{}")),
            "created_at": str(row["created_at"]).replace(" ", "T") if row["created_at"] else None,
            "updated_at": str(row["updated_at"]).replace(" ", "T") if row["updated_at"] else None,
        }

    def _market_snapshot_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        snapshot = json.loads(str(row["snapshot_json"] or "{}"))
        return {
            "analysis_date": str(row["analysis_date"]),
            "market_date": str(row["market_date"]),
            "session_name": str(row["session_name"]),
            "source_name": str(row["source_name"] or ""),
            "source_url": str(row["source_url"] or ""),
            "generated_at": str(row["updated_at"] or row["created_at"]).replace(" ", "T"),
            **snapshot,
        }

    def _stable_fingerprint(self, payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _to_stored_item(self, row: sqlite3.Row) -> StoredSourceItem:
        family_id = row["family_id"] if "family_id" in row.keys() else None
        family_key = row["family_key"] if "family_key" in row.keys() else None
        family_type = row["family_type"] if "family_type" in row.keys() else None
        version_id = row["version_id"] if "version_id" in row.keys() else None

        created_at_value = row["created_at"]
        created_at = None
        if created_at_value:
            created_at = datetime.fromisoformat(str(created_at_value).replace(" ", "T"))

        return StoredSourceItem(
            id=int(row["id"]),
            raw_id=int(row["raw_id"]),
            canonical_url=str(row["canonical_url"]),
            title=str(row["title"]),
            summary=str(row["summary"] or ""),
            excerpt_source=str(row["excerpt_source"] or ""),
            document_type=str(row["document_type"]),
            published_at=str(row["published_at"]) if row["published_at"] is not None else None,
            published_at_source=str(row["published_at_source"] or ""),
            title_hash=str(row["title_hash"] or ""),
            body_hash=str(row["body_hash"] or ""),
            content_hash=str(row["content_hash"] or ""),
            capture_path=str(row["capture_path"] or "direct"),
            capture_provider=str(row["capture_provider"] or ""),
            article_fetch_status=str(row["article_fetch_status"] or "not_attempted"),
            entities=tuple(EntityMention(**item) for item in json.loads(row["normalized_entities"] or "[]")),
            numeric_facts=tuple(NumericFact(**item) for item in json.loads(row["normalized_numeric_facts"] or "[]")),
            source_context=json.loads(str(row["source_context_json"] or "{}")),
            family_id=int(family_id) if family_id is not None else None,
            family_key=str(family_key) if family_key is not None else None,
            family_type=str(family_type) if family_type is not None else None,
            version_id=int(version_id) if version_id is not None else None,
            created_at=created_at,
        )
