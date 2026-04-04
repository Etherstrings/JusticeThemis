# -*- coding: utf-8 -*-
"""Tests for the minimal overnight ledger pipeline."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import replace

import pytest

from src.config import Config
from src.overnight.clustering import build_event_cluster
from src.overnight.contradiction import find_contradictions
from src.overnight.normalizer import normalize_candidate
from src.overnight.types import SourceCandidate
from src.repositories.overnight_repo import OvernightRepository
from src.storage import DatabaseManager


@pytest.fixture()
def db_manager() -> DatabaseManager:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_overnight_ledger.db")
    previous_db_path = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path

    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()

    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if previous_db_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_db_path
        temp_dir.cleanup()


def test_normalizer_canonicalizes_url_and_extracts_tariff_fact() -> None:
    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url=(
            "https://ustr.gov/about-us/policy-offices/press-office/"
            "press-releases/2026/april/sample-announcement?utm_source=test#section"
        ),
        candidate_title="Fact Sheet: USTR announces 25% tariff on imported steel",
        candidate_summary=(
            "The Office of the United States Trade Representative said a 25% tariff "
            "would take effect immediately."
        ),
        candidate_section="Fact Sheet",
    )

    normalized = normalize_candidate(candidate)

    assert normalized.canonical_url == (
        "https://ustr.gov/about-us/policy-offices/press-office/"
        "press-releases/2026/april/sample-announcement"
    )
    assert normalized.document_type == "fact_sheet"
    assert any(entity.name == "USTR" for entity in normalized.entities)
    assert any(
        fact.metric == "tariff_rate" and fact.value == 25.0 and fact.unit == "percent"
        for fact in normalized.numeric_facts
    )


def test_repository_persists_versions_and_clusters_revisions(
    db_manager: DatabaseManager,
) -> None:
    repo = OvernightRepository(db_manager)

    raw_id_1 = repo.create_raw_record(
        source_id="ustr_press",
        fetch_mode="manual",
        payload_hash="payload-hash-v1",
    )
    raw_id_2 = repo.create_raw_record(
        source_id="ustr_press",
        fetch_mode="manual",
        payload_hash="payload-hash-v2",
    )

    candidate_v1 = SourceCandidate(
        candidate_type="article",
        candidate_url="https://ustr.gov/releases/sample-tariff-update?ref=home",
        candidate_title="USTR updates tariff guidance",
        candidate_summary="USTR confirms a 25% tariff on imported steel.",
        candidate_section="Press Release",
    )
    candidate_v2 = SourceCandidate(
        candidate_type="article",
        candidate_url="https://ustr.gov/releases/sample-tariff-update?ref=email",
        candidate_title="USTR updates tariff guidance and implementation timing",
        candidate_summary="USTR confirms a 25% tariff on imported steel effective Monday.",
        candidate_section="Press Release",
    )

    normalized_v1 = replace(normalize_candidate(candidate_v1), raw_id=raw_id_1)
    normalized_v2 = replace(normalize_candidate(candidate_v2), raw_id=raw_id_2)

    stored_v1 = repo.persist_source_item(normalized_v1)
    stored_v2 = repo.persist_source_item(normalized_v2)

    family_id_1 = repo.assign_document_family(
        stored_v1.id,
        family_key=stored_v1.canonical_url,
        family_type="canonical_document",
    )
    family_id_2 = repo.assign_document_family(
        stored_v2.id,
        family_key=stored_v2.canonical_url,
        family_type="canonical_document",
    )
    version_id_1 = repo.attach_document_version(
        stored_v1.id,
        body_hash=stored_v1.body_hash,
        title_hash=stored_v1.title_hash,
    )
    version_id_2 = repo.attach_document_version(
        stored_v2.id,
        body_hash=stored_v2.body_hash,
        title_hash=stored_v2.title_hash,
    )

    family_items = repo.list_source_items_by_family_key(stored_v1.canonical_url)
    cluster = build_event_cluster(family_items)

    assert family_id_1 == family_id_2
    assert version_id_1 != version_id_2
    assert len(family_items) == 2
    assert cluster.anchor_key == stored_v1.canonical_url
    assert cluster.status == "developing"
    assert cluster.event_update.update_type == "version_revised"
    assert cluster.contradictions == []


def test_contradiction_detection_flags_numeric_tariff_conflict(
    db_manager: DatabaseManager,
) -> None:
    repo = OvernightRepository(db_manager)

    raw_id_1 = repo.create_raw_record(
        source_id="ustr_press",
        fetch_mode="manual",
        payload_hash="payload-hash-conflict-1",
    )
    raw_id_2 = repo.create_raw_record(
        source_id="reuters_markets",
        fetch_mode="manual",
        payload_hash="payload-hash-conflict-2",
    )

    candidate_1 = SourceCandidate(
        candidate_type="article",
        candidate_url="https://ustr.gov/releases/tariff-decision",
        candidate_title="USTR confirms 25% tariff on imported steel",
        candidate_summary="The tariff rate was set at 25% for imported steel.",
        candidate_section="Press Release",
    )
    candidate_2 = SourceCandidate(
        candidate_type="article",
        candidate_url="https://www.reuters.com/world/us/tariff-decision-update",
        candidate_title="Report says tariff will be 15% on imported steel",
        candidate_summary="Officials said the tariff rate would be 15% for imported steel.",
        candidate_section="World",
    )

    stored_1 = repo.persist_source_item(replace(normalize_candidate(candidate_1), raw_id=raw_id_1))
    stored_2 = repo.persist_source_item(replace(normalize_candidate(candidate_2), raw_id=raw_id_2))

    contradictions = find_contradictions([stored_1, stored_2])
    cluster = build_event_cluster([stored_1, stored_2])

    assert len(contradictions) == 1
    assert contradictions[0].kind == "numeric_conflict"
    assert contradictions[0].metric == "tariff_rate"
    assert contradictions[0].values == {15.0, 25.0}
    assert cluster.status == "contradictory"
    assert len(cluster.contradictions) == 1


def test_single_item_with_multiple_tariff_facts_is_not_contradictory(
    db_manager: DatabaseManager,
) -> None:
    repo = OvernightRepository(db_manager)
    raw_id = repo.create_raw_record(
        source_id="white_house_fact_sheet",
        fetch_mode="manual",
        payload_hash="payload-hash-multi-fact",
    )

    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url="https://example.com/fact-sheet/tariffs",
        candidate_title="Fact Sheet: steel tariff set at 25% and aluminum tariff set at 10%",
        candidate_summary=(
            "The administration said the steel tariff is 25% and the aluminum tariff is 10%."
        ),
        candidate_section="Fact Sheet",
    )

    stored_item = repo.persist_source_item(replace(normalize_candidate(candidate), raw_id=raw_id))

    contradictions = find_contradictions([stored_item])
    cluster = build_event_cluster([stored_item])

    assert len(stored_item.numeric_facts) >= 2
    assert contradictions == []
    assert cluster.status == "confirmed"
    assert cluster.contradictions == []


def test_database_manager_upgrades_legacy_task1_overnight_schema_for_persistence() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "legacy_task1_overnight.db")
    previous_db_path = os.environ.get("DATABASE_PATH")

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE overnight_raw_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id VARCHAR(100) NOT NULL,
                fetch_mode VARCHAR(32) NOT NULL,
                payload_hash VARCHAR(128) NOT NULL,
                created_at DATETIME
            );
            CREATE TABLE overnight_source_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER NOT NULL,
                canonical_url VARCHAR(1000) NOT NULL,
                title VARCHAR(500) NOT NULL,
                document_type VARCHAR(50) NOT NULL,
                created_at DATETIME
            );
            CREATE TABLE overnight_event_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                core_fact TEXT NOT NULL UNIQUE,
                event_type VARCHAR(64) NOT NULL,
                event_subtype VARCHAR(64) NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    os.environ["DATABASE_PATH"] = db_path
    Config.reset_instance()
    DatabaseManager.reset_instance()

    try:
        db_manager = DatabaseManager.get_instance()
        repo = OvernightRepository(db_manager)
        raw_id = repo.create_raw_record(
            source_id="legacy-upgrade-source",
            fetch_mode="manual",
            payload_hash="legacy-upgrade-payload",
        )
        candidate = SourceCandidate(
            candidate_type="article",
            candidate_url="https://example.com/legacy-upgrade",
            candidate_title="USTR confirms 25% tariff on steel imports",
            candidate_summary="Officials said the tariff rate remains 25% for steel imports.",
            candidate_section="Press Release",
        )

        stored_item = repo.persist_source_item(replace(normalize_candidate(candidate), raw_id=raw_id))
        family_id = repo.assign_document_family(
            stored_item.id,
            family_key=stored_item.canonical_url,
            family_type="canonical_document",
        )
        version_id = repo.attach_document_version(
            stored_item.id,
            body_hash=stored_item.body_hash,
            title_hash=stored_item.title_hash,
        )
        family_items = repo.list_source_items_by_family_key(stored_item.canonical_url)

        inspect_connection = sqlite3.connect(db_path)
        try:
            source_item_columns = {
                row[1] for row in inspect_connection.execute("PRAGMA table_info(overnight_source_items)")
            }
            family_tables = {
                row[0]
                for row in inspect_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'overnight_document_%'"
                )
            }
        finally:
            inspect_connection.close()

        assert family_id > 0
        assert version_id > 0
        assert len(family_items) == 1
        assert {
            "summary",
            "title_hash",
            "body_hash",
            "content_hash",
            "normalized_entities",
            "normalized_numeric_facts",
            "family_id",
        }.issubset(source_item_columns)
        assert family_tables == {"overnight_document_families", "overnight_document_versions"}
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if previous_db_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_db_path
        temp_dir.cleanup()
