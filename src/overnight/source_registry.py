# -*- coding: utf-8 -*-
"""Default overnight source registry."""

from __future__ import annotations

from src.overnight.types import SourceDefinition

_DEFAULT_SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="whitehouse_news",
        display_name="White House News",
        organization_type="official_policy",
        source_class="policy",
        entry_type="section_page",
        entry_urls=("https://www.whitehouse.gov/news/",),
        priority=100,
        poll_interval_seconds=300,
        is_mission_critical=True,
    ),
    SourceDefinition(
        source_id="fed_news",
        display_name="Federal Reserve News",
        organization_type="official_policy",
        source_class="policy",
        entry_type="rss",
        entry_urls=("https://www.federalreserve.gov/feeds/press_all.xml",),
        priority=100,
        poll_interval_seconds=300,
        is_mission_critical=True,
    ),
    SourceDefinition(
        source_id="reuters_topics",
        display_name="Reuters Topics",
        organization_type="wire_media",
        source_class="market",
        entry_type="section_page",
        entry_urls=("https://reutersbest.com/topic/",),
        priority=90,
        poll_interval_seconds=600,
        is_mission_critical=True,
    ),
)


def build_default_source_registry(source_class: str | None = None) -> list[SourceDefinition]:
    if source_class is None:
        return list(_DEFAULT_SOURCES)
    return [source for source in _DEFAULT_SOURCES if source.source_class == source_class]
