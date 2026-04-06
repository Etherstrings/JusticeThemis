# -*- coding: utf-8 -*-
"""Integration tests for overnight API endpoints."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.v1.endpoints.overnight import get_overnight_service
from src.config import Config
from src.overnight.brief_builder import MorningExecutiveBrief, RankedEvent, build_morning_brief
from src.repositories.overnight_repo import OvernightRepository
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


@pytest.fixture()
def client() -> TestClient:
    _reset_auth_globals()
    temp_dir = tempfile.TemporaryDirectory()
    env_path = Path(temp_dir.name) / ".env"
    db_path = Path(temp_dir.name) / "overnight_api_test.db"
    env_path.write_text("ADMIN_AUTH_ENABLED=false\n", encoding="utf-8")
    os.environ["ENV_FILE"] = str(env_path)
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()

    auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=False)
    auth_patcher.start()

    app = create_app(static_dir=Path(temp_dir.name) / "empty-static")
    api_client = TestClient(app)

    try:
        yield api_client
    finally:
        auth_patcher.stop()
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        temp_dir.cleanup()


class FakeOvernightService:
    def __init__(self) -> None:
        self._brief = build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_123",
                    core_fact="USTR announced new tariffs",
                    priority_level="P0",
                    summary="Tariff escalation was published by USTR.",
                    why_it_matters="Trade policy became the main overnight driver.",
                    confidence=0.84,
                    market_reaction="USDCNH weakened first.",
                    source_links=["https://www.ustr.gov/example-release"],
                )
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )

    def get_latest_brief(self):
        return self._brief

    def get_brief_by_id(self, brief_id: str):
        if brief_id != self._brief.brief_id:
            raise LookupError(brief_id)
        return self._brief

    def list_history(self, *, page: int, limit: int, q: str | None = None):
        return {
            "page": page,
            "limit": limit,
            "total": 1,
            "items": [
                {
                    "brief_id": self._brief.brief_id,
                    "digest_date": self._brief.digest_date,
                    "cutoff_time": self._brief.cutoff_time,
                    "topline": self._brief.topline,
                    "generated_at": self._brief.generated_at,
                }
            ],
        }

    def list_event_history(self, *, page: int, limit: int, q: str | None = None):
        return {
            "page": page,
            "limit": limit,
            "total": 1,
            "items": [
                {
                    "event_key": "ustr-announced-new-tariffs",
                    "core_fact": "USTR announced new tariffs",
                    "occurrence_count": 2,
                    "latest_brief_id": "brief_abc",
                    "latest_digest_date": "2026-04-05",
                    "latest_event_id": "event_123",
                    "latest_priority_level": "P0",
                    "average_confidence": 0.8,
                    "occurrences": [
                        {
                            "brief_id": "brief_abc",
                            "digest_date": "2026-04-05",
                            "event_id": "event_123",
                            "priority_level": "P0",
                            "confidence": 0.84,
                        }
                    ],
                }
            ],
        }

    def list_topic_history(self, *, page: int, limit: int, q: str | None = None):
        return {
            "page": page,
            "limit": limit,
            "total": 1,
            "items": [
                {
                    "topic_key": "policy-radar",
                    "title": "政策雷达",
                    "occurrence_count": 2,
                    "total_item_count": 3,
                    "latest_brief_id": "brief_abc",
                    "latest_digest_date": "2026-04-05",
                    "latest_item_count": 2,
                    "recent_briefs": [
                        {
                            "brief_id": "brief_abc",
                            "digest_date": "2026-04-05",
                            "item_count": 2,
                        }
                    ],
                }
            ],
        }

    def get_event_detail(self, event_id: str, brief_id: str | None = None):
        if event_id != "event_123":
            raise LookupError(event_id)
        if brief_id == "brief_hist":
            return {
                "event_id": event_id,
                "priority_level": "P1",
                "core_fact": "USTR announced new tariffs",
                "summary": "Historical brief kept the tariff story on watch.",
                "why_it_matters": "Trade policy remained a follow-through catalyst.",
                "confidence": 0.72,
                "source_links": ["https://www.ustr.gov/historical-release"],
                "evidence_items": [
                    {
                        "headline": "Historical tariff follow-up",
                        "source_name": "USTR Press Releases",
                        "url": "https://www.ustr.gov/historical-release",
                        "summary": "Historical brief kept the tariff story on watch.",
                        "source_type": "official",
                        "coverage_tier": "official_policy",
                        "source_class": "policy",
                    }
                ],
                "judgment_summary": "这条更像历史晨报里的延续线，先看国产替代是否再次放量。",
                "judgment_mode": "heuristic",
            }
        return {
            "event_id": event_id,
            "priority_level": "P0",
            "core_fact": "USTR announced new tariffs",
            "summary": "Tariff escalation was published by USTR.",
            "why_it_matters": "Trade policy became the main overnight driver.",
            "confidence": 0.84,
            "source_links": ["https://www.ustr.gov/example-release"],
            "evidence_items": [
                {
                    "headline": "Example release",
                    "source_name": "USTR Press Releases",
                    "url": "https://www.ustr.gov/example-release",
                    "summary": "Tariff escalation was published by USTR.",
                    "source_type": "official",
                    "coverage_tier": "official_policy",
                    "source_class": "policy",
                }
            ],
            "judgment_summary": "这条更像盘前主线预热，先看自主可控和航运替代链是否同步确认。",
            "judgment_mode": "heuristic",
        }

    def get_brief_delta(self, brief_id: str | None = None):
        target_brief_id = brief_id or self._brief.brief_id
        return {
            "brief_id": target_brief_id,
            "digest_date": "2026-04-05",
            "previous_brief_id": "brief_prev",
            "previous_digest_date": "2026-04-04",
            "summary": "Compared with the previous brief: 1 new, 1 intensified, 1 steady, 1 cooling, 1 dropped.",
            "new_events": [
                {
                    "event_key": "fresh-energy-rally",
                    "core_fact": "Fresh energy rally widened overnight",
                    "current_event_id": "event_new",
                    "previous_event_id": None,
                    "current_priority_level": "P1",
                    "previous_priority_level": "",
                    "current_confidence": 0.77,
                    "previous_confidence": 0.0,
                    "delta_type": "new",
                    "delta_summary": "First appearance in the current brief.",
                }
            ],
            "intensified_events": [
                {
                    "event_key": "ustr-announced-new-tariffs",
                    "core_fact": "USTR announced new tariffs",
                    "current_event_id": "event_123",
                    "previous_event_id": "event_prev_123",
                    "current_priority_level": "P0",
                    "previous_priority_level": "P1",
                    "current_confidence": 0.84,
                    "previous_confidence": 0.72,
                    "delta_type": "intensified",
                    "delta_summary": "Priority moved from P1 to P0.",
                }
            ],
            "steady_events": [
                {
                    "event_key": "fed-speakers-signaled-patience",
                    "core_fact": "Fed speakers signaled patience",
                    "current_event_id": "event_steady",
                    "previous_event_id": "event_prev_steady",
                    "current_priority_level": "P1",
                    "previous_priority_level": "P1",
                    "current_confidence": 0.8,
                    "previous_confidence": 0.78,
                    "delta_type": "steady",
                    "delta_summary": "Priority and confidence stayed broadly unchanged.",
                }
            ],
            "cooling_events": [
                {
                    "event_key": "brent-crude-rally",
                    "core_fact": "Brent crude rally cooled",
                    "current_event_id": "event_cooling",
                    "previous_event_id": "event_prev_cooling",
                    "current_priority_level": "P2",
                    "previous_priority_level": "P1",
                    "current_confidence": 0.7,
                    "previous_confidence": 0.81,
                    "delta_type": "cooling",
                    "delta_summary": "Priority moved from P1 to P2.",
                }
            ],
            "dropped_events": [
                {
                    "event_key": "old-chip-story",
                    "core_fact": "Old chip story dropped out",
                    "current_event_id": None,
                    "previous_event_id": "event_dropped",
                    "current_priority_level": "",
                    "previous_priority_level": "P2",
                    "current_confidence": 0.0,
                    "previous_confidence": 0.74,
                    "delta_type": "dropped",
                    "delta_summary": "Present in the previous brief but not in the current one.",
                }
            ],
        }

    def list_sources(self):
        return {
            "total": 2,
            "mission_critical": 1,
            "items": [
                {
                    "source_id": "whitehouse_news",
                    "display_name": "White House News",
                    "organization_type": "official_policy",
                    "source_class": "policy",
                    "entry_type": "section_page",
                    "entry_urls": ["https://www.whitehouse.gov/news/"],
                    "priority": 100,
                    "poll_interval_seconds": 300,
                    "is_mission_critical": True,
                    "is_enabled": True,
                    "coverage_tier": "official_policy",
                    "region_focus": "US policy",
                    "coverage_focus": "跟踪白宫政策声明、行政动作和事实清单。",
                },
                {
                    "source_id": "reuters_topics",
                    "display_name": "Reuters Topics",
                    "organization_type": "wire_media",
                    "source_class": "market",
                    "entry_type": "section_page",
                    "entry_urls": ["https://www.reuters.com/world/"],
                    "priority": 90,
                    "poll_interval_seconds": 600,
                    "is_mission_critical": False,
                    "is_enabled": True,
                    "coverage_tier": "editorial_media",
                    "region_focus": "Global markets",
                    "coverage_focus": "补充跨市场编辑部快讯与风险叙事。",
                },
            ],
        }

    def get_health_summary(self):
        return {
            "source_health": {
                "total_sources": 2,
                "mission_critical_sources": 1,
                "whitelisted_sources": 2,
                "enabled_mission_critical_sources": 1,
                "coverage_tier_counts": {
                    "official_policy": 1,
                    "editorial_media": 1,
                },
                "source_class_counts": {
                    "policy": 1,
                    "market": 1,
                },
                "coverage_gaps": [
                    "官方数据源覆盖不足",
                    "当前没有日历型 mission-critical 源",
                ],
            },
            "pipeline_health": {
                "brief_count": 1,
                "latest_brief_id": self._brief.brief_id,
                "latest_digest_date": self._brief.digest_date,
                "latest_generated_at": self._brief.generated_at,
            },
            "content_quality": {
                "top_event_count": 1,
                "average_confidence": 0.84,
                "events_needing_confirmation": 0,
                "events_with_primary_sources": 1,
                "events_without_primary_sources": 0,
                "duplicate_core_fact_count": 0,
                "minimum_evidence_gate_passed": True,
                "duplication_gate_passed": True,
            },
            "delivery_health": {
                "notification_available": False,
                "configured_channels": [],
                "channel_names": "",
                "overnight_brief_enabled": False,
            },
        }

    def submit_feedback(
        self,
        *,
        target_type: str,
        target_id: str,
        brief_id: str | None,
        event_id: str | None,
        feedback_type: str,
        comment: str,
    ):
        return {
            "feedback_id": 1,
            "target_type": target_type,
            "target_id": target_id,
            "brief_id": brief_id,
            "event_id": event_id,
            "feedback_type": feedback_type,
            "comment": comment,
            "status": "pending_review",
            "created_at": "2026-04-05T08:05:00",
        }

    def list_feedback(self, *, page: int, limit: int, target_type: str | None, status: str | None):
        return {
            "page": page,
            "limit": limit,
            "total": 1,
            "items": [
                {
                    "feedback_id": 1,
                    "target_type": target_type or "event",
                    "target_id": "event_123",
                    "brief_id": "brief_abc",
                    "event_id": "event_123",
                    "feedback_type": "priority_too_high",
                    "comment": "This event felt less important than the overnight headline.",
                    "status": status or "pending_review",
                    "created_at": "2026-04-05T08:05:00",
                }
            ],
        }

    def update_feedback_status(self, feedback_id: int, *, status: str):
        if feedback_id != 1:
            raise LookupError(feedback_id)
        return {
            "feedback_id": feedback_id,
            "target_type": "event",
            "target_id": "event_123",
            "brief_id": "brief_abc",
            "event_id": "event_123",
            "feedback_type": "priority_too_high",
            "comment": "This event felt less important than the overnight headline.",
            "status": status,
            "created_at": "2026-04-05T08:05:00",
        }


@pytest.fixture()
def client_with_data(client: TestClient) -> TestClient:
    fake_service = FakeOvernightService()
    client.app.dependency_overrides[get_overnight_service] = lambda: fake_service
    try:
        yield client
    finally:
        client.app.dependency_overrides.clear()


def test_get_current_overnight_brief(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/brief/latest")
    assert response.status_code == 200
    payload = response.json()
    assert "topline" in payload
    assert payload["today_watchlist"][0]["bucket_key"] == "needs-confirmation"
    assert payload["today_watchlist"][1]["bucket_key"] == "awaiting-pricing"
    assert payload["today_watchlist"][1]["items"][0]["event_id"] == "event_123"
    assert payload["today_watchlist"][1]["items"][0]["trigger"]
    assert payload["today_watchlist"][1]["items"][0]["action"]


def test_get_latest_overnight_brief_delta(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/brief/latest/delta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_id"]
    assert payload["new_events"][0]["delta_type"] == "new"
    assert payload["intensified_events"][0]["current_priority_level"] == "P0"


def test_get_overnight_brief_delta_by_id(client_with_data: TestClient) -> None:
    latest_response = client_with_data.get("/api/v1/overnight/brief/latest")
    brief_id = latest_response.json()["brief_id"]

    response = client_with_data.get(f"/api/v1/overnight/briefs/{brief_id}/delta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_id"] == brief_id
    assert payload["cooling_events"][0]["delta_type"] == "cooling"


def test_get_overnight_event_detail(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/events/event_123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == "event_123"
    assert payload["source_links"] == ["https://www.ustr.gov/example-release"]
    assert payload["evidence_items"][0]["source_name"] == "USTR Press Releases"
    assert payload["evidence_items"][0]["source_type"] == "official"
    assert payload["judgment_summary"] == "这条更像盘前主线预热，先看自主可控和航运替代链是否同步确认。"
    assert payload["judgment_mode"] == "heuristic"


def test_get_overnight_event_detail_supports_brief_override(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/events/event_123?brief_id=brief_hist")
    assert response.status_code == 200
    payload = response.json()
    assert payload["priority_level"] == "P1"
    assert payload["source_links"] == ["https://www.ustr.gov/historical-release"]
    assert payload["evidence_items"][0]["headline"] == "Historical tariff follow-up"
    assert payload["judgment_summary"] == "这条更像历史晨报里的延续线，先看国产替代是否再次放量。"


def test_get_overnight_brief_history(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/history?page=1&limit=10")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["brief_id"]


def test_get_overnight_brief_detail_by_id(client_with_data: TestClient) -> None:
    latest_response = client_with_data.get("/api/v1/overnight/brief/latest")
    brief_id = latest_response.json()["brief_id"]

    response = client_with_data.get(f"/api/v1/overnight/briefs/{brief_id}")

    assert response.status_code == 200
    assert response.json()["brief_id"] == brief_id


def test_get_overnight_brief_detail_upgrades_legacy_watchlist_shape(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        MorningExecutiveBrief(
            brief_id="legacy-brief",
            digest_date="2026-04-03",
            cutoff_time="07:30",
            topline="Legacy tariff shock drove overnight attention.",
            top_events=[
                {
                    "event_id": "legacy-event",
                    "priority_level": "P0",
                    "core_fact": "Legacy tariff shock",
                    "summary": "Older stored brief without structured watchlist.",
                    "why_it_matters": "Trade policy was still the main overnight driver.",
                    "confidence": 0.84,
                }
            ],
            cross_asset_snapshot=[],
            likely_beneficiaries=[],
            likely_pressure_points=[],
            what_may_get_more_expensive=[],
            policy_radar=[],
            macro_radar=[],
            sector_transmission=[],
            risk_board=[],
            need_confirmation=[],
            today_watchlist=[
                {
                    "title": "待定价",
                    "items": ["Legacy tariff shock"],
                }
            ],
            primary_sources=[],
            evidence_links=[],
            generated_at="2026-04-03T07:31:00",
            version_no=1,
        )
    )

    response = client.get("/api/v1/overnight/briefs/legacy-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["today_watchlist"][1]["bucket_key"] == "awaiting-pricing"
    assert payload["today_watchlist"][1]["items"][0]["core_fact"] == "Legacy tariff shock"


def test_get_overnight_sources(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/sources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["mission_critical"] == 1
    assert payload["items"][0]["source_id"] == "whitehouse_news"
    assert payload["items"][0]["coverage_tier"] == "official_policy"
    assert payload["items"][0]["region_focus"] == "US policy"
    assert payload["items"][0]["coverage_focus"]


def test_get_overnight_health(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_health"]["total_sources"] == 2
    assert payload["pipeline_health"]["brief_count"] == 1
    assert payload["content_quality"]["average_confidence"] == 0.84
    assert payload["content_quality"]["minimum_evidence_gate_passed"] is True
    assert payload["delivery_health"]["notification_available"] is False
    assert payload["source_health"]["enabled_mission_critical_sources"] == 1
    assert payload["source_health"]["coverage_tier_counts"]["official_policy"] == 1
    assert payload["source_health"]["source_class_counts"]["policy"] == 1
    assert payload["source_health"]["coverage_gaps"][0] == "官方数据源覆盖不足"


def test_submit_overnight_feedback(client_with_data: TestClient) -> None:
    response = client_with_data.post(
        "/api/v1/overnight/feedback",
        json={
            "target_type": "event",
            "target_id": "event_123",
            "brief_id": "brief_abc",
            "event_id": "event_123",
            "feedback_type": "priority_too_high",
            "comment": "This event felt less important than the overnight headline.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback_id"] == 1
    assert payload["status"] == "pending_review"
    assert payload["feedback_type"] == "priority_too_high"


def test_list_overnight_feedback_queue(client_with_data: TestClient) -> None:
    response = client_with_data.get(
        "/api/v1/overnight/feedback?page=1&limit=20&target_type=event&status=pending_review"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["target_type"] == "event"
    assert payload["items"][0]["status"] == "pending_review"


def test_update_overnight_feedback_status(client_with_data: TestClient) -> None:
    response = client_with_data.patch(
        "/api/v1/overnight/feedback/1",
        json={"status": "reviewed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback_id"] == 1
    assert payload["status"] == "reviewed"


def test_get_overnight_event_history_from_persisted_briefs(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    older_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_old",
                core_fact="USTR announced new tariffs",
                priority_level="P1",
                summary="Older tariff escalation coverage.",
                why_it_matters="Trade policy remained active.",
                confidence=0.72,
                source_links=["https://www.ustr.gov/example-release-old"],
            )
        ],
        direction_board=[{"title": "Tariff beneficiaries", "items": ["US rail"]}],
        price_pressure_board=[],
        digest_date="2026-04-04",
        cutoff_time="07:30",
        generated_at="2026-04-04T07:31:00",
    )
    latest_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_new",
                core_fact="USTR announced new tariffs",
                priority_level="P0",
                summary="Latest tariff escalation coverage.",
                why_it_matters="Trade policy became the main overnight driver.",
                confidence=0.84,
                source_links=["https://www.ustr.gov/example-release-new"],
            )
        ],
        direction_board=[],
        price_pressure_board=[{"title": "Import costs", "items": ["Copper"]}],
        digest_date="2026-04-05",
        cutoff_time="07:30",
        generated_at="2026-04-05T07:31:00",
    )
    repo.save_morning_brief(older_brief)
    repo.save_morning_brief(latest_brief)

    response = client.get("/api/v1/overnight/history/events?page=1&limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["core_fact"] == "USTR announced new tariffs"
    assert payload["items"][0]["occurrence_count"] == 2
    assert payload["items"][0]["latest_brief_id"] == latest_brief.brief_id
    assert payload["items"][0]["occurrences"][0]["event_id"] == "event_new"


def test_get_overnight_brief_delta_from_persisted_briefs(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    previous_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_prev_tariff",
                core_fact="USTR announced new tariffs",
                priority_level="P1",
                summary="Earlier tariff escalation coverage.",
                why_it_matters="Trade policy stayed active.",
                confidence=0.72,
                source_links=["https://www.ustr.gov/example-release-old"],
            ),
            RankedEvent(
                event_id="event_prev_fed",
                core_fact="Fed speakers signaled patience on cuts",
                priority_level="P1",
                summary="Fed commentary stayed hawkish.",
                why_it_matters="Rates path stayed restrictive.",
                confidence=0.78,
                source_links=["https://www.federalreserve.gov/example-fed"],
            ),
            RankedEvent(
                event_id="event_prev_brent",
                core_fact="Brent crude extended overnight rally",
                priority_level="P1",
                summary="Oil was the cleanest price-pressure line.",
                why_it_matters="Freight and input-cost pressure kept building.",
                confidence=0.81,
                source_links=["https://www.reuters.com/example-brent"],
            ),
            RankedEvent(
                event_id="event_prev_chip",
                core_fact="Older chip supply story faded",
                priority_level="P2",
                summary="This chip story was still on the board yesterday.",
                why_it_matters="It mattered less than trade policy.",
                confidence=0.74,
                source_links=["https://www.reuters.com/example-chip"],
            ),
        ],
        direction_board=[],
        price_pressure_board=[],
        digest_date="2026-04-05",
        cutoff_time="07:30",
        generated_at="2026-04-05T07:31:00",
    )
    latest_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_now_tariff",
                core_fact="USTR announced new tariffs",
                priority_level="P0",
                summary="Latest tariff escalation coverage.",
                why_it_matters="Trade policy became the main overnight driver.",
                confidence=0.84,
                source_links=["https://www.ustr.gov/example-release-new"],
            ),
            RankedEvent(
                event_id="event_now_fed",
                core_fact="Fed speakers signaled patience on cuts",
                priority_level="P1",
                summary="Fed commentary stayed hawkish.",
                why_it_matters="Rates path stayed restrictive.",
                confidence=0.8,
                source_links=["https://www.federalreserve.gov/example-fed"],
            ),
            RankedEvent(
                event_id="event_now_brent",
                core_fact="Brent crude extended overnight rally",
                priority_level="P2",
                summary="Oil still rose but no longer dominated the brief.",
                why_it_matters="Price pressure stayed present but less urgent.",
                confidence=0.7,
                source_links=["https://www.reuters.com/example-brent"],
            ),
            RankedEvent(
                event_id="event_now_cpi",
                core_fact="BLS CPI release is due later today",
                priority_level="P2",
                summary="Macro calendar risk remains in front of the US open.",
                why_it_matters="Data surprise risk could reprice rates and cyclicals.",
                confidence=0.69,
                source_links=["https://www.bls.gov/example-cpi"],
            ),
        ],
        direction_board=[],
        price_pressure_board=[],
        digest_date="2026-04-06",
        cutoff_time="07:30",
        generated_at="2026-04-06T07:31:00",
    )
    repo.save_morning_brief(previous_brief)
    repo.save_morning_brief(latest_brief)

    response = client.get("/api/v1/overnight/brief/latest/delta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_id"] == latest_brief.brief_id
    assert payload["previous_brief_id"] == previous_brief.brief_id
    assert payload["new_events"][0]["core_fact"] == "BLS CPI release is due later today"
    assert payload["intensified_events"][0]["core_fact"] == "USTR announced new tariffs"
    assert payload["steady_events"][0]["core_fact"] == "Fed speakers signaled patience on cuts"
    assert payload["cooling_events"][0]["core_fact"] == "Brent crude extended overnight rally"
    assert payload["dropped_events"][0]["core_fact"] == "Older chip supply story faded"


def test_get_overnight_brief_delta_recovers_from_half_initialized_database_singleton(
    client: TestClient,
) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_prev_tariff",
                    core_fact="USTR announced new tariffs",
                    priority_level="P1",
                    summary="Earlier tariff escalation coverage.",
                    why_it_matters="Trade policy stayed active.",
                    confidence=0.72,
                    source_links=["https://www.ustr.gov/example-release-old"],
                )
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )
    )
    latest_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_now_tariff",
                core_fact="USTR announced new tariffs",
                priority_level="P0",
                summary="Latest tariff escalation coverage.",
                why_it_matters="Trade policy became the main overnight driver.",
                confidence=0.84,
                source_links=["https://www.ustr.gov/example-release-new"],
            )
        ],
        direction_board=[],
        price_pressure_board=[],
        digest_date="2026-04-06",
        cutoff_time="07:30",
        generated_at="2026-04-06T07:31:00",
    )
    repo.save_morning_brief(latest_brief)

    DatabaseManager.reset_instance()
    broken_instance = DatabaseManager.__new__(DatabaseManager)
    assert broken_instance is DatabaseManager._instance
    assert not getattr(broken_instance, "_initialized", False)

    response = client.get("/api/v1/overnight/brief/latest/delta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_id"] == latest_brief.brief_id
    assert payload["intensified_events"][0]["core_fact"] == "USTR announced new tariffs"


def test_get_overnight_topic_history_from_persisted_briefs(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_old",
                    core_fact="USTR announced new tariffs",
                    priority_level="P1",
                    summary="Older tariff escalation coverage.",
                    why_it_matters="Trade policy remained active.",
                    confidence=0.72,
                    source_links=["https://www.ustr.gov/example-release-old"],
                )
            ],
            direction_board=[{"title": "Tariff beneficiaries", "items": ["US rail"]}],
            price_pressure_board=[],
            digest_date="2026-04-04",
            cutoff_time="07:30",
            generated_at="2026-04-04T07:31:00",
        )
    )
    latest_brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="event_new",
                core_fact="USTR announced new tariffs",
                priority_level="P0",
                summary="Latest tariff escalation coverage.",
                why_it_matters="Trade policy became the main overnight driver.",
                confidence=0.84,
                source_links=["https://www.ustr.gov/example-release-new"],
            )
        ],
        direction_board=[],
        price_pressure_board=[{"title": "Import costs", "items": ["Copper"]}],
        digest_date="2026-04-05",
        cutoff_time="07:30",
        generated_at="2026-04-05T07:31:00",
    )
    repo.save_morning_brief(latest_brief)

    response = client.get("/api/v1/overnight/history/topics?page=1&limit=20")

    assert response.status_code == 200
    payload = response.json()
    topic_map = {item["topic_key"]: item for item in payload["items"]}
    assert "policy-radar" in topic_map
    assert "beneficiaries" in topic_map
    assert "price-pressure" in topic_map
    assert topic_map["policy-radar"]["occurrence_count"] == 2
    assert topic_map["price-pressure"]["latest_brief_id"] == latest_brief.brief_id


def test_get_overnight_brief_history_filters_by_query(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_tariff",
                    core_fact="USTR announced new tariffs",
                    priority_level="P1",
                    summary="Tariff escalation coverage.",
                    why_it_matters="Trade policy pressure was already building.",
                    confidence=0.72,
                    source_links=["https://www.ustr.gov/example-release-old"],
                )
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-04",
            cutoff_time="07:30",
            generated_at="2026-04-04T07:31:00",
        )
    )
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_fed",
                    core_fact="Fed speakers signaled patience on cuts",
                    priority_level="P1",
                    summary="Rates commentary coverage.",
                    why_it_matters="Macro tone stayed restrictive.",
                    confidence=0.81,
                    source_links=["https://www.federalreserve.gov/example-speech"],
                )
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )
    )

    response = client.get("/api/v1/overnight/history?page=1&limit=20&q=tariff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert "tariff" in payload["items"][0]["topline"].lower()


def test_get_overnight_event_history_filters_by_query(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_tariff",
                    core_fact="USTR announced new tariffs",
                    priority_level="P1",
                    summary="Tariff escalation coverage.",
                    why_it_matters="Trade policy pressure was already building.",
                    confidence=0.72,
                    source_links=["https://www.ustr.gov/example-release-old"],
                ),
                RankedEvent(
                    event_id="event_fed",
                    core_fact="Fed speakers signaled patience on cuts",
                    priority_level="P1",
                    summary="Rates commentary coverage.",
                    why_it_matters="Macro tone stayed restrictive.",
                    confidence=0.81,
                    source_links=["https://www.federalreserve.gov/example-speech"],
                ),
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )
    )

    response = client.get("/api/v1/overnight/history/events?page=1&limit=20&q=tariff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["core_fact"] == "USTR announced new tariffs"


def test_get_overnight_topic_history_filters_by_query(client: TestClient) -> None:
    repo = OvernightRepository(DatabaseManager.get_instance())
    repo.save_morning_brief(
        build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_tariff",
                    core_fact="USTR announced new tariffs",
                    priority_level="P1",
                    summary="Tariff escalation coverage.",
                    why_it_matters="Trade policy pressure was already building.",
                    confidence=0.72,
                    source_links=["https://www.ustr.gov/example-release-old"],
                )
            ],
            direction_board=[{"title": "受益方向", "items": ["Domestic substitution"]}],
            price_pressure_board=[{"title": "可能涨价", "items": ["Copper"]}],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )
    )

    response = client.get("/api/v1/overnight/history/topics?page=1&limit=20&q=policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["topic_key"] == "policy-radar"


def test_get_current_overnight_brief_returns_404_when_no_brief_exists(client: TestClient) -> None:
    response = client.get("/api/v1/overnight/brief/latest")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_get_overnight_event_detail_returns_404_when_missing(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/events/missing-event")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_get_overnight_brief_detail_returns_404_when_missing(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/briefs/missing-brief")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
