# -*- coding: utf-8 -*-
"""Priority scoring for the minimal overnight intelligence layer."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import get_config
from src.overnight.market_context import MarketEvent, MarketLinkSet, build_market_link_set


@dataclass(frozen=True)
class PriorityResult:
    score: int
    priority: str
    delivery_policy: str
    score_breakdown: dict[str, int]
    reasons: tuple[str, ...]


class PriorityEngine:
    """Small threshold-based scorer for overnight event urgency."""

    def __init__(
        self,
        *,
        p0_cutoff: int | None = None,
        p1_cutoff: int | None = None,
        alert_threshold: str | None = None,
    ):
        config = get_config()
        self.p0_cutoff = p0_cutoff if p0_cutoff is not None else config.overnight_priority_p0_score_cutoff
        self.p1_cutoff = p1_cutoff if p1_cutoff is not None else config.overnight_priority_p1_score_cutoff
        self.alert_threshold = _normalize_priority(alert_threshold or config.overnight_priority_alert_threshold)

    def score(
        self,
        event: MarketEvent,
        link_set: MarketLinkSet | None = None,
    ) -> PriorityResult:
        market_links = link_set or build_market_link_set(event)
        score_breakdown = {
            "officiality": self._score_officiality(event),
            "shock_type": self._score_shock_type(event),
            "cross_border": self._score_cross_border(event),
            "severity": self._score_severity(event),
            "market_breadth": self._score_market_breadth(market_links),
            "market_reaction": self._score_market_reaction(event),
        }
        score = sum(score_breakdown.values())
        priority = self._priority_for_score(score)
        delivery_policy = self._delivery_policy_for_priority(priority)
        reasons = tuple(key for key, value in score_breakdown.items() if value > 0)

        return PriorityResult(
            score=score,
            priority=priority,
            delivery_policy=delivery_policy,
            score_breakdown=score_breakdown,
            reasons=reasons,
        )

    def _score_officiality(self, event: MarketEvent) -> int:
        text = _event_text(event)
        if event.organization_type.lower().startswith("official"):
            return 30
        if event.source_class.lower() == "policy":
            return 25
        if any(token in text for token in ("ustr", "white house", "federal reserve", "treasury")):
            return 20
        return 0

    def _score_shock_type(self, event: MarketEvent) -> int:
        text = _event_text(event)
        if event.event_type.lower() == "trade" and "tariff" in text:
            return 25
        if any(keyword in text for keyword in ("tariff", "trade", "export control", "sanction")):
            return 20
        return 0

    def _score_cross_border(self, event: MarketEvent) -> int:
        text = _event_text(event)
        if "china" in text or "chinese" in text:
            return 10
        return 0

    def _score_severity(self, event: MarketEvent) -> int:
        tariff_rates = [
            fact.value
            for fact in event.numeric_facts
            if fact.metric == "tariff_rate"
        ]
        if not tariff_rates:
            return 0

        max_rate = max(tariff_rates)
        if max_rate >= 25:
            return 15
        if max_rate >= 10:
            return 10
        return 5

    def _score_market_breadth(self, link_set: MarketLinkSet) -> int:
        active_categories = sum(
            1
            for values in (
                link_set.fx,
                link_set.rates,
                link_set.commodities,
                link_set.sector_etfs,
                link_set.companies,
                link_set.regions,
                link_set.transmission_channels,
            )
            if values
        )
        if active_categories >= 6:
            return 15
        if active_categories >= 4:
            return 10
        if active_categories >= 2:
            return 5
        return 0

    def _score_market_reaction(self, event: MarketEvent) -> int:
        normalized = max(0.0, min(float(event.market_reaction_score), 1.0))
        return int(round(normalized * 10))

    def _priority_for_score(self, score: int) -> str:
        if score >= self.p0_cutoff:
            return "P0"
        if score >= self.p1_cutoff:
            return "P1"
        if score >= 40:
            return "P2"
        return "P3"

    def _delivery_policy_for_priority(self, priority: str) -> str:
        if _priority_rank(priority) <= _priority_rank(self.alert_threshold):
            return "night_alert_and_brief"
        return "morning_brief_highlight"


def _event_text(event: MarketEvent) -> str:
    return " ".join(
        part
        for part in (
            event.core_fact,
            event.title,
            event.summary,
            event.event_type,
            event.event_subtype,
            event.source_id,
            event.source_class,
            event.organization_type,
            " ".join(event.entities),
            " ".join(fact.context for fact in event.numeric_facts),
        )
        if part
    ).lower()


def _normalize_priority(value: str) -> str:
    priority = (value or "P0").upper()
    if priority in {"P0", "P1", "P2", "P3"}:
        return priority
    return "P0"


def _priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(_normalize_priority(priority), 0)
