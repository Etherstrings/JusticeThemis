# -*- coding: utf-8 -*-
"""Minimal market-context heuristics for overnight event clusters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.overnight.normalizer import NumericFact


@dataclass(frozen=True)
class MarketEvent:
    """Lightweight event view used by the market context and priority layers."""

    core_fact: str
    title: str = ""
    summary: str = ""
    event_type: str = ""
    event_subtype: str = ""
    source_id: str = ""
    source_class: str = ""
    organization_type: str = ""
    entities: tuple[str, ...] = ()
    numeric_facts: tuple[NumericFact, ...] = ()
    market_reaction_score: float = 0.0


@dataclass(frozen=True)
class MarketLinkSet:
    fx: tuple[str, ...] = ()
    rates: tuple[str, ...] = ()
    commodities: tuple[str, ...] = ()
    sector_etfs: tuple[str, ...] = ()
    companies: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    transmission_channels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "fx": list(self.fx),
            "rates": list(self.rates),
            "commodities": list(self.commodities),
            "sector_etfs": list(self.sector_etfs),
            "companies": list(self.companies),
            "regions": list(self.regions),
            "transmission_channels": list(self.transmission_channels),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, list[str]] | None) -> "MarketLinkSet":
        data = payload or {}
        return cls(
            fx=tuple(data.get("fx", ())),
            rates=tuple(data.get("rates", ())),
            commodities=tuple(data.get("commodities", ())),
            sector_etfs=tuple(data.get("sector_etfs", ())),
            companies=tuple(data.get("companies", ())),
            regions=tuple(data.get("regions", ())),
            transmission_channels=tuple(data.get("transmission_channels", ())),
        )

    def total_links(self) -> int:
        return sum(
            len(values)
            for values in (
                self.fx,
                self.rates,
                self.commodities,
                self.sector_etfs,
                self.companies,
                self.regions,
            )
        )


@dataclass(frozen=True)
class MarketSnapshot:
    event_key: str
    event_type: str
    event_subtype: str
    link_set: MarketLinkSet
    transmission_map: dict[str, tuple[str, ...]]
    rationale: tuple[str, ...] = ()
    id: int | None = None
    cluster_id: int | None = None
    created_at: datetime | None = None


_TRADE_KEYWORDS = (
    "trade",
    "tariff",
    "duties",
    "export control",
    "export curbs",
    "sanction",
)
_CHINA_KEYWORDS = ("china", "chinese")
_ENERGY_KEYWORDS = ("oil", "energy", "crude", "brent")
_INDUSTRIAL_SUBJECTS = {"steel", "aluminum", "aluminium", "copper", "autos", "vehicles"}
_TECH_SUBJECTS = {"semiconductor", "chips", "chip"}


def build_market_link_set(event: MarketEvent) -> MarketLinkSet:
    """Map a small overnight event view into market link buckets."""

    text = _event_text(event)
    subjects = {
        fact.subject.lower()
        for fact in event.numeric_facts
        if fact.subject
    }

    fx: set[str] = set()
    rates: set[str] = set()
    commodities: set[str] = set()
    sector_etfs: set[str] = set()
    companies: set[str] = set()
    regions: set[str] = set()
    transmission_channels: set[str] = set()

    if _contains_any(text, _TRADE_KEYWORDS) or event.event_type.lower() == "trade":
        rates.add("US10Y")
        regions.add("United States")
        transmission_channels.update({"import_costs", "supply_chain", "risk_sentiment"})

    if _contains_any(text, _CHINA_KEYWORDS):
        fx.add("USDCNH")
        commodities.update({"Brent", "Copper"})
        rates.add("CN10Y")
        regions.add("China")
        transmission_channels.update({"fx_repricing", "energy_demand"})

    if _contains_any(text, _ENERGY_KEYWORDS):
        commodities.add("Brent")
        sector_etfs.add("XLE")
        transmission_channels.add("energy_demand")

    if _contains_subject(text, subjects, _INDUSTRIAL_SUBJECTS):
        commodities.update({"Copper"})
        sector_etfs.update({"XLI", "XME"})
        transmission_channels.add("industrial_input_costs")

    if _contains_subject(text, subjects, _TECH_SUBJECTS):
        sector_etfs.add("SOXX")
        companies.update({"NVDA", "TSM"})
        transmission_channels.add("technology_supply_chain")

    return MarketLinkSet(
        fx=_sorted_tuple(fx),
        rates=_sorted_tuple(rates),
        commodities=_sorted_tuple(commodities),
        sector_etfs=_sorted_tuple(sector_etfs),
        companies=_sorted_tuple(companies),
        regions=_sorted_tuple(regions),
        transmission_channels=_sorted_tuple(transmission_channels),
    )


def build_transmission_map(
    event: MarketEvent,
    link_set: MarketLinkSet | None = None,
) -> dict[str, tuple[str, ...]]:
    """Build a deterministic transmission map from event and link heuristics."""

    market_links = link_set or build_market_link_set(event)
    transmission_map: dict[str, tuple[str, ...]] = {}
    text = _event_text(event)

    if event.event_type.lower() == "trade" or "tariff" in text or "trade" in text:
        trade_channels = _select_channels(
            market_links,
            ("import_costs", "supply_chain"),
        )
        if trade_channels:
            transmission_map["trade_policy"] = trade_channels

    if market_links.fx or "china" in text or "chinese" in text:
        cross_border_channels = _select_channels(
            market_links,
            ("fx_repricing",),
        )
        if cross_border_channels:
            transmission_map["cross_border"] = cross_border_channels

    if market_links.commodities or market_links.sector_etfs:
        commodities_channels = _select_channels(
            market_links,
            ("energy_demand", "industrial_input_costs", "technology_supply_chain"),
        )
        if commodities_channels:
            transmission_map["commodities"] = commodities_channels

    if market_links.rates:
        rates_channels = _select_channels(
            market_links,
            ("fx_repricing",),
        )
        if rates_channels:
            transmission_map["rates"] = rates_channels

    return transmission_map


def _event_text(event: MarketEvent) -> str:
    parts = (
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
        " ".join(fact.subject or "" for fact in event.numeric_facts),
    )
    return " ".join(part for part in parts if part).lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_subject(text: str, subjects: set[str], candidates: set[str]) -> bool:
    return any(candidate in text or candidate in subjects for candidate in candidates)


def _sorted_tuple(values: set[str]) -> tuple[str, ...]:
    return tuple(sorted(values))


def _select_channels(
    link_set: MarketLinkSet,
    ordered_candidates: tuple[str, ...],
) -> tuple[str, ...]:
    present = set(link_set.transmission_channels)
    return tuple(channel for channel in ordered_candidates if channel in present)
