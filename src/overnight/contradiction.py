# -*- coding: utf-8 -*-
"""Minimal contradiction checks for normalized overnight facts."""

from __future__ import annotations

from dataclasses import dataclass

from src.overnight.ledger import StoredSourceItem


@dataclass(frozen=True)
class ContradictionFlag:
    kind: str
    metric: str
    values: set[float]
    item_ids: set[int]
    reason: str


def find_contradictions(items: list[StoredSourceItem]) -> list[ContradictionFlag]:
    """Detect explicit numeric conflicts across normalized items."""

    metric_values: dict[tuple[str, str], set[float]] = {}
    metric_item_ids: dict[tuple[str, str], set[int]] = {}

    for item in items:
        for fact in item.numeric_facts:
            key = (fact.metric, fact.unit)
            metric_values.setdefault(key, set()).add(fact.value)
            metric_item_ids.setdefault(key, set()).add(item.id)

    contradictions: list[ContradictionFlag] = []
    for (metric, unit), values in sorted(metric_values.items()):
        if len(values) < 2:
            continue
        contradictions.append(
            ContradictionFlag(
                kind="numeric_conflict",
                metric=metric,
                values=values,
                item_ids=metric_item_ids[(metric, unit)],
                reason=f"Conflicting {metric} values found in {unit}.",
            )
        )

    return contradictions
