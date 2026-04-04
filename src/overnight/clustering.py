# -*- coding: utf-8 -*-
"""Minimal event clustering for the overnight ledger pipeline."""

from __future__ import annotations

from src.overnight.contradiction import find_contradictions
from src.overnight.ledger import EventCluster, EventUpdate, StoredSourceItem


def build_event_cluster(items: list[StoredSourceItem]) -> EventCluster:
    """Build a small event cluster from related source items."""

    if not items:
        raise ValueError("build_event_cluster() requires at least one item")

    ordered_items = tuple(sorted(items, key=lambda item: (item.created_at is None, item.created_at, item.id)))
    anchor_key = ordered_items[0].family_key or ordered_items[0].canonical_url
    contradictions = find_contradictions(list(ordered_items))

    family_keys = {item.family_key or item.canonical_url for item in ordered_items}
    if contradictions:
        status = "contradictory"
    elif len(ordered_items) > 1 and len(family_keys) == 1:
        status = "developing"
    else:
        status = "confirmed"

    if len(ordered_items) > 1 and len(family_keys) == 1:
        event_update = EventUpdate(
            update_type="version_revised",
            reason="Multiple persisted versions share the same document family.",
        )
    else:
        event_update = EventUpdate(
            update_type="new_event",
            reason="Only one document version is present in the cluster.",
        )

    return EventCluster(
        anchor_key=anchor_key,
        status=status,
        items=ordered_items,
        event_update=event_update,
        contradictions=contradictions,
    )
