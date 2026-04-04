# -*- coding: utf-8 -*-
"""Fixture-driven tests for overnight collectors."""

from __future__ import annotations

from pathlib import Path

from src.overnight.collectors.article import ArticleCollector, extract_article_shell
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

    assert len(candidates) == 2
    assert [candidate.candidate_type for candidate in candidates] == ["feed_item", "feed_item"]
    assert [candidate.candidate_title for candidate in candidates] == [
        "Federal Reserve issues FOMC statement",
        "Federal Reserve announces discount rate action",
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == [
        "2026-04-03T14:00:00+00:00",
        "2026-04-02T19:00:00+00:00",
    ]
    assert [candidate.needs_article_fetch for candidate in candidates] == [True, True]


def test_section_collector_extracts_whitehouse_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "whitehouse_news.html"))
    candidates = collector.collect(_source_by_id("whitehouse_news"))

    assert len(candidates) == 2
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/",
        "https://www.whitehouse.gov/briefing-room/presidential-actions/2026/04/03/sample-action/",
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == ["2026-04-04", "2026-04-03"]
    assert [candidate.candidate_tags for candidate in candidates] == [(), ()]
    assert [candidate.needs_article_fetch for candidate in candidates] == [True, True]


def test_section_collector_extracts_reuters_topic_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "reuters_topics.html"))
    candidates = collector.collect(_source_by_id("reuters_topics"))

    assert len(candidates) == 2
    assert [candidate.candidate_type for candidate in candidates] == ["section_card", "section_card"]
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://reutersbest.com/world/us/federal-reserve-official-says-inflation-easing-2026-04-04/",
        "https://reutersbest.com/markets/us/jobs-data-keeps-rate-path-in-focus-2026-04-03/",
    ]
    assert [candidate.candidate_tags for candidate in candidates] == [
        ("markets", "reuters"),
        ("markets", "reuters"),
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == ["2026-04-04", "2026-04-03"]
    assert [candidate.needs_article_fetch for candidate in candidates] == [True, True]


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


def test_extract_article_shell_uses_main_or_article_before_global_paragraph() -> None:
    html = """
    <html>
      <head>
        <title>Fallback Title</title>
      </head>
      <body>
        <p>Top teaser outside article body.</p>
        <main>
          <article>
            <h1>Container Headline</h1>
            <p>Body summary inside article container.</p>
          </article>
        </main>
      </body>
    </html>
    """
    canonical_url, title, summary = extract_article_shell(
        html=html,
        fallback_url="https://example.com/posts/sample/?ref=teaser",
    )

    assert canonical_url == "https://example.com/posts/sample/"
    assert title == "Container Headline"
    assert summary == "Body summary inside article container."


def test_attachment_collector_discovers_document_links() -> None:
    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/04/sample-release/",
        candidate_title="Statement from the White House",
        needs_attachment_fetch=True,
    )
    collector = AttachmentCollector(http_client=FixtureClient(FIXTURE_DIR / "whitehouse_news.html"))

    attachments = collector.expand(candidate)

    assert len(attachments) == 2
    assert [item.candidate_type for item in attachments] == ["attachment", "attachment"]
    assert [item.candidate_url for item in attachments] == [
        "https://www.whitehouse.gov/wp-content/uploads/2026/04/sample-fact-sheet.pdf",
        "https://www.whitehouse.gov/wp-content/uploads/2026/04/sample-data.csv",
    ]
    assert [item.candidate_title for item in attachments] == ["Fact Sheet (PDF)", "Data Appendix (CSV)"]


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

    assert len(candidates) == 3
    assert [candidate.candidate_type for candidate in candidates] == [
        "calendar_event",
        "calendar_event",
        "calendar_event",
    ]
    assert [candidate.candidate_title for candidate in candidates] == [
        "Consumer Price Index",
        "Employment Situation",
        "Producer Price Index",
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == [
        "2026-04-10",
        "2026-04-17",
        "2026-04-24",
    ]
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://www.bls.gov/news.release/cpi.nr0.htm",
        "https://www.bls.gov/news.release/empsit.nr0.htm",
        "https://www.bls.gov/schedule/news_release/",
    ]
    assert [candidate.needs_article_fetch for candidate in candidates] == [True, True, False]
