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
    env_path.write_text("ADMIN_AUTH_ENABLED=false\n", encoding="utf-8")
    os.environ["ENV_FILE"] = str(env_path)
    Config.reset_instance()

    auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=False)
    auth_patcher.start()

    app = create_app(static_dir=Path(temp_dir.name) / "empty-static")
    api_client = TestClient(app)

    try:
        yield api_client
    finally:
        auth_patcher.stop()
        _reset_auth_globals()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        temp_dir.cleanup()


class FakeOvernightService:
    def get_latest_brief(self):
        return build_morning_brief(
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
    client.app.dependency_overrides[get_overnight_service] = lambda: FakeOvernightService()
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


def test_get_current_overnight_brief_returns_404_when_no_brief_exists(client: TestClient) -> None:
    response = client.get("/api/v1/overnight/brief/latest")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_get_overnight_event_detail_returns_404_when_missing(client_with_data: TestClient) -> None:
    response = client_with_data.get("/api/v1/overnight/events/missing-event")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
