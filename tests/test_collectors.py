# -*- coding: utf-8 -*-
"""Fixture-driven tests for overnight collectors."""

from __future__ import annotations

from pathlib import Path

from app.collectors.article import ArticleCollector, extract_article_shell
from app.collectors.attachment import AttachmentCollector
from app.collectors.calendar import CalendarCollector
from app.collectors.feed import FeedCollector
from app.collectors.section import SectionCollector
from app.sources.registry import _apply_registry_safety_guards, build_default_source_registry
from app.sources.types import SourceCandidate, SourceDefinition
from app.sources.validation import MAINLAND_CHINA_OFFICIAL_DISABLE_REASON, is_source_url_allowed, validate_source_url


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


def test_feed_collector_skips_off_domain_entry_links() -> None:
    feed_xml = """
    <rss version="2.0">
      <channel>
        <title>Federal Reserve feed</title>
        <item>
          <title>Fake mirrored statement</title>
          <link>https://mirror.example.com/fed/fake-statement</link>
          <description>Mirrored content on an unrelated host.</description>
          <pubDate>Wed, 25 Mar 2026 11:00:00 EST</pubDate>
        </item>
      </channel>
    </rss>
    """
    collector = FeedCollector(http_client=InlineFixtureClient(feed_xml))

    candidates = collector.collect(_source_by_id("fed_news"))

    assert candidates == []


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


def test_section_collector_extracts_mining_com_industrial_metals_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "mining_com_markets.html"))
    candidates = collector.collect(_source_by_id("mining_com_markets"))

    assert len(candidates) == 2
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://www.mining.com/web/copper-price-slides-as-china-demand-stays-soft/",
        "https://www.mining.com/web/aluminum-market-tightens-as-smelter-cuts-deepen/",
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == ["2026-04-24", "2026-04-24"]


def test_section_collector_extracts_fastmarkets_industrial_metals_cards() -> None:
    collector = SectionCollector(http_client=FixtureClient(FIXTURE_DIR / "fastmarkets_markets.html"))
    candidates = collector.collect(_source_by_id("fastmarkets_markets"))

    assert len(candidates) == 2
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://www.fastmarkets.com/insights/whats-next-for-us-and-mexico-aluminium-key-insights-from-fastmarkets-market-outlook-webinar/",
        "https://www.fastmarkets.com/insights/gcc-steel-supply-crunch-deepens-despite-ceasefire-talks/",
    ]
    assert [candidate.candidate_published_at for candidate in candidates] == ["2026-04-24", "2026-04-24"]


def test_section_collector_caps_generic_candidate_volume_per_entry_url() -> None:
    html = "<html><body>" + "".join(
        f'<h3><a href="/about/policy-offices/press-office/press-releases/2026/april/item-{index}">Item {index}</a></h3>'
        for index in range(120)
    ) + "</body></html>"
    collector = SectionCollector(http_client=InlineFixtureClient(html))
    source = SourceDefinition(
        source_id="test_section_cap",
        display_name="Test Section Cap",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://ustr.gov/about-us/policy-offices/press-office/press-releases",),
        priority=100,
        poll_interval_seconds=300,
        allowed_domains=("ustr.gov",),
    )

    candidates = collector.collect(source)

    assert len(candidates) == 40
    assert candidates[0].candidate_title == "Item 0"


def test_section_collector_accepts_reuters_root_slug_article_links() -> None:
    html = """
    <html>
      <body>
        <h3>
          <a href="https://reutersbest.com/renewables-grew-to-almost-50-of-global-electricity-capacity-in-2025-after-solar-boost/">
            Renewables grew to almost 50% of global electricity capacity in 2025 after solar boost
          </a>
        </h3>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("reuters_topics"))

    assert len(candidates) == 1
    assert candidates[0].candidate_url == (
        "https://reutersbest.com/renewables-grew-to-almost-50-of-global-electricity-capacity-in-2025-after-solar-boost/"
    )


def test_section_collector_accepts_newyorkfed_numeric_detail_links() -> None:
    html = """
    <html>
      <body>
        <div class="paraHeader">
          <a href="/newsevents/news/research/2026/20260407">
            Short-Term Inflation Expectations Increase as Gas Price Growth Expectations Spike
          </a>
        </div>
      </body>
    </html>
    """
    source = SourceDefinition(
        source_id="test_nyfed",
        display_name="New York Fed News",
        organization_type="official_data",
        source_class="macro",
        entry_type="section_page",
        entry_urls=("https://www.newyorkfed.org/newsevents/news",),
        priority=100,
        poll_interval_seconds=300,
        allowed_domains=("newyorkfed.org",),
    )
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(source)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == "https://www.newyorkfed.org/newsevents/news/research/2026/20260407"


def test_section_collector_accepts_worldbank_press_release_links_without_html_suffix() -> None:
    html = """
    <html>
      <body>
        <div>
          <a href="https://www.worldbank.org/en/news/press-release/2026/04/10/world-bank-group-and-imf-to-hold-2029-annual-meetings-in-abu-dhabi-united-arab-emirates">
            World Bank Group and IMF to Hold 2029 Annual Meetings in Abu Dhabi, United Arab Emirates
          </a>
        </div>
      </body>
    </html>
    """
    source = SourceDefinition(
        source_id="test_worldbank",
        display_name="World Bank News",
        organization_type="official_data",
        source_class="macro",
        entry_type="section_page",
        entry_urls=("https://www.worldbank.org/en/news",),
        priority=100,
        poll_interval_seconds=300,
        allowed_domains=("worldbank.org",),
    )
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(source)

    assert len(candidates) == 1
    assert candidates[0].candidate_url.startswith("https://www.worldbank.org/en/news/press-release/2026/04/10/")


def test_section_collector_extracts_iea_news_links_from_path_based_anchor_selectors() -> None:
    html = """
    <html>
      <body>
        <div>
          <a class="m-news-detailed-listing__link" href="/news/global-shocks-have-driven-a-surge-in-energy-policy-activity-and-government-spending">
            Global shocks have driven a surge in energy policy activity and government spending
          </a>
        </div>
      </body>
    </html>
    """
    source = SourceDefinition(
        source_id="test_iea",
        display_name="IEA News",
        organization_type="official_data",
        source_class="macro",
        entry_type="section_page",
        entry_urls=("https://www.iea.org/news",),
        priority=100,
        poll_interval_seconds=300,
        allowed_domains=("iea.org",),
    )
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(source)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == (
        "https://www.iea.org/news/global-shocks-have-driven-a-surge-in-energy-policy-activity-and-government-spending"
    )


def test_section_collector_accepts_cftc_press_release_detail_links() -> None:
    html = """
    <html>
      <body>
        <table>
          <tbody>
            <tr>
              <td><a href="/PressRoom/PressReleases/9209-26">CFTC Announces Agricultural Advisory Committee Members</a></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    source = SourceDefinition(
        source_id="test_cftc",
        display_name="CFTC Press Releases",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.cftc.gov/PressRoom/PressReleases",),
        priority=100,
        poll_interval_seconds=300,
        allowed_domains=("cftc.gov",),
    )
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(source)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == "https://www.cftc.gov/PressRoom/PressReleases/9209-26"


