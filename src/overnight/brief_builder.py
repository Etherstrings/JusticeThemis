# -*- coding: utf-8 -*-
"""Builders for overnight flash alerts and morning executive briefs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from uuid import uuid4


@dataclass(frozen=True)
class RankedEvent:
    event_id: str
    core_fact: str
    priority_level: str
    summary: str = ""
    why_it_matters: str = ""
    confidence: float = 0.0
    market_reaction: str = ""
    source_links: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlashAlert:
    event_id: str
    headline: str
    priority_level: str
    watch_next: list[str]
    confidence: float
    core_fact: str = ""
    market_reaction: str = ""
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    sent_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass(frozen=True)
class MorningExecutiveBrief:
    brief_id: str
    digest_date: str
    cutoff_time: str
    topline: str
    top_events: list[dict[str, object]]
    cross_asset_snapshot: list[dict[str, object]]
    likely_beneficiaries: list[dict[str, object]]
    likely_pressure_points: list[dict[str, object]]
    what_may_get_more_expensive: list[dict[str, object]]
    policy_radar: list[dict[str, object]]
    macro_radar: list[dict[str, object]]
    sector_transmission: list[dict[str, object]]
    risk_board: list[dict[str, object]]
    need_confirmation: list[dict[str, object]]
    today_watchlist: list[dict[str, object]]
    primary_sources: list[dict[str, object]]
    evidence_links: list[dict[str, object]]
    generated_at: str
    version_no: int = 1


@dataclass(frozen=True)
class DeepDiveReport:
    report_id: str
    digest_date: str
    event_cards: list[dict[str, object]]
    appendix: list[dict[str, object]]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    version_no: int = 1


@dataclass(frozen=True)
class EvidenceLedgerView:
    ledger_view_id: str
    digest_date: str
    event_ids: list[str]
    source_item_ids: list[int]
    document_family_ids: list[int]
    official_evidence_ids: list[int]
    media_evidence_ids: list[int]
    market_snapshot_ids: list[int]
    analysis_artifact_ids: list[str]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    version_no: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_morning_brief(
    *,
    events: list[RankedEvent],
    direction_board: list[dict],
    price_pressure_board: list[dict],
    digest_date: str | None = None,
    cutoff_time: str = "07:30",
    generated_at: str | None = None,
) -> MorningExecutiveBrief:
    sorted_events = sorted(events, key=_event_sort_key)
    topline = synthesize_topline(sorted_events)
    top_events = [render_event_summary(event) for event in sorted_events[:10]]
    need_confirmation = [
        render_event_summary(event)
        for event in sorted_events
        if event.confidence < 0.7
    ]

    return MorningExecutiveBrief(
        brief_id=str(uuid4()),
        digest_date=digest_date or date.today().isoformat(),
        cutoff_time=cutoff_time,
        topline=topline,
        top_events=top_events,
        cross_asset_snapshot=[],
        likely_beneficiaries=list(direction_board),
        likely_pressure_points=[],
        what_may_get_more_expensive=list(price_pressure_board),
        policy_radar=_build_policy_radar(sorted_events),
        macro_radar=[],
        sector_transmission=[],
        risk_board=[],
        need_confirmation=need_confirmation,
        today_watchlist=_build_today_watchlist(sorted_events),
        primary_sources=_build_primary_sources(sorted_events),
        evidence_links=[],
        generated_at=generated_at or datetime.now().isoformat(timespec="seconds"),
        version_no=1,
    )


def synthesize_topline(events: list[RankedEvent]) -> str:
    if not events:
        return "No high-priority overnight catalysts were confirmed before cutoff."

    lead = sorted(events, key=_event_sort_key)[0]
    driver = lead.why_it_matters or "The main overnight driver remained unclear."
    first_priced_object = lead.market_reaction or "Cross-asset follow-through is still forming."
    return f"{lead.core_fact} led overnight flow. Driver: {driver} First priced object: {first_priced_object}"


def render_event_summary(event: RankedEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "priority_level": event.priority_level,
        "core_fact": event.core_fact,
        "summary": event.summary,
        "why_it_matters": event.why_it_matters,
        "confidence": event.confidence,
    }


def build_flash_alert(event: RankedEvent, *, watch_next: list[str] | None = None) -> FlashAlert:
    watch_items = list(watch_next or [])
    if not watch_items:
        watch_items.append("Cross-asset follow-through during Asia/Europe open.")

    return FlashAlert(
        event_id=event.event_id,
        headline=event.core_fact,
        priority_level=event.priority_level,
        watch_next=watch_items,
        confidence=event.confidence,
        core_fact=event.core_fact,
        market_reaction=event.market_reaction,
    )


def build_deep_dive_report(*, events: list[RankedEvent]) -> DeepDiveReport:
    return DeepDiveReport(
        report_id=str(uuid4()),
        digest_date=date.today().isoformat(),
        event_cards=[_render_deep_dive_card(event) for event in events],
        appendix=_build_primary_sources(events),
    )


def serialize_evidence_ledger(view: EvidenceLedgerView) -> dict[str, object]:
    return view.to_dict()


def _build_policy_radar(events: list[RankedEvent]) -> list[dict[str, object]]:
    radar: list[dict[str, object]] = []
    for event in events:
        if "policy" in event.summary.lower() or "ustr" in event.core_fact.lower():
            radar.append(
                {
                    "event_id": event.event_id,
                    "title": event.core_fact,
                    "priority_level": event.priority_level,
                }
            )
    return radar


def _build_today_watchlist(events: list[RankedEvent]) -> list[dict[str, object]]:
    confirmation_items = [
        event.core_fact
        for event in events
        if event.confidence < 0.7
    ]
    pricing_items = [
        event.core_fact
        for event in events
        if event.priority_level in {"P0", "P1"}
    ]
    release_items = [
        event.core_fact
        for event in events
        if _is_release_watch(event)
    ]
    observation_items = [
        event.core_fact
        for event in events
        if event.core_fact not in set(confirmation_items + pricing_items + release_items)
    ]
    if not events:
        observation_items = ["Overnight flow was light; monitor open-driven repricing."]

    return [
        {
            "title": "待确认",
            "items": confirmation_items,
        },
        {
            "title": "待定价",
            "items": pricing_items,
        },
        {
            "title": "待发布",
            "items": release_items,
        },
        {
            "title": "待观察",
            "items": observation_items,
        },
    ]


def _build_primary_sources(events: list[RankedEvent]) -> list[dict[str, object]]:
    primary_sources: list[dict[str, object]] = []
    for event in events:
        if not event.source_links:
            continue
        primary_sources.append(
            {
                "event_id": event.event_id,
                "links": list(event.source_links),
            }
        )
    return primary_sources


def _render_deep_dive_card(event: RankedEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "title": event.core_fact,
        "core_fact": event.core_fact,
        "summary": event.summary,
        "why_it_matters": event.why_it_matters,
        "market_reaction": event.market_reaction,
        "confidence": event.confidence,
        "source_links": list(event.source_links),
    }


def _is_release_watch(event: RankedEvent) -> bool:
    text = " ".join((event.core_fact, event.summary)).lower()
    return any(token in text for token in ("release", "schedule", "due", "calendar"))


def _event_sort_key(event: RankedEvent) -> tuple[int, float]:
    return (_priority_rank(event.priority_level), -float(event.confidence))


def _priority_rank(priority_level: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get((priority_level or "").upper(), 4)


__all__ = [
    "DeepDiveReport",
    "EvidenceLedgerView",
    "FlashAlert",
    "MorningExecutiveBrief",
    "RankedEvent",
    "build_deep_dive_report",
    "build_flash_alert",
    "build_morning_brief",
    "render_event_summary",
    "serialize_evidence_ledger",
    "synthesize_topline",
]
