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
    entry_urls: list[str]
    priority: int
    poll_interval_seconds: int
    is_mission_critical: bool = False


@dataclass(frozen=True)
class SourceCandidate:
    canonical_url: str
    title: str
    document_type: str
