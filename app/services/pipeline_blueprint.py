# -*- coding: utf-8 -*-
"""Static operational blueprint for the overnight pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from app.product_identity import LAUNCHD_COMMAND, PIPELINE_COMMAND, PIPELINE_NAME, PRODUCT_NAME
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceDefinition


class PipelineBlueprintService:
    """Describe the fixed overnight flow, source lanes, and entrypoints."""

    def __init__(self, *, registry: Sequence[SourceDefinition] | None = None) -> None:
        if registry is None:
            self.registry = list(build_default_source_registry(include_disabled=True))
            return

        merged_registry = list(registry)
        seen_ids = {source.source_id for source in merged_registry}
        if not any(not source.is_enabled for source in merged_registry):
            for source in build_default_source_registry(include_disabled=True):
                if not source.is_enabled and source.source_id not in seen_ids:
                    merged_registry.append(source)
                    seen_ids.add(source.source_id)
        self.registry = merged_registry

    def build(
        self,
        *,
        max_sources: int = 16,
        limit_per_source: int = 4,
        recent_limit: int = 40,
    ) -> dict[str, Any]:
        enabled_sources = [source for source in self.registry if source.is_enabled]
        disabled_sources = [source for source in self.registry if not source.is_enabled]
        source_lanes = [
            self._build_source_lane(
                lane_id="official_policy",
                title="官方政策主线",
                summary="优先盯政策动作、行政命令、贸易与制裁更新。",
                sources=[source for source in enabled_sources if source.coverage_tier == "official_policy"],
                max_sources=max_sources,
                limit_per_source=limit_per_source,
            ),
            self._build_source_lane(
                lane_id="official_data",
                title="官方数据主线",
                summary="盯宏观、能源与统计数据，用于锚定事实与时间。",
                sources=[source for source in enabled_sources if source.coverage_tier == "official_data"],
                max_sources=max_sources,
                limit_per_source=limit_per_source,
            ),
            self._build_source_lane(
                lane_id="editorial_media",
                title="媒体确认与市场语境",
                summary="用主流媒体补充上下文，但不让其替代官方事实源。",
                sources=[source for source in enabled_sources if source.coverage_tier == "editorial_media"],
                max_sources=max_sources,
                limit_per_source=limit_per_source,
            ),
            {
                "lane_id": "market_snapshot",
                "title": "美股与跨资产收盘快照",
                "summary": "以昨夜美股收盘结果为先，倒推新闻主线解释，不反过来猜盘。",
                "provider_names": ["iFinD History", "Treasury Yield Curve"],
                "instrument_target_count": 23,
                "buckets": [
                    "indexes",
                    "sectors",
                    "rates_fx",
                    "precious_metals",
                    "energy",
                    "industrial_metals",
                    "china_mapped_futures",
                ],
            },
            {
                "lane_id": "llm_exports",
                "title": "AI 投喂产物",
                "summary": "把固定日报和事件主线压缩成可送外部模型的结构化载荷。",
                "artifact_types": [
                    "daily_free_prompt",
                    "daily_premium_prompt",
                    "mmu_handoff",
                ],
                "mmu_stages": [
                    "single_item_understanding",
                    "event_consolidation",
                    "market_attribution",
                    "premium_recommendation",
                ],
            },
        ]

        return {
            "product_name": PRODUCT_NAME,
            "pipeline_name": PIPELINE_NAME,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "objective": "在中国早晨输出固定版隔夜国际新闻、美股收盘和结构化分析产物。",
            "run_window": {
                "timezone": "Asia/Shanghai",
                "target_read_time": "06:15",
                "market_reference": "前一交易日美股收盘",
                "analysis_mode": "fixed_daily_conclusion",
                "recent_limit": max(1, int(recent_limit)),
            },
            "budget": {
                "default_source_budget": min(len(enabled_sources), max(1, int(max_sources))),
                "default_item_budget": min(len(enabled_sources), max(1, int(max_sources))) * max(1, int(limit_per_source)),
                "recent_window_limit": max(1, int(recent_limit)),
            },
            "source_summary": {
                "enabled_source_count": len(enabled_sources),
                "disabled_source_count": len(disabled_sources),
                "mission_critical_source_count": len([source for source in enabled_sources if source.is_mission_critical]),
                "search_discovery_source_count": len([source for source in enabled_sources if source.search_discovery_enabled]),
            },
            "source_lanes": source_lanes,
            "disabled_sources": [
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "disable_reason": source.disable_reason,
                }
                for source in disabled_sources
            ],
            "processing_stages": [
                {
                    "stage_id": "capture_refresh",
                    "title": "新闻抓取刷新",
                    "summary": "按 source registry 抓 section/rss/calendar，必要时再走 search discovery 补漏。",
                },
                {
                    "stage_id": "normalization_and_guardrails",
                    "title": "标准化与可信度约束",
                    "summary": "规范时间、URL、摘录、数字事实和来源可信度，避免把噪声直接送分析层。",
                },
                {
                    "stage_id": "event_clustering",
                    "title": "事件去重与聚类",
                    "summary": "把同一事件的多来源条目聚成 event group，避免重复计权。",
                },
                {
                    "stage_id": "market_snapshot",
                    "title": "美股收盘与跨资产快照",
                    "summary": "先确认指数、板块、贵金属、能源和中国映射期货的昨夜结果。",
                },
                {
                    "stage_id": "fixed_daily_analysis",
                    "title": "固定日报生成",
                    "summary": "生成 free/premium 两层固定日报，作为中国早晨查看的最终缓存结论。",
                },
                {
                    "stage_id": "artifact_export_and_delivery",
                    "title": "产物导出与分发",
                    "summary": "导出 markdown、prompt bundle 和 MMU handoff，并可通过 webhook 推送到下游系统。",
                },
            ],
            "entrypoints": {
                "cli": [
                    {
                        "command": f"uv run {PIPELINE_COMMAND} --analysis-date YYYY-MM-DD",
                        "purpose": "执行固定晨间 pipeline。",
                    },
                    {
                        "command": f"uv run {LAUNCHD_COMMAND} --hour 6 --minute 15",
                        "purpose": "生成本地 launchd 定时模板。",
                    },
                ],
                "api": [
                    {"path": "/api/v1/pipeline/blueprint", "purpose": "查询固定流程蓝图。"},
                    {"path": "/api/v1/dashboard", "purpose": "查看新闻+市场仪表盘。"},
                    {"path": "/api/v1/market/us/daily", "purpose": "查看昨夜美股收盘快照。"},
                    {"path": "/api/v1/analysis/daily", "purpose": "读取固定日报缓存。"},
                    {"path": "/api/v1/analysis/daily/prompt", "purpose": "读取日报 prompt bundle。"},
                    {"path": "/api/v1/mmu/handoff", "purpose": "读取分阶段 MMU handoff 载荷。"},
                ],
            },
        }

    def _build_source_lane(
        self,
        *,
        lane_id: str,
        title: str,
        summary: str,
        sources: list[SourceDefinition],
        max_sources: int,
        limit_per_source: int,
    ) -> dict[str, Any]:
        enabled_sources = [source for source in sources if source.is_enabled]
        default_source_budget = min(len(enabled_sources), max(1, int(max_sources)))
        return {
            "lane_id": lane_id,
            "title": title,
            "summary": summary,
            "source_ids": [source.source_id for source in enabled_sources],
            "source_names": [source.display_name for source in enabled_sources],
            "capture_methods": sorted(
                {
                    source.entry_type
                    for source in enabled_sources
                    if source.entry_type
                }
                | ({"search_discovery"} if any(source.search_discovery_enabled for source in enabled_sources) else set())
            ),
            "default_source_budget": default_source_budget,
            "default_item_budget": default_source_budget * max(1, int(limit_per_source)),
            "mission_critical_count": len([source for source in enabled_sources if source.is_mission_critical]),
        }
