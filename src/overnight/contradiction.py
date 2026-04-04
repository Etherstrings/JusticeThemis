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

    metric_values: dict[tuple[str, str, str | None], set[float]] = {}
    metric_item_ids: dict[tuple[str, str, str | None], set[int]] = {}

    for item in items:
        for fact in item.numeric_facts:
            key = (fact.metric, fact.unit, fact.subject)
            metric_values.setdefault(key, set()).add(fact.value)
            metric_item_ids.setdefault(key, set()).add(item.id)

    contradictions: list[ContradictionFlag] = []
    for (metric, unit, subject), values in sorted(
        metric_values.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2] or ""),
    ):
        item_ids = metric_item_ids[(metric, unit, subject)]
        if len(values) < 2 or len(item_ids) < 2:
            continue
        reason = f"Conflicting {metric} values found in {unit}."
        if subject:
            reason = f"Conflicting {metric} values found in {unit} for {subject}."
        contradictions.append(
            ContradictionFlag(
                kind="numeric_conflict",
                metric=metric,
                values=values,
                item_ids=item_ids,
                reason=reason,
            )
        )

    return contradictions
