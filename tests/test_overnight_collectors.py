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


class InlineFixtureClient:
    def __init__(self, html: str):
        self.html = html

    def fetch(self, _url: str) -> str:
        return self.html


class RoutingInlineFixtureClient:
    def __init__(self, routes: dict[str, str]):
        self.routes = routes

    def fetch(self, url: str) -> str:
        if url not in self.routes:
            raise AssertionError(f"Unexpected fixture url: {url}")
        return self.routes[url]


class FaultTolerantFixtureClient:
    def __init__(self, responses: dict[str, str], failing_urls: set[str]):
        self.responses = responses
        self.failing_urls = failing_urls

    def fetch(self, url: str) -> str:
        if url in self.failing_urls:
            raise RuntimeError(f"boom: {url}")
        if url not in self.responses:
            raise AssertionError(f"Unexpected fixture url: {url}")
        return self.responses[url]


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


def test_feed_collector_resolves_relative_links_against_feed_url() -> None:
    feed_xml = """
    <rss version="2.0">
      <channel>
        <title>EIA: Press Releases</title>
        <item>
          <title>EIA launches pilot survey on energy use at data centers</title>
          <link>/pressroom/releases/press585.php</link>
          <description>Energy Information Administration release summary.</description>
          <pubDate>Wed, 25 Mar 2026 11:00:00 EST</pubDate>
        </item>
      </channel>
    </rss>
    """
    collector = FeedCollector(http_client=InlineFixtureClient(feed_xml))

    candidates = collector.collect(_source_by_id("eia_pressroom"))

    assert len(candidates) == 1
    assert candidates[0].candidate_url == "https://www.eia.gov/pressroom/releases/press585.php"


def test_feed_collector_merges_multiple_entry_urls() -> None:
    first_feed = """
    <rss version="2.0"><channel><item><title>First item</title><link>https://example.com/first</link></item></channel></rss>
    """
    second_feed = """
    <rss version="2.0"><channel><item><title>Second item</title><link>https://example.com/second</link></item></channel></rss>
    """
    source = SourceDefinition(
        source_id="test_feed",
        display_name="Test Feed",
        organization_type="official_policy",
        source_class="policy",
        entry_type="rss",
        entry_urls=("https://example.com/feed-a.xml", "https://example.com/feed-b.xml"),
        priority=1,
        poll_interval_seconds=300,
    )
    collector = FeedCollector(
        http_client=RoutingInlineFixtureClient(
            {
                "https://example.com/feed-a.xml": first_feed,
                "https://example.com/feed-b.xml": second_feed,
            }
        )
    )

    candidates = collector.collect(source)

    assert [candidate.candidate_title for candidate in candidates] == ["First item", "Second item"]


def test_feed_collector_skips_failed_entry_url_and_uses_later_feed() -> None:
    second_feed = """
    <rss version="2.0"><channel><item><title>Second item</title><link>https://example.com/second</link></item></channel></rss>
    """
    source = SourceDefinition(
        source_id="test_feed",
        display_name="Test Feed",
        organization_type="official_policy",
        source_class="policy",
        entry_type="rss",
        entry_urls=("https://example.com/feed-a.xml", "https://example.com/feed-b.xml"),
        priority=1,
        poll_interval_seconds=300,
    )
    collector = FeedCollector(
        http_client=FaultTolerantFixtureClient(
            responses={"https://example.com/feed-b.xml": second_feed},
            failing_urls={"https://example.com/feed-a.xml"},
        )
    )

    candidates = collector.collect(source)

    assert [candidate.candidate_title for candidate in candidates] == ["Second item"]


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


def test_section_collector_merges_multiple_entry_urls() -> None:
    first_page = """
    <html><body><h3><a href="https://example.com/article/one">First article from first page</a></h3></body></html>
    """
    second_page = """
    <html><body><h3><a href="https://example.com/article/two">Second article from second page</a></h3></body></html>
    """
    source = SourceDefinition(
        source_id="test_section",
        display_name="Test Section",
        organization_type="wire_media",
        source_class="market",
        entry_type="section_page",
        entry_urls=("https://example.com/page-a", "https://example.com/page-b"),
        priority=1,
        poll_interval_seconds=300,
    )
    collector = SectionCollector(
        http_client=RoutingInlineFixtureClient(
            {
                "https://example.com/page-a": first_page,
                "https://example.com/page-b": second_page,
            }
        )
    )

    candidates = collector.collect(source)

    assert [candidate.candidate_title for candidate in candidates] == [
        "First article from first page",
        "Second article from second page",
    ]


def test_section_collector_skips_failed_entry_url_and_uses_later_page() -> None:
    second_page = """
    <html><body><h3><a href="https://example.com/article/two">Second article from second page</a></h3></body></html>
    """
    source = SourceDefinition(
        source_id="test_section",
        display_name="Test Section",
        organization_type="wire_media",
        source_class="market",
        entry_type="section_page",
        entry_urls=("https://example.com/page-a", "https://example.com/page-b"),
        priority=1,
        poll_interval_seconds=300,
    )
    collector = SectionCollector(
        http_client=FaultTolerantFixtureClient(
            responses={"https://example.com/page-b": second_page},
            failing_urls={"https://example.com/page-a"},
        )
    )

    candidates = collector.collect(source)

    assert [candidate.candidate_title for candidate in candidates] == ["Second article from second page"]


