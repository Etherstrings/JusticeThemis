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
    confirmation_events = [
        event
        for event in events
        if event.confidence < 0.7
    ]
    pricing_events = [
        event
        for event in events
        if event.priority_level in {"P0", "P1"}
    ]
    release_events = [
        event
        for event in events
        if _is_release_watch(event)
    ]

    consumed = {id(event) for event in confirmation_events + pricing_events + release_events}
    observation_events = [
        event
        for event in events
        if id(event) not in consumed
    ]

    return [
        _render_watch_bucket(
            bucket_key="needs-confirmation",
            title="待确认",
            summary="先确认事实和执行细节，再决定是否升级判断。",
            items=[
                _render_watch_item(
                    event,
                    bucket_key="needs-confirmation",
                    label="确认原文与细则",
                    trigger=_coalesce_watch_text(
                        event.summary,
                        "等待更多一手原文、细则或正式执行安排。",
                    ),
                    action="补原文、补细则、补执行时间。确认前不把它当确定结论。",
                )
                for event in confirmation_events
            ],
        ),
        _render_watch_bucket(
            bucket_key="awaiting-pricing",
            title="待定价",
            summary="盯第一定价对象，确认是否沿传导链继续扩散。",
            items=[
                _render_watch_item(
                    event,
                    bucket_key="awaiting-pricing",
                    label="观察定价扩散",
                    trigger=_coalesce_watch_text(
                        event.market_reaction,
                        "关注 Asia / Europe open 的第一波定价对象。",
                    ),
                    action="盯受益方向、承压方向和跨资产跟随，确认是不是单点波动。",
                )
                for event in pricing_events
            ],
        ),
        _render_watch_bucket(
            bucket_key="scheduled-release",
            title="待发布",
            summary="正式发布时间前，预期不能替代结果。",
            items=[
                _render_watch_item(
                    event,
                    bucket_key="scheduled-release",
                    label="等待正式发布",
                    trigger="发布窗口临近，等待正式数据或声明落地。",
                    action="结果落地前不提前下结论，防止把预期错当事实。",
                )
                for event in release_events
            ],
        ),
        _render_watch_bucket(
            bucket_key="monitoring",
            title="待观察",
            summary="跟踪二次发酵，避免把普通噪音误升级。",
            items=[
                _render_watch_item(
                    event,
                    bucket_key="monitoring",
                    label="跟踪二次发酵",
                    trigger=_coalesce_watch_text(
                        event.why_it_matters,
                        "观察它是否升级成更高优先级事件。",
                    ),
                    action="如果没有二次确认或市场跟随，不主动上调优先级。",
                )
                for event in observation_events
            ]
            or [
                {
                    "watch_id": "monitoring:light-flow",
                    "bucket_key": "monitoring",
                    "label": "轻流量环境观察",
                    "event_id": None,
                    "core_fact": "Overnight flow was light; monitor open-driven repricing.",
                    "priority_level": "",
                    "confidence": 0.0,
                    "trigger": "开盘后若无新增催化，观察是否只是情绪性重定价。",
                    "action": "没有新证据前，不把轻流量波动误判成主线。",
                    "market_reaction": "",
                }
            ],
        ),
    ]


def _render_watch_bucket(
    *,
    bucket_key: str,
    title: str,
    summary: str,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "bucket_key": bucket_key,
        "title": title,
        "summary": summary,
        "items": items,
    }


def _render_watch_item(
    event: RankedEvent,
    *,
    bucket_key: str,
    label: str,
    trigger: str,
    action: str,
) -> dict[str, object]:
    return {
        "watch_id": f"{bucket_key}:{_slugify_watch_value(event.event_id or event.core_fact)}",
        "bucket_key": bucket_key,
        "label": label,
        "event_id": event.event_id,
        "core_fact": event.core_fact,
        "priority_level": event.priority_level,
        "confidence": event.confidence,
        "trigger": trigger,
        "action": action,
        "market_reaction": event.market_reaction,
    }


def _coalesce_watch_text(*values: str) -> str:
    for value in values:
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return ""


def _slugify_watch_value(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return slug.strip("-") or "watch-item"


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
