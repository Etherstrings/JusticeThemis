# -*- coding: utf-8 -*-
"""Fixture-driven tests for overnight collectors."""

from __future__ import annotations

from pathlib import Path

from src.overnight.collectors.article import ArticleCollector
from src.overnight.collectors.attachment import AttachmentCollector
from src.overnight.collectors.calendar import CalendarCollector
from src.overnight.collectors.feed import FeedCollector
from src.overnight.collectors.section import SectionCollector
from src.overnight.source_registry import build_default_source_registry
from src.overnight.types import SourceCandidate, SourceDefinition


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class FixtureClient:
    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path

    def fetch(self, _url: str) -> str:
        return self.fixture_path.read_text(encoding="utf-8")


def _source_by_id(source_id: str) -> SourceDefinition:
    return next(source for source in build_default_source_registry() if source.source_id == source_id)


def test_feed_collector_parses_fed_items() -> None:
    collector = FeedCollector(http_client=FixtureClient(FIXTURE_DIR / "fed_feed.xml"))
    candidates = collector.collect(_source_by_id("fed_news"))

    assert candidates
    assert all(candidate.candidate_type == "feed_item" for candidate in candidates)
    assert any("Federal Reserve" in candidate.candidate_title for candidate in candidates)
    assert all(candidate.needs_article_fetch is True for candidate in candidates)


def test_section_collector_extracts_whitehouse_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "whitehouse_news.html"))
    candidates = collector.collect(_source_by_id("whitehouse_news"))

    assert candidates
    assert candidates[0].needs_article_fetch is True
    assert candidates[0].candidate_url.startswith("https://www.whitehouse.gov/")


def test_section_collector_extracts_reuters_topic_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "reuters_topics.html"))
    candidates = collector.collect(_source_by_id("reuters_topics"))

    assert candidates
    assert all(candidate.candidate_type == "section_card" for candidate in candidates)
    assert all(candidate.needs_article_fetch is True for candidate in candidates)
    assert candidates[0].candidate_tags == ("markets", "reuters")


def test_article_collector_canonicalizes_candidate_from_html() -> None:
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/?utm_source=test",
        candidate_title="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=FixtureClient(FIXTURE_DIR / "whitehouse_news.html"))

    expanded = collector.expand(candidate)

    assert expanded.candidate_url == (
        "https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/"
    )
    assert expanded.candidate_title == "Statement from the White House"
    assert expanded.candidate_summary.startswith("The White House announced")
    assert expanded.needs_article_fetch is False


def test_attachment_collector_discovers_document_links() -> None:
    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/",
        candidate_title="Statement from the White House",
        needs_attachment_fetch=True,
    )
    collector = AttachmentCollector(http_client=FixtureClient(FIXTURE_DIR / "whitehouse_news.html"))

    attachments = collector.expand(candidate)

    assert attachments
    assert all(item.candidate_type == "attachment" for item in attachments)
    assert any(item.candidate_url.endswith(".pdf") for item in attachments)


def test_calendar_collector_parses_release_schedule_rows() -> None:
    schedule_source = SourceDefinition(
        source_id="bls_schedule",
        display_name="BLS Schedule",
        organization_type="official_data",
        source_class="calendar",
        entry_type="calendar_page",
        entry_urls=("https://www.bls.gov/schedule/news_release/",),
        priority=80,
        poll_interval_seconds=86400,
        is_mission_critical=False,
    )
    collector = CalendarCollector(http_client=FixtureClient(FIXTURE_DIR / "bls_schedule.html"))

    candidates = collector.collect(schedule_source)

    assert candidates
    assert all(candidate.candidate_type == "calendar_event" for candidate in candidates)
    assert candidates[0].candidate_published_at == "2026-04-10"
    assert candidates[0].candidate_title == "Consumer Price Index"