def test_section_collector_extracts_bis_press_release_links() -> None:
    html = """
    <html>
      <body>
        <div class="mx-auto max-w-7xl px-6 my-12">
          <div>
            <ul class="mt-4">
              <li class="mb-2">
                <div class="border-b border-finnishwinter py-6">
                  <a
                    class="relative grid h-full rounded transition-all mb-4"
                    href="/press-release/department-commerce-revises-license-review-policy-semiconductors-exported-china"
                  >
                    Department of Commerce Revises License Review Policy for Semiconductors Exported to China
                  </a>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("bis_news_updates"))

    assert len(candidates) == 1
    assert candidates[0].candidate_title == (
        "Department of Commerce Revises License Review Policy for Semiconductors Exported to China"
    )
    assert candidates[0].candidate_url == (
        "https://media.bis.gov/press-release/department-commerce-revises-license-review-policy-semiconductors-exported-china"
    )


def test_section_collector_extracts_ofac_recent_action_links() -> None:
    html = """
    <html>
      <body>
        <div class="view-content">
          <div class="margin-bottom-4 search-result views-row">
            <div class="font-sans-lg margin-bottom-05 margin-top-1 text-no-underline">
              <a href="/recent-actions/20260408">
                Issuance of Amended Russia-related General License and Frequently Asked Questions
              </a>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("ofac_recent_actions"))

    assert len(candidates) == 1
    assert candidates[0].candidate_url == "https://ofac.treasury.gov/recent-actions/20260408"


def test_section_collector_extracts_doe_collection_item_links() -> None:
    html = """
    <html>
      <body>
        <ul class="collection collection--compact-icons">
          <li class="collection-item">
            <div class="collection-item--type-press-releases collection-item-wrapper">
              <div class="collection-item__title title-sm">
                <a class="collection-item__link" href="/articles/fact-sheet-delivering-us-oil-and-natural-gas-production">
                  FACT SHEET: Delivering On U.S. Oil And Natural Gas Production
                </a>
              </div>
            </div>
          </li>
        </ul>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("doe_articles"))

    assert len(candidates) == 1
    assert candidates[0].candidate_url == (
        "https://www.energy.gov/articles/fact-sheet-delivering-us-oil-and-natural-gas-production"
    )


def test_section_collector_skips_off_domain_card_links() -> None:
    html = """
    <html>
      <body>
        <section id="news-feed">
          <article class="news-card">
            <a href="https://mirror.example.com/whitehouse/fake-policy">Mirrored policy card</a>
            <p class="summary">Unofficial mirrored content on another host.</p>
            <time datetime="2026-04-04">April 4, 2026</time>
          </article>
        </section>
      </body>
    </html>
    """
    collector = SectionCollector(http_client=InlineFixtureClient(html))

    candidates = collector.collect(_source_by_id("whitehouse_news"))

    assert candidates == []


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
          <table>
            <tbody>
              <tr class="release-row">
                <td>
                  <a href="/news/2026/personal-income-and-outlays-january-2026">
                    Personal Income and Outlays, January 2026
                  </a>
                </td>
                <td>
                  <time datetime="2026-03-13T08:30:00-04:00">March 13, 2026</time>
                </td>
              </tr>
            </tbody>
          </table>
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
    assert candidates[0].candidate_published_at == "2026-03-13T08:30:00-04:00"
    assert candidates[0].candidate_published_at_source == "section:nearby_time"


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
    assert expanded.candidate_excerpt_source == "body_selector:main"
    assert expanded.needs_article_fetch is False


def test_article_collector_uses_html_published_time_when_available() -> None:
    html = """
    <html>
      <head>
        <title>Policy Statement</title>
        <meta property="article:published_time" content="2026-04-07T10:30:00+00:00" />
      </head>
      <body>
        <main>
          <article>
            <h1>Policy Statement</h1>
            <p>Detailed policy text.</p>
          </article>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://example.com/policy-statement",
        candidate_title="Policy Statement",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-04-07T10:30:00+00:00"
    assert expanded.candidate_published_at_source == "html:meta_article_published_time"


def test_article_collector_extracts_ofac_release_date_field() -> None:
    html = """
    <html>
      <body>
        <article>
          <h1>OFAC action</h1>
          <div class="field field--name-field-release-date field--type-datetime field--label-visually_hidden">
            <div class="field__item">04/08/2026</div>
          </div>
          <div class="field field--name-body">
            <div class="field__item">
              <p>OFAC issued an amended general license and related FAQs.</p>
            </div>
          </div>
        </article>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://ofac.treasury.gov/recent-actions/20260408",
        candidate_title="OFAC action",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-04-08"
    assert expanded.candidate_published_at_source == "html:field_release_date"


def test_article_collector_extracts_bis_published_on_from_embedded_json() -> None:
    html = """
    <html>
      <head>
        <title>BIS Release</title>
        <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "node": {
                  "publishedOn": {
                    "time": "2026-03-27T04:00:00+00:00"
                  }
                }
              }
            }
          }
        </script>
      </head>
      <body>
        <main>
          <h1>BIS Release</h1>
          <p>FOR IMMEDIATE RELEASE | March 27, 2026 | BIS reaches settlement.</p>
          <p>ORDER</p>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://media.bis.gov/press-release/sample-release",
        candidate_title="BIS Release",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-03-27T04:00:00+00:00"
    assert expanded.candidate_published_at_source == "html:embedded_json_published_on"


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
    canonical_url, title, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://example.com/posts/sample/?ref=teaser",
    )

    assert canonical_url == "https://example.com/posts/sample/"
    assert title == "Container Headline"
    assert summary == "Body summary inside article container."
    assert excerpt_source == "body_selector:article"


