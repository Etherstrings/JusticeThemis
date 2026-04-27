# -*- coding: utf-8 -*-
"""Tests for the frontend-facing v1 API."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
import requests

from app.db import Database
from app.main import create_app
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.frontend_api import FrontendApiService
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate, SourceDefinition


class FailingHttpClient:
    def __init__(self, *, status_code: int = 403, message: str = "Forbidden") -> None:
        self.status_code = status_code
        self.message = message
        self.fetches: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetches.append(url)
        response = requests.Response()
        response.status_code = self.status_code
        response.url = url
        raise requests.HTTPError(
            f"{self.status_code} Client Error: {self.message} for url: {url}",
            response=response,
        )


def _seed_item(
    repo: OvernightRepository,
    *,
    source_id: str,
    url: str,
    title: str,
    summary: str,
    published_at: str,
    created_at: str,
    source_context: dict[str, object] | None = None,
) -> int:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url=url,
            candidate_title=title,
            candidate_summary=summary,
            candidate_excerpt_source="body_selector:main",
            candidate_published_at=published_at,
            candidate_published_at_source="rss:published",
            source_context=source_context,
        )
    )
    raw_id = repo.create_raw_record(
        source_id=source_id,
        fetch_mode="test_seed",
        payload_hash=f"{source_id}:{published_at}:{title}",
    )
    stored = repo.persist_source_item(replace(normalized, raw_id=raw_id))
    repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
    repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
    with repo.db.connect() as connection:
        connection.execute(
            "UPDATE overnight_source_items SET created_at = ? WHERE id = ?",
            (created_at, stored.id),
        )
    return stored.id


def _build_seeded_client(database_path: Path) -> tuple[TestClient, dict[str, int]]:
    database = Database(database_path)
    repo = OvernightRepository(database)
    item_ids = {
        "fed_ready": _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/hawkish-rates",
            title="Federal Reserve says inflation and rates may stay restrictive",
            summary=(
                "Federal Reserve officials said inflation remains elevated, Treasury yields stayed firm, "
                "and rates may need to remain restrictive while markets assess the next FOMC path."
            ),
            published_at="2026-04-07T01:00:00+00:00",
            created_at="2026-04-07 09:01:00",
        ),
        "census_ready": _seed_item(
            repo,
            source_id="census_economic_indicators",
            url="https://example.com/census/trade-exports",
            title="U.S. trade data shows exports rose 12% as imports stabilized",
            summary=(
                "The latest Census release showed trade conditions improved as exports rose 12% and "
                "inventories stabilized, giving an official read on external demand and shipping activity."
            ),
            published_at="2026-04-07T00:30:00+00:00",
            created_at="2026-04-07 09:02:00",
        ),
        "whitehouse_review": _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/statement-bilateral-talks",
            title="Statement from the White House on bilateral talks",
            summary=(
                "The White House released a statement on bilateral talks and future cooperation, "
                "but the text did not yet specify tariffs, subsidies, procurement rules, or sector lists."
            ),
            published_at="2026-04-07T00:10:00+00:00",
            created_at="2026-04-07 09:03:00",
        ),
        "ap_other": _seed_item(
            repo,
            source_id="ap_business",
            url="https://example.com/ap/oil-shipping",
            title="AP reports oil and shipping costs rise after Hormuz tensions",
            summary=(
                "AP reported that oil prices and shipping costs moved higher after new Hormuz tensions, "
                "adding context for overnight energy and logistics risk even before official follow-up."
            ),
            published_at="2026-04-07T02:00:00+00:00",
            created_at="2026-04-07 09:04:00",
        ),
        "cnbc_other": _seed_item(
            repo,
            source_id="cnbc_world",
            url="https://example.com/cnbc/market-wrap",
            title="CNBC says markets wait for more policy detail",
            summary=(
                "CNBC said global markets stayed cautious and waited for more policy detail, "
                "offering useful context but no direct official market mapping for A-share sectors."
            ),
            published_at="2026-04-07T02:30:00+00:00",
            created_at="2026-04-07 09:05:00",
        ),
    }
    capture_service = OvernightSourceCaptureService(
        repo=repo,
        registry=build_default_source_registry(),
    )
    client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))
    return client, item_ids


def _admin_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
    monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
    return {"X-Admin-Access-Key": "secret-admin"}


class FakeMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object] | None) -> None:
        self.snapshot = snapshot

    def get_daily_snapshot(self, *, analysis_date: str | None = None):
        return self.snapshot


def test_dashboard_endpoint_groups_primary_watchlist_and_background_news() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client, _item_ids = _build_seeded_client(Path(temp_dir) / "test_frontend_dashboard.db")

        response = client.get("/api/v1/dashboard")

        assert response.status_code == 200
        payload = response.json()
        assert payload["hero"] == {
            "total_items": 5,
            "ready_count": 2,
            "review_count": 2,
            "background_count": 1,
            "official_count": 3,
            "editorial_count": 2,
        }
        assert [item["source_id"] for item in payload["lead_signals"]] == [
            "fed_news",
            "census_economic_indicators",
        ]
        assert [item["source_id"] for item in payload["watchlist"]] == [
            "whitehouse_news",
            "ap_business",
        ]
        assert [item["source_id"] for item in payload["background"]] == ["cnbc_world"]
        assert payload["source_health"]["total_sources"] == len(build_default_source_registry())
        assert payload["source_health"]["active_sources"] == 5
        assert payload["source_health"]["sources"][0]["source_id"] == "fed_news"
        assert payload["market_board"] == {}
        assert payload["mainlines"] == []


def test_news_endpoint_supports_tabs_filters_search_and_cursor_pagination() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client, item_ids = _build_seeded_client(Path(temp_dir) / "test_frontend_news.db")

        page_one = client.get("/api/v1/news", params={"limit": 2})
        other_news = client.get("/api/v1/news", params={"tab": "other", "limit": 10})
        search = client.get("/api/v1/news", params={"q": "Hormuz", "limit": 10})
        filtered = client.get(
            "/api/v1/news",
            params={"analysis_status": "review", "source_id": "whitehouse_news", "limit": 10},
        )
        page_two = client.get("/api/v1/news", params={"limit": 2, "cursor": "2"})

        assert page_one.status_code == 200
        page_one_payload = page_one.json()
        assert page_one_payload["total"] == 5
        assert page_one_payload["returned"] == 2
        assert page_one_payload["next_cursor"] == "2"
        assert [item["item_id"] for item in page_one_payload["items"]] == [
            item_ids["fed_ready"],
            item_ids["census_ready"],
        ]

        assert other_news.status_code == 200
        assert [item["source_id"] for item in other_news.json()["items"]] == [
            "ap_business",
            "cnbc_world",
        ]

        assert search.status_code == 200
        assert [item["item_id"] for item in search.json()["items"]] == [item_ids["ap_other"]]

        assert filtered.status_code == 200
        assert [item["item_id"] for item in filtered.json()["items"]] == [item_ids["whitehouse_review"]]

        assert page_two.status_code == 200
        page_two_payload = page_two.json()
        assert page_two_payload["items"][0]["item_id"] == item_ids["whitehouse_review"]
        assert page_two_payload["next_cursor"] == "4"


def test_news_detail_endpoint_returns_full_item_payload() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client, item_ids = _build_seeded_client(Path(temp_dir) / "test_frontend_detail.db")

        response = client.get(f"/api/v1/news/{item_ids['fed_ready']}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["item"]["item_id"] == item_ids["fed_ready"]
        assert payload["item"]["source_id"] == "fed_news"
        assert payload["item"]["analysis_status"] == "ready"
        assert payload["item"]["body_detail_level"] == "detailed"
        assert payload["item"]["source_time_reliability"] == "high"
        assert payload["item"]["why_it_matters_cn"]
        assert payload["item"]["key_numbers"] == []
        assert payload["item"]["fact_table"]
        assert payload["item"]["fact_table"][0]["fact_type"] == "sentence"
        assert payload["item"]["policy_actions"] == [
            "利率路径维持偏紧",
        ]
        assert payload["item"]["market_implications"][0]["direction"] == "银行/保险"
        assert payload["item"]["uncertainties"]
        assert payload["item"]["source_capture_confidence"]["level"] == "high"
        assert payload["item"]["cross_source_confirmation"]["level"] == "single_source"
        assert payload["item"]["cross_source_confirmation"]["confirmed_by_item_ids"] == []
        assert payload["item"]["fact_conflicts"] == []
        assert payload["item"]["event_cluster"]["cluster_status"] == "single_source"
        assert payload["item"]["event_cluster"]["member_item_ids"] == [item_ids["fed_ready"]]
        assert "Federal Reserve News" in payload["item"]["llm_ready_brief"]
        assert payload["item"]["beneficiary_directions"] == [
            "银行/保险",
            "高股息防御",
        ]
        assert payload["item"]["pressured_directions"] == ["高估值成长链"]
        assert payload["item"]["evidence_points"]
        assert payload["item"]["capture_path"] == "direct"
        assert payload["item"]["capture_provider"] is None
        assert payload["item"]["article_fetch_status"] == "not_attempted"
        assert payload["item"]["capture_provenance"] == {
            "capture_path": "direct",
            "is_search_fallback": False,
            "search_provider": None,
            "article_fetch_status": "not_attempted",
        }


def test_news_detail_endpoint_returns_404_for_missing_item() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client, _item_ids = _build_seeded_client(Path(temp_dir) / "test_frontend_missing_detail.db")

        response = client.get("/api/v1/news/999999")

        assert response.status_code == 404
        assert response.json() == {"detail": "News item not found"}


def test_news_and_sources_views_exclude_stale_items_from_current_window() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_stale_window.db")
        repo = OvernightRepository(database)
        fresh_item_id = _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/fresh-policy",
            title="Fresh White House policy update",
            summary="A timely policy update tied to the current overnight window.",
            published_at="2026-04-10T01:00:00+00:00",
            created_at="2026-04-10 09:01:00",
        )
        stale_item_id = _seed_item(
            repo,
            source_id="bis_news_updates",
            url="https://example.com/bis/stale-tariff",
            title="Older BIS tariff notice",
            summary="A stale policy notice captured again today but published far outside the overnight window.",
            published_at="2025-08-19T12:55:00+00:00",
            created_at="2026-04-10 09:05:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        news_response = client.get("/api/v1/news", params={"limit": 10})
        source_response = client.get("/api/v1/sources")

        assert news_response.status_code == 200
        news_payload = news_response.json()
        assert [item["item_id"] for item in news_payload["items"]] == [fresh_item_id]
        assert all(item["item_id"] != stale_item_id for item in news_payload["items"])

        assert source_response.status_code == 200
        source_payload = source_response.json()
        assert source_payload["active_sources"] == 1
        bis_row = next(source for source in source_payload["sources"] if source["source_id"] == "bis_news_updates")
        assert bis_row["item_count"] == 0
        assert bis_row["freshness_status"] == "inactive"


def test_news_endpoint_can_switch_to_full_pool_mode_and_include_stale_items() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_full_pool.db")
        repo = OvernightRepository(database)
        fresh_item_id = _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/fresh-policy",
            title="Fresh White House policy update",
            summary="A timely policy update tied to the current overnight window.",
            published_at="2026-04-10T01:00:00+00:00",
            created_at="2026-04-10 09:01:00",
        )
        stale_item_id = _seed_item(
            repo,
            source_id="bis_news_updates",
            url="https://example.com/bis/stale-tariff",
            title="Older BIS tariff notice",
            summary="A stale policy notice captured again today but published far outside the overnight window.",
            published_at="2025-08-19T12:55:00+00:00",
            created_at="2026-04-10 09:05:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        current_response = client.get("/api/v1/news", params={"limit": 10})
        full_response = client.get("/api/v1/news", params={"limit": 10, "pool_mode": "full"})

        assert current_response.status_code == 200
        current_payload = current_response.json()
        assert current_payload["pool_mode"] == "current"
        assert current_payload["current_window_total"] == 1
        assert current_payload["full_pool_total"] == 2
        assert [item["item_id"] for item in current_payload["items"]] == [fresh_item_id]

        assert full_response.status_code == 200
        full_payload = full_response.json()
        assert full_payload["pool_mode"] == "full"
        assert full_payload["current_window_total"] == 1
        assert full_payload["full_pool_total"] == 2
        assert {item["item_id"] for item in full_payload["items"]} == {fresh_item_id, stale_item_id}
        assert full_payload["filters"]["pool_mode"] == "full"


def test_dashboard_endpoint_diversifies_lead_signals_across_sources() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_diverse_dashboard.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/first",
            title="Federal Reserve says rates may stay restrictive",
            summary=(
                "Federal Reserve officials said inflation remains sticky and rates may stay restrictive "
                "while Treasury yields and liquidity conditions remain in focus."
            ),
            published_at="2026-04-10T02:00:00+00:00",
            created_at="2026-04-10 09:01:00",
        )
        _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/second",
            title="Federal Reserve officials say policy path still depends on inflation",
            summary=(
                "Federal Reserve officials repeated that inflation progress is uneven and the next policy "
                "path still depends on incoming macro data and Treasury yield behavior."
            ),
            published_at="2026-04-10T01:30:00+00:00",
            created_at="2026-04-10 09:02:00",
        )
        _seed_item(
            repo,
            source_id="census_economic_indicators",
            url="https://example.com/census/trade",
            title="Census says wholesale trade and inventories improved",
            summary=(
                "The latest Census release showed wholesale trade and inventories improved, providing an "
                "official macro read on U.S. demand and shipping conditions."
            ),
            published_at="2026-04-10T01:00:00+00:00",
            created_at="2026-04-10 09:03:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        response = client.get("/api/v1/dashboard", params={"bucket_limit": 2})

        assert response.status_code == 200
        payload = response.json()
        assert [item["source_id"] for item in payload["lead_signals"]] == [
            "fed_news",
            "census_economic_indicators",
        ]


def test_sources_endpoint_exposes_configured_sources_with_recent_activity_summary() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client, _item_ids = _build_seeded_client(Path(temp_dir) / "test_frontend_sources.db")

        response = client.get("/api/v1/sources")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_sources"] == len(build_default_source_registry())
        assert payload["active_sources"] == 5
        assert payload["inactive_sources"] == payload["total_sources"] - payload["active_sources"]

        fed_row = next(source for source in payload["sources"] if source["source_id"] == "fed_news")
        assert fed_row["item_count"] == 1
        assert fed_row["ready_count"] == 1
        assert fed_row["latest_analysis_status"] == "ready"
        assert fed_row["latest_title"] == "Federal Reserve says inflation and rates may stay restrictive"
        assert fed_row["source_group"] == "official_policy"
        assert fed_row["content_mode"] == "rates"
        assert fed_row["asset_tags"] == ["rates", "usd", "technology", "equities"]
        assert fed_row["mainline_tags"] == ["rates_liquidity", "macro_data", "tech_semiconductor"]
        assert fed_row["search_discovery_enabled"] is False
        assert fed_row["search_query_count"] == 0

        bls_row = next(source for source in payload["sources"] if source["source_id"] == "bls_news_releases")
        assert bls_row["item_count"] == 0
        assert bls_row["latest_title"] is None
        assert bls_row["search_discovery_enabled"] is True
        assert bls_row["search_query_count"] >= 1


def test_sources_endpoint_exposes_refresh_cooldown_state(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        admin_headers = _admin_headers(monkeypatch)
        database = Database(Path(temp_dir) / "test_frontend_source_cooldown.db")
        repo = OvernightRepository(database)
        source = SourceDefinition(
            source_id="cooldown_source",
            display_name="Cooldown Source",
            organization_type="official_data",
            source_class="macro",
            entry_type="rss",
            entry_urls=("https://example.com/cooldown.xml",),
            priority=90,
            poll_interval_seconds=300,
            is_mission_critical=True,
        )
        http_client = FailingHttpClient()
        now_values = iter(
            [
                datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 10, 1, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 10, 2, 0, tzinfo=timezone.utc),
            ]
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=[source],
            http_client=http_client,
            now_fn=lambda: next(now_values),
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                frontend_api_service=FrontendApiService(
                    repo=repo,
                    capture_service=capture_service,
                    registry=[source],
                ),
            )
        )

        client.post(
            "/refresh",
            params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5},
            headers=admin_headers,
        )
        client.post(
            "/refresh",
            params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5},
            headers=admin_headers,
        )
        client.post(
            "/refresh",
            params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5},
            headers=admin_headers,
        )

        response = client.get("/api/v1/sources")

        assert response.status_code == 200
        payload = response.json()
        row = next(source_row for source_row in payload["sources"] if source_row["source_id"] == "cooldown_source")
        assert row["last_refresh_status"] == "cooldown"
        assert row["operational_status"] == "cooldown"
        assert row["consecutive_failure_count"] == 2
        assert row["cooldown_until"] == "2026-04-10T07:00:00+00:00"
        assert row["last_error"].startswith("403 Client Error")
        assert row["last_candidate_count"] == 0
        assert row["last_persisted_count"] == 0


def test_sources_endpoint_uses_latest_published_item_for_source_summary() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_source_latest.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/older",
            title="Federal Reserve says policy remains restrictive",
            summary=(
                "Federal Reserve officials said inflation and rates remained elevated while markets "
                "waited for the next FOMC decision and Treasury yield path."
            ),
            published_at="2026-04-07T00:30:00+00:00",
            created_at="2026-04-07 09:01:00",
        )
        _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/newer",
            title="Federal Reserve says inflation cooled while rates stay restrictive",
            summary=(
                "Federal Reserve officials said inflation cooled slightly but rates stayed restrictive, "
                "keeping the next FOMC path and Treasury yields in focus."
            ),
            published_at="2026-04-07T02:15:00+00:00",
            created_at="2026-04-07 09:02:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        response = client.get("/api/v1/sources")

        assert response.status_code == 200
        payload = response.json()
        fed_row = next(source for source in payload["sources"] if source["source_id"] == "fed_news")
        assert fed_row["item_count"] == 2
        assert fed_row["latest_title"] == "Federal Reserve says inflation cooled while rates stay restrictive"
        assert fed_row["latest_published_at"] == "2026-04-07T02:15:00+00:00"
        assert fed_row["latest_freshness_bucket"] == "breaking"
        assert fed_row["latest_is_timely"] is True
        assert fed_row["freshness_status"] == "fresh"
        assert fed_row["latest_publication_lag_minutes"] == 407


def test_sources_endpoint_exposes_conflicted_quality_status_for_search_page_time_mismatch() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_source_quality_conflict.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="tradingeconomics_hk",
            url="https://tradingeconomics.com/hong-kong/stock-market/news/491538",
            title="Hong Kong Shares Down for 4th Session",
            summary="Hong Kong shares fell again as China data disappointed.",
            published_at="2026-04-21",
            created_at="2026-04-25 09:37:27",
            source_context={
                "published_at_diagnostics": {
                    "search_published_at": "2026-04-21",
                    "search_published_at_source": "search:published",
                    "page_published_at": "2026-01-05T02:07:09+00:00",
                    "page_published_at_source": "html:jsonld_datePublished",
                    "selected_published_at": "2026-04-21",
                    "selected_published_at_source": "search:published",
                    "published_at_conflict": True,
                }
            },
        )
        repo.upsert_source_refresh_state(
            source_id="tradingeconomics_hk",
            last_status="ok",
            last_error="",
            consecutive_failure_count=0,
            cooldown_until=None,
            last_attempted_at="2026-04-25T09:37:30+00:00",
            last_success_at="2026-04-25T09:37:30+00:00",
            last_candidate_count=3,
            last_selected_candidate_count=3,
            last_persisted_count=3,
            last_published_at_conflict_count=3,
            last_elapsed_seconds=0.0,
        )
        capture_service = OvernightSourceCaptureService(repo=repo, registry=build_default_source_registry())
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        response = client.get("/api/v1/sources")

        assert response.status_code == 200
        payload = response.json()
        row = next(source for source in payload["sources"] if source["source_id"] == "tradingeconomics_hk")
        assert row["latest_published_at_conflict"] is True
        assert row["last_published_at_conflict_count"] == 3
        assert row["quality_status"] == "conflicted"
        assert "时间冲突" in row["quality_note"]


def test_dashboard_endpoint_exposes_market_board_and_ranked_mainlines_when_available() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_dashboard_market_board.db")
        repo = OvernightRepository(database)
        fed_item_id = _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/hawkish-rates",
            title="Federal Reserve says inflation and rates may stay restrictive",
            summary=(
                "Federal Reserve officials said inflation remains elevated, Treasury yields stayed firm, "
                "and rates may need to remain restrictive while markets assess the next FOMC path."
            ),
            published_at="2026-04-07T01:00:00+00:00",
            created_at="2026-04-07 09:01:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        repo.create_daily_analysis_report(
            analysis_date="2026-04-07",
            access_tier="free",
            provider_name="rule_based",
            provider_model="",
            input_item_ids=[fed_item_id],
            report={
                "summary": {"headline": "利率主线偏紧。"},
                "mainlines": [
                    {
                        "mainline_id": "rates_liquidity__2026-04-07",
                        "mainline_bucket": "rates_liquidity",
                        "headline": "利率流动性压力抬升",
                        "importance_rank": 1,
                    }
                ],
                "direction_calls": [],
                "stock_calls": [],
                "risk_watchpoints": [],
                "supporting_items": [],
            },
        )
        snapshot_service = FakeMarketSnapshotService(
            {
                "analysis_date": "2026-04-07",
                "asset_board": {
                    "headline": "纳指领涨，收益率回落。",
                    "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 3.0}],
                    "sectors": [{"symbol": "XLK", "display_name": "科技板块", "change_pct": 5.0}],
                    "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -4.5}],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                    "china_mapped_futures": [],
                },
            }
        )
        frontend_api_service = FrontendApiService(
            repo=repo,
            capture_service=capture_service,
            registry=build_default_source_registry(),
            market_snapshot_service=snapshot_service,
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                frontend_api_service=frontend_api_service,
                market_snapshot_service=snapshot_service,
            )
        )

        response = client.get("/api/v1/dashboard")

        assert response.status_code == 200
        payload = response.json()
        assert payload["market_board"]["headline"] == "纳指领涨，收益率回落。"
        assert payload["mainlines"] == [
            {
                "mainline_id": "rates_liquidity__2026-04-07",
                "mainline_bucket": "rates_liquidity",
                "headline": "利率流动性压力抬升",
                "importance_rank": 1,
            }
        ]


def test_dashboard_endpoint_exposes_market_regimes_and_secondary_event_groups() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_frontend_dashboard_regimes.db")
        repo = OvernightRepository(database)
        fed_item_id = _seed_item(
            repo,
            source_id="fed_news",
            url="https://example.com/fed/dovish-shift",
            title="Federal Reserve says data softened and yields eased",
            summary="Treasury yields eased while technology shares outperformed into the close.",
            published_at="2026-04-10T01:00:00+00:00",
            created_at="2026-04-10 09:01:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        repo.create_daily_analysis_report(
            analysis_date="2026-04-10",
            access_tier="free",
            provider_name="rule_based",
            provider_model="",
            input_item_ids=[fed_item_id],
            report={
                "summary": {"headline": "科技主线偏强。"},
                "mainlines": [
                    {
                        "mainline_id": "tech_semiconductor__2026-04-10",
                        "mainline_bucket": "tech_semiconductor",
                        "headline": "科技/半导体主线走强",
                        "importance_rank": 1,
                    }
                ],
                "market_regimes": [
                    {
                        "regime_id": "2026-04-10__technology_risk_on",
                        "regime_key": "technology_risk_on",
                        "confidence": "high",
                        "strength": 2.4,
                    }
                ],
                "secondary_event_groups": [
                    {
                        "cluster_id": "trade_policy__steel__41",
                        "headline": "White House updates tariff language",
                        "downgrade_reason": "no_regime_match",
                    }
                ],
                "direction_calls": [],
                "stock_calls": [],
                "risk_watchpoints": [],
                "supporting_items": [],
            },
        )
        snapshot_service = FakeMarketSnapshotService(
            {
                "analysis_date": "2026-04-10",
                "asset_board": {
                    "headline": "纳指上涨，半导体领涨。",
                    "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.1}],
                    "sectors": [{"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 4.0}],
                    "rates_fx": [],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                    "china_mapped_futures": [],
                },
            }
        )
        frontend_api_service = FrontendApiService(
            repo=repo,
            capture_service=capture_service,
            registry=build_default_source_registry(),
            market_snapshot_service=snapshot_service,
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                frontend_api_service=frontend_api_service,
                market_snapshot_service=snapshot_service,
            )
        )

        response = client.get("/api/v1/dashboard")

        assert response.status_code == 200
        payload = response.json()
        assert payload["market_regimes"][0]["regime_key"] == "technology_risk_on"
        assert payload["secondary_event_groups"][0]["cluster_id"] == "trade_policy__steel__41"
        assert payload["mainlines"][0]["mainline_id"] == "tech_semiconductor__2026-04-10"
