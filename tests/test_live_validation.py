# -*- coding: utf-8 -*-
"""Tests for env-backed live validation helpers."""

from __future__ import annotations

from pathlib import Path
import os

from app.live_validation import (
    DEFAULT_SOURCE_IDS,
    build_market_snapshot_validation_report,
    collect_section_capture_validation_report,
    collect_market_snapshot_validation_report,
    collect_search_validation_report,
    load_env_values_from_files,
    summarize_search_candidates,
)
from app.sources.types import SourceCandidate, SourceDefinition


class FakeProvider:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeSearchDiscoveryService:
    def __init__(self, candidates: list[SourceCandidate]) -> None:
        self.providers = (FakeProvider("Tavily"), FakeProvider("SerpAPI"))
        self._candidates = list(candidates)
        self.calls: list[tuple[str, int, int]] = []

    def discover(
        self,
        *,
        source: SourceDefinition,
        max_results: int = 5,
        days: int = 7,
    ) -> list[SourceCandidate]:
        self.calls.append((source.source_id, max_results, days))
        return list(self._candidates[:max_results])


class FakeMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot
        self.called = False

    def refresh_us_close_snapshot(self) -> dict[str, object]:
        self.called = True
        return dict(self.snapshot)


class FakeSectionCollector:
    def __init__(self, candidates: list[SourceCandidate]) -> None:
        self._candidates = list(candidates)
        self.calls: list[str] = []

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        self.calls.append(source.source_id)
        return list(self._candidates)


class FakeArticleCollector:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def expand(self, candidate: SourceCandidate) -> SourceCandidate:
        self.calls.append(candidate.candidate_url)
        return SourceCandidate(
            candidate_type=candidate.candidate_type,
            candidate_url=candidate.candidate_url,
            candidate_title=candidate.candidate_title,
            candidate_summary="Expanded article summary",
            candidate_published_at="2026-04-08T12:00:00+00:00",
            candidate_excerpt_source="html:article_body",
        )


class RecordingMarketSnapshotService:
    def __init__(self) -> None:
        self.seen_refresh_token = os.environ.get("IFIND_REFRESH_TOKEN", "")

    def refresh_us_close_snapshot(self) -> dict[str, object]:
        return {
            "analysis_date": "2026-04-09",
            "market_date": "2026-04-08",
            "source_name": "iFinD History",
            "headline": "done",
            "capture_summary": {"missing_symbols": [], "failed_instruments": []},
            "indexes": [],
            "sectors": [],
            "precious_metals": [],
            "energy": [],
            "industrial_metals": [],
        }


def _source(*, source_id: str = "treasury_press_releases") -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        display_name="Treasury Press Releases",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://home.treasury.gov/news/press-releases",),
        priority=95,
        poll_interval_seconds=600,
        allowed_domains=("treasury.gov",),
        search_discovery_enabled=True,
        search_queries=("site:home.treasury.gov/news/press-releases treasury press release",),
    )


def test_load_env_values_from_files_applies_later_file_overrides(tmp_path: Path) -> None:
    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text(
        'BOCHA_API_KEYS="bocha-base"\n'
        "TAVILY_API_KEYS=tavily-base\n"
        "SERPAPI_API_KEYS=serp-base\n",
        encoding="utf-8",
    )
    local_env.write_text(
        "BOCHA_API_KEYS='bocha-local'\n"
        "SERPAPI_API_KEYS=serp-local # inline comment\n",
        encoding="utf-8",
    )

    loaded = load_env_values_from_files(
        env_file_paths=(base_env, local_env),
        env_names=("BOCHA_API_KEYS", "TAVILY_API_KEYS", "SERPAPI_API_KEYS", "BRAVE_API_KEYS"),
    )

    assert loaded == {
        "BOCHA_API_KEYS": "bocha-local",
        "TAVILY_API_KEYS": "tavily-base",
        "SERPAPI_API_KEYS": "serp-local",
    }


def test_default_live_validation_source_ids_follow_current_boundary() -> None:
    assert "whitehouse_news" in DEFAULT_SOURCE_IDS
    assert "ustr_press_releases" in DEFAULT_SOURCE_IDS
    assert "doe_articles" in DEFAULT_SOURCE_IDS
    assert "state_spokesperson_releases" not in DEFAULT_SOURCE_IDS
    assert "dod_news_releases" not in DEFAULT_SOURCE_IDS


