# -*- coding: utf-8 -*-
"""Core type contracts for overnight source collection."""

from __future__ import annotations

from dataclasses import dataclass


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
    region_focus: str = ""
    coverage_focus: str = ""


@dataclass(frozen=True)
class SourceCandidate:
    candidate_type: str
    candidate_url: str
    candidate_title: str
    candidate_summary: str = ""
    candidate_published_at: str | None = None
    candidate_section: str | None = None
    candidate_tags: tuple[str, ...] = ()
    needs_article_fetch: bool = False
    needs_attachment_fetch: bool = False
