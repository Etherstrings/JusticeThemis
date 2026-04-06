# -*- coding: utf-8 -*-
"""Tests for overnight source capture and recent-item listing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.config import Config
from src.overnight.source_registry import build_default_source_registry
from src.overnight.types import SourceCandidate, SourceDefinition
from src.repositories.overnight_repo import OvernightRepository
from src.services.overnight_source_capture_service import OvernightSourceCaptureService
from src.storage import DatabaseManager


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class RoutingFixtureClient:
    def __init__(self, routes: dict[str, Path]):
        self.routes = routes
        self.fetches: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetches.append(url)
        for fragment, fixture_path in self.routes.items():
            if fragment in url:
                return fixture_path.read_text(encoding="utf-8")
        raise AssertionError(f"No fixture mapped for url: {url}")


@pytest.fixture()
def db_manager() -> DatabaseManager:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_overnight_source_capture.db")
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


def test_source_capture_service_collects_and_lists_recent_items(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    http_client = RoutingFixtureClient(
        {
            "whitehouse.gov/news/": FIXTURE_DIR / "whitehouse_news.html",
            "whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html",
        }
    )
    registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
    service = OvernightSourceCaptureService(
        repo=repo,
        registry=registry,
        http_client=http_client,
    )

    result = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)

    assert result["collected_sources"] == 1
    assert result["collected_items"] == 1
    assert result["items"][0]["source_id"] == "whitehouse_news"
    assert result["items"][0]["source_name"] == "White House News"
    assert result["items"][0]["title"] == "Statement from the White House"
    assert result["items"][0]["summary"].startswith("The White House announced")

    recent_items = service.list_recent_items(limit=5)
    assert recent_items["total"] == 1
    assert recent_items["items"][0]["canonical_url"].startswith("https://www.whitehouse.gov/briefing-room/")


def test_source_capture_service_selects_highest_priority_sources_first(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    registry = [
        SourceDefinition(
            source_id="low_priority",
            display_name="Low Priority",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/low.xml",),
            priority=10,
            poll_interval_seconds=300,
        ),
        SourceDefinition(
            source_id="high_priority",
            display_name="High Priority",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/high.xml",),
            priority=100,
            poll_interval_seconds=300,
        ),
        SourceDefinition(
            source_id="medium_priority",
            display_name="Medium Priority",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/medium.xml",),
            priority=60,
            poll_interval_seconds=300,
        ),
    ]
    service = OvernightSourceCaptureService(repo=repo, registry=registry, http_client=RoutingFixtureClient({}))

    selected = service._select_sources(max_sources=2)

    assert [source.source_id for source in selected] == ["high_priority", "medium_priority"]


def test_source_capture_service_keeps_going_until_it_fills_successful_sources(db_manager: DatabaseManager) -> None:
    repo = OvernightRepository(db_manager)
    registry = [
        SourceDefinition(
            source_id="first_empty",
            display_name="First Empty",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/first.xml",),
            priority=100,
            poll_interval_seconds=300,
        ),
        SourceDefinition(
            source_id="second_working",
            display_name="Second Working",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/second.xml",),
            priority=90,
            poll_interval_seconds=300,
        ),
        SourceDefinition(
            source_id="third_working",
            display_name="Third Working",
            organization_type="official_policy",
            source_class="policy",
            entry_type="rss",
            entry_urls=("https://example.com/third.xml",),
            priority=80,
            poll_interval_seconds=300,
        ),
    ]
    service = OvernightSourceCaptureService(repo=repo, registry=registry, http_client=RoutingFixtureClient({}))

    candidate = SourceCandidate(
        candidate_type="feed_item",
        candidate_url="https://example.com/item-1",
        candidate_title="Sample title",
        candidate_summary="Sample summary",
        needs_article_fetch=False,
    )

    captured_ids: list[str] = []

    def fake_collect(source: SourceDefinition):
        if source.source_id == "first_empty":
            return []
        return [candidate]

    def fake_persist(source: SourceDefinition, _candidate: SourceCandidate):
        captured_ids.append(source.source_id)
        return object()

    service._collect_source_candidates = fake_collect  # type: ignore[method-assign]
    service._persist_candidate = fake_persist  # type: ignore[method-assign]
    service.list_recent_items = lambda limit=20: {"total": len(captured_ids), "items": []}  # type: ignore[assignment]

    result = service.refresh(limit_per_source=1, max_sources=2, recent_limit=5)

    assert result["collected_sources"] == 2
    assert captured_ids == ["second_working", "third_working"]