def test_extract_article_shell_prefers_richer_body_excerpt_over_short_meta_description() -> None:
    html = """
    <html>
      <head>
        <title>Policy Update</title>
        <meta name="description" content="Short deck." />
      </head>
      <body>
        <main>
          <article>
            <h1>Policy Update</h1>
            <p>The administration published a broader trade and industrial policy update overnight.</p>
            <p>The release adds implementation detail on supply chains, tariff timing, and agency coordination.</p>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://example.com/policy-update",
    )

    assert summary.startswith("The administration published a broader trade and industrial policy update overnight.")
    assert "tariff timing" in summary
    assert excerpt_source == "body_selector:article"


def test_extract_article_shell_prefers_jsonld_article_body_over_generic_dom_teaser() -> None:
    html = """
    <html>
      <head>
        <title>Market Wrap</title>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "Market Wrap",
            "articleBody": "U.S. stocks advanced after Treasury yields eased and investors reassessed the latest tariff signals from Washington. Semiconductor shares led gains, while crude held firm above $82 a barrel as traders weighed shipping disruptions and refinery demand."
          }
        </script>
      </head>
      <body>
        <main>
          <article>
            <h1>Market Wrap</h1>
            <p>Watch live market coverage.</p>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://example.com/market-wrap",
    )

    assert summary.startswith("U.S. stocks advanced after Treasury yields eased")
    assert "Semiconductor shares led gains" in summary
    assert excerpt_source == "jsonld:articleBody"


def test_extract_article_shell_uses_site_specific_body_selector_for_eia_press_releases() -> None:
    html = """
    <html>
      <head>
        <title>EIA Press Release (03/25/2026): EIA launches pilot survey on energy use at data centers</title>
      </head>
      <body>
        <h1>U.S. Energy Information Administration - EIA - Independent Statistics and Analysis</h1>
        <div class="search-menu-toggle">
          <p>Menu</p>
        </div>
        <div class="pagecontent mr_temp4">
          <div class="main_col">
            <p>U.S. ENERGY INFORMATION ADMINISTRATION<br />WASHINGTON DC 20585</p>
            <p>FOR IMMEDIATE RELEASE<br />March 25, 2026</p>
            <h1>EIA launches pilot survey on energy use at data centers</h1>
            <p>EIA is launching three voluntary pilot field studies to evaluate energy consumption in data centers, with web-based pilot surveys in Texas and Washington state as well as in-person interviews in Northern Virginia and Washington, DC.</p>
            <p>EIA identified 196 companies operating data centers across Texas, Washington state, and the Northern Virginia-DC region. Each company will be asked to report on the energy use of at least one data center in the targeted region.</p>
            <p>"A tremendous amount of excellent work goes into our retrospective consumption surveys, but they were conceived decades ago," EIA Administrator Tristan Abbey said.</p>
            <div class="feature">The product described in this press release was prepared by the U.S. Energy Information Administration.</div>
            <p>EIA Program Contact: Kenneth Pick, EIAMedia@eia.gov</p>
          </div>
        </div>
      </body>
    </html>
    """
    canonical_url, title, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.eia.gov/pressroom/releases/press585.php",
    )

    assert canonical_url == "https://www.eia.gov/pressroom/releases/press585.php"
    assert title == "EIA launches pilot survey on energy use at data centers"
    assert summary.startswith("EIA is launching three voluntary pilot field studies to evaluate energy consumption")
    assert "EIA identified 196 companies operating data centers" in summary
    assert "FOR IMMEDIATE RELEASE" not in summary
    assert "EIA Program Contact" not in summary
    assert excerpt_source == "body_selector:.pagecontent.mr_temp4"


def test_extract_article_shell_formats_eia_list_item_lead_as_section_label() -> None:
    html = """
    <html>
      <body>
        <div class="pagecontent mr_temp4">
          <div class="main_col">
            <h1>Energy Outlook</h1>
            <p>Key takeaways from the April STEO are below.</p>
            <li>Global oil production. Oil flows through the Strait of Hormuz continue to be limited causing oil storage to fill quickly.</li>
            <li>Crude oil price forecast. The Brent crude oil spot price averaged $103 per barrel in March.</li>
          </div>
        </div>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.eia.gov/pressroom/releases/sample-outlook.php",
    )

    assert "Key takeaways from the April STEO are below." not in summary
    assert "Global oil production: Oil flows through the Strait of Hormuz continue to be limited" in summary
    assert "Crude oil price forecast: The Brent crude oil spot price averaged $103 per barrel in March." in summary
    assert excerpt_source == "body_selector:.pagecontent.mr_temp4"


def test_extract_article_shell_uses_site_specific_body_selector_for_treasury_pages() -> None:
    html = """
    <html>
      <head>
        <title>Treasury Press Release</title>
        <meta name="description" content="Short deck that should not win." />
      </head>
      <body>
        <main>
          <div class="left-nav">
            <p>Press Releases</p>
            <p>Statements & Remarks</p>
          </div>
          <article class="entity--type-node">
            <div class="field field--name-field-news-body">
              <p><strong>WASHINGTON, D.C.</strong> Treasury announced a sanctions update tied to overseas shipping networks.</p>
              <p>The action targets facilitators, vessel operators, and financing conduits linked to the network.</p>
              <p class="text-align-center">###</p>
            </div>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://home.treasury.gov/news/press-releases/sb0433",
    )

    assert summary.startswith("WASHINGTON, D.C. Treasury announced a sanctions update tied to overseas shipping networks.")
    assert "facilitators, vessel operators, and financing conduits" in summary
    assert "Press Releases" not in summary
    assert "###" not in summary
    assert excerpt_source == "body_selector:.field--name-field-news-body"


def test_extract_article_shell_filters_ustr_media_registration_lines() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="field--name-body">
            <p>WASHINGTON — Ambassador Jamieson Greer will travel to Michigan and Ohio to tour manufacturing plants and meet with industry executives.</p>
            <p>During the swing, he will discuss how the administration's trade policies are accelerating reindustrialization and raising worker wages.</p>
            <p>This event is open to registered media.</p>
            <p>Please RSVP to MBX.USTR.Media@ustr.eop.gov to register and list each event you plan on attending.</p>
          </div>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://ustr.gov/about/policy-offices/press-office/press-releases/2026/april/sample",
    )

    assert "registered media" not in summary
    assert "Please RSVP" not in summary
    assert summary.startswith("WASHINGTON — Ambassador Jamieson Greer will travel to Michigan and Ohio")
    assert excerpt_source == "body_selector:.field--name-body"


