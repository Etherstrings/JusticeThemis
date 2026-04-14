# -*- coding: utf-8 -*-
"""Fixture-backed end-to-end regression for regime-grounded pipeline outputs."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

from app.db import Database
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.daily_analysis import DailyAnalysisService
from app.services.handoff import HandoffService
from app.services.mmu_handoff import MMUHandoffService
from app.services.source_capture import OvernightSourceCaptureService
from app.services.ticker_enrichment import TickerEnrichmentService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate


class StaticMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot

    def get_daily_snapshot(self, *, analysis_date: str | None = None):
        return self.snapshot


class FakeTickerEnrichmentProvider:
    name = "Fake Enrichment"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def is_configured(self) -> bool:
        return True

    def supports_symbol(self, symbol: str) -> bool:
        return symbol in {"SOXX", "XLK"}

    def fetch_symbol_context(self, *, symbol: str) -> dict[str, object]:
        self.calls.append(symbol)
        return {
            "profile": {"symbol": symbol, "name": f"Name {symbol}"},
            "quote": {"symbol": symbol, "price": 100.0},
        }


def _seed_item(
    repo: OvernightRepository,
    *,
    source_id: str,
    url: str,
    title: str,
    summary: str,
    published_at: str,
    created_at: str,
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


def test_regime_grounded_pipeline_path_produces_reports_and_mmu_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "test_pipeline_regression.db"))
        _seed_item(
            repo,
            source_id="bis_news_updates",
            url="https://example.com/bis/tech",
            title="BIS updates semiconductor guidance",
            summary="Semiconductor controls tighten while technology assets outperform overnight.",
            published_at="2026-04-10T00:10:00+00:00",
            created_at="2026-04-10 08:15:00",
        )
        _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/trade",
            title="White House updates tariff language",
            summary="Trade language changed, but the move lacks direct cross-asset confirmation.",
            published_at="2026-04-10T00:30:00+00:00",
            created_at="2026-04-10 08:35:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        market_snapshot_service = StaticMarketSnapshotService(
            {
                "analysis_date": "2026-04-10",
                "market_regimes": [
                    {
                        "regime_id": "2026-04-10__technology_risk_on",
                        "regime_key": "technology_risk_on",
                        "triggered": True,
                        "direction": "bullish",
                        "strength": 2.4,
                        "confidence": "high",
                        "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                        "supporting_observations": [],
                        "suppressed_by": [],
                    }
                ],
                "market_regime_evaluations": [
                    {
                        "regime_id": "2026-04-10__technology_risk_on",
                        "regime_key": "technology_risk_on",
                        "triggered": True,
                        "direction": "bullish",
                        "strength": 2.4,
                        "confidence": "high",
                        "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                        "supporting_observations": [],
                        "suppressed_by": [],
                    }
                ],
                "asset_board": {
                    "analysis_date": "2026-04-10",
                    "headline": "纳指与半导体领涨，收益率回落。",
                    "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.2}],
                    "sectors": [
                        {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 4.3},
                        {"symbol": "XLK", "display_name": "科技板块", "change_pct": 3.1},
                    ],
                    "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -2.0}],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                },
            }
        )
        enrichment_service = TickerEnrichmentService(
            repo=repo,
            providers=[FakeTickerEnrichmentProvider()],
        )
        daily_analysis_service = DailyAnalysisService(
            repo=repo,
            capture_service=capture_service,
            market_snapshot_service=market_snapshot_service,
            ticker_enrichment_service=enrichment_service,
        )
        handoff_service = HandoffService(
            capture_service=capture_service,
            market_snapshot_service=market_snapshot_service,
        )
        mmu_service = MMUHandoffService()

        reports = daily_analysis_service.generate_daily_reports(analysis_date="2026-04-10")
        premium_report = next(report for report in reports["reports"] if report["access_tier"] == "premium")
        handoff = handoff_service.get_handoff(limit=20, analysis_date="2026-04-10")
        bundle = mmu_service.build_bundle(
            handoff=handoff,
            analysis_report=premium_report,
            access_tier="premium",
        )
        secondary_cluster_id = premium_report["secondary_event_groups"][0]["cluster_id"]

        assert premium_report["market_regimes"][0]["regime_key"] == "technology_risk_on"
        assert premium_report["mainlines"][0]["regime_ids"] == ["2026-04-10__technology_risk_on"]
        assert secondary_cluster_id
        assert premium_report["ticker_enrichments"]
        assert handoff["mainlines"][0]["regime_ids"] == ["2026-04-10__technology_risk_on"]
        assert handoff["secondary_event_groups"][0]["cluster_id"] == secondary_cluster_id
        assert bundle["market_regimes"][0]["regime_key"] == "technology_risk_on"
        assert bundle["premium_recommendation"]["ticker_enrichments"][0]["symbol"] == "SOXX"