def test_summarize_search_candidates_counts_same_domain_hits_and_providers() -> None:
    source = _source()
    candidates = [
        SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://home.treasury.gov/news/press-releases/sample-one",
            candidate_title="Sample One",
            capture_provider="tavily",
        ),
        SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://home.treasury.gov/news/press-releases/sample-two",
            candidate_title="Sample Two",
            capture_provider="serpapi",
        ),
        SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://mirror.example.com/treasury/sample-three",
            candidate_title="Sample Three",
            capture_provider="tavily",
        ),
    ]

    summary = summarize_search_candidates(source=source, candidates=candidates)

    assert summary["total_candidates"] == 3
    assert summary["same_domain_candidates"] == 2
    assert summary["provider_counts"] == {"tavily": 2, "serpapi": 1}
    assert summary["sample_urls"] == [
        "https://home.treasury.gov/news/press-releases/sample-one",
        "https://home.treasury.gov/news/press-releases/sample-two",
        "https://mirror.example.com/treasury/sample-three",
    ]


def test_collect_search_validation_report_uses_service_sources_and_limits() -> None:
    source = _source(source_id="state_spokesperson_releases")
    candidates = [
        SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://www.state.gov/briefings-statements/sample-release",
            candidate_title="Sample Release",
            capture_provider="tavily",
        ),
    ]
    service = FakeSearchDiscoveryService(candidates)

    report = collect_search_validation_report(
        service=service,
        sources=(source,),
        max_results=4,
        days=3,
    )

    assert report["provider_names"] == ["Tavily", "SerpAPI"]
    assert report["source_ids"] == ["state_spokesperson_releases"]
    assert report["sources"][0]["source_id"] == "state_spokesperson_releases"
    assert report["sources"][0]["total_candidates"] == 1
    assert report["sources"][0]["search_discovery_enabled"] is True
    assert service.calls == [("state_spokesperson_releases", 4, 3)]


def test_collect_search_validation_report_marks_disabled_sources_without_querying_service() -> None:
    source = SourceDefinition(
        source_id="bis_news_updates",
        display_name="BIS News Updates",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://media.bis.gov/news-updates",),
        priority=97,
        poll_interval_seconds=600,
        allowed_domains=("bis.gov",),
        search_discovery_enabled=False,
    )
    service = FakeSearchDiscoveryService([])

    report = collect_search_validation_report(service=service, sources=(source,), max_results=4, days=7)

    assert report["sources"] == [
        {
            "source_id": "bis_news_updates",
            "display_name": "BIS News Updates",
            "allowed_domains": ["bis.gov"],
            "search_discovery_enabled": False,
            "query_count": 0,
            "status": "disabled",
            "total_candidates": 0,
            "same_domain_candidates": 0,
            "provider_counts": {},
            "sample_urls": [],
        }
    ]
    assert service.calls == []


def test_collect_search_validation_report_marks_enabled_sources_unconfigured_without_querying_service() -> None:
    source = _source(source_id="ofac_recent_actions")
    service = FakeSearchDiscoveryService([])
    service.providers = ()

    report = collect_search_validation_report(service=service, sources=(source,), max_results=4, days=7)

    assert report["provider_names"] == []
    assert report["sources"] == [
        {
            "source_id": "ofac_recent_actions",
            "display_name": "Treasury Press Releases",
            "allowed_domains": ["treasury.gov"],
            "search_discovery_enabled": True,
            "query_count": 1,
            "status": "unconfigured",
            "error": "No search discovery providers configured",
            "total_candidates": 0,
            "same_domain_candidates": 0,
            "provider_counts": {},
            "sample_urls": [],
        }
    ]
    assert service.calls == []


def test_collect_section_capture_validation_report_summarizes_candidates_and_article_samples() -> None:
    source = _source(source_id="ofac_recent_actions")
    collector = FakeSectionCollector(
        [
            SourceCandidate(
                candidate_type="section_card",
                candidate_url="https://ofac.treasury.gov/recent-actions/20260408",
                candidate_title="OFAC action",
            )
        ]
    )
    article_collector = FakeArticleCollector()

    report = collect_section_capture_validation_report(
        collector=collector,
        article_collector=article_collector,
        sources=(source,),
        article_sample_limit=1,
    )

    assert collector.calls == ["ofac_recent_actions"]
    assert article_collector.calls == ["https://ofac.treasury.gov/recent-actions/20260408"]
    assert report["sources"][0]["status"] == "ok"
    assert report["sources"][0]["total_candidates"] == 1
    assert report["sources"][0]["sample_urls"] == ["https://ofac.treasury.gov/recent-actions/20260408"]
    assert report["sources"][0]["article_samples"] == [
        {
            "url": "https://ofac.treasury.gov/recent-actions/20260408",
            "title": "OFAC action",
            "published_at": "2026-04-08T12:00:00+00:00",
            "summary": "Expanded article summary",
            "excerpt_source": "html:article_body",
        }
    ]


