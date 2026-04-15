# -*- coding: utf-8 -*-
"""Tests for fixed daily analysis generation and retrieval."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.daily_analysis_provider import RuleBasedDailyAnalysisProvider
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate


class StaticMarketSnapshotService:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot

    def get_daily_snapshot(self, *, analysis_date: str | None = None):
        return self.snapshot


class RecordingTickerEnrichmentService:
    def __init__(self, records: list[dict[str, object]] | None = None) -> None:
        self.records = list(records or [])
        self.calls: list[dict[str, object]] = []

    def collect(
        self,
        *,
        analysis_date: str,
        session_name: str,
        access_tier: str,
        mainlines: list[dict[str, object]],
        market_regimes: list[dict[str, object]],
        stock_calls: list[dict[str, object]],
        explicit_symbols: list[str] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "analysis_date": analysis_date,
                "session_name": session_name,
                "access_tier": access_tier,
                "mainlines": mainlines,
                "market_regimes": market_regimes,
                "stock_calls": stock_calls,
                "explicit_symbols": list(explicit_symbols or []),
            }
        )
        return {
            "status": "ok",
            "records": list(self.records),
            "attempted_symbol_count": len({str(record.get("symbol", "")).strip() for record in self.records}),
            "error_count": 0,
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


def _build_analysis_client(database_path: Path) -> TestClient:
    database = Database(database_path)
    repo = OvernightRepository(database)
    _seed_item(
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
    _seed_item(
        repo,
        source_id="census_economic_indicators",
        url="https://example.com/census/trade-exports",
        title="U.S. trade data shows exports rose 12% as imports stabilized",
        summary=(
            "The latest Census release showed trade conditions improved as exports rose 12% and "
            "inventories stabilized, giving an official read on external demand and logistics conditions."
        ),
        published_at="2026-04-07T00:30:00+00:00",
        created_at="2026-04-07 09:02:00",
    )
    _seed_item(
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
    )
    capture_service = OvernightSourceCaptureService(
        repo=repo,
        registry=build_default_source_registry(),
    )
    return TestClient(create_app(database=database, repo=repo, capture_service=capture_service))


def _admin_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("OVERNIGHT_ADMIN_API_KEY", "secret-admin")
    monkeypatch.delenv("OVERNIGHT_ALLOW_UNSAFE_ADMIN", raising=False)
    return {"X-Admin-Access-Key": "secret-admin"}


def test_generate_daily_analysis_creates_fixed_free_and_premium_versions(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        client = _build_analysis_client(Path(temp_dir) / "test_daily_analysis_generate.db")

        response = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_date"] == "2026-04-07"
        assert [report["access_tier"] for report in payload["reports"]] == ["free", "premium"]
        assert [report["version"] for report in payload["reports"]] == [1, 1]
        assert payload["reports"][0]["provider"]["name"] == "rule_based"
        assert "mainlines" in payload["reports"][0]
        assert payload["reports"][0]["narratives"]["market_view"]
        assert payload["reports"][0]["narratives"]["policy_view"]
        assert payload["reports"][0]["direction_calls"]
        assert payload["reports"][0]["headline_news"]
        assert payload["reports"][0]["direction_calls"][0]["evidence_points"]
        assert payload["reports"][0]["direction_calls"][0]["follow_up_checks"]
        assert payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]["final_score"] >= 1
        assert "source_capture_confidence_bonus" in payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]
        assert "cross_source_confirmation_bonus" in payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]
        assert "fact_conflict_penalty" in payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]
        assert "timeliness_bonus" in payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]
        assert "staleness_penalty" in payload["reports"][0]["supporting_items"][0]["signal_score_breakdown"]
        assert "timeliness" in payload["reports"][0]["supporting_items"][0]
        assert "source_capture_confidence" in payload["reports"][0]["supporting_items"][0]
        assert "cross_source_confirmation" in payload["reports"][0]["supporting_items"][0]
        assert "fact_conflicts" in payload["reports"][0]["supporting_items"][0]
        assert "event_cluster" in payload["reports"][0]["supporting_items"][0]
        assert payload["reports"][0]["supporting_items"][0]["llm_ready_brief"]
        assert payload["reports"][1]["stock_calls"]


def test_rule_based_daily_analysis_builds_headline_news_with_official_and_editorial_mix() -> None:
    provider = RuleBasedDailyAnalysisProvider()

    def make_item(
        *,
        item_id: int,
        source_id: str,
        source_name: str,
        title: str,
        coverage_tier: str,
        priority: int,
        analysis_status: str,
        analysis_confidence: str,
        llm_ready_brief: str,
    ) -> dict[str, object]:
        return {
            "item_id": item_id,
            "source_id": source_id,
            "source_name": source_name,
            "title": title,
            "coverage_tier": coverage_tier,
            "priority": priority,
            "analysis_status": analysis_status,
            "analysis_confidence": analysis_confidence,
            "a_share_relevance": "high",
            "source_capture_confidence": {"level": "high", "score": 90 if coverage_tier != "editorial_media" else 68},
            "cross_source_confirmation": {
                "level": "moderate" if coverage_tier != "editorial_media" else "single_source",
                "supporting_source_count": 1 if coverage_tier != "editorial_media" else 0,
            },
            "fact_conflicts": [],
            "event_cluster": {
                "cluster_id": f"cluster_{item_id}",
                "cluster_status": "confirmed",
                "primary_item_id": item_id,
                "item_count": 1,
                "source_count": 1,
                "official_source_count": 1 if coverage_tier != "editorial_media" else 0,
                "member_item_ids": [item_id],
                "member_source_ids": [source_id],
                "latest_published_at": f"2026-04-07T0{item_id}:00:00+00:00",
                "topic_tags": ["macro_data"],
                "fact_signatures": [],
            },
            "timeliness": {
                "anchor_time": "2026-04-07T08:00:00+00:00",
                "age_hours": 1.0 + item_id,
                "publication_lag_minutes": 20,
                "freshness_bucket": "fresh",
                "is_timely": True,
                "timeliness_flags": [],
            },
            "beneficiary_directions": ["进口替代制造链"],
            "pressured_directions": [],
            "price_up_signals": [],
            "follow_up_checks": ["确认执行细则。"],
            "evidence_points": [f"evidence_{item_id}"],
            "impact_summary": f"impact_{item_id}",
            "llm_ready_brief": llm_ready_brief,
        }

    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="free",
        items=[
            make_item(
                item_id=1,
                source_id="whitehouse_news",
                source_name="White House News",
                title="Official item 1",
                coverage_tier="official_policy",
                priority=100,
                analysis_status="ready",
                analysis_confidence="high",
                llm_ready_brief="official_brief_1",
            ),
            make_item(
                item_id=2,
                source_id="fed_news",
                source_name="Federal Reserve News",
                title="Official item 2",
                coverage_tier="official_data",
                priority=100,
                analysis_status="ready",
                analysis_confidence="high",
                llm_ready_brief="official_brief_2",
            ),
            make_item(
                item_id=3,
                source_id="bea_news",
                source_name="BEA News",
                title="Official item 3",
                coverage_tier="official_data",
                priority=95,
                analysis_status="ready",
                analysis_confidence="high",
                llm_ready_brief="official_brief_3",
            ),
            make_item(
                item_id=4,
                source_id="treasury_press_releases",
                source_name="Treasury Press Releases",
                title="Official item 4",
                coverage_tier="official_policy",
                priority=95,
                analysis_status="ready",
                analysis_confidence="high",
                llm_ready_brief="official_brief_4",
            ),
            make_item(
                item_id=5,
                source_id="ap_business",
                source_name="AP Business",
                title="Editorial item 1",
                coverage_tier="editorial_media",
                priority=70,
                analysis_status="review",
                analysis_confidence="medium",
                llm_ready_brief="editorial_brief_1",
            ),
            make_item(
                item_id=6,
                source_id="kitco_news",
                source_name="Kitco News",
                title="Editorial item 2",
                coverage_tier="editorial_media",
                priority=68,
                analysis_status="review",
                analysis_confidence="medium",
                llm_ready_brief="editorial_brief_2",
            ),
        ],
    )

    headline_news = list(report["headline_news"])

    assert headline_news
    assert any(item["coverage_tier"] == "official_policy" or item["coverage_tier"] == "official_data" for item in headline_news)
    assert any(item["coverage_tier"] == "editorial_media" for item in headline_news)
    assert any(item["source_id"] == "kitco_news" for item in headline_news)


def test_rule_based_daily_analysis_reuses_mainlines_for_directions_and_stock_calls() -> None:
    provider = RuleBasedDailyAnalysisProvider()
    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="premium",
        items=[
            {
                "item_id": 1,
                "source_id": "bis_news_updates",
                "source_name": "BIS News Updates",
                "title": "BIS updates semiconductor export guidance",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 92},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "semiconductor_supply_chain__guidance__1",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [1],
                    "member_source_ids": ["bis_news_updates"],
                    "latest_published_at": "2026-04-07T01:00:00+00:00",
                    "topic_tags": ["semiconductor_supply_chain"],
                    "fact_signatures": [],
                },
                "timeliness": {
                    "anchor_time": "2026-04-07T02:00:00+00:00",
                    "age_hours": 0.5,
                    "publication_lag_minutes": 30,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["自主可控半导体链"],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认具体管制口径。"],
                "evidence_points": ["Semiconductor guidance tightened."],
                "impact_summary": "半导体主线继续强化。",
                "llm_ready_brief": "item_id=1 | BIS News Updates",
            }
        ],
        market_snapshot={
            "asset_board": {
                "analysis_date": "2026-04-07",
                "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 3.0}],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": 5.0},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 6.0},
                ],
                "rates_fx": [],
                "precious_metals": [],
                "energy": [],
                "industrial_metals": [],
            }
        },
        mainlines=[
            {
                "mainline_id": "tech_semiconductor__2026-04-07",
                "mainline_bucket": "tech_semiconductor",
                "headline": "科技/半导体主线走强",
                "linked_event_ids": ["semiconductor_supply_chain__guidance__1"],
                "confidence": "high",
            }
        ],
    )

    assert report["mainlines"][0]["mainline_id"] == "tech_semiconductor__2026-04-07"
    assert report["direction_calls"][0]["evidence_mainline_ids"] == ["tech_semiconductor__2026-04-07"]
    assert report["stock_calls"][0]["linked_mainline_ids"] == ["tech_semiconductor__2026-04-07"]


def test_rule_based_daily_analysis_synthesizes_direction_calls_from_regime_backed_mainlines() -> None:
    provider = RuleBasedDailyAnalysisProvider()
    report = provider.generate_report(
        analysis_date="2026-04-10",
        access_tier="premium",
        items=[
            {
                "item_id": 1,
                "source_id": "bis_news_updates",
                "source_name": "BIS News Updates",
                "title": "BIS confirms additional chip-control guidance",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 93},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "semiconductor_supply_chain__guidance__1",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [1],
                    "member_source_ids": ["bis_news_updates"],
                    "latest_published_at": "2026-04-10T00:10:00+00:00",
                    "topic_tags": ["semiconductor_supply_chain"],
                    "fact_signatures": [],
                },
                "timeliness": {
                    "anchor_time": "2026-04-10T02:00:00+00:00",
                    "age_hours": 0.4,
                    "publication_lag_minutes": 18,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": [],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认新增限制口径。"],
                "evidence_points": ["BIS guidance tightened for advanced chips."],
                "impact_summary": "出口限制主线继续强化。",
                "llm_ready_brief": "item_id=1 | BIS confirms additional chip-control guidance",
            }
        ],
        market_snapshot={
            "market_regimes": [
                {
                    "regime_id": "2026-04-10__technology_risk_on",
                    "regime_key": "technology_risk_on",
                    "triggered": True,
                    "direction": "bullish",
                    "strength": 2.6,
                    "confidence": "high",
                    "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                    "supporting_observations": [],
                    "suppressed_by": [],
                }
            ],
            "asset_board": {
                "analysis_date": "2026-04-10",
                "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.3}],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": 3.5},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 4.2},
                ],
                "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -2.1}],
                "precious_metals": [],
                "energy": [],
                "industrial_metals": [],
            },
        },
        mainlines=[
            {
                "mainline_id": "tech_semiconductor__2026-04-10",
                "mainline_bucket": "tech_semiconductor",
                "headline": "科技/半导体主线走强",
                "linked_event_ids": ["semiconductor_supply_chain__guidance__1"],
                "regime_ids": ["2026-04-10__technology_risk_on"],
                "market_effect": "科技偏多",
                "confidence": "high",
            }
        ],
    )

    assert report["direction_calls"][0]["direction"] == "自主可控半导体链"
    assert report["direction_calls"][0]["evidence_mainline_ids"] == ["tech_semiconductor__2026-04-10"]
    assert report["direction_calls"][0]["evidence_regime_ids"] == ["2026-04-10__technology_risk_on"]
    assert report["stock_calls"][0]["ticker"] == "688981.SH"
    assert "科技/半导体主线走强" in report["summary"]["headline"]
    assert "科技/半导体主线走强" in report["narratives"]["sector_view"]


def test_get_daily_analysis_returns_latest_cached_report_and_premium_requires_key(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        client = _build_analysis_client(Path(temp_dir) / "test_daily_analysis_read.db")

        first_generate = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )
        second_generate = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )
        free_response = client.get("/api/v1/analysis/daily", params={"analysis_date": "2026-04-07", "tier": "free"})
        premium_denied = client.get("/api/v1/analysis/daily", params={"analysis_date": "2026-04-07", "tier": "premium"})
        premium_allowed = client.get(
            "/api/v1/analysis/daily",
            params={"analysis_date": "2026-04-07", "tier": "premium"},
            headers={"X-Premium-Access-Key": "secret-premium"},
        )

        assert first_generate.status_code == 200
        assert second_generate.status_code == 200
        assert free_response.status_code == 200
        free_payload = free_response.json()
        assert free_payload["analysis_date"] == "2026-04-07"
        assert free_payload["access_tier"] == "free"
        assert free_payload["version"] == 2
        assert free_payload["summary"]["report_type"] == "daily_fixed"
        assert "source_capture_confidence" in free_payload["scoring_method"]["item_signal_formula"]
        assert "timeliness_bonus" in free_payload["scoring_method"]["item_signal_formula"]
        assert free_payload["narratives"]["market_view"]
        assert free_payload["narratives"]["sector_view"]
        assert any(call["direction"] == "银行/保险" for call in free_payload["direction_calls"])
        assert any(call["direction"] == "油服" for call in free_payload["direction_calls"])
        assert all(call["direction"] != "油气开采" for call in free_payload["direction_calls"])
        assert any(item["item_id"] for item in free_payload["supporting_items"])
        assert premium_denied.status_code == 403
        assert premium_denied.json() == {"detail": "Premium access key required"}

        assert premium_allowed.status_code == 200
        premium_payload = premium_allowed.json()
        assert premium_payload["access_tier"] == "premium"
        assert premium_payload["version"] == 2
        assert premium_payload["stock_calls"]
        assert any(call["ticker"] == "600583.SH" for call in premium_payload["stock_calls"])


def test_generate_daily_analysis_excludes_stale_same_day_captures(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        admin_headers = _admin_headers(monkeypatch)
        database = Database(Path(temp_dir) / "test_daily_analysis_excludes_stale.db")
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

        response = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-10"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        free_report = next(report for report in payload["reports"] if report["access_tier"] == "free")
        assert free_report["input_item_ids"] == [fresh_item_id]
        assert all(item["item_id"] != stale_item_id for item in free_report["supporting_items"])
        assert free_report["input_snapshot"]["item_count"] == 1


def test_generate_daily_analysis_uses_market_date_news_window_when_snapshot_rolls_forward() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_daily_analysis_market_date_window.db")
        repo = OvernightRepository(database)
        prior_window_item_id = _seed_item(
            repo,
            source_id="ap_world",
            url="https://example.com/ap/iran-talks",
            title="Iran talks remain in focus after overnight energy shock",
            summary="Officials weigh next steps after overnight oil-market volatility and renewed Middle East diplomacy.",
            published_at="2026-04-15T04:45:34+00:00",
            created_at="2026-04-15 15:54:57",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        market_snapshot_service = StaticMarketSnapshotService(
            {
                "analysis_date": "2026-04-16",
                "market_date": "2026-04-15",
                "capture_summary": {
                    "capture_status": "complete",
                    "captured_instrument_count": 25,
                    "missing_symbols": [],
                    "core_missing_symbols": [],
                },
                "market_regimes": [
                    {
                        "regime_id": "2026-04-16__china_proxy_strength",
                        "regime_key": "china_proxy_strength",
                        "triggered": True,
                        "direction": "bullish",
                        "strength": 1.6,
                        "confidence": "medium",
                        "driving_symbols": ["KWEB", "FXI"],
                        "supporting_observations": [],
                        "suppressed_by": [],
                    }
                ],
                "market_regime_evaluations": [],
                "asset_board": {
                    "analysis_date": "2026-04-16",
                    "headline": "纳指综指 +0.85%；标普500 +0.24%；美国10年期国债收益率 -0.93%；WTI原油 +0.17%；黄金 -0.96%；风险状态 mixed。",
                    "indexes": [
                        {"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 0.85, "priority": 98},
                        {"symbol": "^GSPC", "display_name": "标普500", "change_pct": 0.24, "priority": 100},
                    ],
                    "sectors": [
                        {"symbol": "XLE", "display_name": "能源板块", "change_pct": 0.48, "priority": 82},
                    ],
                    "sentiment": [
                        {"symbol": "^VIX", "display_name": "VIX", "change_pct": 1.52, "priority": 92},
                    ],
                    "rates_fx": [
                        {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -0.93, "priority": 76},
                    ],
                    "precious_metals": [
                        {"symbol": "GC=F", "display_name": "黄金", "change_pct": -0.96, "priority": 72},
                    ],
                    "energy": [
                        {"symbol": "CL=F", "display_name": "WTI原油", "change_pct": 0.17, "priority": 70},
                    ],
                    "industrial_metals": [],
                    "china_mapped_futures": [],
                },
            }
        )
        from app.services.daily_analysis import DailyAnalysisService

        service = DailyAnalysisService(
            repo=repo,
            capture_service=capture_service,
            market_snapshot_service=market_snapshot_service,
        )

        result = service.generate_daily_reports(analysis_date="2026-04-16", recent_limit=50)

    free_report = next(report for report in result["reports"] if report["access_tier"] == "free")
    assert free_report["input_item_ids"] == [prior_window_item_id]
    assert free_report["input_snapshot"]["item_count"] == 1
    assert free_report["supporting_items"][0]["item_id"] == prior_window_item_id
    assert free_report["market_snapshot"]["analysis_date"] == "2026-04-16"


def test_generate_daily_analysis_includes_secondary_event_groups(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        admin_headers = _admin_headers(monkeypatch)
        database = Database(Path(temp_dir) / "test_daily_analysis_secondary_groups.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/trade/secondary",
            title="White House updates tariff language",
            summary="Trade policy update without clear market confirmation.",
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
                        "strength": 2.0,
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
                        "strength": 2.0,
                        "confidence": "high",
                        "driving_symbols": ["SOXX", "XLK", "^IXIC"],
                        "supporting_observations": [],
                        "suppressed_by": [],
                    }
                ],
                "asset_board": {
                    "analysis_date": "2026-04-10",
                    "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.0}],
                    "sectors": [
                        {"symbol": "XLK", "display_name": "科技板块", "change_pct": 4.0},
                        {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 5.0},
                    ],
                    "rates_fx": [],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                },
            }
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                market_snapshot_service=market_snapshot_service,
            )
        )

        response = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-10"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        free_report = next(report for report in response.json()["reports"] if report["access_tier"] == "free")
        assert "secondary_event_groups" in free_report


def test_generate_daily_analysis_runs_ticker_enrichment_for_premium_only(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_daily_analysis_ticker_enrichment.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="bis_news_updates",
            url="https://example.com/bis/tech",
            title="BIS updates semiconductor guidance",
            summary="Semiconductor policy update supports a stronger overnight technology mainline.",
            published_at="2026-04-10T00:15:00+00:00",
            created_at="2026-04-10 08:20:00",
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
                        "strength": 2.1,
                        "confidence": "high",
                        "driving_symbols": ["SOXX", "XLK"],
                        "supporting_observations": [],
                        "suppressed_by": [],
                    }
                ],
                "market_regime_evaluations": [],
                "asset_board": {
                    "analysis_date": "2026-04-10",
                    "indexes": [{"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": 2.0}],
                    "sectors": [
                        {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 4.0},
                        {"symbol": "XLK", "display_name": "科技板块", "change_pct": 3.0},
                    ],
                    "rates_fx": [],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                },
            }
        )
        enrichment_service = RecordingTickerEnrichmentService(
            records=[
                {
                    "symbol": "SOXX",
                    "provider_name": "Alpha Vantage",
                    "status": "ready",
                    "payload": {"profile": {"symbol": "SOXX"}},
                }
            ]
        )
        from app.services.daily_analysis import DailyAnalysisService

        service = DailyAnalysisService(
            repo=repo,
            capture_service=capture_service,
            market_snapshot_service=market_snapshot_service,
            ticker_enrichment_service=enrichment_service,
        )

        result = service.generate_daily_reports(analysis_date="2026-04-10", recent_limit=50)

        free_report = next(report for report in result["reports"] if report["access_tier"] == "free")
        premium_report = next(report for report in result["reports"] if report["access_tier"] == "premium")
        assert enrichment_service.calls == [
            {
                "analysis_date": "2026-04-10",
                "session_name": "daily_analysis",
                "access_tier": "premium",
                "mainlines": premium_report["mainlines"],
                "market_regimes": premium_report["market_regimes"],
                "stock_calls": premium_report["stock_calls"],
                "explicit_symbols": [],
            }
        ]
        assert free_report["ticker_enrichments"] == []
        assert premium_report["ticker_enrichments"][0]["symbol"] == "SOXX"
        assert premium_report["enrichment_summary"]["status"] == "ok"


def test_rule_based_daily_analysis_uses_provenance_bonus_and_conflict_penalty() -> None:
    provider = RuleBasedDailyAnalysisProvider()
    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="free",
        items=[
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "title": "White House keeps 25% steel tariff",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 92},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "conflicted",
                    "primary_item_id": 1,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 1,
                    "member_item_ids": [1, 2],
                    "member_source_ids": ["whitehouse_news", "ap_business"],
                    "latest_published_at": "2026-04-08T02:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
                "timeliness": {
                    "anchor_time": "2026-04-07T02:00:00+00:00",
                    "age_hours": 0.5,
                    "publication_lag_minutes": 30,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["进口替代制造链"],
                "pressured_directions": ["对美出口链"],
                "price_up_signals": [],
                "follow_up_checks": ["确认税率与执行时间。"],
                "evidence_points": ["25% tariff remains in place"],
                "impact_summary": "贸易政策继续偏紧。",
                "llm_ready_brief": "item_id=1 | White House News",
            },
            {
                "item_id": 2,
                "source_id": "ap_business",
                "source_name": "AP Business",
                "title": "AP says tariff may move to 15%",
                "coverage_tier": "editorial_media",
                "priority": 60,
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "medium", "score": 61},
                "cross_source_confirmation": {"level": "single_source", "supporting_source_count": 0},
                "fact_conflicts": [
                    {
                        "conflict_type": "numeric_mismatch",
                        "metric": "tariff_rate",
                        "subject": "steel",
                        "current_value_text": "15.0%",
                        "other_value_text": "25.0%",
                        "other_item_id": 1,
                        "other_source_id": "whitehouse_news",
                        "other_source_name": "White House News",
                    }
                ],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "conflicted",
                    "primary_item_id": 1,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 1,
                    "member_item_ids": [1, 2],
                    "member_source_ids": ["whitehouse_news", "ap_business"],
                    "latest_published_at": "2026-04-08T02:00:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
                "timeliness": {
                    "anchor_time": "2026-04-08T02:00:00+00:00",
                    "age_hours": 96.0,
                    "publication_lag_minutes": 1500,
                    "freshness_bucket": "stale",
                    "is_timely": False,
                    "timeliness_flags": ["stale_publication", "delayed_capture"],
                },
                "beneficiary_directions": ["进口替代制造链"],
                "pressured_directions": ["对美出口链"],
                "price_up_signals": [],
                "follow_up_checks": ["等待官方确认。"],
                "evidence_points": ["AP discussed a possible lower tariff"],
                "impact_summary": "媒体消息需要官方确认。",
                "llm_ready_brief": "item_id=2 | AP Business",
            },
        ],
    )

    supporting_items = {item["item_id"]: item for item in report["supporting_items"]}
    official_item = supporting_items[1]
    editorial_item = supporting_items[2]

    assert official_item["signal_score"] > editorial_item["signal_score"]
    assert official_item["signal_score_breakdown"]["source_capture_confidence_bonus"] >= 2
    assert official_item["signal_score_breakdown"]["cross_source_confirmation_bonus"] == 1
    assert official_item["signal_score_breakdown"]["fact_conflict_penalty"] == 0
    assert official_item["signal_score_breakdown"]["timeliness_bonus"] == 3
    assert official_item["signal_score_breakdown"]["staleness_penalty"] == 0
    assert editorial_item["signal_score_breakdown"]["fact_conflict_penalty"] == 1
    assert editorial_item["signal_score_breakdown"]["timeliness_bonus"] == 0
    assert editorial_item["signal_score_breakdown"]["staleness_penalty"] == 2
    assert report["direction_calls"][0]["confirmed_item_count"] == 1
    assert report["direction_calls"][0]["conflicted_item_count"] == 1


def test_rule_based_daily_analysis_deduplicates_direction_weight_inside_same_event_cluster() -> None:
    provider = RuleBasedDailyAnalysisProvider()
    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="free",
        items=[
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "title": "White House keeps 25% steel tariff",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 92},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 2,
                    "member_item_ids": [1, 2],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases"],
                    "latest_published_at": "2026-04-07T01:50:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
                "timeliness": {
                    "anchor_time": "2026-04-07T02:00:00+00:00",
                    "age_hours": 0.5,
                    "publication_lag_minutes": 30,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["进口替代制造链"],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认税率与执行时间。"],
                "evidence_points": ["25% tariff remains in place"],
                "impact_summary": "贸易政策继续偏紧。",
                "llm_ready_brief": "item_id=1 | White House News",
            },
            {
                "item_id": 2,
                "source_id": "ustr_press_releases",
                "source_name": "USTR Press Releases",
                "title": "USTR confirms 25% steel tariff",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 90},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "trade_policy__tariff_rate__steel",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 2,
                    "member_item_ids": [1, 2],
                    "member_source_ids": ["whitehouse_news", "ustr_press_releases"],
                    "latest_published_at": "2026-04-07T01:50:00+00:00",
                    "topic_tags": ["trade_policy"],
                    "fact_signatures": ["tariff_rate:steel"],
                },
                "timeliness": {
                    "anchor_time": "2026-04-07T02:00:00+00:00",
                    "age_hours": 0.2,
                    "publication_lag_minutes": 10,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["进口替代制造链"],
                "pressured_directions": [],
                "price_up_signals": [],
                "follow_up_checks": ["确认税率与执行时间。"],
                "evidence_points": ["USTR confirmed current tariff path"],
                "impact_summary": "贸易政策继续偏紧。",
                "llm_ready_brief": "item_id=2 | USTR Press Releases",
            },
        ],
    )

    direction_call = next(call for call in report["direction_calls"] if call["direction"] == "进口替代制造链")
    supporting_items = {item["item_id"]: item for item in report["supporting_items"]}
    expected_max_score = max(supporting_items[1]["signal_score"], supporting_items[2]["signal_score"])

    assert direction_call["score"] == expected_max_score
    assert direction_call["event_cluster_count"] == 1
    assert direction_call["evidence_item_ids"] == [1, 2]


def test_rule_based_daily_analysis_compresses_overlapping_energy_siblings_before_stock_mapping() -> None:
    provider = RuleBasedDailyAnalysisProvider()

    def make_item(
        *,
        item_id: int,
        cluster_id: str,
        title: str,
        beneficiary_directions: list[str],
        evidence_point: str,
    ) -> dict[str, object]:
        return {
            "item_id": item_id,
            "source_id": f"energy_source_{item_id}",
            "source_name": f"Energy Source {item_id}",
            "title": title,
            "coverage_tier": "official_policy",
            "priority": 100,
            "analysis_status": "ready",
            "analysis_confidence": "high",
            "a_share_relevance": "high",
            "source_capture_confidence": {"level": "high", "score": 92},
            "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
            "fact_conflicts": [],
            "event_cluster": {
                "cluster_id": cluster_id,
                "cluster_status": "confirmed",
                "primary_item_id": item_id,
                "item_count": 1,
                "source_count": 1,
                "official_source_count": 1,
                "member_item_ids": [item_id],
                "member_source_ids": [f"energy_source_{item_id}"],
                "latest_published_at": f"2026-04-07T0{item_id}:00:00+00:00",
                "topic_tags": ["energy_shipping"],
                "fact_signatures": [cluster_id],
            },
            "timeliness": {
                "anchor_time": "2026-04-07T03:00:00+00:00",
                "age_hours": 0.5,
                "publication_lag_minutes": 20,
                "freshness_bucket": "breaking",
                "is_timely": True,
                "timeliness_flags": [],
            },
            "beneficiary_directions": list(beneficiary_directions),
            "pressured_directions": [],
            "price_up_signals": [],
            "follow_up_checks": ["确认能源政策执行细则。"],
            "evidence_points": [evidence_point],
            "impact_summary": "能源主线继续强化。",
            "llm_ready_brief": f"item_id={item_id} | Energy Source {item_id}",
        }

    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="premium",
        items=[
            make_item(
                item_id=1,
                cluster_id="energy_upstream__1",
                title="White House backs offshore energy expansion",
                beneficiary_directions=["油服", "油气开采"],
                evidence_point="Offshore energy expansion remains a priority.",
            ),
            make_item(
                item_id=2,
                cluster_id="energy_upstream__2",
                title="DOE says pipeline buildout supports service demand",
                beneficiary_directions=["油服"],
                evidence_point="Pipeline buildout lifts energy service demand.",
            ),
        ],
    )

    visible_directions = [call["direction"] for call in report["direction_calls"]]
    visible_tickers = [call["ticker"] for call in report["stock_calls"]]

    assert "油服" in visible_directions
    assert "油气开采" not in visible_directions
    assert "600583.SH" in visible_tickers
    assert "600871.SH" in visible_tickers
    assert "600938.SH" not in visible_tickers
    assert "601857.SH" not in visible_tickers


def test_rule_based_daily_analysis_emits_chinese_first_user_briefs_for_headline_news() -> None:
    provider = RuleBasedDailyAnalysisProvider()

    def make_item(
        *,
        item_id: int,
        source_id: str,
        source_name: str,
        title: str,
        impact_summary: str,
        llm_ready_brief: str,
        evidence_points: list[str],
    ) -> dict[str, object]:
        return {
            "item_id": item_id,
            "source_id": source_id,
            "source_name": source_name,
            "title": title,
            "coverage_tier": "official_policy" if item_id == 1 else "editorial_media",
            "priority": 100 if item_id == 1 else 70,
            "analysis_status": "ready" if item_id == 1 else "review",
            "analysis_confidence": "high" if item_id == 1 else "medium",
            "a_share_relevance": "high",
            "source_capture_confidence": {"level": "high" if item_id == 1 else "medium", "score": 90 if item_id == 1 else 65},
            "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1 if item_id == 1 else 0},
            "fact_conflicts": [],
            "event_cluster": {
                "cluster_id": f"brief_cluster_{item_id}",
                "cluster_status": "confirmed",
                "primary_item_id": item_id,
                "item_count": 1,
                "source_count": 1,
                "official_source_count": 1 if item_id == 1 else 0,
                "member_item_ids": [item_id],
                "member_source_ids": [source_id],
                "latest_published_at": f"2026-04-07T0{item_id}:00:00+00:00",
                "topic_tags": ["trade_policy"] if item_id == 1 else ["energy_shipping"],
                "fact_signatures": [],
            },
            "timeliness": {
                "anchor_time": "2026-04-07T03:00:00+00:00",
                "age_hours": 0.5,
                "publication_lag_minutes": 20,
                "freshness_bucket": "breaking",
                "is_timely": True,
                "timeliness_flags": [],
            },
            "beneficiary_directions": ["进口替代制造链"] if item_id == 1 else ["油服"],
            "pressured_directions": [],
            "price_up_signals": [],
            "follow_up_checks": ["确认执行细则。"],
            "evidence_points": list(evidence_points),
            "impact_summary": impact_summary,
            "llm_ready_brief": llm_ready_brief,
        }

    report = provider.generate_report(
        analysis_date="2026-04-07",
        access_tier="free",
        items=[
            make_item(
                item_id=1,
                source_id="whitehouse_news",
                source_name="White House News",
                title="白宫确认维持钢铁关税",
                impact_summary="item_id=1 | 2026-04-07 03:00 CST | White House News | authority=primary_official",
                llm_ready_brief="item_id=1 | White House News | watch=确认税率与执行时间。",
                evidence_points=["维持 25% 钢铁关税。", "关注执行时间。"],
            ),
            make_item(
                item_id=2,
                source_id="ap_business",
                source_name="AP Business",
                title="航运运价继续上涨",
                impact_summary="",
                llm_ready_brief="",
                evidence_points=["中东冲突扰动航线。", "油价和运价同步抬升。"],
            ),
        ],
    )

    headline_news = list(report["headline_news"])
    official_item = next(item for item in headline_news if item["item_id"] == 1)
    editorial_item = next(item for item in headline_news if item["item_id"] == 2)

    assert official_item["user_brief_cn"]
    assert official_item["brief_source"] == "synthesized_cn"
    assert "item_id=" not in official_item["user_brief_cn"]
    assert "白宫确认维持钢铁关税" in official_item["user_brief_cn"]
    assert editorial_item["user_brief_cn"]
    assert editorial_item["brief_source"] == "evidence_points"
    assert "中东冲突扰动航线" in editorial_item["user_brief_cn"]


def test_rule_based_daily_analysis_emits_detailed_market_moves_and_editorial_driver_chain() -> None:
    provider = RuleBasedDailyAnalysisProvider()

    report = provider.generate_report(
        analysis_date="2026-04-15",
        access_tier="free",
        items=[
            {
                "item_id": 1,
                "source_id": "whitehouse_news",
                "source_name": "White House News",
                "title": "Trump team weighs additional Middle East deployment",
                "coverage_tier": "official_policy",
                "priority": 100,
                "analysis_status": "ready",
                "analysis_confidence": "high",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "high", "score": 92},
                "cross_source_confirmation": {"level": "moderate", "supporting_source_count": 1},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "middle_east_energy__deployment__1",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 1,
                    "source_count": 1,
                    "official_source_count": 1,
                    "member_item_ids": [1],
                    "member_source_ids": ["whitehouse_news"],
                    "latest_published_at": "2026-04-15T06:00:00+00:00",
                    "topic_tags": ["energy_shipping"],
                    "fact_signatures": [],
                },
                "timeliness": {
                    "anchor_time": "2026-04-15T07:00:00+00:00",
                    "age_hours": 0.5,
                    "publication_lag_minutes": 25,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["油服"],
                "pressured_directions": ["航空与燃油敏感运输链"],
                "price_up_signals": ["原油/燃料油"],
                "follow_up_checks": ["确认霍尔木兹通行状态和增兵节奏。"],
                "evidence_points": [
                    "五角大楼将在未来几天向中东增派数千名美军。",
                    "市场担心霍尔木兹海峡运输风险抬升。",
                ],
                "impact_summary": "item_id=1 | White House News | authority=primary_official",
                "llm_ready_brief": "item_id=1 | White House News | watch=确认霍尔木兹状态。",
                "key_numbers": [
                    {"metric": "Brent", "subject": "盘中涨幅", "value_text": "+1.60%"},
                    {"metric": "WTI", "subject": "盘中涨幅", "value_text": "+1.50%"},
                ],
                "fact_table": [
                    {"text": "ICE 布油盘中突破 96 美元/桶。"},
                    {"text": "WTI 原油升至 92.69 美元/桶。"},
                ],
            },
            {
                "item_id": 2,
                "source_id": "cnbc_markets",
                "source_name": "CNBC Markets",
                "title": "Hormuz blockade concerns lift oil intraday",
                "coverage_tier": "editorial_media",
                "priority": 80,
                "analysis_status": "review",
                "analysis_confidence": "medium",
                "a_share_relevance": "high",
                "source_capture_confidence": {"level": "medium", "score": 68},
                "cross_source_confirmation": {"level": "single_source", "supporting_source_count": 0},
                "fact_conflicts": [],
                "event_cluster": {
                    "cluster_id": "middle_east_energy__deployment__1",
                    "cluster_status": "confirmed",
                    "primary_item_id": 1,
                    "item_count": 2,
                    "source_count": 2,
                    "official_source_count": 1,
                    "member_item_ids": [1, 2],
                    "member_source_ids": ["whitehouse_news", "cnbc_markets"],
                    "latest_published_at": "2026-04-15T06:20:00+00:00",
                    "topic_tags": ["energy_shipping"],
                    "fact_signatures": [],
                },
                "timeliness": {
                    "anchor_time": "2026-04-15T07:00:00+00:00",
                    "age_hours": 0.3,
                    "publication_lag_minutes": 18,
                    "freshness_bucket": "breaking",
                    "is_timely": True,
                    "timeliness_flags": [],
                },
                "beneficiary_directions": ["油服"],
                "pressured_directions": ["化工下游成本敏感链"],
                "price_up_signals": ["原油/燃料油"],
                "follow_up_checks": ["确认伊朗出口是否实质下降。"],
                "evidence_points": [
                    "分析人士预计封锁若持续，伊朗将在约两周内被迫减产。",
                    "霍尔木兹海峡流量不确定性继续抬升。",
                ],
                "impact_summary": "",
                "llm_ready_brief": "",
                "key_numbers": [
                    {"metric": "Iran exports", "subject": "disruption window", "value_text": "10-15天"},
                ],
                "fact_table": [
                    {"text": "咨询机构认为若出口被切断，伊朗仅能维持 10 到 15 天生产。"},
                ],
            },
        ],
        market_snapshot={
            "analysis_date": "2026-04-15",
            "capture_summary": {
                "capture_status": "partial",
                "captured_instrument_count": 6,
                "missing_symbols": ["XLK"],
                "core_missing_symbols": ["XLK"],
            },
            "asset_board": {
                "headline": "布伦特原油 +1.60%；WTI原油 +1.50%；黄金 -0.40%；美国10年期国债收益率 +0.06%；风险状态 risk_off。",
                "indexes": [
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": -0.8, "priority": 90},
                    {"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": -1.1, "priority": 92},
                ],
                "sectors": [],
                "sentiment": [],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": 0.06, "priority": 80},
                ],
                "precious_metals": [
                    {"symbol": "GC=F", "display_name": "黄金", "change_pct": -0.4, "priority": 81},
                ],
                "energy": [
                    {"symbol": "BZ=F", "display_name": "布伦特原油", "change_pct": 1.6, "priority": 84},
                    {"symbol": "CL=F", "display_name": "WTI原油", "change_pct": 1.5, "priority": 83},
                ],
                "industrial_metals": [],
                "china_mapped_futures": [
                    {
                        "future_code": "pta",
                        "future_name": "PTA",
                        "watch_direction": "up",
                        "watch_score": 1.3,
                        "driver_summary": "布伦特原油 +1.60%；WTI原油 +1.50%。",
                    }
                ],
                "key_moves": {
                    "strongest_move": {"symbol": "BZ=F", "display_name": "布伦特原油", "change_pct": 1.6, "priority": 84},
                    "weakest_move": {"symbol": "GC=F", "display_name": "黄金", "change_pct": -0.4, "priority": 81},
                },
                "risk_signals": {"risk_mode": "risk_off"},
            },
            "risk_signals": {"risk_mode": "risk_off"},
            "market_regimes": [],
            "market_regime_evaluations": [],
        },
    )

    market_move_brief = dict(report["market_move_brief"])
    assert "布伦特原油 +1.60%" in market_move_brief["headline"]
    assert any(item["label"] == "布伦特原油" and item["change_pct"] == "+1.60%" for item in market_move_brief["cross_asset_moves"])
    assert market_move_brief["strongest_move"]["label"] == "布伦特原油"
    assert market_move_brief["weakest_move"]["label"] == "黄金"
    assert market_move_brief["market_data_note"]

    event_drivers = list(report["event_drivers"])
    assert event_drivers
    assert event_drivers[0]["source_name"] == "White House News"
    assert event_drivers[0]["detail_facts"]
    assert "Brent=+1.60%" in "；".join(event_drivers[0]["detail_facts"])
    assert report["editorial_chain_cn"]
    assert "布伦特原油 +1.60%" in report["editorial_chain_cn"]
    assert "White House News" in report["editorial_chain_cn"]
    assert "油服" in report["editorial_chain_cn"]


def test_generate_daily_analysis_explains_missing_mainline_grounding_and_caps_confidence_when_core_market_gaps_exist(
    monkeypatch,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        admin_headers = _admin_headers(monkeypatch)
        database = Database(Path(temp_dir) / "test_daily_analysis_market_gap.db")
        repo = OvernightRepository(database)
        _seed_item(
            repo,
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/energy-gap",
            title="White House says energy expansion remains a priority",
            summary="A timely policy update tied to energy expansion and shipping costs.",
            published_at="2026-04-10T01:00:00+00:00",
            created_at="2026-04-10 09:01:00",
        )
        capture_service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
        )
        market_snapshot_service = StaticMarketSnapshotService(
            {
                "analysis_date": "2026-04-10",
                "market_regimes": [],
                "market_regime_evaluations": [],
                "capture_summary": {
                    "capture_status": "partial",
                    "captured_instrument_count": 1,
                    "missing_symbols": ["^GSPC", "^IXIC", "XLK"],
                    "core_missing_symbols": ["^GSPC", "^IXIC", "XLK"],
                },
                "asset_board": {
                    "analysis_date": "2026-04-10",
                    "indexes": [],
                    "sectors": [],
                    "rates_fx": [{"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": 0.0}],
                    "precious_metals": [],
                    "energy": [],
                    "industrial_metals": [],
                },
            }
        )
        client = TestClient(
            create_app(
                database=database,
                repo=repo,
                capture_service=capture_service,
                market_snapshot_service=market_snapshot_service,
            )
        )

        response = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-10"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        free_report = next(report for report in response.json()["reports"] if report["access_tier"] == "free")
        assert free_report["mainline_coverage"]["status"] == "degraded"
        assert free_report["mainline_coverage"]["market_data_status"] == "partial"
        assert "core_market_gap" in free_report["mainline_coverage"]["suppression_reasons"]
        assert free_report["summary"]["confidence"] != "high"
        assert "不完整" in free_report["summary"]["core_view"]
        assert any("市场" in item or "核心" in item for item in free_report["risk_watchpoints"])


def test_get_daily_analysis_prompt_bundle_returns_provider_agnostic_messages(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        client = _build_analysis_client(Path(temp_dir) / "test_daily_analysis_prompt.db")
        client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )

        free_prompt = client.get("/api/v1/analysis/daily/prompt", params={"analysis_date": "2026-04-07", "tier": "free"})
        premium_prompt = client.get(
            "/api/v1/analysis/daily/prompt",
            params={"analysis_date": "2026-04-07", "tier": "premium"},
            headers={"X-Premium-Access-Key": "secret-premium"},
        )

        assert free_prompt.status_code == 200
        free_payload = free_prompt.json()
        assert free_payload["analysis_date"] == "2026-04-07"
        assert free_payload["access_tier"] == "free"
        assert free_payload["report_version"] == 1
        assert free_payload["provider_target"] == "external_llm_ready"
        assert [message["role"] for message in free_payload["messages"]] == ["system", "user"]
        assert "不要输出具体个股买卖建议" in free_payload["messages"][0]["content"]
        assert free_payload["input_item_ids"] == [1, 2, 3]
        assert free_payload["source_audit_pack"]["included_item_count"] == len(free_payload["source_audit_pack"]["supporting_items"])
        assert free_payload["source_audit_pack"]["event_group_count"] >= 1
        assert free_payload["source_audit_pack"]["supporting_items"][0]["item_id"] == 1
        assert free_payload["source_audit_pack"]["event_groups"][0]["items"]
        assert "source_audit_pack" in free_payload["messages"][1]["content"]
        assert "event_groups" in free_payload["messages"][1]["content"]

        assert premium_prompt.status_code == 200
        premium_payload = premium_prompt.json()
        assert premium_payload["access_tier"] == "premium"
        assert "可以输出具体个股映射" in premium_payload["messages"][0]["content"]


def test_daily_analysis_versions_endpoint_lists_latest_to_oldest(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        client = _build_analysis_client(Path(temp_dir) / "test_daily_analysis_versions.db")

        client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )
        client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        )

        response = client.get("/api/v1/analysis/daily/versions", params={"analysis_date": "2026-04-07", "tier": "free"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["analysis_date"] == "2026-04-07"
        assert payload["access_tier"] == "free"
        assert [item["version"] for item in payload["versions"]] == [2, 1]
        assert payload["versions"][0]["input_fingerprint"]
        assert payload["versions"][0]["report_fingerprint"]


def test_get_daily_analysis_can_read_specific_version_and_prompt_version(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("OVERNIGHT_PREMIUM_API_KEY", "secret-premium")
        admin_headers = _admin_headers(monkeypatch)
        client = _build_analysis_client(Path(temp_dir) / "test_daily_analysis_specific_version.db")

        first = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        ).json()
        second = client.post(
            "/api/v1/analysis/daily/generate",
            params={"analysis_date": "2026-04-07"},
            headers=admin_headers,
        ).json()
        report_v1 = client.get("/api/v1/analysis/daily", params={"analysis_date": "2026-04-07", "tier": "free", "version": 1})
        prompt_v1 = client.get("/api/v1/analysis/daily/prompt", params={"analysis_date": "2026-04-07", "tier": "free", "version": 1})

        assert first["reports"][0]["version"] == 1
        assert second["reports"][0]["version"] == 2
        assert report_v1.status_code == 200
        report_payload = report_v1.json()
        assert report_payload["version"] == 1
        assert report_payload["summary"]["report_type"] == "daily_fixed"

        assert prompt_v1.status_code == 200
        prompt_payload = prompt_v1.json()
        assert prompt_payload["report_version"] == 1
        assert prompt_payload["input_item_ids"] == [1, 2, 3]


def test_get_daily_analysis_prompt_bundle_returns_404_when_report_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = TestClient(create_app(database=Database(Path(temp_dir) / "test_daily_analysis_prompt_empty.db")))

        response = client.get("/api/v1/analysis/daily/prompt", params={"analysis_date": "2026-04-07", "tier": "free"})

        assert response.status_code == 404
        assert response.json() == {"detail": "Daily analysis not found"}


def test_get_daily_analysis_versions_returns_404_when_report_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = TestClient(create_app(database=Database(Path(temp_dir) / "test_daily_analysis_versions_empty.db")))

        response = client.get("/api/v1/analysis/daily/versions", params={"analysis_date": "2026-04-07", "tier": "free"})

        assert response.status_code == 404
        assert response.json() == {"detail": "Daily analysis not found"}


def test_get_daily_analysis_returns_404_when_report_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = TestClient(create_app(database=Database(Path(temp_dir) / "test_daily_analysis_empty.db")))

        response = client.get("/api/v1/analysis/daily", params={"analysis_date": "2026-04-07", "tier": "free"})

        assert response.status_code == 404
        assert response.json() == {"detail": "Daily analysis not found"}
