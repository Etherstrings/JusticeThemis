# -*- coding: utf-8 -*-
"""Webhook delivery for overnight pipeline outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

import requests


class WebhookTransport(Protocol):
    def post(self, *, url: str, json: dict[str, Any], timeout: float) -> Any:
        """Post one JSON webhook payload."""


class RequestsWebhookTransport:
    def post(self, *, url: str, json: dict[str, Any], timeout: float) -> requests.Response:
        response = requests.post(url, json=json, timeout=timeout)
        response.raise_for_status()
        return response


class PipelineDeliveryService:
    def __init__(self, *, transport: WebhookTransport | None = None) -> None:
        self.transport = transport or RequestsWebhookTransport()

    def build_webhook_payload(
        self,
        *,
        summary: dict[str, Any],
        health: dict[str, Any],
        blueprint: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "event_type": "overnight_pipeline_delivery",
            "delivered_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "health": health,
            "blueprint": blueprint,
            "artifacts": [
                {
                    "artifact_type": str(artifact.get("artifact_type", "")).strip(),
                    "content_type": str(artifact.get("content_type", "")).strip(),
                    "path": str(artifact.get("path", "")).strip(),
                    "filename_hint": str(artifact.get("filename_hint", "")).strip(),
                }
                for artifact in artifacts
            ],
            "artifact_payloads": {
                str(artifact.get("artifact_type", "")).strip(): artifact.get("payload")
                for artifact in artifacts
                if str(artifact.get("artifact_type", "")).strip()
            },
        }

    def deliver_webhook(
        self,
        *,
        webhook_url: str,
        summary: dict[str, Any],
        health: dict[str, Any],
        blueprint: dict[str, Any],
        artifacts: list[dict[str, Any]],
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        payload = self.build_webhook_payload(
            summary=summary,
            health=health,
            blueprint=blueprint,
            artifacts=artifacts,
        )
        response = self.transport.post(
            url=str(webhook_url).strip(),
            json=payload,
            timeout=float(timeout),
        )
        return {
            "status": "ok",
            "status_code": int(getattr(response, "status_code", 0) or 0),
            "artifact_count": len(artifacts),
            "webhook_url": str(webhook_url).strip(),
            "response_preview": str(getattr(response, "text", "") or "")[:200],
        }
