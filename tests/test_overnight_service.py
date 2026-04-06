# -*- coding: utf-8 -*-
"""Tests for overnight service detail enrichment."""

from __future__ import annotations

from src.overnight.brief_builder import RankedEvent, build_morning_brief
from src.services.overnight_service import OvernightService


def _build_brief(
    *,
    brief_id: str,
    digest_date: str,
    priority_level: str,
    confidence: float,
    summary: str,
    why_it_matters: str,
    source_links: list[str],
):
    brief = build_morning_brief(
        events=[
            RankedEvent(
                event_id="evt-001",
                core_fact="USTR announced new tariffs",
                priority_level=priority_level,
                summary=summary,
                why_it_matters=why_it_matters,
                confidence=confidence,
                market_reaction="USDCNH weakened first.",
                source_links=source_links,
            )
        ],
        direction_board=[],
        price_pressure_board=[],
        digest_date=digest_date,
        cutoff_time="07:30",
        generated_at=f"{digest_date}T07:31:00",
    )
    return brief.__class__(
        **{
            **brief.__dict__,
            "brief_id": brief_id,
        }
    )


class _FakeRepo:
    def __init__(self, latest_brief, historical_brief) -> None:
        self._latest_brief = latest_brief
        self._historical = {historical_brief.brief_id: historical_brief}

    def get_latest_morning_brief(self):
        return self._latest_brief

    def get_morning_brief(self, brief_id: str):
        if brief_id == self._latest_brief.brief_id:
            return self._latest_brief
        return self._historical.get(brief_id)


def test_get_event_detail_builds_structured_evidence_and_judgment() -> None:
    latest_brief = _build_brief(
        brief_id="brief-latest",
        digest_date="2026-04-05",
        priority_level="P0",
        confidence=0.84,
        summary="Tariff escalation was published by USTR.",
        why_it_matters="Trade policy became the main overnight driver.",
        source_links=["https://ustr.gov/about-us/policy-offices/press-office/press-releases/2026/april/tariff-update"],
    )
    service = OvernightService(repo=_FakeRepo(latest_brief, latest_brief))

    detail = service.get_event_detail("evt-001")

    assert detail["source_links"] == [
        "https://ustr.gov/about-us/policy-offices/press-office/press-releases/2026/april/tariff-update"
    ]
    assert detail["evidence_items"][0]["source_name"] == "USTR Press Releases"
    assert detail["evidence_items"][0]["source_type"] == "official"
    assert detail["evidence_items"][0]["headline"]
    assert detail["judgment_summary"]
    assert detail["judgment_mode"] in {"heuristic", "model"}


def test_get_event_detail_can_read_a_specific_brief() -> None:
    latest_brief = _build_brief(
        brief_id="brief-latest",
        digest_date="2026-04-05",
        priority_level="P0",
        confidence=0.84,
        summary="Tariff escalation was published by USTR.",
        why_it_matters="Trade policy became the main overnight driver.",
        source_links=["https://ustr.gov/about-us/policy-offices/press-office/press-releases/2026/april/tariff-update"],
    )
    historical_brief = _build_brief(
        brief_id="brief-historical",
        digest_date="2026-04-04",
        priority_level="P1",
        confidence=0.73,
        summary="Treasury follow-up kept sanctions risk on watch.",
        why_it_matters="The historical brief treated it as a secondary transmission line.",
        source_links=["https://home.treasury.gov/news/press-releases/jy0001"],
    )
    service = OvernightService(repo=_FakeRepo(latest_brief, historical_brief))

    detail = service.get_event_detail("evt-001", brief_id="brief-historical")

    assert detail["priority_level"] == "P1"
    assert detail["summary"] == "Treasury follow-up kept sanctions risk on watch."
    assert detail["source_links"] == ["https://home.treasury.gov/news/press-releases/jy0001"]
    assert detail["evidence_items"][0]["source_name"] == "Treasury Press Releases"
