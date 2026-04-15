# -*- coding: utf-8 -*-
"""Shared dataclasses for the overnight capture ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.normalizer import EntityMention, NumericFact


@dataclass(frozen=True)
class StoredSourceItem:
    id: int
    raw_id: int
    canonical_url: str
    title: str
    summary: str
    excerpt_source: str
    document_type: str
    published_at: str | None
    published_at_source: str
    title_hash: str
    body_hash: str
    content_hash: str
    capture_path: str
    capture_provider: str
    article_fetch_status: str
    entities: tuple[EntityMention, ...]
    numeric_facts: tuple[NumericFact, ...]
    source_context: dict[str, object] = field(default_factory=dict)
    family_id: int | None = None
    family_key: str | None = None
    family_type: str | None = None
    version_id: int | None = None
    created_at: datetime | None = None
