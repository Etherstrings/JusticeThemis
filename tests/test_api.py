from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from app.repository import OvernightRepository
from app.services.search_discovery import SearchDiscoveryResult, SearchDiscoveryService
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.types import SourceDefinition
from app.sources.registry import build_default_source_registry


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class RoutingFixtureClient:
    def __init__(self, routes: dict[str, Path]):
        self.routes = routes

    def fetch(self, url: str) -> str:
        for fragment, fixture_path in self.routes.items():
            if fragment in url:
                return fixture_path.read_text(encoding="utf-8")
        raise AssertionError(f"No fixture mapped for url: {url}")


class StaticSearchProvider:
    def __init__(self, name: str, results: list[SearchDiscoveryResult]) -> None:
        self.name = name
        self.results = results
        self.is_available = True

    def search(self, *, query: str, max_results: int, days: int = 7):
        return self.results[:max_results]


class FakeMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object] | None) -> None:
        self.snapshot = snapshot

    def get_daily_snapshot(self, *, analysis_date: str | None = None):
        return self.snapshot

    def get_external_signals(self, *, analysis_date: str | None = None):
        if self.snapshot is None:
            return None
        return {
            "analysis_date": self.snapshot.get("analysis_date"),
            "market_date": self.snapshot.get("market_date"),
            "external_market_signals": self.snapshot.get("external_market_signals"),
            "prediction_markets": self.snapshot.get("prediction_markets"),
            "kalshi_signals": self.snapshot.get("kalshi_signals"),
            "fedwatch_signals": self.snapshot.get("fedwatch_signals"),
            "cftc_signals": self.snapshot.get("cftc_signals"),
        }


class FakeAnalysisDateAwareHandoffService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_handoff(self, *, limit: int = 20, analysis_date: str | None = None, include_stale: bool = False):
        self.calls.append({"limit": limit, "analysis_date": analysis_date, "include_stale": include_stale})
        return {
            "analysis_date": analysis_date or "latest",
            "market_snapshot": {"analysis_date": analysis_date or "latest", "asset_board": {}},
            "items": [],
            "event_groups": [],
            "mainlines": [],
        }


class FakeAnalysisDateAwareDailyAnalysisService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_daily_report(self, *, analysis_date: str | None = None, access_tier: str = "free", version: int | None = None):
        self.calls.append({"analysis_date": analysis_date, "access_tier": access_tier, "version": version})
        return {"analysis_date": analysis_date or "latest", "access_tier": access_tier}


class FakePremiumAwareMMUService:
    def build_bundle(self, *, handoff, analysis_report=None, item_limit: int = 8, access_tier: str = "free"):
        return {
            "handoff_analysis_date": handoff.get("analysis_date"),
            "report_analysis_date": analysis_report.get("analysis_date") if isinstance(analysis_report, dict) else None,
            "report_access_tier": analysis_report.get("access_tier") if isinstance(analysis_report, dict) else None,
            "access_tier": access_tier,
            "item_limit": item_limit,
        }


class FakePassThroughMMUService:
    def build_bundle(self, *, handoff, analysis_report=None, item_limit: int = 8, access_tier: str = "free"):
        return {
            "handoff_analysis_date": handoff.get("analysis_date"),
            "report_analysis_date": analysis_report.get("analysis_date") if isinstance(analysis_report, dict) else None,
            "access_tier": access_tier,
            "item_limit": item_limit,
        }


class FakeRefreshCaptureService:
    def __init__(self) -> None:
        self.calls: list[dict[str, int]] = []

    def refresh(self, *, limit_per_source: int = 2, max_sources: int = 6, recent_limit: int = 12):
        self.calls.append(
            {
                "limit_per_source": limit_per_source,
                "max_sources": max_sources,
                "recent_limit": recent_limit,
            }
        )
        return {
            "collected_sources": max_sources,
            "collected_items": limit_per_source * max_sources,
            "total": recent_limit,
            "items": [],
        }

    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None):
        return {"total": 0, "items": []}

    def render_recent_item_row(self, row):
        return row


def test_items_endpoint_returns_empty_payload_initially() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_empty.db")
        client = TestClient(create_app(database=database))

        response = client.get("/items")

        assert response.status_code == 200
        assert response.json() == {
            "total": 0,
            "items": [],
        }


