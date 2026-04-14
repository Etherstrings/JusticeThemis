# -*- coding: utf-8 -*-
"""Tests for cached/live source excerpt enrichment."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

import requests

from app.db import Database
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.source_excerpt import OvernightSourceExcerptService, RequestsHttpClient
from app.sources.types import SourceCandidate


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class FixtureClient:
    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path
        self.fetch_count = 0

    def fetch(self, _url: str) -> str:
        self.fetch_count += 1
        return self.fixture_path.read_text(encoding="utf-8")


class _FakeResponse:
    def __init__(
        self,
        *,
        text: str,
        status_code: int = 200,
        encoding: str = "utf-8",
        apparent_encoding: str = "utf-8",
    ) -> None:
        self._raw_bytes = text.encode("utf-8")
        self.status_code = status_code
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding

    @property
    def text(self) -> str:
        return self._raw_bytes.decode(self.encoding, errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class _FlakySession:
    def __init__(self) -> None:
        self.call_count = 0

    def get(self, _url: str, *, timeout: int, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        self.call_count += 1
        if self.call_count < 3:
            raise requests.exceptions.SSLError("EOF occurred in violation of protocol")
        return _FakeResponse(text="<html>ok</html>")


class _EncodingPreferenceSession:
    def get(self, _url: str, *, timeout: int, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        return _FakeResponse(
            text="Summary of Economic Projections — Participants submitted projections for inflation.",
            encoding="ISO-8859-1",
            apparent_encoding="utf-8",
        )


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


def test_enrich_source_excerpt_fetches_article_shell_and_persists_cache() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_overnight_source_excerpt.db")
        repo = OvernightRepository(database)
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

        cached = repo.list_latest_source_items_by_urls(
            ["https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/"]
        )
        assert cached
        assert next(iter(cached.values())).summary.startswith("The White House announced")


def test_enrich_source_excerpt_reuses_cached_source_item_without_refetch() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_overnight_source_excerpt_cache.db")
        repo = OvernightRepository(database)
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


def test_requests_http_client_retries_transient_ssl_failures() -> None:
    session = _FlakySession()
    client = RequestsHttpClient(
        session=session,
        retry_attempts=3,
        backoff_seconds=0.0,
        sleep_fn=lambda _seconds: None,
    )

    result = client.fetch("https://example.com/test")

    assert result == "<html>ok</html>"
    assert session.call_count == 3


def test_requests_http_client_prefers_apparent_encoding_over_latin1_fallback() -> None:
    session = _EncodingPreferenceSession()
    client = RequestsHttpClient(
        session=session,
        retry_attempts=1,
        backoff_seconds=0.0,
        sleep_fn=lambda _seconds: None,
    )

    result = client.fetch("https://example.com/test")

    assert "â" not in result
    assert "Summary of Economic Projections" in result
