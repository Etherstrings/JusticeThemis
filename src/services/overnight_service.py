# -*- coding: utf-8 -*-
"""Service layer for overnight brief API endpoints."""

from __future__ import annotations

from typing import Any

from src.config import get_config
from src.overnight.brief_builder import MorningExecutiveBrief
from src.overnight.runner import OvernightRunner
from src.repositories.overnight_repo import OvernightRepository


class OvernightBriefNotFoundError(LookupError):
    """Raised when no overnight brief can be produced yet."""


class OvernightEventNotFoundError(LookupError):
    """Raised when the requested overnight event is not present."""


class OvernightService:
    """Provide overnight brief and event detail payloads for API consumers."""

    def __init__(
        self,
        runner: OvernightRunner | None = None,
        repo: OvernightRepository | None = None,
    ) -> None:
        self.runner = runner or OvernightRunner()
        self.repo = repo or OvernightRepository()

    def get_latest_brief(self) -> MorningExecutiveBrief:
        latest = self.repo.get_latest_morning_brief()
        if latest is not None and latest.top_events:
            return latest

        config = get_config()
        result = self.runner.run_digest(
            cutoff_time=config.overnight_digest_cutoff,
            send_notification=False,
        )
        brief = result.morning_brief
        if not brief.top_events:
            raise OvernightBriefNotFoundError("No overnight brief is available yet.")
        return brief

    def get_brief_by_id(self, brief_id: str) -> MorningExecutiveBrief:
        brief = self.repo.get_morning_brief(brief_id)
        if brief is None:
            raise OvernightBriefNotFoundError(f"Overnight brief not found: {brief_id}")
        return brief

    def get_event_detail(self, event_id: str) -> dict[str, Any]:
        brief = self.get_latest_brief()
        for event in brief.top_events:
            if str(event.get("event_id")) == event_id:
                return {
                    "event_id": event_id,
                    "priority_level": str(event.get("priority_level", "")),
                    "core_fact": str(event.get("core_fact", "")),
                    "summary": str(event.get("summary", "")),
                    "why_it_matters": str(event.get("why_it_matters", "")),
                    "confidence": float(event.get("confidence", 0.0) or 0.0),
                }

        raise OvernightEventNotFoundError(event_id)

    def list_history(self, *, page: int, limit: int) -> dict[str, Any]:
        history = self.repo.list_morning_briefs(page=page, limit=limit)
        if int(history.get("total", 0) or 0) > 0:
            return history

        # Fallback to generating the latest brief once, then reloading persisted history.
        self.get_latest_brief()
        history = self.repo.list_morning_briefs(page=page, limit=limit)
        if int(history.get("total", 0) or 0) > 0:
            return history

        raise OvernightBriefNotFoundError("No overnight brief history is available yet.")