def test_extract_article_shell_stops_before_ustr_itinerary_schedule() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="field--name-body">
            <p>WASHINGTON — Ambassador Jamieson Greer will visit manufacturers in Michigan and Ohio.</p>
            <p>Thursday, April 9</p>
            <li>Atomic Industries Time: 10:45 AM Location: 13780 East 11 Mile Road, Warren, MI 48089</li>
            <li>Time: 10:45 AM</li>
            <li>Location: 13780 East 11 Mile Road, Warren, MI 48089</li>
            <li>Stellantis Warren Truck Assembly Plant ( no plant floor walk, pen and pad following ) Time: 2:00 PM Location: 21500 Mound Road, Warren, MI 48091</li>
          </div>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://ustr.gov/about/policy-offices/press-office/press-releases/2026/april/sample-itinerary",
    )

    assert "Time:" not in summary
    assert "Location:" not in summary
    assert "Thursday, April 9" not in summary
    assert "Atomic Industries" not in summary
    assert "Stellantis Warren Truck Assembly Plant" not in summary
    assert summary.startswith("WASHINGTON — Ambassador Jamieson Greer will visit manufacturers")
    assert excerpt_source == "body_selector:.field--name-body"


def test_extract_article_shell_filters_contact_and_attachment_boilerplate_from_fed_pages() -> None:
    html = """
    <html>
      <body>
        <div id="article">
          <div class="col-xs-12 col-sm-8 col-md-8">
            <p>The Federal Reserve Board announced a supervisory action tied to control failures.</p>
            <p>Additional enforcement actions can be searched for here.</p>
            <p>For media inquiries, please email media@example.com or call 202-000-0000.</p>
            <p>For media inquiries, email media@example.com or call 202-452-2955.</p>
            <p>Attachment (PDF)</p>
            <p>Projections (PDF) | Accessible Materials</p>
          </div>
        </div>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.federalreserve.gov/newsevents/pressreleases/enforcement20260403a.htm",
    )

    assert summary == "The Federal Reserve Board announced a supervisory action tied to control failures."
    assert excerpt_source == "body_selector:#article .col-xs-12.col-sm-8.col-md-8"


def test_extract_article_shell_filters_release_schedule_and_stat_footnotes() -> None:
    html = """
    <html>
      <body>
        <article>
          <h1>International Trade</h1>
          <p>The U.S. Census Bureau and the U.S. Bureau of Economic Analysis announced today that the goods and services deficit was $57.3 billion in February, up $2.7 billion from $54.7 billion in January, revised.</p>
          <p>Next release: Tuesday, May 5, 2026</p>
          <p>(*) Statistical significance is not applicable or not measurable.</p>
          <p>Source: U.S. Census Bureau, U.S. Bureau of Economic Analysis; U.S. International Trade in Goods and Services, April 2, 2026</p>
        </article>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.bea.gov/news/sample-trade-release",
    )

    assert summary.startswith(
        "The U.S. Census Bureau and the U.S. Bureau of Economic Analysis announced today"
    )
    assert "Next release:" not in summary
    assert "Statistical significance" not in summary
    assert "Source:" not in summary
    assert excerpt_source == "body_selector:article"


def test_extract_article_shell_formats_short_paragraph_heading_as_section_label() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="entry-content wp-block-post-content">
            <p class="has-heading-3-font-size">Executive Summary</p>
            <p>The GENIUS Act requires stablecoin issuers to maintain one-to-one reserves and prohibits yield payments.</p>
          </div>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.whitehouse.gov/research/sample-whitehouse-paper",
    )

    assert summary.startswith("Executive Summary: The GENIUS Act requires stablecoin issuers")
    assert excerpt_source == "body_selector:.entry-content.wp-block-post-content"


def test_extract_article_shell_formats_exhibit_heading_paragraph_as_section_label() -> None:
    html = """
    <html>
      <body>
        <article>
          <p>Topline deficit narrowed in March.</p>
          <p class="text-align-center text-center">Exports, Imports, and Balance (exhibit 1)</p>
          <p>February exports were $314.8 billion, $12.6 billion more than January exports.</p>
        </article>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.bea.gov/news/sample-trade-release",
    )

    assert "Exports, Imports, and Balance (exhibit 1): February exports were $314.8 billion" in summary
    assert excerpt_source == "body_selector:article"


def test_extract_article_shell_truncates_at_sentence_boundary_for_long_pages() -> None:
    html = """
    <html>
      <body>
        <main>
          <p>{}</p>
          <p>The final sentence should remain complete.</p>
        </main>
      </body>
    </html>
    """.format(
        " ".join(["This is a long policy sentence."] * 90)
    )
    _, _, summary, _ = extract_article_shell(
        html=html,
        fallback_url="https://example.com/long-policy-page",
    )

    assert len(summary) <= 1600
    assert summary.endswith(".")
    assert "The final sentence should remain complete." not in summary or summary.endswith("complete.")


def test_article_collector_prefers_richer_feed_summary_when_page_body_is_generic() -> None:
    html = """
    <html>
      <head>
        <title>Foreign Trade</title>
      </head>
      <body>
        <main>
          <h1>Foreign Trade</h1>
          <p>International Trade is the official source for U.S. export and import statistics.</p>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="feed_item",
        candidate_url="https://www.census.gov/foreign-trade/index.html",
        candidate_title="U.S. International Trade in Goods and Services",
        candidate_summary=(
            "The nation's international trade deficit in goods and services increased to $57.3 billion in February "
            "from $54.7 billion in January (revised), as imports increased more than exports."
        ),
        candidate_excerpt_source="feed:summary",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_summary.startswith("The nation's international trade deficit in goods and services increased")
    assert expanded.candidate_excerpt_source == "candidate_summary:preferred"


def test_extract_article_shell_filters_photo_captions() -> None:
    html = """
    <html>
      <body>
        <main>
          <article>
            <p>A person walks in front of an electronic stock board showing Japan’s Nikkei index in Tokyo. (AP Photo/Eugene Hoshiko)</p>
            <p>TOKYO (AP) — Asian shares were mixed in cautious trading Tuesday as oil prices remained in focus.</p>
            <p>Investors were watching President Donald Trump's deadline for Iran to reopen the Strait of Hormuz.</p>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://apnews.com/article/sample",
    )

    assert summary.startswith("TOKYO (AP) — Asian shares were mixed in cautious trading Tuesday")
    assert "(AP Photo/" not in summary
    assert excerpt_source == "body_selector:main article"


def test_extract_article_shell_normalizes_spaces_before_punctuation() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="RichTextStoryBody">
            <p>WASHINGTON (AP) — NATO Secretary-General Mark Rutte is expected to meet with President Donald Trump over the Iran war .</p>
            <p>Trump had suggested allies help reopen the Strait of Hormuz , a vital shipping waterway .</p>
          </div>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://apnews.com/article/sample-punctuation-spacing",
    )

    assert "war ." not in summary
    assert "Hormuz ," not in summary
    assert "waterway ." not in summary
    assert "Iran war." in summary
    assert "Hormuz, a vital shipping waterway." in summary
    assert excerpt_source == "body_selector:.RichTextStoryBody"


def test_extract_article_shell_normalizes_spaces_inside_parentheses() -> None:
    html = """
    <html>
      <body>
        <main>
          <article>
            <p>Some analyses estimate the effect on lending in the trillions of dollars ( Nigrinis 2025 ).</p>
            <p>Officials said the baseline case ( with conservative assumptions ) remains limited.</p>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://example.com/parenthetical-spacing",
    )

    assert "( Nigrinis 2025 )" not in summary
    assert "( with conservative assumptions )" not in summary
    assert "(Nigrinis 2025)." in summary
    assert "(with conservative assumptions)" in summary
    assert excerpt_source == "body_selector:article"