def test_collect_market_snapshot_validation_report_summarizes_buckets_and_missing_symbols() -> None:
    service = FakeMarketSnapshotService(
        {
            "analysis_date": "2026-04-09",
            "market_date": "2026-04-08",
            "source_name": "Yahoo Finance Chart",
            "headline": "美股科技和贵金属走强，能源偏弱。",
            "capture_summary": {
                "capture_status": "partial",
                "captured_instrument_count": 5,
                "missing_symbols": ["BZ=F", "ALI=F"],
                "failed_instruments": [{"symbol": "BZ=F", "reason": "timeout"}],
            },
            "indexes": [{"symbol": "^GSPC"}, {"symbol": "^IXIC"}],
            "sectors": [{"symbol": "XLK"}],
            "sentiment": [{"symbol": "^VIX"}],
            "rates_fx": [{"symbol": "^TNX"}],
            "precious_metals": [{"symbol": "GC=F"}],
            "energy": [{"symbol": "CL=F"}],
            "industrial_metals": [],
        }
    )

    report = collect_market_snapshot_validation_report(service=service)

    assert report["status"] == "ok"
    assert report["analysis_date"] == "2026-04-09"
    assert report["bucket_counts"] == {
        "indexes": 2,
        "sectors": 1,
        "sentiment": 1,
        "rates_fx": 1,
        "precious_metals": 1,
        "energy": 1,
        "industrial_metals": 0,
    }
    assert report["missing_symbols"] == ["BZ=F", "ALI=F"]
    assert report["failed_instruments"] == [{"symbol": "BZ=F", "reason": "timeout"}]
    assert service.called is True


def test_collect_market_snapshot_validation_report_exposes_provider_hits_and_tiered_missing() -> None:
    service = FakeMarketSnapshotService(
        {
            "analysis_date": "2026-04-09",
            "market_date": "2026-04-08",
            "source_name": "iFinD History, Yahoo Finance Chart",
            "headline": "科技偏强，贵金属缺失。",
            "capture_summary": {
                "capture_status": "partial",
                "captured_instrument_count": 6,
                "missing_symbols": ["GC=F"],
                "core_missing_symbols": [],
                "supporting_missing_symbols": ["GC=F"],
                "optional_missing_symbols": [],
                "provider_hits": {"iFinD History": 4, "Yahoo Finance Chart": 2},
                "freshness_status_counts": {"fresh": 6},
                "failed_instruments": [],
            },
            "indexes": [{"symbol": "^GSPC"}],
            "sectors": [{"symbol": "XLK"}],
            "sentiment": [{"symbol": "^VIX"}],
            "rates_fx": [{"symbol": "^TNX"}],
            "precious_metals": [],
            "energy": [{"symbol": "CL=F"}],
            "industrial_metals": [],
        }
    )

    report = collect_market_snapshot_validation_report(service=service)

    assert report["provider_hits"] == {"iFinD History": 4, "Yahoo Finance Chart": 2}
    assert report["core_missing_symbols"] == []
    assert report["supporting_missing_symbols"] == ["GC=F"]
    assert report["optional_missing_symbols"] == []
    assert report["freshness_status_counts"] == {"fresh": 6}


def test_build_market_snapshot_validation_report_loads_ifind_env_from_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("IFIND_REFRESH_TOKEN=refresh-from-file\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_service_factory(repo):  # noqa: ANN001
        service = RecordingMarketSnapshotService()
        captured["refresh_token"] = service.seen_refresh_token
        return service

    report = build_market_snapshot_validation_report(
        env_file_paths=(env_file,),
        service_factory=fake_service_factory,
    )

    assert captured["refresh_token"] == "refresh-from-file"
    assert report["loaded_env_names"] == ["IFIND_REFRESH_TOKEN"]
