# -*- coding: utf-8 -*-
"""Overnight runner orchestration for morning brief delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any, Callable, Protocol

from sqlalchemy import select

from src.notification import NotificationService
from src.overnight.brief_builder import MorningExecutiveBrief, RankedEvent, build_morning_brief
from src.repositories.overnight_repo import OvernightRepository
from src.storage import DatabaseManager, OvernightEventCluster

logger = logging.getLogger(__name__)


class RankedEventRepository(Protocol):
    def list_ranked_events(self, *, cutoff_time: str) -> list[RankedEvent]:
        """Return ranked overnight events for the given cutoff."""


class OvernightNotifier(Protocol):
    def send_overnight_brief(self, brief: MorningExecutiveBrief) -> bool:
        """Deliver a generated overnight brief."""


@dataclass(frozen=True)
class OvernightRunResult:
    morning_brief: MorningExecutiveBrief
    sent_alerts: list[Any] = field(default_factory=list)


class _DatabaseFallbackRankedEventRepo:
    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self._now_provider = now_provider or datetime.now

    def list_ranked_events(self, *, cutoff_time: str) -> list[RankedEvent]:
        window_start, window_end = _resolve_digest_window(cutoff_time, self._now_provider())
        with self.db.get_session() as session:
            rows = session.execute(
                select(OvernightEventCluster)
                .where(OvernightEventCluster.updated_at >= window_start)
                .where(OvernightEventCluster.updated_at <= window_end)
                .order_by(
                    OvernightEventCluster.updated_at.desc(),
                    OvernightEventCluster.id.desc(),
                )
            ).scalars().all()

        return [
            RankedEvent(
                event_id=f"cluster-{row.id}",
                core_fact=row.core_fact,
                priority_level=_priority_level_for_cluster(row.event_type),
                summary=f"{row.event_type}:{row.event_subtype}",
                why_it_matters=f"Cluster derived from persisted {row.event_type} overnight event.",
                confidence=0.6,
            )
            for row in rows
        ]


class OvernightRunner:
    """Minimal runner: ranked events -> brief -> notification."""

    def __init__(
        self,
        *,
        repo: RankedEventRepository | None = None,
        notifier: OvernightNotifier | None = None,
        storage_repo: OvernightRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if repo is None:
            self.repo: RankedEventRepository = _DatabaseFallbackRankedEventRepo(
                now_provider=now_provider,
            )
        elif hasattr(repo, "list_ranked_events"):
            self.repo = repo
        else:
            logger.warning("Overnight repo does not expose list_ranked_events; using database fallback.")
            self.repo = _DatabaseFallbackRankedEventRepo(
                now_provider=now_provider,
            )

        self.notifier = notifier or NotificationService()
        self.storage_repo = storage_repo or OvernightRepository()

    def run_digest(self, *, cutoff_time: str, send_notification: bool = True) -> OvernightRunResult:
        events = list(self.repo.list_ranked_events(cutoff_time=cutoff_time))
        brief = build_morning_brief(
            events=events,
            direction_board=self._build_directions(events),
            price_pressure_board=self._build_prices(events),
            cutoff_time=cutoff_time,
        )
        self.storage_repo.save_morning_brief(brief)
        if send_notification:
            self.notifier.send_overnight_brief(brief)
        return OvernightRunResult(morning_brief=brief, sent_alerts=[])

    @staticmethod
    def _build_directions(events: list[RankedEvent]) -> list[dict[str, object]]:
        drivers = [event.core_fact for event in events if event.priority_level in {"P0", "P1"} and event.core_fact]
        if not drivers:
            return []
        return [{"title": "Policy direction board", "items": drivers[:5]}]

    @staticmethod
    def _build_prices(events: list[RankedEvent]) -> list[dict[str, object]]:
        price_items = [event.market_reaction for event in events if event.market_reaction]
        if not price_items:
            return []
        return [{"title": "Price pressure board", "items": price_items[:5]}]


__all__ = [
    "OvernightRunner",
    "OvernightRunResult",
]


def _priority_level_for_cluster(event_type: str) -> str:
    normalized = (event_type or "").lower()
    if normalized in {"trade", "policy"}:
        return "P1"
    if normalized in {"macro", "rates"}:
        return "P2"
    return "P3"


def _resolve_digest_window(cutoff_time: str, now: datetime) -> tuple[datetime, datetime]:
    hour_text, minute_text = cutoff_time.split(":", 1)
    cutoff_today = now.replace(
        hour=int(hour_text),
        minute=int(minute_text),
        second=0,
        microsecond=0,
    )
    window_end = cutoff_today if now >= cutoff_today else now
    return (window_end - timedelta(days=1), window_end)