def test_extract_article_shell_prefers_ap_rich_text_story_body_over_main_carousel_text() -> None:
    html = """
    <html>
      <body>
        <main class="Page-main">
          <div class="CarouselSlide">
            <div class="CarouselSlide-info">
              <div class="CarouselSlide-info-content">
                <span class="CarouselSlide-infoDescription">
                  <p>The narrow, bending waterway in the Persian Gulf is a key trade route between the Middle East and the rest of the world.</p>
                  <p>Oil prices plunged and U.S. stock futures jumped after U.S. President Donald Trump held off on his threat of devastating attacks on Iran.</p>
                </span>
              </div>
            </div>
          </div>
          <bsp-story-page>
            <div class="Page-storyBody gtmMainScrollContent">
              <div class="RichTextStoryBody RichTextBody">
                <p>Wall Street surged in Wednesday premarket trading as oil prices plunged 16% after the U.S. and Iran agreed to a two-week ceasefire that includes the reopening of the Strait of Hormuz.</p>
                <p>Futures for the S&P 500 jumped 2.7% before the opening bell and futures for the Dow Jones Industrial Average climbed 2.6%.</p>
              </div>
            </div>
          </bsp-story-page>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://apnews.com/article/sample",
    )

    assert summary.startswith("Wall Street surged in Wednesday premarket trading")
    assert "The narrow, bending waterway" not in summary
    assert excerpt_source == "body_selector:.RichTextStoryBody"


def test_extract_article_shell_filters_ap_contributor_and_social_boilerplate() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="RichTextStoryBody">
            <p>Wall Street surged after oil prices fell sharply on the ceasefire announcement.</p>
            <p>Analysts said the rally still depends on whether Hormuz shipping normalizes.</p>
            <p>___</p>
            <p>Associated Press videographer Mayuko Ono in Tokyo and writer Jon Gambrell in Dubai, United Arab Emirates, contributed to this report.</p>
            <p>Yuri Kageyama is on Threads: https://www.threads.com/@yurikageyama</p>
          </div>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://apnews.com/article/sample-ap-footer",
    )

    assert "___" not in summary
    assert "contributed to this report" not in summary
    assert "is on Threads:" not in summary
    assert summary.endswith("normalizes.")
    assert excerpt_source == "body_selector:.RichTextStoryBody"


def test_extract_article_shell_prefers_matching_embedded_json_teaser_for_kitco_article() -> None:
    html = """
    <html>
      <body>
        <article>
          <p>Ernest Hoffman is a Crypto and Market Reporter for Kitco News. He has over 15 years of experience as a writer, editor, broadcaster and producer.</p>
          <p>This generic author profile should not be preferred over the matching article teaser.</p>
        </article>
        <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "article": {
                  "urlAlias": "/news/article/2026-04-10/sample-kitco-article",
                  "teaserSnippet": "(Kitco News) - Gold prices moved higher after softer inflation data reinforced expectations for lower real yields.",
                  "body": "<p><strong>Ernest Hoffman</strong> is a Crypto and Market Reporter for Kitco News.</p>"
                }
              }
            }
          }
        </script>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.kitco.com/news/article/2026-04-10/sample-kitco-article",
    )

    assert summary.startswith("(Kitco News) - Gold prices moved higher after softer inflation data")
    assert "Crypto and Market Reporter for Kitco News" not in summary
    assert excerpt_source == "embedded_json:teaserSnippet"


def test_extract_article_shell_normalizes_html_entities_in_embedded_json_summary() -> None:
    html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "article": {
                  "urlAlias": "/news/article/2026-04-10/sample-kitco-article",
                  "teaserSnippet": "(Kitco News) - Gold demand&nbsp;rose after inflation data cooled."
                }
              }
            }
          }
        </script>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.kitco.com/news/article/2026-04-10/sample-kitco-article",
    )

    assert "&nbsp;" not in summary
    assert "Gold demand rose after inflation data cooled." in summary
    assert excerpt_source == "embedded_json:teaserSnippet"


def test_extract_article_shell_prefers_kitco_teaser_over_author_bio_with_name_prefix() -> None:
    html = """
    <html>
      <body>
        <article>
          <p>Neils Christensen: Neils Christensen has a diploma in journalism from Lethbridge College and has more than a decade of reporting experience working for news organizations throughout Canada. He can be contacted at: 1 866 925 4826 ext. 1526 nchristensen at kitco.com @KitcoNewsNOW</p>
        </article>
        <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "article": {
                  "urlAlias": "/news/article/2026-04-10/sample-kitco-live-article",
                  "teaserSnippet": "(Kitco News) - Gold extended its rally as inflation fears and geopolitical uncertainty supported safe-haven demand."
                }
              }
            }
          }
        </script>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://www.kitco.com/news/article/2026-04-10/sample-kitco-live-article",
    )

    assert summary.startswith("(Kitco News) - Gold extended its rally")
    assert "has a diploma in journalism" not in summary
    assert excerpt_source == "embedded_json:teaserSnippet"


def test_extract_article_shell_skips_farmdoc_leading_author_metadata_list_items() -> None:
    html = """
    <html>
      <body>
        <article>
          <h1>The Iran Conflict and Fertilizer Markets</h1>
          <li>Henrique Monaco, Gary Schnitkey, Nick Paulson, Andre Vieira Lobo, and Joao Arromatte</li>
          <li>Department of Agricultural and Consumer Economics</li>
          <li>University of Illinois</li>
          <p>Latest developments in the Middle East have repercussions on energy, fertilizers, and commodity markets. Fertilizer prices have soared well above historical averages.</p>
          <p>For U.S. farmers, these price movements and supply risks could have large impacts on the 2027 crop year.</p>
        </article>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://farmdocdaily.illinois.edu/2026/04/sample-farmdoc-article.html",
    )

    assert summary.startswith("Latest developments in the Middle East have repercussions")
    assert "Henrique Monaco" not in summary
    assert excerpt_source == "body_selector:article"


