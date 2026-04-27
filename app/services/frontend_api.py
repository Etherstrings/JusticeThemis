# -*- coding: utf-8 -*-
"""Frontend-facing presentation service for professional dashboard APIs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Protocol

from app.repository import OvernightRepository
from app.services.current_window import filter_current_window_items
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceDefinition


class MarketSnapshotProvider(Protocol):
    def get_daily_snapshot(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        """Return one persisted market snapshot."""


class FrontendApiService:
    ANALYSIS_STATUS_ORDER = {
        "ready": 0,
        "review": 1,
        "background": 2,
    }

    A_SHARE_RELEVANCE_ORDER = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    COVERAGE_TIER_ORDER = {
        "official_policy": 0,
        "official_data": 1,
        "editorial_media": 2,
    }

    DEFAULT_BUCKET_LIMIT = 5
    DEFAULT_LIST_LIMIT = 20
    MAX_LIST_LIMIT = 50
    DEFAULT_RECENT_POOL_LIMIT = 300

    def __init__(
        self,
        *,
        repo: OvernightRepository,
        capture_service: OvernightSourceCaptureService,
        registry: list[SourceDefinition] | None = None,
        market_snapshot_service: MarketSnapshotProvider | None = None,
    ) -> None:
        self.repo = repo
        self.capture_service = capture_service
        self.registry = list(registry or build_default_source_registry())
        self.market_snapshot_service = market_snapshot_service

    def get_dashboard(self, *, bucket_limit: int = DEFAULT_BUCKET_LIMIT) -> dict[str, Any]:
        items = self._load_recent_pool(limit=max(self.DEFAULT_RECENT_POOL_LIMIT, bucket_limit * 10), pool_mode="current")
        ready = [item for item in items if str(item.get("analysis_status", "")).strip() == "ready"]
        review = [item for item in items if str(item.get("analysis_status", "")).strip() == "review"]
        background = [item for item in items if str(item.get("analysis_status", "")).strip() == "background"]
        coverage_counts = Counter(str(item.get("coverage_tier", "")).strip() for item in items)
        source_summary = self.list_sources()
        market_snapshot = (
            self.market_snapshot_service.get_daily_snapshot()
            if self.market_snapshot_service is not None
            else None
        )
        analysis_date = (
            str(dict(market_snapshot).get("analysis_date", "")).strip()
            if isinstance(market_snapshot, dict)
            else ""
        )
        latest_free_report = (
            self.repo.get_latest_daily_analysis_report(
                analysis_date=analysis_date,
                access_tier="free",
            )
            if analysis_date
            else None
        )

        return {
            "generated_at": self._generated_at(),
            "hero": {
                "total_items": len(items),
                "ready_count": len(ready),
                "review_count": len(review),
                "background_count": len(background),
                "official_count": coverage_counts.get("official_policy", 0) + coverage_counts.get("official_data", 0),
                "editorial_count": coverage_counts.get("editorial_media", 0),
            },
            "lead_signals": self._take_diverse_items(ready, limit=max(1, bucket_limit), max_per_source=1),
            "watchlist": self._take_diverse_items(review, limit=max(1, bucket_limit), max_per_source=2),
            "background": self._take_diverse_items(background, limit=max(1, bucket_limit), max_per_source=2),
            "source_health": {
                "total_sources": source_summary["total_sources"],
                "active_sources": source_summary["active_sources"],
                "inactive_sources": source_summary["inactive_sources"],
                "sources": source_summary["sources"][: max(1, bucket_limit)],
            },
            "market_board": dict(market_snapshot.get("asset_board", {}) or {}) if isinstance(market_snapshot, dict) else {},
            "mainlines": list(dict(latest_free_report or {}).get("mainlines", []) or [])[: max(1, bucket_limit)],
            "market_regimes": list(dict(latest_free_report or {}).get("market_regimes", []) or [])[: max(1, bucket_limit)],
            "secondary_event_groups": list(dict(latest_free_report or {}).get("secondary_event_groups", []) or [])[
                : max(1, bucket_limit)
            ],
        }

    def list_news(
        self,
        *,
        tab: str = "all",
        analysis_status: str | None = None,
        coverage_tier: str | None = None,
        source_id: str | None = None,
        q: str | None = None,
        pool_mode: str = "current",
        limit: int = DEFAULT_LIST_LIMIT,
        cursor: int = 0,
    ) -> dict[str, Any]:
        safe_limit = min(self.MAX_LIST_LIMIT, max(1, int(limit)))
        safe_cursor = max(0, int(cursor))
        pool_limit = min(
            500,
            max(
                self.DEFAULT_RECENT_POOL_LIMIT,
                (safe_cursor + safe_limit) * 4,
            ),
        )
        full_pool = self._load_recent_pool(limit=pool_limit, pool_mode="full")
        current_pool = self._load_recent_pool(limit=pool_limit, pool_mode="current")
        normalized_pool_mode = self._normalize_pool_mode(pool_mode)
        items = self._filter_items(
            current_pool if normalized_pool_mode == "current" else full_pool,
            tab=tab,
            analysis_status=analysis_status,
            coverage_tier=coverage_tier,
            source_id=source_id,
            q=q,
        )
        total = len(items)
        page = items[safe_cursor: safe_cursor + safe_limit]
        next_cursor = safe_cursor + safe_limit
        return {
            "generated_at": self._generated_at(),
            "pool_mode": normalized_pool_mode,
            "current_window_total": len(current_pool),
            "full_pool_total": len(full_pool),
            "total": total,
            "returned": len(page),
            "limit": safe_limit,
            "next_cursor": str(next_cursor) if next_cursor < total else None,
            "filters": {
                "tab": tab,
                "analysis_status": analysis_status,
                "coverage_tier": coverage_tier,
                "source_id": source_id,
                "q": q,
                "pool_mode": normalized_pool_mode,
            },
            "items": page,
        }

    def get_news_item(self, *, item_id: int) -> dict[str, Any] | None:
        row = self.repo.get_source_item_by_id(item_id)
        if row is None:
            return None
        return {
            "generated_at": self._generated_at(),
            "item": self.capture_service.render_recent_item_row(row),
        }

    def list_sources(self) -> dict[str, Any]:
        items = self._load_recent_pool(limit=self.DEFAULT_RECENT_POOL_LIMIT, pool_mode="current")
        items_by_source: dict[str, list[dict[str, Any]]] = {}
        source_refresh_states = self.repo.list_source_refresh_states(
            source_ids=[source.source_id for source in self.registry]
        )
        for item in items:
            source_id = str(item.get("source_id", "")).strip()
            if not source_id:
                continue
            items_by_source.setdefault(source_id, []).append(item)

        source_rows: list[dict[str, Any]] = []
        active_sources = 0
        for source in self.registry:
            source_items = items_by_source.get(source.source_id, [])
            refresh_state = dict(source_refresh_states.get(source.source_id, {}) or {})
            if source_items:
                active_sources += 1
            ready_count = sum(1 for item in source_items if item.get("analysis_status") == "ready")
            review_count = sum(1 for item in source_items if item.get("analysis_status") == "review")
            background_count = sum(1 for item in source_items if item.get("analysis_status") == "background")
            latest_item = self._latest_item(source_items)
            freshness_fields = self._source_freshness_fields(latest_item)
            quality_fields = self._source_quality_fields(latest_item, refresh_state=refresh_state)
            source_rows.append(
                {
                    "source_id": source.source_id,
                    "source_name": source.display_name,
                    "coverage_tier": source.coverage_tier,
                    "source_group": source.source_group,
                    "source_tier": source.source_tier,
                    "content_mode": source.content_mode,
                    "asset_tags": list(source.asset_tags),
                    "mainline_tags": list(source.mainline_tags),
                    "organization_type": source.organization_type,
                    "source_class": source.source_class,
                    "entry_type": source.entry_type,
                    "priority": int(source.priority),
                    "poll_interval_seconds": int(source.poll_interval_seconds),
                    "is_mission_critical": bool(source.is_mission_critical),
                    "search_discovery_enabled": bool(source.search_discovery_enabled),
                    "search_query_count": len([query for query in source.search_queries if query.strip()]),
                    "region_focus": source.region_focus,
                    "coverage_focus": source.coverage_focus,
                    "item_count": len(source_items),
                    "ready_count": ready_count,
                    "review_count": review_count,
                    "background_count": background_count,
                    "latest_item_id": latest_item.get("item_id") if latest_item is not None else None,
                    "latest_title": latest_item.get("title") if latest_item is not None else None,
                    "latest_published_at": latest_item.get("published_at") if latest_item is not None else None,
                    "latest_analysis_status": latest_item.get("analysis_status") if latest_item is not None else None,
                    "latest_a_share_relevance": latest_item.get("a_share_relevance") if latest_item is not None else None,
                    "last_refresh_status": str(refresh_state.get("last_refresh_status", "")).strip() or None,
                    "operational_status": self._source_operational_status(refresh_state=refresh_state),
                    "consecutive_failure_count": int(refresh_state.get("consecutive_failure_count", 0) or 0),
                    "cooldown_until": refresh_state.get("cooldown_until"),
                    "last_error": refresh_state.get("last_error"),
                    "last_attempted_at": refresh_state.get("last_attempted_at"),
                    "last_success_at": refresh_state.get("last_success_at"),
                    "last_candidate_count": int(refresh_state.get("last_candidate_count", 0) or 0),
                    "last_selected_candidate_count": int(refresh_state.get("last_selected_candidate_count", 0) or 0),
                    "last_persisted_count": int(refresh_state.get("last_persisted_count", 0) or 0),
                    "last_published_at_conflict_count": int(refresh_state.get("last_published_at_conflict_count", 0) or 0),
                    "last_elapsed_seconds": float(refresh_state.get("last_elapsed_seconds", 0.0) or 0.0),
                    **freshness_fields,
                    **quality_fields,
                }
            )

        source_rows.sort(
            key=lambda item: (
                -int(item.get("item_count", 0) or 0),
                -int(item.get("ready_count", 0) or 0),
                -int(item.get("priority", 0) or 0),
                str(item.get("source_id", "")),
            )
        )

        return {
            "generated_at": self._generated_at(),
            "total_sources": len(self.registry),
            "active_sources": active_sources,
            "inactive_sources": len(self.registry) - active_sources,
            "sources": source_rows,
        }

    def _source_operational_status(self, *, refresh_state: dict[str, Any]) -> str:
        last_status = str(refresh_state.get("last_refresh_status", "")).strip()
        if last_status == "cooldown":
            return "cooldown"
        cooldown_until = str(refresh_state.get("cooldown_until") or "").strip()
        if cooldown_until:
            try:
                if datetime.fromisoformat(cooldown_until.replace("Z", "+00:00")) > datetime.now().astimezone():
                    return "cooldown"
            except ValueError:
                return "cooldown"
        if last_status == "error":
            return "error"
        if last_status == "ok":
            return "healthy"
        if last_status == "empty":
            return "idle"
        return "unknown"

    def _load_recent_pool(self, *, limit: int, pool_mode: str = "current") -> list[dict[str, Any]]:
        items = list(self.capture_service.list_recent_items(limit=limit).get("items", []))
        if self._normalize_pool_mode(pool_mode) == "current":
            items = filter_current_window_items(items)
        items.sort(key=self._sort_key)
        return items

    def _normalize_pool_mode(self, value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "full":
            return "full"
        return "current"

    def _filter_items(
        self,
        items: list[dict[str, Any]],
        *,
        tab: str,
        analysis_status: str | None,
        coverage_tier: str | None,
        source_id: str | None,
        q: str | None,
    ) -> list[dict[str, Any]]:
        normalized_tab = tab.strip() or "all"
        filtered = list(items)

        if normalized_tab == "signals":
            filtered = [item for item in filtered if item.get("analysis_status") == "ready"]
        elif normalized_tab == "watchlist":
            filtered = [item for item in filtered if item.get("analysis_status") == "review"]
        elif normalized_tab == "other":
            filtered = [
                item
                for item in filtered
                if item.get("analysis_status") == "background"
                or item.get("coverage_tier") == "editorial_media"
            ]

        if analysis_status:
            filtered = [
                item
                for item in filtered
                if str(item.get("analysis_status", "")).strip() == analysis_status.strip()
            ]
        if coverage_tier:
            filtered = [
                item
                for item in filtered
                if str(item.get("coverage_tier", "")).strip() == coverage_tier.strip()
            ]
        if source_id:
            filtered = [
                item
                for item in filtered
                if str(item.get("source_id", "")).strip() == source_id.strip()
            ]
        if q:
            query = q.strip().lower()
            filtered = [
                item
                for item in filtered
                if query
                in " ".join(
                    str(item.get(field, "")).lower()
                    for field in ("title", "summary", "source_name", "impact_summary")
                )
            ]
        return filtered

    def _latest_item(self, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not items:
            return None
        return min(
            items,
            key=lambda item: (
                self._timestamp(item.get("published_at")),
                self._timestamp(item.get("created_at")),
                -int(item.get("item_id", 0) or 0),
            ),
        )

    def _source_freshness_fields(self, latest_item: dict[str, Any] | None) -> dict[str, Any]:
        if latest_item is None:
            return {
                "latest_freshness_bucket": None,
                "latest_is_timely": None,
                "latest_publication_lag_minutes": None,
                "freshness_status": "inactive",
            }

        timeliness = dict(latest_item.get("timeliness", {}) or {})
        freshness_bucket = str(timeliness.get("freshness_bucket", "")).strip() or None
        is_timely = timeliness.get("is_timely")
        publication_lag_minutes = timeliness.get("publication_lag_minutes")
        flags = {
            str(flag).strip()
            for flag in list(timeliness.get("timeliness_flags", []) or [])
            if str(flag).strip()
        }
        freshness_status = "watch"
        if freshness_bucket in {"breaking", "overnight"} and "delayed_capture" not in flags:
            freshness_status = "fresh"
        elif freshness_bucket in {"stale", "undated"} or "missing_published_time" in flags:
            freshness_status = "stale"
        elif "delayed_capture" in flags:
            freshness_status = "delayed"
        elif freshness_bucket == "recent":
            freshness_status = "watch"

        return {
            "latest_freshness_bucket": freshness_bucket,
            "latest_is_timely": is_timely if isinstance(is_timely, bool) else None,
            "latest_publication_lag_minutes": publication_lag_minutes,
            "freshness_status": freshness_status,
        }

    def _source_quality_fields(self, latest_item: dict[str, Any] | None, *, refresh_state: dict[str, Any]) -> dict[str, Any]:
        diagnostics = dict(dict(latest_item or {}).get("source_context", {}) or {}).get("published_at_diagnostics", {}) or {}
        conflict_count = int(refresh_state.get("last_published_at_conflict_count", 0) or 0)
        published_at_conflict = bool(diagnostics.get("published_at_conflict")) or conflict_count > 0
        freshness_status = self._source_freshness_fields(latest_item).get("freshness_status")
        quality_status = "clean"
        quality_note = None
        if published_at_conflict or conflict_count > 0:
            quality_status = "conflicted"
            quality_note = "search 时间与页面时间冲突，当前先按搜索时间入库。"
        elif freshness_status == "stale":
            quality_status = "stale"
            quality_note = "最新样本不在当前窗口。"
        elif freshness_status == "delayed":
            quality_status = "delayed"
            quality_note = "最新样本发布时间可靠，但抓取明显偏晚。"
        return {
            "latest_published_at_conflict": published_at_conflict,
            "quality_status": quality_status,
            "quality_note": quality_note,
        }

    def _sort_key(self, item: dict[str, Any]) -> tuple[int, int, int, float, int, float, int]:
        coverage_tier = str(item.get("coverage_tier", "")).strip()
        analysis_status = str(item.get("analysis_status", "")).strip()
        relevance = str(item.get("a_share_relevance", "")).strip()
        priority = int(item.get("priority", 0) or 0)
        item_id = int(item.get("item_id", 0) or 0)
        freshness = self._timestamp(item.get("published_at"))
        capture_time = self._timestamp(item.get("created_at"))
        return (
            self.ANALYSIS_STATUS_ORDER.get(analysis_status, 99),
            self.COVERAGE_TIER_ORDER.get(coverage_tier, 99),
            self.A_SHARE_RELEVANCE_ORDER.get(relevance, 99),
            freshness,
            -priority,
            capture_time,
            -item_id,
        )

    def _take_diverse_items(self, items: list[dict[str, Any]], *, limit: int, max_per_source: int) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))
        safe_cap = max(1, int(max_per_source))
        selected: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        source_counts: Counter[str] = Counter()

        for item in items:
            source_id = str(item.get("source_id", "")).strip() or "__unknown__"
            if source_counts[source_id] >= safe_cap:
                deferred.append(item)
                continue
            selected.append(item)
            source_counts[source_id] += 1
            if len(selected) >= safe_limit:
                return selected

        for item in deferred:
            selected.append(item)
            if len(selected) >= safe_limit:
                break

        return selected

    def _timestamp(self, value: object) -> float:
        candidate = str(value or "").strip()
        if not candidate:
            return float("inf")
        try:
            return -datetime.fromisoformat(candidate.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return float("inf")

    def _generated_at(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
