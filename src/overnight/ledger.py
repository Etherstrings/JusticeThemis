# -*- coding: utf-8 -*-
"""Shared dataclasses for the overnight ledger pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.overnight.normalizer import EntityMention, NumericFact

if TYPE_CHECKING:
    from src.overnight.contradiction import ContradictionFlag


@dataclass(frozen=True)
class StoredSourceItem:
    id: int
    raw_id: int
    canonical_url: str
    title: str
    summary: str
    document_type: str
    title_hash: str
    body_hash: str
    content_hash: str
    entities: tuple[EntityMention, ...]
    numeric_facts: tuple[NumericFact, ...]
    family_id: int | None = None
    family_key: str | None = None
    family_type: str | None = None
    version_id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class EventUpdate:
    update_type: str
    reason: str


@dataclass(frozen=True)
class EventCluster:
    anchor_key: str
    status: str
    items: tuple[StoredSourceItem, ...]
    event_update: EventUpdate
    contradictions: list[ContradictionFlag]