def test_article_collector_strips_repeated_title_prefix_from_summary() -> None:
    html = """
    <html>
      <body>
        <main>
          <article>
            <p>Asian shares are mixed ahead of Trump's deadline for Iran to reopen oil route: TOKYO (AP) — Asian shares were mixed in cautious trading Tuesday.</p>
            <p>Oil prices remained in focus as investors tracked geopolitical risk.</p>
          </article>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://apnews.com/article/sample",
        candidate_title="Asian shares are mixed ahead of Trump's deadline for Iran to reopen oil route",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_summary.startswith("TOKYO (AP) — Asian shares were mixed in cautious trading Tuesday.")


def test_article_collector_follows_accessible_materials_page_when_article_body_is_generic() -> None:
    main_html = """
    <html>
      <body>
        <div id="article">
          <div class="col-xs-12 col-sm-8 col-md-8">
            <p>The attached tables and charts released on Wednesday summarize the economic projections made by Federal Open Market Committee participants in conjunction with the March 17-18 meeting.</p>
            <p><a href="/monetarypolicy/fomcprojtabl20260318.htm">Accessible Materials</a></p>
          </div>
        </div>
      </body>
    </html>
    """
    accessible_html = """
    <html>
      <body>
        <div id="content">
          <h1>March 18, 2026: FOMC Projections materials, accessible version</h1>
          <p>Summary of Economic Projections. In conjunction with the Federal Open Market Committee meeting held on March 17-18, 2026, meeting participants submitted projections for GDP growth, the unemployment rate, and inflation.</p>
          <p>Participants also submitted assessments of the appropriate path of the federal funds rate and its longer-run value.</p>
        </div>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318b.htm",
        candidate_title="Federal Reserve Board and Federal Open Market Committee release economic projections from the March 17-18 FOMC meeting",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(
        http_client=RoutingInlineFixtureClient(
            {
                "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318b.htm": main_html,
                "https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260318.htm": accessible_html,
            }
        )
    )

    expanded = collector.expand(candidate)

    assert expanded.candidate_summary.startswith("Summary of Economic Projections.")
    assert "GDP growth" in expanded.candidate_summary
    assert expanded.candidate_excerpt_source == "linked_page:accessible_materials->body_selector:#content"


def test_article_collector_trims_fed_accessible_material_boilerplate_before_summary_heading() -> None:
    main_html = """
    <html>
      <body>
        <div id="article">
          <div class="col-xs-12 col-sm-8 col-md-8">
            <p>The attached tables and charts released on Wednesday summarize the economic projections made by Federal Open Market Committee participants in conjunction with the March 17-18 meeting.</p>
            <p><a href="/monetarypolicy/fomcprojtabl20260318.htm">Accessible Materials</a></p>
          </div>
        </div>
      </body>
    </html>
    """
    accessible_html = """
    <html>
      <body>
        <div id="content">
          <h2>Federal Open Market Committee</h2>
          <h3>March 18, 2026: FOMC Projections materials, accessible version</h3>
          <h3>Accessible version</h3>
          <p>For release at 2:00 p.m., EDT, March 18, 2026</p>
          <h4>Summary of Economic Projections</h4>
          <p>In conjunction with the Federal Open Market Committee meeting held on March 17-18, 2026, meeting participants submitted projections for GDP growth, the unemployment rate, and inflation.</p>
          <h4>Table 1. Economic projections</h4>
          <p>Percent</p>
        </div>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="article",
        candidate_url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318b.htm",
        candidate_title="Federal Reserve Board and Federal Open Market Committee release economic projections from the March 17-18 FOMC meeting",
        candidate_summary="",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(
        http_client=RoutingInlineFixtureClient(
            {
                "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318b.htm": main_html,
                "https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260318.htm": accessible_html,
            }
        )
    )

    expanded = collector.expand(candidate)

    assert expanded.candidate_summary.startswith(
        "Summary of Economic Projections: In conjunction with the Federal Open Market Committee meeting held on March 17-18, 2026"
    )
    assert "Accessible version" not in expanded.candidate_summary
    assert "For release at" not in expanded.candidate_summary
    assert "Table 1." not in expanded.candidate_summary
    assert expanded.candidate_excerpt_source == "linked_page:accessible_materials->body_selector:#content"


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
    reuters_source = _source_by_id("reuters_topics")
    cnbc_source = _source_by_id("cnbc_world")

    assert bea_source.entry_urls == ("https://www.bea.gov/news/current-releases",)
    assert census_source.entry_type == "rss"
    assert census_source.entry_urls == ("https://www.census.gov/economic-indicators/indicator.xml",)
    assert eia_source.entry_type == "rss"
    assert eia_source.entry_urls == ("https://www.eia.gov/rss/press_rss.xml",)
    assert reuters_source.entry_urls == (
        "https://reutersbest.com/topic/commodities-energy/",
        "https://reutersbest.com/topic/economics-central-banking/",
        "https://reutersbest.com/topic/equities/",
        "https://reutersbest.com/topic/markets/",
        "https://reutersbest.com/topic/politics-general/",
    )
    assert cnbc_source.entry_type == "rss"
    assert cnbc_source.entry_urls == (
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    )


def test_feed_collector_normalizes_html_summary_into_readable_text() -> None:
    feed_xml = """
    <rss version="2.0">
      <channel>
        <title>Census Economic Indicators</title>
        <item>
          <title>Advance Monthly Sales for Retail and Food Services</title>
          <link>https://www.census.gov/retail/index.html</link>
          <description><![CDATA[
            <p>Advance retail sales increased 1.2% in March.</p>
            <p>Motor vehicles and food services were the largest contributors.</p>
          ]]></description>
          <pubDate>Tue, 07 Apr 2026 08:30:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    collector = FeedCollector(http_client=InlineFixtureClient(feed_xml))

    candidates = collector.collect(_source_by_id("census_economic_indicators"))

    assert len(candidates) == 1
    assert candidates[0].candidate_summary == (
        "Advance retail sales increased 1.2% in March. "
        "Motor vehicles and food services were the largest contributors."
    )
    assert candidates[0].candidate_excerpt_source == "feed:summary"


