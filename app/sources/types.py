# -*- coding: utf-8 -*-
"""Core type contracts for overnight source collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    display_name: str
    organization_type: str
    source_class: str
    entry_type: str
    entry_urls: tuple[str, ...]
    priority: int
    poll_interval_seconds: int
    is_mission_critical: bool = False
    coverage_tier: str = ""
    source_group: str = ""
    source_tier: str = ""
    content_mode: str = ""
    asset_tags: tuple[str, ...] = ()
    mainline_tags: tuple[str, ...] = ()
    region_focus: str = ""
    coverage_focus: str = ""
    allowed_domains: tuple[str, ...] = ()
    require_https: bool = True
    search_discovery_enabled: bool = False
    search_queries: tuple[str, ...] = ()
    is_enabled: bool = True
    disable_reason: str = ""


@dataclass(frozen=True)
class SourceCandidate:
    candidate_type: str
    candidate_url: str
    candidate_title: str
    candidate_summary: str = ""
    candidate_excerpt_source: str = ""
    candidate_published_at: str | None = None
    candidate_published_at_source: str = ""
    candidate_section: str | None = None
    candidate_tags: tuple[str, ...] = ()
    candidate_entity_names: tuple[str, ...] = ()
    source_context: dict[str, Any] | None = None
    needs_article_fetch: bool = False
    needs_attachment_fetch: bool = False
    capture_path: str = "direct"
    capture_provider: str = ""
    article_fetch_status: str = "not_attempted"
