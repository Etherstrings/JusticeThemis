# -*- coding: utf-8 -*-
"""Tests for env-backed search discovery supplementation."""

from __future__ import annotations

from app.services.search_discovery import SearchDiscoveryResult, SearchDiscoveryService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceDefinition


class FakeSearchProvider:
    def __init__(self, name: str, results: list[SearchDiscoveryResult]):
        self.name = name
        self.results = results
        self.queries: list[str] = []
        self.is_available = True

    def search(self, *, query: str, max_results: int, days: int = 7) -> list[SearchDiscoveryResult]:
        self.queries.append(query)
        return self.results[:max_results]


def test_search_discovery_service_reads_provider_keys_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BOCHA_API_KEYS", "bocha-a,bocha-b")
    monkeypatch.setenv("TAVILY_API_KEYS", "tavily-a")
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    monkeypatch.delenv("BRAVE_API_KEYS", raising=False)

    service = SearchDiscoveryService.from_environment()

    assert [provider.name for provider in service.providers] == ["Bocha", "Tavily"]


def test_search_discovery_service_prioritizes_serpapi_when_available(monkeypatch) -> None:
    monkeypatch.setenv("BOCHA_API_KEYS", "bocha-a")
    monkeypatch.setenv("TAVILY_API_KEYS", "tavily-a")
    monkeypatch.setenv("SERPAPI_API_KEYS", "serp-a")
    monkeypatch.delenv("BRAVE_API_KEYS", raising=False)

    service = SearchDiscoveryService.from_environment()

    assert [provider.name for provider in service.providers] == ["SerpAPI", "Bocha", "Tavily"]