def test_feed_collector_normalizes_census_summary_line_breaks_and_percent_artifacts() -> None:
    feed_xml = """
    <rss version="2.0">
      <channel>
        <title>Census Economic Indicators</title>
        <item>
          <title>Advance Monthly Manufacturers' Shipments, Inventories, and Orders</title>
          <link>https://www.census.gov/manufacturing/m3/</link>
          <description><![CDATA[
            New orders for manufactured durable goods in February, down four of the last five months, decreased $4.4 billion or 1.4 percent to $315.5 billion.<p><br />February 2026: -1.4° % Change<br />January 2026 (r): -0.5° % Change<br /></p>
          ]]></description>
          <pubDate>Tue, 07 Apr 2026 08:30:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    collector = FeedCollector(http_client=InlineFixtureClient(feed_xml))

    candidates = collector.collect(_source_by_id("census_economic_indicators"))

    assert len(candidates) == 1
    assert candidates[0].candidate_summary == (
        "New orders for manufactured durable goods in February, down four of the last five months, "
        "decreased $4.4 billion or 1.4 percent to $315.5 billion. "
        "February 2026: -1.4% Change. "
        "January 2026 (r): -0.5% Change."
    )
    assert candidates[0].candidate_excerpt_source == "feed:summary"


def test_extract_article_shell_keeps_more_than_eight_short_body_blocks() -> None:
    html = """
    <html>
      <body>
        <main>
          <article>
            <p>Paragraph 1 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 2 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 3 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 4 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 5 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 6 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 7 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 8 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 9 adds a concrete detail about the overnight policy release.</p>
            <p>Paragraph 10 adds a concrete detail about the overnight policy release.</p>
          </article>
        </main>
      </body>
    </html>
    """
    _, _, summary, excerpt_source = extract_article_shell(
        html=html,
        fallback_url="https://example.com/deep-policy-update",
    )

    assert "Paragraph 9 adds a concrete detail about the overnight policy release." in summary
    assert "Paragraph 10 adds a concrete detail about the overnight policy release." in summary
    assert excerpt_source == "body_selector:article"


def test_article_collector_prefers_article_level_datetime_over_section_date() -> None:
    html = """
    <html>
      <head>
        <title>Policy Statement</title>
        <meta property="article:published_time" content="2026-04-07T10:30:00+00:00" />
      </head>
      <body>
        <main>
          <article>
            <h1>Policy Statement</h1>
            <p>Detailed policy text with implementation timing and agency scope.</p>
          </article>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://example.com/policy-statement",
        candidate_title="Policy Statement",
        candidate_summary="",
        candidate_published_at="2026-04-07",
        candidate_published_at_source="section:time",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-04-07T10:30:00+00:00"
    assert expanded.candidate_published_at_source == "html:meta_article_published_time"


def test_article_collector_does_not_replace_full_section_datetime_with_time_only_html_value() -> None:
    html = """
    <html>
      <body>
        <main>
          <article>
            <h1>Gold Market Update</h1>
            <time>14:00</time>
            <p>Gold prices rose after a softer-than-expected inflation print.</p>
          </article>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="section_card",
        candidate_url="https://example.com/gold-market-update",
        candidate_title="Gold Market Update",
        candidate_summary="",
        candidate_published_at="2026-04-10T10:13:58-04:00",
        candidate_published_at_source="section:time",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-04-10T10:13:58-04:00"
    assert expanded.candidate_published_at_source == "section:time"


def test_article_collector_keeps_newer_search_published_time_when_html_time_is_older() -> None:
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-01-12T15:30:00+08:00" />
      </head>
      <body>
        <main>
          <article>
            <h1>Hong Kong Stocks Rally</h1>
            <p>Hong Kong and mainland shares rallied on improving risk appetite.</p>
          </article>
        </main>
      </body>
    </html>
    """
    candidate = SourceCandidate(
        candidate_type="search_result",
        candidate_url="https://example.com/hong-kong-stocks-rally",
        candidate_title="Hong Kong Stocks Rally",
        candidate_summary="Hong Kong shares gained as sentiment improved.",
        candidate_published_at="2026-04-19",
        candidate_published_at_source="search:published",
        needs_article_fetch=True,
    )
    collector = ArticleCollector(http_client=InlineFixtureClient(html))

    expanded = collector.expand(candidate)

    assert expanded.candidate_published_at == "2026-04-19"
    assert expanded.candidate_published_at_source == "search:published"
    assert dict(expanded.source_context or {}).get("published_at_diagnostics") == {
        "search_published_at": "2026-04-19",
        "search_published_at_source": "search:published",
        "page_published_at": "2026-01-12T15:30:00+08:00",
        "page_published_at_source": "html:meta_article_published_time",
        "selected_published_at": "2026-04-19",
        "selected_published_at_source": "search:published",
        "published_at_conflict": True,
    }


def test_normalize_published_at_value_parses_month_day_year_dash_time() -> None:
    from app.collectors.article import _normalize_published_at_value

    assert _normalize_published_at_value("Apr 24, 2026 - 10:36 PM") == "2026-04-24T22:36:00"