def test_refresh_endpoint_defaults_to_production_capture_budget(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        database = Database(Path(temp_dir) / "test_api_refresh_defaults.db")
        capture_service = FakeRefreshCaptureService()
        client = TestClient(create_app(database=database, capture_service=capture_service))

        response = client.post("/refresh")

        assert response.status_code == 200
        assert capture_service.calls == [
            {
                "limit_per_source": 6,
                "max_sources": 26,
                "recent_limit": 120,
            }
        ]


def test_refresh_endpoint_requires_admin_key_when_unsafe_mode_disabled(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
        monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
        database = Database(Path(temp_dir) / "test_api_refresh_admin.db")
        capture_service = FakeRefreshCaptureService()
        client = TestClient(create_app(database=database, capture_service=capture_service))

        response = client.post("/refresh")

        assert response.status_code == 403
        assert response.json() == {"detail": "Admin access key required"}
        assert capture_service.calls == []


def test_refresh_endpoint_accepts_admin_key(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
        monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
        database = Database(Path(temp_dir) / "test_api_refresh_admin_ok.db")
        capture_service = FakeRefreshCaptureService()
        client = TestClient(create_app(database=database, capture_service=capture_service))

        response = client.post("/refresh", headers={"X-Admin-Access-Key": "secret-admin"})

        assert response.status_code == 200
        assert len(capture_service.calls) == 1


def test_healthz_is_public_and_minimal() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_healthz.db")
        client = TestClient(create_app(database=database))

        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "JusticeThemis",
        }


def test_documented_frontend_dev_origin_can_call_backend_api() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_frontend_cors.db")
        client = TestClient(create_app(database=database))

        response = client.options(
            "/api/v1/news",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_alternate_local_frontend_dev_port_is_allowed_for_preview_fallback() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_frontend_cors_fallback.db")
        client = TestClient(create_app(database=database))

        response = client.options(
            "/api/v1/news",
            headers={
                "Origin": "http://127.0.0.1:5175",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5175"


def test_external_market_signals_endpoint_returns_signal_layer_only() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_external_signals.db")
        client = TestClient(
            create_app(
                database=database,
                market_snapshot_service=FakeMarketSnapshotService(
                    {
                        "analysis_date": "2026-04-22",
                        "market_date": "2026-04-21",
                        "external_market_signals": {"ready_provider_count": 3, "provider_count": 4},
                        "prediction_markets": {"status": "ready"},
                        "kalshi_signals": {"status": "ready"},
                        "fedwatch_signals": {"status": "source_restricted"},
                        "cftc_signals": {"status": "ready"},
                    }
                ),
            )
        )

        response = client.get("/api/v1/market/external-signals/daily", params={"analysis_date": "2026-04-22"})

        assert response.status_code == 200
        assert response.json() == {
            "analysis_date": "2026-04-22",
            "market_date": "2026-04-21",
            "external_market_signals": {"ready_provider_count": 3, "provider_count": 4},
            "prediction_markets": {"status": "ready"},
            "kalshi_signals": {"status": "ready"},
            "fedwatch_signals": {"status": "source_restricted"},
            "cftc_signals": {"status": "ready"},
        }


def test_readyz_requires_admin_key_when_unsafe_mode_disabled(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
        monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
        database = Database(Path(temp_dir) / "test_api_readyz_protected.db")
        client = TestClient(create_app(database=database))

        response = client.get("/readyz")

        assert response.status_code == 403
        assert response.json() == {"detail": "Admin access key required"}


def test_readyz_reports_sanitized_runtime_state_and_unsafe_mode(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.delenv("OVERNIGHT_ADMIN_API_KEY", raising=False)
        monkeypatch.delenv("OVERNIGHT_PREMIUM_API_KEY", raising=False)
        monkeypatch.delenv("IFIND_REFRESH_TOKEN", raising=False)
        monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
        monkeypatch.delenv("BOCHA_API_KEYS", raising=False)
        monkeypatch.delenv("BOCHA_API_KEY", raising=False)
        monkeypatch.delenv("SERPAPI_API_KEYS", raising=False)
        monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEYS", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_API_KEYS", raising=False)
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        database = Database(Path(temp_dir) / "test_api_readyz_unsafe.db")
        client = TestClient(create_app(database=database))

        response = client.get("/readyz")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "JusticeThemis"
        assert payload["auth"] == {
            "premium_configured": False,
            "admin_configured": False,
            "unsafe_admin_mode": True,
        }
        assert payload["features"]["market_snapshot"]["ifind_configured"] is False
        assert payload["features"]["search_discovery"]["provider_count"] == 0
        assert "OVERNIGHT_ADMIN_API_KEY" not in str(payload)


def test_readyz_reports_ticker_enrichment_configuration(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "alpha-test-key")
        database = Database(Path(temp_dir) / "test_api_readyz_enrichment.db")
        client = TestClient(create_app(database=database))

        response = client.get("/readyz")

        assert response.status_code == 200
        payload = response.json()
        assert payload["features"]["ticker_enrichment"]["available"] is True
        assert payload["features"]["ticker_enrichment"]["provider_count"] == 1
        assert payload["features"]["ticker_enrichment"]["configured_env_names"] == ["ALPHA_VANTAGE_API_KEY"]


def test_refresh_and_handoff_endpoints_expose_captured_news_with_source_metadata(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        database = Database(Path(temp_dir) / "test_api_refresh.db")
        repo = OvernightRepository(database)
        http_client = RoutingFixtureClient(
            {
                "whitehouse.gov/news/": FIXTURE_DIR / "whitehouse_news.html",
                "whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html",
            }
        )
        registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=registry,
            http_client=http_client,
        )
        client = TestClient(create_app(database=database, capture_service=capture_service))

        refresh_response = client.post("/refresh", params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5})
        items_response = client.get("/items?limit=5&include_stale=true")
        handoff_response = client.get("/handoff?limit=5&include_stale=true")

        assert refresh_response.status_code == 200
        assert refresh_response.json()["collected_items"] == 1

        assert items_response.status_code == 200
        items_payload = items_response.json()
        assert items_payload["total"] == 1
        assert items_payload["items"][0]["source_id"] == "whitehouse_news"
        assert items_payload["items"][0]["source_name"] == "White House News"
        assert items_payload["items"][0]["canonical_url"].startswith("https://www.whitehouse.gov/briefing-room/")
        assert items_payload["items"][0]["excerpt_source"] == "body_selector:main"
        assert items_payload["items"][0]["excerpt_char_count"] == len(items_payload["items"][0]["summary"])
        assert items_payload["items"][0]["published_at_source"] == "section:time"
        assert items_payload["items"][0]["summary_quality"] == "high"
        assert items_payload["items"][0]["a_share_relevance"] == "medium"
        assert "官方政策源" in items_payload["items"][0]["a_share_relevance_reason"]
        assert items_payload["items"][0]["impact_summary"]
        assert items_payload["items"][0]["beneficiary_directions"] == []
        assert items_payload["items"][0]["follow_up_checks"]
        assert items_payload["items"][0]["analysis_status"] == "review"
        assert items_payload["items"][0]["analysis_confidence"] == "medium"
        assert "missing_direct_market_mapping" in items_payload["items"][0]["analysis_blockers"]
        assert items_payload["items"][0]["evidence_points"]

        assert handoff_response.status_code == 200
        handoff_payload = handoff_response.json()
        assert handoff_payload["total"] == 1
        assert handoff_payload["items"][0]["source_id"] == "whitehouse_news"
        assert handoff_payload["items"][0]["excerpt_source"] == "body_selector:main"
        assert handoff_payload["items"][0]["summary_quality"] == "high"
        assert handoff_payload["items"][0]["a_share_relevance"] == "medium"
        assert handoff_payload["items"][0]["impact_summary"]
        assert handoff_payload["items"][0]["analysis_status"] == "review"
        assert handoff_payload["items"][0]["evidence_points"]
        assert "官方源优先" in handoff_payload["prompt_scaffold"]


def test_mmu_handoff_endpoint_returns_staged_payload_bundle(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        database = Database(Path(temp_dir) / "test_api_mmu_handoff.db")
        repo = OvernightRepository(database)
        http_client = RoutingFixtureClient(
            {
                "whitehouse.gov/news/": FIXTURE_DIR / "whitehouse_news.html",
                "whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html",
            }
        )
        registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=registry,
            http_client=http_client,
        )
        snapshot_service = FakeMarketSnapshotService(
            {
                "analysis_date": "2026-04-04",
                "asset_board": {
                    "headline": "收益率回落，科技板块偏强。",
                    "indexes": [],
                    "sectors": [{"symbol": "XLK", "display_name": "科技板块", "change_pct": 3.5}],
                    "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -2.5}],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                    "china_mapped_futures": [],
                },
            }
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                market_snapshot_service=snapshot_service,
            )
        )

        client.post("/refresh", params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5})
        response = client.get("/api/v1/mmu/handoff", params={"limit": 3, "include_stale": True})

        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_date"] == "2026-04-04"
        assert payload["single_item_understanding"][0]["handoff_type"] == "single_item_understanding"
        assert payload["event_consolidation"][0]["handoff_type"] == "event_consolidation"
        assert payload["market_attribution"]["handoff_type"] == "market_attribution"
        assert payload["premium_recommendation"]["handoff_type"] == "premium_recommendation"


def test_pipeline_blueprint_endpoint_returns_flow_description() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_blueprint.db")
        client = TestClient(create_app(database=database))

        response = client.get("/api/v1/pipeline/blueprint")

        assert response.status_code == 200
        payload = response.json()
        assert payload["product_name"] == "JusticeThemis"
        assert payload["pipeline_name"] == "justice_themis"
        assert payload["run_window"]["timezone"] == "Asia/Shanghai"
        assert any(lane["lane_id"] == "official_policy" for lane in payload["source_lanes"])
        assert any(endpoint["path"] == "/api/v1/mmu/handoff" for endpoint in payload["entrypoints"]["api"])


def test_mmu_handoff_endpoint_forwards_analysis_date_to_handoff_service() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_api_mmu_analysis_date.db")
        handoff_service = FakeAnalysisDateAwareHandoffService()
        daily_analysis_service = FakeAnalysisDateAwareDailyAnalysisService()
        client = TestClient(
            create_app(
                database=database,
                handoff_service=handoff_service,
                daily_analysis_service=daily_analysis_service,
                mmu_handoff_service=FakePassThroughMMUService(),
            )
        )

        response = client.get("/api/v1/mmu/handoff", params={"limit": 3, "analysis_date": "2026-04-09"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["handoff_analysis_date"] == "2026-04-09"
        assert payload["report_analysis_date"] == "2026-04-09"
        assert handoff_service.calls == [{"limit": 20, "analysis_date": "2026-04-09", "include_stale": False}]


def test_mmu_handoff_endpoint_premium_tier_requires_key_and_uses_premium_report(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        database = Database(Path(temp_dir) / "test_api_mmu_premium.db")
        handoff_service = FakeAnalysisDateAwareHandoffService()
        daily_analysis_service = FakeAnalysisDateAwareDailyAnalysisService()
        client = TestClient(
            create_app(
                database=database,
                handoff_service=handoff_service,
                daily_analysis_service=daily_analysis_service,
                mmu_handoff_service=FakePremiumAwareMMUService(),
            )
        )

        denied = client.get("/api/v1/mmu/handoff", params={"tier": "premium", "analysis_date": "2026-04-09"})
        allowed = client.get(
            "/api/v1/mmu/handoff",
            params={"tier": "premium", "analysis_date": "2026-04-09"},
            headers={"X-Premium-Access-Key": "secret-premium"},
        )

        assert denied.status_code == 403
        assert denied.json() == {"detail": "Premium access key required"}
        assert allowed.status_code == 200
        payload = allowed.json()
        assert payload["access_tier"] == "premium"
        assert payload["report_access_tier"] == "premium"


def test_refresh_endpoint_uses_search_discovery_when_primary_source_yields_no_candidates(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", "true")
        database = Database(Path(temp_dir) / "test_api_search_discovery.db")
        repo = OvernightRepository(database)
        http_client = RoutingFixtureClient(
            {
                "state.gov/briefings-statements/": FIXTURE_DIR / "empty_page.html",
                "state.gov/briefings-statements/sample-release": FIXTURE_DIR / "state_article.html",
            }
        )
        registry = [
            SourceDefinition(
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
        ]
        search_service = SearchDiscoveryService(
            providers=(
                StaticSearchProvider(
                    "Tavily",
                    [
                        SearchDiscoveryResult(
                            title="State Department Statement",
                            snippet="Detailed policy statement sourced through discovery.",
                            url="https://www.state.gov/briefings-statements/sample-release",
                            published_at="2026-04-09",
                        )
                    ],
                ),
            )
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=registry,
            http_client=http_client,
            search_discovery_service=search_service,
        )
        client = TestClient(create_app(database=database, repo=repo, capture_service=capture_service))

        refresh_response = client.post("/refresh", params={"limit_per_source": 1, "max_sources": 1, "recent_limit": 5})

        assert refresh_response.status_code == 200
        payload = refresh_response.json()
        assert payload["collected_items"] == 1
        assert payload["items"][0]["source_id"] == "state_briefings"
        assert payload["items"][0]["canonical_url"] == "https://www.state.gov/briefings-statements/sample-release"
        assert payload["items"][0]["summary"]
        assert payload["items"][0]["capture_path"] == "search_discovery"
        assert payload["items"][0]["capture_provider"] == "tavily"
        assert payload["items"][0]["article_fetch_status"] == "expanded"
        assert payload["items"][0]["capture_provenance"] == {
            "capture_path": "search_discovery",
            "is_search_fallback": True,
            "search_provider": "tavily",
            "article_fetch_status": "expanded",
        }
