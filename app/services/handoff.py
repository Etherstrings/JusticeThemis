# -*- coding: utf-8 -*-
"""Official-first handoff packaging for downstream model reasoning."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Protocol

from app.services.current_window import filter_current_window_items
from app.services.mainline_engine import MainlineEngine


class RecentItemsProvider(Protocol):
    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, Any]:
        """Return recent source items."""


class MarketSnapshotProvider(Protocol):
    def get_daily_snapshot(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        """Return one persisted market snapshot."""


class HandoffService:
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

    SOURCE_HANDOFF_TIER_ORDER = {
        "official_policy": 0,
        "official_data": 1,
        "editorial_media": 2,
    }

    SOURCE_HANDOFF_GROUP_META = {
        "official_policy": {
            "title": "Official Policy",
            "summary": "Primary policy sources. Read these first for direct government actions and statements.",
        },
        "official_data": {
            "title": "Official Data",
            "summary": "Primary statistical and macro data sources. Use these to anchor facts and timing.",
        },
        "editorial_media": {
            "title": "Editorial Media",
            "summary": "Media follow-up and market color. Use for context after official sources.",
        },
    }

    def __init__(
        self,
        *,
        capture_service: RecentItemsProvider,
        market_snapshot_service: MarketSnapshotProvider | None = None,
    ) -> None:
        self.capture_service = capture_service
        self.market_snapshot_service = market_snapshot_service
        self.mainline_engine = MainlineEngine()

    def get_handoff(
        self,
        *,
        limit: int = 20,
        analysis_date: str | None = None,
        include_stale: bool = False,
    ) -> dict[str, Any]:
        requested_limit = max(1, int(limit))
        pool_limit = min(100, max(requested_limit * 3, 30))
        recent_pool = list(
            self.capture_service.list_recent_items(limit=pool_limit, analysis_date=analysis_date).get("items", [])
        )
        if not include_stale:
            recent_pool = filter_current_window_items(recent_pool)
        recent_pool.sort(key=self._source_item_handoff_sort_key)
        recent_items = recent_pool[:requested_limit]
        market_snapshot = (
            self.market_snapshot_service.get_daily_snapshot(analysis_date=analysis_date)
            if self.market_snapshot_service is not None
            else None
        )

        groups: list[dict[str, Any]] = []
        for coverage_tier in self._ordered_source_handoff_tiers(recent_items):
            group_items = [
                item
                for item in recent_items
                if str(item.get("coverage_tier", "")).strip() == coverage_tier
            ]
            if not group_items:
                continue
            meta = self.SOURCE_HANDOFF_GROUP_META.get(coverage_tier, {})
            groups.append(
                {
                    "coverage_tier": coverage_tier,
                    "title": str(meta.get("title", coverage_tier or "other_sources")),
                    "summary": str(meta.get("summary", "Grouped by source type for downstream reasoning.")),
                    "items": group_items,
                }
            )

        coverage_counts = Counter(str(item.get("coverage_tier", "")).strip() for item in recent_items)
        event_groups = self._build_event_groups(recent_pool)
        mainline_context = self._build_mainline_context(event_groups=event_groups, market_snapshot=market_snapshot)
        mainlines = list(mainline_context.get("mainlines", []) or [])

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "official_first": True,
            "total": len(recent_items),
            "official_item_count": coverage_counts.get("official_policy", 0) + coverage_counts.get("official_data", 0),
            "editorial_item_count": coverage_counts.get("editorial_media", 0),
            "prompt_scaffold": (
                "官方源优先。请先阅读 official_policy 和 official_data，再阅读 editorial_media。"
                " 如果提供了 event_groups，先按事件簇阅读，再下钻到单条 item，避免把同一事件重复计权。"
                " 先处理 analysis_status=ready 的条目，再看 review，background 仅作背景。"
                " 在同一层级里优先处理 a_share_relevance=high 的条目。"
                " 每条结论都优先引用 evidence_points 里的事实点。"
                " 优先使用 published_at_display、published_at_precision、source_authority、source_integrity、"
                " content_metrics、source_time_reliability、data_quality_flags、timeliness、source_capture_confidence、"
                " cross_source_confirmation、fact_conflicts 和 event_cluster 判断时间精度、"
                " 信息完整度与交叉验证强度。"
                " 如果存在 market_snapshot，先用它确认昨夜美股收盘的风险偏好和板块强弱，再回到新闻条目解释原因。"
                " 可以先参考 item 内的 llm_ready_brief、impact_summary、beneficiary_directions、"
                " pressured_directions、price_up_signals 和 follow_up_checks，再决定是否需要进一步推理。"
                " 输出时只保留已经落地的事实，不要把媒体猜测写成结论；"
                " 每条判断必须引用 item_id 和 source_name，并分别给出 A 股可能受益方向、承压方向、"
                " 可能涨价方向、需要继续确认的点。"
            ),
            "market_snapshot": market_snapshot or {},
            "market_regimes": list(mainline_context.get("market_regimes", []) or []),
            "handoff_outline": self._build_handoff_outline(recent_items, market_snapshot=market_snapshot),
            "items": recent_items,
            "groups": groups,
            "event_groups": event_groups,
            "mainlines": mainlines,
            "secondary_event_groups": list(mainline_context.get("secondary_event_groups", []) or []),
        }

    def _ordered_source_handoff_tiers(self, items: list[dict[str, Any]]) -> list[str]:
        tiers = {
            str(item.get("coverage_tier", "")).strip()
            for item in items
            if str(item.get("coverage_tier", "")).strip()
        }
        return sorted(
            tiers,
            key=lambda tier: (
                self.SOURCE_HANDOFF_TIER_ORDER.get(tier, 99),
                tier,
            ),
        )

    def _source_item_handoff_sort_key(self, item: dict[str, Any]) -> tuple[int, int, int, float, int, float, int]:
        coverage_tier = str(item.get("coverage_tier", "")).strip()
        analysis_status = str(item.get("analysis_status", "")).strip()
        relevance = str(item.get("a_share_relevance", "")).strip()
        priority = int(item.get("priority", 0) or 0)
        item_id = int(item.get("item_id", 0) or 0)
        freshness = self._source_item_sort_timestamp(item.get("published_at"))
        capture_time = self._source_item_sort_timestamp(item.get("created_at"))
        return (
            self.SOURCE_HANDOFF_TIER_ORDER.get(coverage_tier, 99),
            self.ANALYSIS_STATUS_ORDER.get(analysis_status, 99),
            self.A_SHARE_RELEVANCE_ORDER.get(relevance, 99),
            freshness,
            -priority,
            capture_time,
            -item_id,
        )

    def _source_item_sort_timestamp(self, value: object) -> float:
        candidate = str(value or "").strip()
        if not candidate:
            return float("inf")
        try:
            return -datetime.fromisoformat(candidate.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return float("inf")

    def _build_handoff_outline(
        self,
        items: list[dict[str, Any]],
        *,
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "market_context": (
                str(market_snapshot.get("headline", "")).strip()
                if isinstance(market_snapshot, dict)
                else ""
            ),
            "priority_item_ids": [int(item.get("item_id", 0) or 0) for item in items],
            "official_item_ids": [
                int(item.get("item_id", 0) or 0)
                for item in items
                if str(item.get("coverage_tier", "")).strip() in {"official_policy", "official_data"}
            ],
            "editorial_item_ids": [
                int(item.get("item_id", 0) or 0)
                for item in items
                if str(item.get("coverage_tier", "")).strip() == "editorial_media"
            ],
            "watch_item_ids": [
                int(item.get("item_id", 0) or 0)
                for item in items
                if str(item.get("analysis_status", "")).strip() == "review"
            ],
            "background_item_ids": [
                int(item.get("item_id", 0) or 0)
                for item in items
                if str(item.get("analysis_status", "")).strip() == "background"
            ],
            "event_cluster_ids": list(
                dict.fromkeys(
                    self._event_cluster_id(item)
                    for item in items
                )
            ),
            "field_priority": [
                "published_at_display",
                "published_at_precision",
                "source_authority",
                "source_integrity",
                "content_metrics",
                "source_time_reliability",
                "data_quality_flags",
                "timeliness",
                "body_detail_level",
                "source_capture_confidence",
                "key_numbers",
                "fact_table",
                "cross_source_confirmation",
                "fact_conflicts",
                "event_cluster",
                "policy_actions",
                "market_implications",
                "uncertainties",
                "llm_ready_brief",
                "why_it_matters_cn",
                "evidence_points",
                "impact_summary",
            ],
        }

    def _build_event_groups(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in items:
            cluster = self._normalized_event_cluster(item)
            cluster_id = str(cluster.get("cluster_id", "")).strip()
            if cluster_id not in grouped:
                grouped[cluster_id] = {
                    "cluster_id": cluster_id,
                    "cluster_status": str(cluster.get("cluster_status", "")).strip() or "single_source",
                    "primary_item_id": int(cluster.get("primary_item_id", 0) or 0),
                    "item_count": int(cluster.get("item_count", 0) or 0),
                    "source_count": int(cluster.get("source_count", 0) or 0),
                    "official_source_count": int(cluster.get("official_source_count", 0) or 0),
                    "item_ids": list(cluster.get("member_item_ids", []) or []),
                    "source_ids": list(cluster.get("member_source_ids", []) or []),
                    "latest_published_at": cluster.get("latest_published_at"),
                    "topic_tags": list(cluster.get("topic_tags", []) or []),
                    "fact_signatures": list(cluster.get("fact_signatures", []) or []),
                    "items": [],
                }
                order.append(cluster_id)
            group = grouped[cluster_id]
            item_id = int(item.get("item_id", 0) or 0)
            source_id = str(item.get("source_id", "")).strip()
            if item_id not in group["item_ids"]:
                group["item_ids"].append(item_id)
            if source_id and source_id not in group["source_ids"]:
                group["source_ids"].append(source_id)
            group["items"].append(item)

        event_groups = [grouped[cluster_id] for cluster_id in order]
        for group in event_groups:
            primary_item_id = int(group.get("primary_item_id", 0) or 0)
            group["items"].sort(
                key=lambda item: (
                    0 if int(item.get("item_id", 0) or 0) == primary_item_id else 1,
                    self._source_item_handoff_sort_key(item),
                )
            )
            primary_item = next(
                (
                    item
                    for item in group["items"]
                    if int(item.get("item_id", 0) or 0) == int(group.get("primary_item_id", 0) or 0)
                ),
                group["items"][0],
            )
            group["headline"] = str(primary_item.get("title", "")).strip()
            group["primary_source_name"] = str(primary_item.get("source_name", "")).strip()
        event_groups.sort(
            key=lambda group: self._source_item_handoff_sort_key(group["items"][0]) if group["items"] else (99, 99, 99, float("inf"), 0, float("inf"), 0)
        )
        return event_groups

    def _build_mainline_context(
        self,
        *,
        event_groups: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(market_snapshot, dict):
            return {"market_regimes": [], "mainlines": [], "secondary_event_groups": []}
        market_board = market_snapshot.get("asset_board")
        if not isinstance(market_board, dict):
            market_board = market_snapshot
        if not isinstance(market_board, dict):
            return {"market_regimes": [], "mainlines": [], "secondary_event_groups": []}

        market_regimes = list(market_snapshot.get("market_regimes", []) or [])
        market_regime_evaluations = list(market_snapshot.get("market_regime_evaluations", []) or [])
        if market_regimes or market_regime_evaluations:
            result = self.mainline_engine.build_result(
                market_board=market_board,
                market_regimes=market_regimes,
                market_regime_evaluations=market_regime_evaluations,
                event_groups=event_groups,
            )
            return {
                "market_regimes": market_regimes,
                "mainlines": list(result.get("mainlines", []) or []),
                "secondary_event_groups": list(result.get("secondary_event_groups", []) or []),
            }

        events = [
            {
                "event_id": str(group.get("cluster_id", "")).strip(),
                "event_status": str(group.get("cluster_status", "")).strip(),
                "official_source_count": int(group.get("official_source_count", 0) or 0),
                "source_count": int(group.get("source_count", 0) or 0),
                "topic_tags": list(group.get("topic_tags", []) or []),
                "affected_assets": self._event_group_affected_assets(group),
                "key_facts": list(group.get("fact_signatures", []) or []),
            }
            for group in event_groups
            if str(group.get("cluster_id", "")).strip()
        ]
        if not events:
            return {"market_regimes": [], "mainlines": [], "secondary_event_groups": []}
        return {
            "market_regimes": [],
            "mainlines": self.mainline_engine.build(market_board=market_board, events=events),
            "secondary_event_groups": [],
        }

    def _event_group_affected_assets(self, group: dict[str, Any]) -> list[str]:
        affected_assets: list[str] = []
        for item in list(group.get("items", []) or []):
            for implication in list(item.get("market_implications", []) or []):
                direction = str(implication.get("direction", "")).strip()
                if direction:
                    affected_assets.append(direction)
            for field in ("beneficiary_directions", "pressured_directions", "price_up_signals"):
                for direction in list(item.get(field, []) or []):
                    candidate = str(direction).strip()
                    if candidate:
                        affected_assets.append(candidate)
        return list(dict.fromkeys(affected_assets))

    def _normalized_event_cluster(self, item: dict[str, Any]) -> dict[str, Any]:
        event_cluster = dict(item.get("event_cluster", {}) or {})
        item_id = int(item.get("item_id", 0) or 0)
        if not str(event_cluster.get("cluster_id", "")).strip():
            event_cluster = {
                "cluster_id": f"item_{item_id}",
                "cluster_status": "single_source",
                "primary_item_id": item_id,
                "item_count": 1,
                "source_count": 1 if str(item.get("source_id", "")).strip() else 0,
                "official_source_count": 1 if str(item.get("coverage_tier", "")).strip() in {"official_policy", "official_data"} else 0,
                "member_item_ids": [item_id],
                "member_source_ids": [str(item.get("source_id", "")).strip()] if str(item.get("source_id", "")).strip() else [],
                "latest_published_at": item.get("published_at"),
                "topic_tags": [],
                "fact_signatures": [],
            }
        return event_cluster

    def _event_cluster_id(self, item: dict[str, Any]) -> str:
        return str(self._normalized_event_cluster(item).get("cluster_id", "")).strip()
