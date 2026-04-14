from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api_access import build_readiness_report, require_admin_access, require_premium_access
from app.db import Database
from app.product_identity import PRODUCT_NAME
from app.repository import OvernightRepository
from app.runtime_config import load_runtime_environment
from app.runtime_defaults import (
    DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
    DEFAULT_CAPTURE_MAX_SOURCES,
    DEFAULT_CAPTURE_RECENT_LIMIT,
)
from app.services.daily_analysis import DailyAnalysisService
from app.services.current_window import filter_current_window_items
from app.services.frontend_api import FrontendApiService
from app.services.handoff import HandoffService
from app.services.market_snapshot import UsMarketSnapshotService
from app.services.mmu_handoff import MMUHandoffService
from app.services.pipeline_blueprint import PipelineBlueprintService
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry

UI_DIR = Path(__file__).parent / "ui"

def create_app(
    *,
    database: Database | None = None,
    repo: OvernightRepository | None = None,
    capture_service: OvernightSourceCaptureService | None = None,
    handoff_service: HandoffService | None = None,
    frontend_api_service: FrontendApiService | None = None,
    daily_analysis_service: DailyAnalysisService | None = None,
    market_snapshot_service: UsMarketSnapshotService | None = None,
    mmu_handoff_service: MMUHandoffService | None = None,
    pipeline_blueprint_service: PipelineBlueprintService | None = None,
) -> FastAPI:
    load_runtime_environment()
    database = database or Database()
    repo = repo or OvernightRepository(database)
    registry = build_default_source_registry()
    capture_service = capture_service or OvernightSourceCaptureService(
        repo=repo,
        registry=registry,
    )
    market_snapshot_service = market_snapshot_service or UsMarketSnapshotService(repo=repo)
    handoff_service = handoff_service or HandoffService(
        capture_service=capture_service,
        market_snapshot_service=market_snapshot_service,
    )
    presentation_capture_service = OvernightSourceCaptureService(
        repo=repo,
        registry=registry,
    )
    frontend_api_service = frontend_api_service or FrontendApiService(
        repo=repo,
        capture_service=presentation_capture_service,
        registry=registry,
        market_snapshot_service=market_snapshot_service,
    )
    daily_analysis_service = daily_analysis_service or DailyAnalysisService(
        repo=repo,
        capture_service=presentation_capture_service,
        market_snapshot_service=market_snapshot_service,
    )
    mmu_handoff_service = mmu_handoff_service or MMUHandoffService()
    pipeline_blueprint_service = pipeline_blueprint_service or PipelineBlueprintService(
        registry=build_default_source_registry(include_disabled=True),
    )

    app = FastAPI(title=PRODUCT_NAME)
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": PRODUCT_NAME,
        }

    @app.get("/readyz")
    def readyz(
        x_admin_access_key: str | None = Header(default=None, alias="X-Admin-Access-Key"),
    ) -> dict[str, object]:
        require_admin_access(x_admin_access_key)
        return build_readiness_report(database=database, registry=build_default_source_registry(include_disabled=True))

    @app.get("/items")
    def list_items(limit: int = 20, include_stale: bool = False) -> dict[str, object]:
        payload = capture_service.list_recent_items(limit=max(30, max(1, int(limit)) * 3))
        items = list(payload.get("items", []) or [])
        if not include_stale:
            items = filter_current_window_items(items)
        items = items[: max(1, int(limit))]
        return {
            "total": len(items),
            "items": items,
        }

    @app.post("/refresh")
    def refresh(
        limit_per_source: int = DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
        max_sources: int = DEFAULT_CAPTURE_MAX_SOURCES,
        recent_limit: int = DEFAULT_CAPTURE_RECENT_LIMIT,
        x_admin_access_key: str | None = Header(default=None, alias="X-Admin-Access-Key"),
    ) -> dict[str, object]:
        require_admin_access(x_admin_access_key)
        return capture_service.refresh(
            limit_per_source=limit_per_source,
            max_sources=max_sources,
            recent_limit=recent_limit,
        )

    @app.get("/handoff")
    def get_handoff(limit: int = 20, include_stale: bool = False) -> dict[str, object]:
        return handoff_service.get_handoff(limit=limit, include_stale=include_stale)

    @app.get("/api/v1/dashboard")
    def get_dashboard(bucket_limit: int = 5) -> dict[str, object]:
        return frontend_api_service.get_dashboard(bucket_limit=bucket_limit)

    @app.get("/api/v1/pipeline/blueprint")
    def get_pipeline_blueprint(
        max_sources: int = DEFAULT_CAPTURE_MAX_SOURCES,
        limit_per_source: int = DEFAULT_CAPTURE_LIMIT_PER_SOURCE,
        recent_limit: int = DEFAULT_CAPTURE_RECENT_LIMIT,
    ) -> dict[str, object]:
        return pipeline_blueprint_service.build(
            max_sources=max(1, int(max_sources)),
            limit_per_source=max(1, int(limit_per_source)),
            recent_limit=max(1, int(recent_limit)),
        )

    @app.get("/api/v1/news")
    def list_frontend_news(
        tab: str = "all",
        analysis_status: str | None = None,
        coverage_tier: str | None = None,
        source_id: str | None = None,
        q: str | None = None,
        pool_mode: str = "current",
        limit: int = 20,
        cursor: int = 0,
    ) -> dict[str, object]:
        return frontend_api_service.list_news(
            tab=tab,
            analysis_status=analysis_status,
            coverage_tier=coverage_tier,
            source_id=source_id,
            q=q,
            pool_mode=pool_mode,
            limit=limit,
            cursor=cursor,
        )

    @app.get("/api/v1/news/{item_id}")
    def get_frontend_news_item(item_id: int) -> dict[str, object]:
        payload = frontend_api_service.get_news_item(item_id=item_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="News item not found")
        return payload

    @app.get("/api/v1/sources")
    def list_frontend_sources() -> dict[str, object]:
        return frontend_api_service.list_sources()

    @app.post("/api/v1/market/us/refresh")
    def refresh_us_market_snapshot(
        x_admin_access_key: str | None = Header(default=None, alias="X-Admin-Access-Key"),
    ) -> dict[str, object]:
        require_admin_access(x_admin_access_key)
        return market_snapshot_service.refresh_us_close_snapshot()

    @app.get("/api/v1/market/us/daily")
    def get_us_market_snapshot(analysis_date: str | None = None) -> dict[str, object]:
        payload = market_snapshot_service.get_daily_snapshot(analysis_date=analysis_date)
        if payload is None:
            raise HTTPException(status_code=404, detail="U.S. market snapshot not found")
        return payload

    @app.post("/api/v1/analysis/daily/generate")
    def generate_daily_analysis(
        analysis_date: str | None = None,
        x_admin_access_key: str | None = Header(default=None, alias="X-Admin-Access-Key"),
    ) -> dict[str, object]:
        require_admin_access(x_admin_access_key)
        return daily_analysis_service.generate_daily_reports(analysis_date=analysis_date)

    @app.get("/api/v1/analysis/daily")
    def get_daily_analysis(
        analysis_date: str | None = None,
        tier: str = "free",
        version: int | None = None,
        x_premium_access_key: str | None = Header(default=None, alias="X-Premium-Access-Key"),
    ) -> dict[str, object]:
        normalized_tier = tier.strip() or "free"
        if normalized_tier == "premium":
            require_premium_access(x_premium_access_key)

        payload = daily_analysis_service.get_daily_report(
            analysis_date=analysis_date,
            access_tier=normalized_tier,
            version=version,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Daily analysis not found")
        return payload

    @app.get("/api/v1/analysis/daily/versions")
    def list_daily_analysis_versions(
        analysis_date: str | None = None,
        tier: str = "free",
        x_premium_access_key: str | None = Header(default=None, alias="X-Premium-Access-Key"),
    ) -> dict[str, object]:
        normalized_tier = tier.strip() or "free"
        if normalized_tier == "premium":
            require_premium_access(x_premium_access_key)

        payload = daily_analysis_service.list_report_versions(
            analysis_date=analysis_date,
            access_tier=normalized_tier,
        )
        if not payload["versions"]:
            raise HTTPException(status_code=404, detail="Daily analysis not found")
        return payload

    @app.get("/api/v1/analysis/daily/prompt")
    def get_daily_analysis_prompt(
        analysis_date: str | None = None,
        tier: str = "free",
        version: int | None = None,
        x_premium_access_key: str | None = Header(default=None, alias="X-Premium-Access-Key"),
    ) -> dict[str, object]:
        normalized_tier = tier.strip() or "free"
        if normalized_tier == "premium":
            require_premium_access(x_premium_access_key)

        payload = daily_analysis_service.get_prompt_bundle(
            analysis_date=analysis_date,
            access_tier=normalized_tier,
            version=version,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Daily analysis not found")
        return payload

    @app.get("/api/v1/mmu/handoff")
    def get_mmu_handoff(
        limit: int = 8,
        analysis_date: str | None = None,
        tier: str = "free",
        include_stale: bool = False,
        x_premium_access_key: str | None = Header(default=None, alias="X-Premium-Access-Key"),
    ) -> dict[str, object]:
        normalized_tier = tier.strip() or "free"
        if normalized_tier == "premium":
            require_premium_access(x_premium_access_key)
        handoff_payload = handoff_service.get_handoff(
            limit=max(20, limit),
            analysis_date=analysis_date,
            include_stale=include_stale,
        )
        analysis_report = daily_analysis_service.get_daily_report(
            analysis_date=analysis_date,
            access_tier=normalized_tier,
        )
        if normalized_tier == "premium" and analysis_report is None:
            raise HTTPException(status_code=404, detail="Daily analysis not found")
        return mmu_handoff_service.build_bundle(
            handoff=handoff_payload,
            analysis_report=analysis_report,
            item_limit=limit,
            access_tier=normalized_tier,
        )

    return app


app = create_app()