def test_section_collector_extracts_ustr_field_content_links() -> None:
    html = """
    <html>
      <body>
        <span class="field-content">
          <a href="/about/policy-offices/press-office/press-releases/2026/april/trade-deal-update">
            USTR Announces Trade Deal Update
          </a>
        </span>
        <span class="field-content">
          <a href="/about-us/policy-offices/press-office/speeches-and-remarks">
            Speeches and Remarks
          </a>
        </span>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("ustr_press_releases"))

    assert len(candidates) == 1
    assert candidates[0].candidate_title == "USTR Announces Trade Deal Update"
    assert candidates[0].candidate_url == (
        "https://ustr.gov/about/policy-offices/press-office/press-releases/2026/april/trade-deal-update"
    )


def test_section_collector_extracts_treasury_press_release_cards() -> None:
    html = """
    <html>
      <body>
        <div class="news-title">
          <a href="/news/press-releases/sb0433">Treasury Announces New Sanctions Action</a>
        </div>
        <p>Sanctions action targets an overseas shipping network.</p>
        <div class="more-link">
          <a href="/news/press-releases">View All Press Releases</a>
        </div>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("treasury_press_releases"))

    assert len(candidates) == 1
    assert candidates[0].candidate_title == "Treasury Announces New Sanctions Action"
    assert candidates[0].candidate_summary == "Sanctions action targets an overseas shipping network."
    assert candidates[0].candidate_url == "https://home.treasury.gov/news/press-releases/sb0433"


def test_section_collector_extracts_bea_current_release_links() -> None:
    html = """
    <html>
      <body>
        <div class="view-content">
          <a href="/news/2026/personal-income-and-outlays-january-2026">
            Personal Income and Outlays, January 2026
          </a>
          <a href="/news/current-releases">News Releases</a>
        </div>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("bea_news"))

    assert len(candidates) == 1
    assert candidates[0].candidate_title == "Personal Income and Outlays, January 2026"
    assert candidates[0].candidate_url == "https://www.bea.gov/news/2026/personal-income-and-outlays-january-2026"


def test_section_collector_skips_ap_video_links_and_keeps_article_links() -> None:
    html = """
    <html>
      <body>
        <h3>
          <a href="https://apnews.com/video/trump-addresses-economy">Trump addresses the economy in campaign stop</a>
        </h3>
        <h3>
          <a href="https://apnews.com/article/stock-markets-trump-oil-war-iran-148682a5d853dbdb16aaf08e554b001b">
            US stocks and oil prices flip-flop ahead of Trump deadline
          </a>
        </h3>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("ap_business"))

    assert len(candidates) == 1
    assert candidates[0].candidate_title == "US stocks and oil prices flip-flop ahead of Trump deadline"
    assert candidates[0].candidate_url == (
        "https://apnews.com/article/stock-markets-trump-oil-war-iran-148682a5d853dbdb16aaf08e554b001b"
    )


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


def test_article_collector_keeps_specific_candidate_title_when_page_title_is_generic() -> None:
    html = """
    <html>
      <head>
        <title>News Release</title>
        <link rel="canonical" href="https://www.bea.gov/news/2026/personal-income-and-outlays-january-2026" />
        <meta name="description" content="Personal income increased in January 2026 while spending cooled." />
      </head>
      <body>
        <main>
          <h1>News Release</h1>
          <p>Personal income increased in January 2026 while spending cooled.</p>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://www.bea.gov/news/2026/personal-income-and-outlays-january-2026",
        candidate_title="Personal Income and Outlays, January 2026",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_title == "Personal Income and Outlays, January 2026"
    assert expanded.candidate_summary == "Personal income increased in January 2026 while spending cooled."


def test_article_collector_keeps_specific_candidate_title_when_page_title_is_site_branding() -> None:
    html = """
    <html>
      <head>
        <title>U.S. Energy Information Administration - EIA - Independent Statistics and Analysis</title>
        <link rel="canonical" href="https://www.eia.gov/pressroom/releases/press585.php" />
        <meta name="description" content="Pilot survey tracks energy use at data centers." />
      </head>
      <body>
        <main>
          <h1>U.S. Energy Information Administration - EIA - Independent Statistics and Analysis</h1>
          <p>Pilot survey tracks energy use at data centers.</p>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="feed_item",
        candidate_url="https://www.eia.gov/pressroom/releases/press585.php",
        candidate_title="EIA launches pilot survey on energy use at data centers",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_title == "EIA launches pilot survey on energy use at data centers"


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


def test_default_source_registry_prefers_capture_friendly_urls() -> None:
    bea_source = _source_by_id("bea_news")
    census_source = _source_by_id("census_economic_indicators")
    eia_source = _source_by_id("eia_pressroom")
    cnbc_source = _source_by_id("cnbc_world")

    assert bea_source.entry_urls == ("https://www.bea.gov/news/current-releases",)
    assert census_source.entry_type == "rss"
    assert census_source.entry_urls == ("https://www.census.gov/economic-indicators/indicator.xml",)
    assert eia_source.entry_type == "rss"
    assert eia_source.entry_urls == ("https://www.eia.gov/rss/press_rss.xml",)
    assert cnbc_source.entry_type == "rss"
    assert cnbc_source.entry_urls == (
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    )