def test_search_discovery_filters_off_domain_results_and_normalizes_candidates() -> None:
    source = SourceDefinition(
        source_id="state_briefings",
        display_name="State Briefings",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.state.gov/briefings-statements/",),
        priority=90,
        poll_interval_seconds=900,
        allowed_domains=("state.gov",),
        search_discovery_enabled=True,
        search_queries=("site:state.gov/briefings-statements state department statement",),
    )
    provider = FakeSearchProvider(
        "Tavily",
        [
            SearchDiscoveryResult(
                title="Department Press Briefing",
                snippet="Official statement with trade and sanctions detail.",
                url="https://www.state.gov/briefings-statements/department-press-briefing/",
                published_at="2026-04-09",
            ),
            SearchDiscoveryResult(
                title="Mirrored summary",
                snippet="Mirror site should be filtered out.",
                url="https://mirror.example.com/state/briefing",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=5)

    assert provider.queries == ["site:state.gov/briefings-statements state department statement"]
    assert len(candidates) == 1
    assert candidates[0].candidate_type == "search_result"
    assert candidates[0].candidate_url == "https://www.state.gov/briefings-statements/department-press-briefing/"
    assert candidates[0].candidate_excerpt_source == "search:tavily"
    assert candidates[0].candidate_published_at == "2026-04-09"
    assert candidates[0].candidate_published_at_source == "search:published"
    assert candidates[0].needs_article_fetch is True


def test_search_discovery_cleans_navigation_noise_from_excerpt() -> None:
    source = SourceDefinition(
        source_id="state_briefings",
        display_name="State Briefings",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.state.gov/briefings-statements/",),
        priority=90,
        poll_interval_seconds=900,
        allowed_domains=("state.gov",),
        search_discovery_enabled=True,
        search_queries=("site:state.gov/releases/office-of-the-spokesperson state department release",),
    )
    provider = FakeSearchProvider(
        "Tavily",
        [
            SearchDiscoveryResult(
                title="State Department Release",
                snippet=(
                    "# State Department Release\n\n"
                    "Cookie Settings\n"
                    "Skip to main content\n"
                    "An official website of the United States Government\n"
                    "This statement details new sanctions coordination and diplomatic measures with allies."
                ),
                url="https://www.state.gov/releases/office-of-the-spokesperson/2026/04/sample-release/",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=1)

    assert len(candidates) == 1
    assert "Cookie Settings" not in candidates[0].candidate_summary
    assert "Skip to main content" not in candidates[0].candidate_summary
    assert "new sanctions coordination" in candidates[0].candidate_summary


def test_search_discovery_does_not_reintroduce_raw_excerpt_when_all_lines_are_noise() -> None:
    source = SourceDefinition(
        source_id="state_briefings",
        display_name="State Briefings",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.state.gov/briefings-statements/",),
        priority=90,
        poll_interval_seconds=900,
        allowed_domains=("state.gov",),
        search_discovery_enabled=True,
        search_queries=("site:state.gov/releases/office-of-the-spokesperson state department release",),
    )
    provider = FakeSearchProvider(
        "Tavily",
        [
            SearchDiscoveryResult(
                title="State Department Release",
                snippet=(
                    "Cookie Settings\n"
                    "Skip to main content\n"
                    "We use cookies to make our website work better.\n"
                    "Preferences- [x] Preferences\n"
                ),
                url="https://www.state.gov/releases/office-of-the-spokesperson/2026/04/sample-release/",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=1)

    assert len(candidates) == 1
    assert candidates[0].candidate_summary == ""


def test_search_discovery_filters_entry_url_even_when_path_casing_differs() -> None:
    source = SourceDefinition(
        source_id="dod_releases",
        display_name="DOD Releases",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.defense.gov/News/Releases/",),
        priority=90,
        poll_interval_seconds=900,
        allowed_domains=("defense.gov",),
        search_discovery_enabled=True,
        search_queries=("site:defense.gov/News/Releases defense deployment statement",),
    )
    provider = FakeSearchProvider(
        "Tavily",
        [
            SearchDiscoveryResult(
                title="Releases",
                snippet="Listing page should be skipped.",
                url="https://www.defense.gov/News/releases/",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))

    assert service.discover(source=source, max_results=1) == []


def test_search_discovery_filters_white_house_gallery_pages_as_low_value_results() -> None:
    source = next(item for item in build_default_source_registry() if item.source_id == "whitehouse_news")
    provider = FakeSearchProvider(
        "Bocha",
        [
            SearchDiscoveryResult(
                title="White House Gallery",
                snippet="Gallery page should be skipped even when it is same-domain.",
                url="https://www.whitehouse.gov/gallery/39665/",
                published_at="2026-04-09",
            ),
            SearchDiscoveryResult(
                title="Fact Sheet: Semiconductor Supply Chain Update",
                snippet="White House fact sheet on tariffs, supply chains, and domestic semiconductor capacity.",
                url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/09/fact-sheet-semiconductor-supply-chain-update/",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=2)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == (
        "https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/09/fact-sheet-semiconductor-supply-chain-update/"
    )


def test_search_discovery_filters_white_house_pagination_pages_as_low_value_results() -> None:
    source = next(item for item in build_default_source_registry() if item.source_id == "whitehouse_news")
    provider = FakeSearchProvider(
        "SerpAPI",
        [
            SearchDiscoveryResult(
                title="Releases – Page 53 of 53",
                snippet="Pagination page should be skipped.",
                url="https://www.whitehouse.gov/releases/page/53/",
                published_at="2026-04-09",
            ),
            SearchDiscoveryResult(
                title="Strong March Jobs Report Signals Accelerating Momentum Under President Trump",
                snippet="Official White House release page with macro and labor framing.",
                url="https://www.whitehouse.gov/releases/2026/04/strong-march-jobs-report-signals-accelerating-momentum-under-president-trump/",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=2)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == (
        "https://www.whitehouse.gov/releases/2026/04/strong-march-jobs-report-signals-accelerating-momentum-under-president-trump/"
    )


def test_default_source_registry_uses_white_house_queries_for_real_article_paths() -> None:
    source = next(item for item in build_default_source_registry() if item.source_id == "whitehouse_news")

    assert source.search_discovery_enabled is True
    assert any('site:whitehouse.gov "fact sheet"' in query for query in source.search_queries)
    assert any('site:whitehouse.gov "presidential action"' in query for query in source.search_queries)


def test_search_discovery_filters_ustr_node_page_as_low_value_result() -> None:
    source = next(item for item in build_default_source_registry() if item.source_id == "ustr_press_releases")
    provider = FakeSearchProvider(
        "SerpAPI",
        [
            SearchDiscoveryResult(
                title="USTR node page",
                snippet="Opaque node page should be skipped.",
                url="https://ustr.gov/node",
                published_at="2026-04-09",
            ),
            SearchDiscoveryResult(
                title="Ambassador Greer Travel to Michigan and Ohio",
                snippet="Official USTR press release article.",
                url="https://ustr.gov/about/policy-offices/press-office/press-releases/2026/april/ambassador-greer-travel-michigan-and-ohio-tour-manufacturing-plants-and-meet-manufacturing-workers",
                published_at="2026-04-09",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=2)

    assert len(candidates) == 1
    assert candidates[0].candidate_url.endswith("/ambassador-greer-travel-michigan-and-ohio-tour-manufacturing-plants-and-meet-manufacturing-workers")


def test_search_discovery_filters_ofac_general_license_listing_as_low_value_result() -> None:
    source = next(item for item in build_default_source_registry() if item.source_id == "ofac_recent_actions")
    provider = FakeSearchProvider(
        "SerpAPI",
        [
            SearchDiscoveryResult(
                title="General Licenses",
                snippet="Category listing should be skipped.",
                url="https://ofac.treasury.gov/recent-actions/general-licenses",
                published_at="2026-04-09",
            ),
            SearchDiscoveryResult(
                title="Issuance of Amended Russia-related General License",
                snippet="Official OFAC recent action article.",
                url="https://ofac.treasury.gov/recent-actions/20260408",
                published_at="2026-04-08",
            ),
        ],
    )

    service = SearchDiscoveryService(providers=(provider,))
    candidates = service.discover(source=source, max_results=2)

    assert len(candidates) == 1
    assert candidates[0].candidate_url == "https://ofac.treasury.gov/recent-actions/20260408"
