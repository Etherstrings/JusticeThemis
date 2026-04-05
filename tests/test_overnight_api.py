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
from src.overnight.brief_builder import RankedEvent, build_morning_brief
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

    def list_history(self, *, page: int, limit: int):
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

    def get_event_detail(self, event_id: str):
        if event_id != "event_123":
            raise LookupError(event_id)
        return {
            "event_id": event_id,
            "priority_level": "P0",
            "core_fact": "USTR announced new tariffs",
            "summary": "Tariff escalation was published by USTR.",
            "why_it_matters": "Trade policy became the main overnight driver.",
            "confidence": 0.84,
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
    assert "topline" in response.json()


def test_get_overnight_event_detail(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/events/event_123")
    assert response.status_code == 200
    assert response.json()["event_id"] == "event_123"


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
