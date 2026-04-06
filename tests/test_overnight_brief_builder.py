# -*- coding: utf-8 -*-
"""Tests for overnight brief rendering and analysis packets."""

from __future__ import annotations

from src.notification import NotificationService
from src.overnight.analysis import PolicyAnalystOutput, SkepticalReviewPacket
from src.overnight.brief_builder import (
    EvidenceLedgerView,
    FlashAlert,
    RankedEvent,
    build_deep_dive_report,
    build_flash_alert,
    build_morning_brief,
    serialize_evidence_ledger,
)


def make_ranked_event(
    *,
    core_fact: str = "USTR announced new tariffs",
    priority_level: str = "P0",
    confidence: float = 0.82,
    why_it_matters: str = "Trade policy escalation became the main overnight driver.",
    market_reaction: str = "USDCNH weakened first in cross-asset pricing.",
) -> RankedEvent:
    return RankedEvent(
        event_id="evt-001",
        core_fact=core_fact,
        priority_level=priority_level,
        summary="Tariff escalation was published by USTR.",
        why_it_matters=why_it_matters,
        confidence=confidence,
        market_reaction=market_reaction,
        source_links=["https://www.ustr.gov/example-release"],
    )


def make_flash_alert() -> FlashAlert:
    return FlashAlert(
        alert_id="alert-001",
        event_id="evt-001",
        headline="USTR announced new tariffs",
        priority_level="P0",
        watch_next=[
            "Official tariff schedule release timing",
            "Cross-asset follow-through in Asia open",
        ],
        confidence=0.8,
    )


def test_brief_builder_renders_topline_and_price_pressure() -> None:
    brief = build_morning_brief(
        events=[make_ranked_event(core_fact="USTR announced new tariffs", priority_level="P0")],
        direction_board=[{"title": "Policy beneficiaries", "items": ["defense"]}],
        price_pressure_board=[{"title": "直接涨价", "items": ["Brent crude"]}],
    )
    assert "USTR announced new tariffs" in brief.topline
    assert "main overnight driver" in brief.topline
    assert "USDCNH weakened first" in brief.topline
    assert brief.what_may_get_more_expensive[0]["items"] == ["Brent crude"]


def test_notification_service_formats_flash_alert() -> None:
    content = NotificationService().format_overnight_flash_alert(make_flash_alert())
    assert "watch next" in content.lower()


def test_notification_service_formats_morning_brief_sections() -> None:
    content = NotificationService().format_overnight_brief(
        build_morning_brief(
            events=[make_ranked_event()],
            direction_board=[{"title": "Policy beneficiaries", "items": ["defense"]}],
            price_pressure_board=[{"title": "直接涨价", "items": ["Brent crude"]}],
        )
    )

    assert "Morning Executive Brief" in content
    assert "Likely Beneficiaries" in content
    assert "Primary Sources" in content
    assert "Trade policy escalation became the main overnight driver." in content
    assert "https://www.ustr.gov/example-release" in content


def test_analysis_packets_capture_policy_and_skeptical_review_state() -> None:
    policy = PolicyAnalystOutput(
        event_id="evt-001",
        policy_status="announced",
        issuing_authority="USTR",
        immediate_implications=["Higher import costs for steel"],
        confidence=0.78,
    )
    skeptical = SkepticalReviewPacket(
        event_id="evt-001",
        challenge_points=["Pending implementation details"],
        downgraded_confidence=0.63,
    )

    assert policy.immediate_implications == ["Higher import costs for steel"]
    assert skeptical.challenge_points == ["Pending implementation details"]


def test_build_flash_alert_assigns_alert_id_and_default_watch_next() -> None:
    alert = build_flash_alert(make_ranked_event(), watch_next=[])

    assert alert.alert_id
    assert alert.watch_next == ["Cross-asset follow-through during Asia/Europe open."]


def test_morning_brief_builds_all_watchlist_buckets() -> None:
    brief = build_morning_brief(
        events=[
            make_ranked_event(priority_level="P0", confidence=0.61),
            make_ranked_event(
                core_fact="BLS CPI release is due later today",
                priority_level="P2",
                confidence=0.91,
            ),
        ],
        direction_board=[],
        price_pressure_board=[],
    )

    assert [bucket["bucket_key"] for bucket in brief.today_watchlist] == [
        "needs-confirmation",
        "awaiting-pricing",
        "scheduled-release",
        "monitoring",
    ]
    assert [bucket["title"] for bucket in brief.today_watchlist] == ["待确认", "待定价", "待发布", "待观察"]

    confirmation_item = brief.today_watchlist[0]["items"][0]
    assert confirmation_item["event_id"] == "evt-001"
    assert confirmation_item["priority_level"] == "P0"
    assert confirmation_item["confidence"] == 0.61
    assert confirmation_item["trigger"]
    assert confirmation_item["action"]

    release_item = brief.today_watchlist[2]["items"][0]
    assert release_item["core_fact"] == "BLS CPI release is due later today"
    assert release_item["event_id"] == "evt-001"


def test_morning_brief_sorts_top_events_by_priority() -> None:
    brief = build_morning_brief(
        events=[
            make_ranked_event(core_fact="Lower-priority macro note", priority_level="P2", confidence=0.90),
            make_ranked_event(core_fact="Top tariff shock", priority_level="P0", confidence=0.70),
        ],
        direction_board=[],
        price_pressure_board=[],
    )

    assert brief.top_events[0]["core_fact"] == "Top tariff shock"


def test_morning_brief_honors_digest_metadata_overrides() -> None:
    brief = build_morning_brief(
        events=[make_ranked_event()],
        direction_board=[],
        price_pressure_board=[],
        digest_date="2026-04-04",
        cutoff_time="06:45",
        generated_at="2026-04-04T06:46:00",
    )

    assert brief.digest_date == "2026-04-04"
    assert brief.cutoff_time == "06:45"
    assert brief.generated_at == "2026-04-04T06:46:00"


def test_deep_dive_report_renders_event_cards() -> None:
    report = build_deep_dive_report(events=[make_ranked_event()])

    assert report.event_cards[0]["core_fact"] == "USTR announced new tariffs"


def test_evidence_ledger_serialization_preserves_ids() -> None:
    payload = serialize_evidence_ledger(
        EvidenceLedgerView(
            ledger_view_id="ledger-001",
            digest_date="2026-04-05",
            event_ids=["evt-001"],
            source_item_ids=[10],
            document_family_ids=[20],
            official_evidence_ids=[30],
            media_evidence_ids=[40],
            market_snapshot_ids=[50],
            analysis_artifact_ids=["analysis-001"],
        )
    )

    assert payload["event_ids"] == ["evt-001"]
    assert payload["analysis_artifact_ids"] == ["analysis-001"]