def test_default_source_registry_exposes_cross_market_metadata_and_strategic_sources() -> None:
    registry = build_default_source_registry()
    all_registry = build_default_source_registry(include_disabled=True)
    by_id = {source.source_id: source for source in registry}
    all_by_id = {source.source_id: source for source in all_registry}

    assert by_id["whitehouse_news"].source_group == "official_policy"
    assert by_id["whitehouse_news"].source_tier == "P0"
    assert by_id["whitehouse_news"].content_mode == "policy"
    assert by_id["whitehouse_news"].asset_tags == ("rates", "trade", "technology", "energy")
    assert by_id["whitehouse_news"].mainline_tags == (
        "rates_liquidity",
        "trade_export_control",
        "tech_semiconductor",
        "geopolitics_energy",
    )
    assert by_id["whitehouse_news"].search_discovery_enabled is True
    assert len(by_id["whitehouse_news"].search_queries) == 2

    assert by_id["eia_pressroom"].source_group == "commodity_data"
    assert by_id["eia_pressroom"].content_mode == "energy"
    assert by_id["eia_pressroom"].asset_tags == ("oil", "natural_gas", "chemicals", "shipping")
    assert by_id["eia_pressroom"].mainline_tags == ("geopolitics_energy", "industrials_chemicals", "shipping_logistics")

    assert by_id["bis_news_updates"].source_group == "official_policy"
    assert by_id["bis_news_updates"].source_tier == "P0"
    assert by_id["bis_news_updates"].content_mode == "technology"
    assert by_id["bis_news_updates"].allowed_domains == ("bis.gov",)

    assert by_id["bls_news_releases"].search_discovery_enabled is True
    assert len(by_id["bls_news_releases"].search_queries) == 3
    assert any("filetype:htm" in query and "nr0" in query for query in by_id["bls_news_releases"].search_queries)
    assert by_id["ofac_recent_actions"].search_discovery_enabled is True
    assert len(by_id["ofac_recent_actions"].search_queries) == 2
    assert by_id["ofac_recent_actions"].source_group == "official_policy"
    assert by_id["doe_articles"].source_group == "commodity_data"
    assert by_id["doe_articles"].search_discovery_enabled is True
    assert len(by_id["doe_articles"].search_queries) == 3
    assert any("LNG grid coal reliability manufacturing" in query for query in by_id["doe_articles"].search_queries)
    assert by_id["newyorkfed_news"].source_group == "official_data"
    assert by_id["newyorkfed_news"].content_mode == "rates"
    assert by_id["newyorkfed_news"].search_discovery_enabled is True
    assert by_id["ecb_press"].source_group == "official_data"
    assert by_id["ecb_press"].content_mode == "rates"
    assert by_id["cftc_general_press_releases"].source_group == "commodity_data"
    assert by_id["cftc_enforcement_press_releases"].content_mode == "commodities"
    assert by_id["iea_news"].source_group == "commodity_data"
    assert by_id["iea_news"].search_discovery_enabled is True
    assert len(by_id["iea_news"].search_queries) == 4
    assert any("site:iea.org/reports" in query for query in by_id["iea_news"].search_queries)
    assert by_id["worldbank_news"].source_group == "official_data"
    assert by_id["kitco_news"].source_group == "commodity_data"
    assert by_id["kitco_news"].content_mode == "precious_metals"
    assert by_id["oilprice_world_news"].source_group == "commodity_data"
    assert by_id["oilprice_world_news"].content_mode == "energy"
    assert by_id["farmdoc_daily"].source_group == "commodity_data"
    assert by_id["farmdoc_daily"].content_mode == "agriculture"
    assert by_id["scmp_markets"].source_group == "market_media"
    assert by_id["scmp_markets"].content_mode == "market"
    assert by_id["scmp_markets"].search_discovery_enabled is True
    assert len(by_id["scmp_markets"].search_queries) == 3
    assert by_id["tradingeconomics_hk"].source_group == "market_media"
    assert by_id["tradingeconomics_hk"].content_mode == "market"
    assert by_id["tradingeconomics_hk"].search_discovery_enabled is True
    assert len(by_id["tradingeconomics_hk"].search_queries) == 2
    assert by_id["cnbc_markets"].source_group == "market_media"
    assert by_id["cnbc_markets"].content_mode == "market"
    assert by_id["cnbc_technology"].source_group == "market_media"
    assert by_id["cnbc_technology"].content_mode == "technology"
    assert by_id["ap_world"].source_group == "market_media"
    assert by_id["ap_technology"].content_mode == "technology"
    assert by_id["ap_economy"].content_mode == "macro"
    assert by_id["ap_financial_markets"].content_mode == "market"

    assert "state_spokesperson_releases" not in by_id
    assert "dod_news_releases" not in by_id
    assert all_by_id["state_spokesperson_releases"].is_enabled is False
    assert all_by_id["dod_news_releases"].is_enabled is False


def test_default_source_registry_requires_cross_market_metadata_for_all_sources() -> None:
    registry = build_default_source_registry()

    assert registry
    for source in registry:
        assert source.source_group, source.source_id
        assert source.source_tier, source.source_id
        assert source.content_mode, source.source_id
        assert source.asset_tags, source.source_id
        assert source.mainline_tags, source.source_id


def test_default_source_registry_does_not_probe_mainland_china_official_domains() -> None:
    blocked_tokens = (
        "gov.cn",
        "pbc.gov.cn",
        "stats.gov.cn",
        "mofcom.gov.cn",
        "ndrc.gov.cn",
        "csrc.gov.cn",
        "safe.gov.cn",
        "customs.gov.cn",
        "chinatax.gov.cn",
    )
    registry = build_default_source_registry()

    assert registry
    for source in registry:
        searchable_text = " ".join(
            [
                source.source_id,
                source.display_name,
                *source.entry_urls,
                *source.allowed_domains,
                *source.search_queries,
            ]
        ).lower()
        for token in blocked_tokens:
            assert token not in searchable_text, source.source_id


def test_source_registry_safety_guard_disables_mainland_china_official_sources_without_blocking_readhub() -> None:
    official_source = SourceDefinition(
        source_id="unsafe_stats_cn",
        display_name="Unsafe Mainland Statistics Source",
        organization_type="official_data",
        source_class="macro",
        entry_type="section_page",
        entry_urls=("https://www.stats.gov.cn/sj/",),
        priority=10,
        poll_interval_seconds=3600,
        allowed_domains=("stats.gov.cn",),
        search_discovery_enabled=True,
        search_queries=("site:stats.gov.cn China macro data",),
    )
    readhub_source = next(source for source in build_default_source_registry() if source.source_id == "readhub_daily_digest")

    guarded = _apply_registry_safety_guards(official_source)

    assert guarded.is_enabled is False
    assert guarded.disable_reason == MAINLAND_CHINA_OFFICIAL_DISABLE_REASON
    assert _apply_registry_safety_guards(readhub_source).is_enabled is True


def test_source_url_validation_rejects_mainland_china_official_domains_even_when_allowed() -> None:
    source = SourceDefinition(
        source_id="manual_stats_cn",
        display_name="Manual Mainland Statistics Source",
        organization_type="official_data",
        source_class="macro",
        entry_type="section_page",
        entry_urls=("https://www.stats.gov.cn/sj/",),
        priority=10,
        poll_interval_seconds=3600,
        allowed_domains=("stats.gov.cn",),
    )

    result = validate_source_url("https://www.stats.gov.cn/sj/zxfb/", source)

    assert result["domain_status"] == "verified"
    assert result["blocked_reason"] == MAINLAND_CHINA_OFFICIAL_DISABLE_REASON
    assert result["url_valid"] is False
    assert is_source_url_allowed("https://www.stats.gov.cn/sj/zxfb/", source) is False


def test_china_related_search_queries_stay_site_scoped_to_allowed_domains() -> None:
    china_markers = ("china", "hong kong", "kweb", "fxi", "adr", "adrs")
    blocked_tokens = ("gov.cn", "pbc.gov.cn", "stats.gov.cn", "mofcom.gov.cn", "ndrc.gov.cn", "csrc.gov.cn", "safe.gov.cn")

    for source in build_default_source_registry():
        for query in source.search_queries:
            normalized = query.lower()
            if not any(marker in normalized for marker in china_markers):
                continue
            assert "site:" in normalized, source.source_id
            assert any(f"site:{domain}" in normalized for domain in source.allowed_domains), source.source_id
            assert all(token not in normalized for token in blocked_tokens), source.source_id
