# -*- coding: utf-8 -*-
"""Tests for overnight runner and scheduler wiring."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from main import _should_run_overnight_mode
from src.config import Config
from src.overnight.brief_builder import RankedEvent
from src.overnight.runner import OvernightRunner
from src.scheduler import Scheduler
from src.storage import DatabaseManager, OvernightEventCluster


class FakeRepo:
    def __init__(self, events: list[RankedEvent]):
        self._events = events
        self.requested_cutoff_time: str | None = None

    @classmethod
    def with_ranked_event(cls) -> "FakeRepo":
        return cls(
            [
                RankedEvent(
                    event_id="evt-001",
                    core_fact="USTR announced new tariffs",
                    priority_level="P0",
                    summary="Tariff escalation was published by USTR.",
                    why_it_matters="Trade policy became the key overnight driver.",
                    confidence=0.84,
                    market_reaction="USDCNH weakened first.",
                    source_links=["https://www.ustr.gov/example-release"],
                )
            ]
        )

    def list_ranked_events(self, *, cutoff_time: str) -> list[RankedEvent]:
        self.requested_cutoff_time = cutoff_time
        return list(self._events)


class FakeNotifier:
    def __init__(self) -> None:
        self.briefs: list[object] = []
        self.flash_alerts: list[object] = []

    def send_overnight_brief(self, brief: object) -> bool:
        self.briefs.append(brief)
        return True

    def send_overnight_flash_alert(self, alert: object) -> bool:
        self.flash_alerts.append(alert)
        return True


@pytest.fixture()
def db_manager() -> DatabaseManager:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_overnight_runner.db")
    previous_db_path = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path

    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()

    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if previous_db_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_db_path
        temp_dir.cleanup()


def test_runner_generates_digest_from_event_updates() -> None:
    repo = FakeRepo.with_ranked_event()
    notifier = FakeNotifier()

    runner = OvernightRunner(repo=repo, notifier=notifier)
    result = runner.run_digest(cutoff_time="07:30")

    assert repo.requested_cutoff_time == "07:30"
    assert result.morning_brief is not None
    assert result.morning_brief.cutoff_time == "07:30"
    assert result.morning_brief.top_events[0]["core_fact"] == "USTR announced new tariffs"
    assert result.sent_alerts == []
    assert notifier.briefs == [result.morning_brief]


def test_runner_can_skip_notification_delivery() -> None:
    notifier = FakeNotifier()
    runner = OvernightRunner(repo=FakeRepo.with_ranked_event(), notifier=notifier)

    result = runner.run_digest(cutoff_time="07:30", send_notification=False)

    assert result.morning_brief is not None
    assert notifier.briefs == []


def test_runner_default_repo_reads_event_clusters_from_database(db_manager: DatabaseManager) -> None:
    reference_now = datetime(2026, 4, 5, 8, 0, 0)
    with db_manager.get_session() as session:
        session.add(
            OvernightEventCluster(
                core_fact="Fed signaled policy continuity overnight.",
                event_type="policy",
                event_subtype="statement",
                created_at=reference_now - timedelta(hours=4),
                updated_at=reference_now - timedelta(hours=4),
            )
        )
        session.commit()
    notifier = FakeNotifier()

    runner = OvernightRunner(
        notifier=notifier,
        now_provider=lambda: reference_now,
    )
    result = runner.run_digest(cutoff_time="07:30")

    assert result.morning_brief.top_events[0]["core_fact"] == "Fed signaled policy continuity overnight."
    assert notifier.briefs == [result.morning_brief]


def test_runner_default_repo_limits_events_to_recent_cutoff_window(db_manager: DatabaseManager) -> None:
    reference_now = datetime(2026, 4, 5, 8, 0, 0)
    with db_manager.get_session() as session:
        session.add_all(
            [
                OvernightEventCluster(
                    core_fact="Fresh overnight trade shock.",
                    event_type="trade",
                    event_subtype="tariff",
                    created_at=reference_now - timedelta(hours=5),
                    updated_at=reference_now - timedelta(hours=5),
                ),
                OvernightEventCluster(
                    core_fact="Stale historical policy item.",
                    event_type="policy",
                    event_subtype="statement",
                    created_at=reference_now - timedelta(days=3),
                    updated_at=reference_now - timedelta(days=3),
                ),
            ]
        )
        session.commit()

    runner = OvernightRunner(
        notifier=FakeNotifier(),
        now_provider=lambda: reference_now,
    )
    result = runner.run_digest(cutoff_time="07:30")

    facts = [event["core_fact"] for event in result.morning_brief.top_events]
    assert facts == ["Fresh overnight trade shock."]


def test_scheduler_registers_overnight_digest_job() -> None:
    scheduler = Scheduler(schedule_time="18:00")

    try:
        scheduler.set_overnight_task(lambda: None, digest_cutoff="07:30", run_immediately=False)

        jobs = scheduler.schedule.get_jobs()

        assert len(jobs) == 1
        assert jobs[0].at_time.strftime("%H:%M") == "07:30"
    finally:
        scheduler.schedule.clear()


def test_scheduler_binds_callbacks_per_job() -> None:
    scheduler = Scheduler(schedule_time="18:00")
    calls: list[str] = []

    try:
        scheduler.set_daily_task(lambda: calls.append("daily"), run_immediately=False)
        scheduler.set_overnight_task(
            lambda: calls.append("overnight"),
            digest_cutoff="07:30",
            run_immediately=False,
        )

        jobs = scheduler.schedule.get_jobs()
        jobs[0].job_func()
        jobs[1].job_func()

        assert calls == ["daily", "overnight"]
    finally:
        scheduler.schedule.clear()


def test_explicit_modes_override_configured_overnight_mode() -> None:
    args = SimpleNamespace(
        overnight_brief=False,
        backtest=True,
        market_review=False,
        webui=False,
        webui_only=False,
        serve=False,
        serve_only=False,
    )
    config = SimpleNamespace(overnight_brief_enabled=True)

    assert _should_run_overnight_mode(args, config) is False
