# -*- coding: utf-8 -*-
"""Tests for cached/live source excerpt enrichment."""

from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from src.config import Config
from src.overnight.normalizer import normalize_candidate
from src.overnight.types import SourceCandidate
from src.repositories.overnight_repo import OvernightRepository
from src.services.overnight_source_excerpt_service import OvernightSourceExcerptService
from src.storage import DatabaseManager, OvernightSourceItem


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class FixtureClient:
    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path
        self.fetch_count = 0

    def fetch(self, _url: str) -> str:
        self.fetch_count += 1
        return self.fixture_path.read_text(encoding="utf-8")


def _make_cached_candidate_summary():
    return normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/",
            candidate_title="Statement from the White House",
            candidate_summary="Cached White House summary.",
            candidate_section="White House News",
        )
    )


@pytest.fixture()
def db_manager() -> DatabaseManager:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_overnight_source_excerpt.db")
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


def test_enrich_source_excerpt_fetches_article_shell_and_persists_cache(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    fixture_client = FixtureClient(FIXTURE_DIR / "whitehouse_news.html")
    service = OvernightSourceExcerptService(repo=repo, http_client=fixture_client)

    enriched = service.resolve(
        url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/?utm_source=test",
        fallback_title="Fallback title",
        source_id="whitehouse_news",
    )

    assert enriched is not None
    assert enriched.title == "Statement from the White House"
    assert enriched.summary.startswith("The White House announced")
    assert fixture_client.fetch_count == 1

    with db_manager.get_session() as session:
        rows = session.query(OvernightSourceItem).all()

    assert len(rows) == 1
    assert rows[0].canonical_url == "https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/"
    assert rows[0].summary.startswith("The White House announced")


def test_enrich_source_excerpt_reuses_cached_source_item_without_refetch(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    raw_id = repo.create_raw_record(
        source_id="whitehouse_news",
        fetch_mode="manual",
        payload_hash="cached-whitehouse-item",
    )
    stored = repo.persist_source_item(replace(_make_cached_candidate_summary(), raw_id=raw_id))
    fixture_client = FixtureClient(FIXTURE_DIR / "whitehouse_news.html")
    service = OvernightSourceExcerptService(repo=repo, http_client=fixture_client)

    enriched = service.resolve(
        url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/?utm_source=test",
        fallback_title="Fallback title",
        source_id="whitehouse_news",
    )

    assert enriched is not None
    assert enriched.id == stored.id
    assert enriched.summary == "Cached White House summary."
    assert fixture_client.fetch_count == 0
