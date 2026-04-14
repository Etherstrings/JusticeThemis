# -*- coding: utf-8 -*-
"""Shared helpers for filtering the current actionable overnight window."""

from __future__ import annotations

from typing import Any


CURRENT_WINDOW_BUCKETS = frozenset({"breaking", "overnight", "recent"})


def is_current_window_item(item: dict[str, Any]) -> bool:
    timeliness = dict(item.get("timeliness", {}) or {})
    if not timeliness:
        return True

    is_timely = timeliness.get("is_timely")
    if isinstance(is_timely, bool):
        return is_timely

    freshness_bucket = str(timeliness.get("freshness_bucket", "")).strip()
    if freshness_bucket:
        return freshness_bucket in CURRENT_WINDOW_BUCKETS

    return True


def filter_current_window_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if is_current_window_item(item)]

