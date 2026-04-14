# -*- coding: utf-8 -*-
"""Tests for pipeline delivery webhook support."""

from __future__ import annotations

from app.services.pipeline_delivery import PipelineDeliveryService


class FakeResponse:
    def __init__(self, status_code: int = 202, text: str = "accepted") -> None:
        self.status_code = status_code
        self.text = text


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(self, *, url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()


def test_pipeline_delivery_service_builds_and_posts_webhook_payload() -> None:
    transport = FakeTransport()
    service = PipelineDeliveryService(transport=transport)

    result = service.deliver_webhook(
        webhook_url="https://example.com/hook",
        summary={"analysis_date": "2026-04-10", "status": "ok"},
        health={"status": "ok", "blocking_issues": [], "warnings": []},
        blueprint={"source_summary": {"enabled_source_count": 12}},
        artifacts=[
            {
                "artifact_type": "daily_free_prompt",
                "content_type": "application/json",
                "payload": {"messages": [{"role": "system", "content": "free"}]},
            }
        ],
        timeout=8.0,
    )

    assert result["status"] == "ok"
    assert result["status_code"] == 202
    assert result["artifact_count"] == 1
    assert transport.calls[0]["url"] == "https://example.com/hook"
    posted = transport.calls[0]["json"]
    assert posted["event_type"] == "overnight_pipeline_delivery"
    assert posted["summary"]["analysis_date"] == "2026-04-10"
    assert posted["health"]["status"] == "ok"
    assert posted["blueprint"]["source_summary"]["enabled_source_count"] == 12
    assert posted["artifact_payloads"]["daily_free_prompt"]["messages"][0]["content"] == "free"
