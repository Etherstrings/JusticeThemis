# -*- coding: utf-8 -*-
"""Tests for overnight source capture and recent-item listing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.config import Config
from src.overnight.source_registry import build_default_source_registry
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

