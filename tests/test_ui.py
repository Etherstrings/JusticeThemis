# -*- coding: utf-8 -*-
"""Tests for the browser-visible inspection UI."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app


def test_root_serves_inspection_ui() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_ui.db")
        client = TestClient(create_app(database=database))

        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "JusticeThemis" in response.text
        assert "Overnight Signal Desk" in response.text
        assert "Refresh Sources" in response.text


def test_ui_static_assets_are_served() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_ui_assets.db")
        client = TestClient(create_app(database=database))

        response = client.get("/ui/app.js")

        assert response.status_code == 200
        assert "loadDashboard" in response.text
