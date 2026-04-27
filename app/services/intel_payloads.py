# -*- coding: utf-8 -*-
"""Render-ready payload builders for source-intel and world-money-flow outputs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Protocol
from zoneinfo import ZoneInfo

class SourceItemsProvider(Protocol):
    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, Any]:
        """Return recent rendered source items."""


class MarketSnapshotProvider(Protocol):
    def get_daily_snapshot(self, *, analysis_date: str | None = None) -> dict[str, Any] | None:
        """Return one persisted market snapshot."""


_STATUS_ORDER = {
    "ready": 0,
    "review": 1,
    "background": 2,
}

_AUTHORITY_ORDER = {
    "primary_official": 0,
    "editorial_context": 1,
    "other": 2,
}

_GROUP_CLUSTER_MAX_ITEMS = 6
_GROUP_CLUSTER_MAX_SOURCES = 4

_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "geopolitics",
        (
            "trade_policy",
            "energy_shipping",
            "geopolit",
            "war",
            "ceasefire",
            "iran",
            "israel",
            "ukraine",
            "shipping",
            "hormuz",
            "tariff",
            "sanction",
            "export control",
            "blockade",
        ),
    ),
    (
        "commodities",
        (
            "gold_market",
            "silver_market",
            "copper_market",
            "aluminum_market",
            "industrial_metals",
            "oil",
            "crude",
            "gold",
            "silver",
            "copper",
            "aluminum",
            "aluminium",
            "commodity",
            "energy",
            "lng",
            "natural gas",
            "metals",
            "etf",
        ),
    ),
    (
        "tech_ai_and_major_companies",
        (
            "semiconductor_supply_chain",
            "semiconductor",
            "chip",
            "ai",
            "openai",
            "anthropic",
            "claude",
            "gpt",
            "deepseek",
            "meta",
            "amazon",
            "google",
            "microsoft",
            "nvidia",
            "intel",
            "amd",
            "product hunt",
            "github",
        ),
    ),
    (
        "macro_policy",
        (
            "rates_macro",
            "fed",
            "fomc",
            "ecb",
            "boj",
            "central bank",
            "inflation",
            "cpi",
            "ppi",
            "payroll",
            "employment",
            "yield",
            "treasury",
            "policy",
            "stimulus",
            "cftc",
            "regulation",
            "jurisdiction",
        ),
    ),
    (
        "rates_and_fx",
        (
            "dollar",
            "usd",
            "fx",
            "forex",
            "currency",
            "cnh",
            "eurusd",
            "usdjpy",
            "rates_fx",
            "yield curve",
        ),
    ),
    (
        "equity_and_sector_moves",
        (
            "equity",
            "stocks",
            "shares",
            "index",
            "sector",
            "earnings",
            "ipo",
            "nasdaq",
            "s&p",
            "dow",
            "rally",
            "selloff",
        ),
    ),
)

_DIRECTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rates_down", ("rate cut", "yields fell", "yield fell", "dovish")),
    ("rates_up", ("higher yields", "yields rose", "hawkish", "restrictive")),
    ("risk_on", ("rally", "record high", "risk-on", "surge", "jumped")),
    ("risk_off", ("selloff", "risk-off", "slump", "panic", "drop")),
    ("oil_up", ("oil rose", "crude rose", "brent rose", "wti rose")),
)

_MONEY_RELEVANCE_KEYWORDS: tuple[str, ...] = (
    "market",
    "markets",
    "wall street",
    "stocks",
    "shares",
    "equity",
    "equities",
    "bond",
    "bonds",
    "yield",
    "yields",
    "treasury",
    "rates",
    "rate cut",
    "inflation",
    "cpi",
    "ppi",
    "fed",
    "fomc",
    "ecb",
    "boj",
    "dollar",
    "usd",
    "yuan",
    "cnh",
    "fx",
    "forex",
    "oil",
    "crude",
    "gold",
    "silver",
    "copper",
    "aluminum",
    "aluminium",
    "commodity",
    "commodities",
    "freight",
    "tanker",
    "container",
    "dry bulk",
    "strait of hormuz",
    "hormuz",
    "pipeline",
    "electricity",
    "power",
    "lng",
    "coal",
    "uranium",
    "lithium",
    "rare earth",
    "minerals",
    "mining",
    "earnings",
    "revenue",
    "profit",
    "sales",
    "ipo",
    "valuation",
    "etf",
    "flows",
    "liquidity",
    "investor",
    "investors",
    "tariff",
    "trade",
    "shipping",
    "export control",
    "sanction",
    "ofac",
    "cftc",
    "fedwatch",
    "polymarket",
    "kalshi",
    "option",
    "options",
    "volatility",
    "vix",
    "swap",
    "swaps",
    "spread",
    "yield curve",
    "semiconductor",
    "chip",
    "chips",
    "ai",
    "openai",
    "anthropic",
    "deepseek",
    "nvidia",
    "intel",
    "amd",
    "tesla",
    "amazon",
    "meta",
    "google",
    "microsoft",
)

_BROAD_FINANCE_SOURCE_MARKERS: tuple[str, ...] = (
    "cnbc",
    "reuters",
    "bloomberg",
    "marketwatch",
    "wsj",
    "wall street",
    "financial times",
    "ft ",
    "kitco",
    "oilprice",
    "readhub",
    "36kr",
    "hacker news",
    "product hunt",
    "ap ",
    "associated press",
    "mining.com",
    "fastmarkets",
)

_CEREMONIAL_EXCLUDE_MARKERS: tuple[str, ...] = (
    "first lady",
    "state visit",
    "welcome his majesty",
    "arbor day",
    "king charles",
    "queen camilla",
)

_NEWS_PRIORITY_SOURCE_SCORES: dict[str, int] = {
    "ap financial markets": 45,
    "ap world": 38,
    "ap business": 30,
    "ap economy": 34,
    "cnbc markets": 42,
    "cnbc world": 40,
    "cnbc technology": 34,
    "kitco news": 28,
    "fastmarkets market insights": 28,
    "mining.com markets": 26,
    "oilprice world news": 24,
    "ecb press": 22,
    "federal reserve news": 28,
    "ustr press releases": 20,
    "ofac recent actions": 24,
    "cftc general press releases": 26,
    "cftc enforcement press releases": 20,
    "department of energy articles": -10,
    "white house news": -18,
}

_NEWS_SOURCE_CAP_OVERRIDES: dict[str, int] = {
    "ap financial markets": 3,
    "ap world": 3,
    "cnbc markets": 3,
    "cnbc world": 3,
    "cnbc technology": 3,
    "kitco news": 3,
    "department of energy articles": 1,
    "white house news": 1,
}

_NEWS_PRIORITY_MARKERS: tuple[tuple[str, int], ...] = (
    ("iran", 18),
    ("hormuz", 22),
    ("oil", 14),
    ("crude", 14),
    ("gold", 12),
    ("fed", 12),
    ("federal reserve", 12),
    ("yield", 10),
    ("inflation", 10),
    ("tariff", 12),
    ("trade", 10),
    ("shipping", 12),
    ("freight", 12),
    ("critical minerals", 14),
    ("minerals", 8),
    ("semiconductor", 12),
    ("chip", 10),
    ("ai", 8),
    ("nvidia", 16),
    ("intel", 16),
    ("amd", 14),
    ("amazon", 10),
    ("meta", 10),
    ("google", 10),
    ("anthropic", 10),
    ("etf", 8),
    ("earnings", 12),
    ("ipo", 10),
    ("prediction market", 12),
    ("polymarket", 12),
    ("kalshi", 12),
    ("cftc", 12),
    ("dollar swap", 12),
)

_NEWS_DEPRIORITIZE_MARKERS: tuple[tuple[str, int], ...] = (
    ("fact sheet", -18),
    ("presidential message", -22),
    ("for the american people", -12),
    ("here's what happened", -12),
    ("apologizes", -14),
    ("killings", -18),
    ("granted bond", -14),
    ("visually impaired", -16),
    ("hearing loss", -14),
    ("american dream", -12),
)


class OvernightIntelPayloadService:
    """Build readable intelligence payloads from existing captured items and market data."""

    def __init__(
        self,
        *,
        capture_service: SourceItemsProvider,
        market_snapshot_service: MarketSnapshotProvider | None = None,
    ) -> None:
        self.capture_service = capture_service
        self.market_snapshot_service = market_snapshot_service
        self._shanghai_tz = ZoneInfo("Asia/Shanghai")

    def get_source_intel_payload(
        self,
        *,
        analysis_date: str | None = None,
        limit: int = 60,
        include_stale: bool = False,
    ) -> dict[str, Any]:
        if analysis_date:
            resolved_analysis_date = str(analysis_date).strip()
            items = self._load_items(
                analysis_date=resolved_analysis_date,
                limit=limit,
                include_stale=include_stale,
            )
            market_snapshot = self._get_market_snapshot(analysis_date=resolved_analysis_date)
        else:
            items = self._load_items(
                analysis_date=None,
                limit=limit,
                include_stale=include_stale,
            )
            resolved_analysis_date = self._resolve_analysis_date(
                requested=None,
                market_snapshot=None,
                items=items,
            )
            market_snapshot = self._get_market_snapshot(analysis_date=resolved_analysis_date)
        groups = self._build_group_entries(items)
        grouped_items = {
            topic: entries[:6]
            for topic, entries in groups.items()
            if entries
        }
        headline_items = self._sorted_entries(
            [entry for entries in groups.values() for entry in entries]
        )[:8]
        source_status = self._build_source_status(items=items)
        time_window = self._build_time_window(
            analysis_date=resolved_analysis_date,
            market_snapshot=market_snapshot,
            items=items,
        )
        return {
            "analysis_date": resolved_analysis_date,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "time_window": time_window,
            "editorial_rules": {
                "goal": "先把这段时差里全球所有和钱相关的事情收干净，再交给后面的对照模块",
                "max_items_per_group": 6,
                "dedupe_enabled": True,
                "explanation_style": "一句人话",
            },
            "summary": {
                "headline": self._build_source_headline(
                    headline_items=headline_items,
                    market_snapshot=market_snapshot,
                ),
                "source_item_count": len(items),
                "headline_item_count": len(headline_items),
                "topic_group_count": len(grouped_items),
            },
            "headline_items": headline_items,
            "grouped_items": grouped_items,
            "source_status": source_status,
        }

    def get_yesterday_world_money_flow_payload(
        self,
        *,
        analysis_date: str | None = None,
        limit: int = 60,
        include_stale: bool = False,
    ) -> dict[str, Any]:
        source_payload = self.get_source_intel_payload(
            analysis_date=analysis_date,
            limit=limit,
            include_stale=include_stale,
        )
        requested_analysis_date = analysis_date or str(source_payload.get("analysis_date", "")).strip() or None
        market_snapshot = self._get_market_snapshot(
            analysis_date=requested_analysis_date,
        )
        market_snapshot_status = "exact" if market_snapshot is not None else "missing"
        if market_snapshot is None and self.market_snapshot_service is not None:
            market_snapshot = self.market_snapshot_service.get_daily_snapshot()
            if market_snapshot is not None:
                market_snapshot_status = "stale_fallback"
        grouped_items = dict(source_payload.get("grouped_items", {}) or {})
        asset_board = dict(dict(market_snapshot or {}).get("asset_board", {}) or {})
        risk_signals = dict(dict(market_snapshot or {}).get("risk_signals", {}) or {})
        grouped_macro = list(grouped_items.get("macro_policy", []) or [])
        grouped_geopolitics = list(grouped_items.get("geopolitics", []) or [])
        grouped_equity = list(grouped_items.get("equity_and_sector_moves", []) or [])
        grouped_rates = list(grouped_items.get("rates_and_fx", []) or [])
        grouped_commodities = list(grouped_items.get("commodities", []) or [])
        grouped_tech = list(grouped_items.get("tech_ai_and_major_companies", []) or [])

        payload = {
            "analysis_date": str(source_payload.get("analysis_date", "")).strip(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "market_snapshot_status": {
                "status": market_snapshot_status,
                "requested_analysis_date": str(requested_analysis_date or "").strip() or None,
                "snapshot_analysis_date": str(dict(market_snapshot or {}).get("analysis_date", "")).strip() or None,
            },
            "time_window": {
                **dict(source_payload.get("time_window", {}) or {}),
                "label": "昨天世界钱往哪里",
                "subtitle": "美东收盘后到中国早晨，这段时差里全球和钱相关的事情",
            },
            "global_headline": self._build_world_headline(
                source_payload=source_payload,
                asset_board=asset_board,
                risk_signals=risk_signals,
            ),
            "headline_events": list(source_payload.get("headline_items", []) or [])[:4],
            "macro_policy": grouped_macro[:4],
            "geopolitics": grouped_geopolitics[:4],
            "equity_and_sector_moves": self._merge_section_entries(
                entries=[
                    *grouped_equity,
                    *self._build_market_section(
                        items=[
                            *list(asset_board.get("indexes", []) or []),
                            *list(asset_board.get("sectors", []) or []),
                        ],
                        topic="equity_and_sector_moves",
                        max_items=6,
                    ),
                ],
                max_items=6,
            ),
            "rates_and_fx": self._merge_section_entries(
                entries=[
                    *grouped_rates,
                    *self._build_market_section(
                        items=list(asset_board.get("rates_fx", []) or []),
                        topic="rates_and_fx",
                        max_items=6,
                    ),
                ],
                max_items=6,
            ),
            "commodities": self._merge_section_entries(
                entries=[
                    *grouped_commodities,
                    *self._build_market_section(
                        items=[
                            *list(asset_board.get("precious_metals", []) or []),
                            *list(asset_board.get("energy", []) or []),
                            *list(asset_board.get("industrial_metals", []) or []),
                        ],
                        topic="commodities",
                        max_items=6,
                    ),
                ],
                max_items=6,
            ),
            "tech_ai_and_major_companies": grouped_tech[:5],
            "cross_asset_links": self._build_cross_asset_links(
                grouped_items=grouped_items,
                asset_board=asset_board,
                risk_signals=risk_signals,
            ),
            "source_index": dict(source_payload.get("source_status", {}) or {}).get("top_sources", []),
        }
        return payload

    def get_world_money_flow_image_payload(
        self,
        *,
        analysis_date: str | None = None,
        limit: int = 60,
        include_stale: bool = False,
    ) -> dict[str, Any]:
        world_payload = self.get_yesterday_world_money_flow_payload(
            analysis_date=analysis_date,
            limit=limit,
            include_stale=include_stale,
        )
        raw_items = self._load_items(
            analysis_date=analysis_date,
            limit=max(120, limit * 2),
            include_stale=include_stale,
        )
        analysis_date_value = str(world_payload.get("analysis_date", "")).strip() or None
        market_snapshot = self._get_market_snapshot(analysis_date=analysis_date_value)
        if market_snapshot is None and self.market_snapshot_service is not None:
            market_snapshot = self.market_snapshot_service.get_daily_snapshot()
        asset_board = dict(dict(market_snapshot or {}).get("asset_board", {}) or {})
        risk_signals = dict(dict(market_snapshot or {}).get("risk_signals", {}) or {})

        news_pool = self._dedupe_entries_by_group(
            [
                *list(world_payload.get("headline_events", []) or []),
                *list(world_payload.get("geopolitics", []) or []),
                *list(world_payload.get("macro_policy", []) or []),
                *list(world_payload.get("tech_ai_and_major_companies", []) or []),
                *[entry for entry in list(world_payload.get("equity_and_sector_moves", []) or []) if self._is_news_entry(entry)],
                *[entry for entry in list(world_payload.get("commodities", []) or []) if self._is_news_entry(entry)],
            ]
        )
        top_news = news_pool[:10]
        market_board = self._build_market_board(asset_board=asset_board, risk_signals=risk_signals)
        news_digest = self._build_image_news_digest(
            world_payload=world_payload,
            raw_items=raw_items,
            max_items=20,
        )
        side_signals = self._build_simple_side_signals(
            market_snapshot=market_snapshot,
            news_items=raw_items,
        )
        source_count = int(dict(world_payload.get("source_status", {}) or {}).get("active_source_count", 0) or 0)
        if source_count <= 0:
            source_count = len(
                {
                    str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
                    for item in raw_items
                    if str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
                }
            )
        hero = self._build_simple_hero(
            news_digest=news_digest,
            market_board=market_board,
            risk_signals=risk_signals,
        )
        image_blocks = self._build_image_blocks(
            analysis_date=str(world_payload.get("analysis_date", "")).strip(),
            hero=hero,
            news_digest=news_digest,
            market_board=market_board,
            side_signals=side_signals,
        )
        return {
            "analysis_date": str(world_payload.get("analysis_date", "")).strip(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "meta": {
                "analysis_date": str(world_payload.get("analysis_date", "")).strip(),
                "time_window_label": str(dict(world_payload.get("time_window", {}) or {}).get("label", "")).strip(),
                "subtitle": str(dict(world_payload.get("time_window", {}) or {}).get("subtitle", "")).strip(),
                "market_snapshot_status": str(dict(world_payload.get("market_snapshot_status", {}) or {}).get("status", "")).strip(),
                "source_count": source_count,
            },
            "hero": hero,
            "image_blocks": image_blocks,
            "market_board": market_board,
            "news_digest": news_digest,
            "side_signals": side_signals,
            "raw_headlines": [self._to_image_item(item) for item in top_news[:10]],
            "source_index": list(world_payload.get("source_index", []) or []),
            "render_hints": {
                "layout_family": "portrait_dense_v1",
                "news_count": len(news_digest),
                "market_count": len(market_board),
                "emphasis_order": ["hero", "news_digest", "market_board", "side_signals"],
            },
        }

    def _build_image_blocks(
        self,
        *,
        analysis_date: str,
        hero: dict[str, Any],
        news_digest: list[dict[str, Any]],
        market_board: list[dict[str, Any]],
        side_signals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "title_block": {
                "title": "昨天世界钱往哪里",
                "date": analysis_date,
                "conclusion": self._build_image_conclusion(market_board=market_board, news_digest=news_digest),
                "summary": self._build_image_summary(market_board=market_board, news_digest=news_digest),
            },
            "flow_block": {
                "title": "钱的方向",
                "items": self._build_money_direction_items(market_board=market_board, news_digest=news_digest),
            },
            "drivers_block": {
                "title": "推动资金移动的事件",
                "items": news_digest[:16],
            },
            "data_block": {
                "title": "全市场证据",
                "groups": [
                    {
                        "label": "股指 / 板块",
                        "items": self._pick_market_board_items(
                            market_board,
                            keywords=("风险状态", "标普", "纳指", "道指", "罗素", "科技板块", "半导体", "金融板块", "能源板块"),
                            max_items=9,
                        ),
                    },
                    {
                        "label": "利率 / 汇率 / 波动",
                        "items": self._pick_market_board_items(
                            market_board,
                            keywords=("国债收益率", "美元指数", "离岸人民币", "VIX"),
                            max_items=8,
                        ),
                    },
                    {
                        "label": "商品 / 能源 / 金属",
                        "items": self._pick_market_board_items(
                            market_board,
                            keywords=("黄金", "白银", "原油", "天然气", "铜", "铝"),
                            max_items=8,
                        ),
                    },
                    {
                        "label": "航运 / 全球 / 信用 / 加密",
                        "items": self._pick_market_board_items(
                            market_board,
                            keywords=("航运", "干散货", "新兴市场", "发达市场", "欧元区", "日本", "比特币", "以太坊", "长期美债", "高收益债", "投资级债", "垃圾债", "中国互联网", "中国大型股"),
                            max_items=16,
                        ),
                    },
                    {
                        "label": "中国期货映射",
                        "items": self._pick_market_board_items(
                            market_board,
                            keywords=("甲醇", "乙二醇", "PX", "PTA", "纯碱", "玻璃", "碳酸锂", "工业硅"),
                            max_items=8,
                        ),
                    },
                ],
            },
            "mapping_block": {
                "title": "接下来盯哪里",
                "items": self._build_image_mapping_items(news_digest=news_digest, side_signals=side_signals),
            },
        }

    def _build_image_conclusion(self, *, market_board: list[dict[str, Any]], news_digest: list[dict[str, Any]]) -> str:
        semi = self._find_market_title(market_board, "半导体板块")
        tech = self._find_market_title(market_board, "科技板块")
        oil = self._find_market_title(market_board, "WTI原油")
        gold = self._find_market_title(market_board, "黄金")
        if semi or tech:
            return f"钱继续往AI硬件和美股大盘集中，但中东、油运和黄金还在提醒市场别太放松。"
        if oil or gold:
            return "钱没有单边冲风险资产，商品和避险线还在抢定价权。"
        return "钱在重新分配：强的地方继续被追，弱的地方被资金绕开。"

    def _build_image_summary(self, *, market_board: list[dict[str, Any]], news_digest: list[dict[str, Any]]) -> str:
        key_prices = [
            self._find_market_title(market_board, "半导体板块"),
            self._find_market_title(market_board, "科技板块"),
            self._find_market_title(market_board, "纳指"),
            self._find_market_title(market_board, "美国10年期国债收益率"),
            self._find_market_title(market_board, "黄金"),
            self._find_market_title(market_board, "WTI原油"),
        ]
        key_news = [str(item.get("title", "")).strip() for item in news_digest[:3] if str(item.get("title", "")).strip()]
        price_text = "，".join(item for item in key_prices if item)
        news_text = "；".join(key_news)
        if price_text and news_text:
            return f"一句话：钱追AI，避险没走。{price_text}。背后是：{news_text}。"
        return price_text or news_text

    def _build_money_direction_items(
        self,
        *,
        market_board: list[dict[str, Any]],
        news_digest: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        semi = self._find_market_title(market_board, "半导体板块")
        tech = self._find_market_title(market_board, "科技板块")
        nasdaq = self._find_market_title(market_board, "纳指")
        ten_year = self._find_market_title(market_board, "美国10年期国债收益率")
        gold = self._find_market_title(market_board, "黄金")
        wti = self._find_market_title(market_board, "WTI原油")
        dry_bulk = self._find_market_title(market_board, "干散货ETF")
        btc = self._find_market_title(market_board, "比特币")
        items = [
            self._simple_image_item(
                title="流入：AI硬件和美股科技",
                summary=self._compact_market_titles((semi, tech, nasdaq)) or "科技和AI仍是资金最愿意追的方向。",
                source="image_blocks",
            ),
            self._simple_image_item(
                title="保留：美债和黄金",
                summary=self._compact_market_titles((ten_year, gold)) or "风险偏好回来了，但避险线没有完全退场。",
                source="image_blocks",
            ),
            self._simple_image_item(
                title="流出：能源现货、航运弹性和加密",
                summary=self._compact_market_titles((wti, dry_bulk, btc)) or "高波动资产没有一起涨，说明这不是全面风险偏好。",
                source="image_blocks",
            ),
            self._simple_image_item(
                title="主要矛盾：AI推指数，中东压风险",
                summary="英伟达、英特尔把指数往上拉；美伊、霍尔木兹、油运又让资金不敢完全放开。",
                source="image_blocks",
            ),
        ]
        return items

    def _compact_market_titles(self, titles: tuple[str, ...]) -> str:
        compacted = []
        for title in titles:
            text = str(title or "").strip()
            if not text:
                continue
            compacted.append(text.replace(" ", ""))
        return " / ".join(compacted)

    def _find_market_title(self, market_board: list[dict[str, Any]], keyword: str) -> str:
        for item in market_board:
            title = str(item.get("title", "")).strip()
            if keyword in title:
                return title
        return ""

    def _pick_market_board_items(
        self,
        market_board: list[dict[str, Any]],
        *,
        keywords: tuple[str, ...],
        max_items: int,
    ) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in market_board:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            if not any(keyword in title for keyword in keywords):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            picked.append(item)
            if len(picked) >= max_items:
                break
        return picked

    def _build_image_mapping_items(
        self,
        *,
        news_digest: list[dict[str, Any]],
        side_signals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mapping: list[dict[str, Any]] = []
        news_text = " ".join(
            str(item.get("title", "")).strip()
            for item in news_digest[:12]
            if str(item.get("title", "")).strip()
        )
        if any(token in news_text for token in ("英伟达", "英特尔", "芯片", "Anthropic", "DeepSeek", "AI")):
            mapping.append(self._simple_image_item(
                title="AI和芯片新闻",
                summary="先看半导体、科技板块和纳指，这是昨夜最直接的资金表达。",
                source="image_blocks",
            ))
        if any(token in news_text for token in ("伊朗", "美伊", "霍尔木兹", "油运", "豁免")):
            mapping.append(self._simple_image_item(
                title="中东和航道新闻",
                summary="先看原油、黄金、航运和VIX，谈判一反复，价格也会跟着反复。",
                source="image_blocks",
            ))
        if any(token in news_text for token in ("矿产", "矿业", "供应链", "制裁", "关税")):
            mapping.append(self._simple_image_item(
                title="供应链和制裁新闻",
                summary="先看资源品、制造链和相关国家ETF，政策动作会慢慢传到估值和订单。",
                source="image_blocks",
            ))
        if side_signals:
            mapping.extend(side_signals[:3])
        return self._dedupe_image_items(mapping)[:6]

    def _build_image_news_digest(
        self,
        *,
        world_payload: dict[str, Any],
        raw_items: list[dict[str, Any]],
        max_items: int,
    ) -> list[dict[str, Any]]:
        grouped_from_world = self._dedupe_entries_by_group(
            [
                *list(world_payload.get("headline_events", []) or []),
                *list(world_payload.get("geopolitics", []) or []),
                *list(world_payload.get("macro_policy", []) or []),
                *list(world_payload.get("tech_ai_and_major_companies", []) or []),
                *[entry for entry in list(world_payload.get("equity_and_sector_moves", []) or []) if self._is_news_entry(entry)],
                *[entry for entry in list(world_payload.get("commodities", []) or []) if self._is_news_entry(entry)],
            ]
        )
        full_groups = self._build_group_entries(raw_items)
        grouped_from_raw = self._sorted_entries(
            [entry for entries in full_groups.values() for entry in entries]
        )
        grouped_items = [
            self._to_image_item(entry)
            for entry in self._dedupe_entries_by_group([*grouped_from_world, *grouped_from_raw])[: max_items * 3]
            if self._is_digest_entry_candidate(entry) and len(list(entry.get("member_item_ids", []) or [])) > 1
        ]
        raw_items_rendered = self._build_humanized_raw_news_items(raw_items, max_items=max_items * 2)
        merged: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for item in [*raw_items_rendered, *grouped_items]:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            key = title.lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            merged.append(item)
            if len(merged) >= max_items:
                break
        return merged

    def _build_humanized_raw_news_items(self, items: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
        rendered: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for item in sorted(items, key=self._news_digest_sort_key):
            if not self._is_digest_candidate(item):
                continue
            image_item = self._raw_item_to_image_story(item)
            if not self._is_digest_entry_candidate(image_item):
                continue
            title = str(image_item.get("title", "")).strip()
            if not title:
                continue
            key = title.lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            rendered.append(image_item)
            if len(rendered) >= max_items:
                break
        return rendered

    def _load_items(
        self,
        *,
        analysis_date: str | None,
        limit: int,
        include_stale: bool,
    ) -> list[dict[str, Any]]:
        fetch_limit = min(500, max(120, int(limit) * 8))
        items: list[dict[str, Any]] = []
        if analysis_date:
            exact_items = list(
                self.capture_service.list_recent_items(
                    limit=fetch_limit,
                    analysis_date=analysis_date,
                ).get("items", [])
                or []
            )
            recent_items = list(
                self.capture_service.list_recent_items(
                    limit=fetch_limit,
                    analysis_date=None,
                ).get("items", [])
                or []
            )
            merged_items = self._dedupe_items_by_id([*exact_items, *recent_items])
            window_items = [item for item in merged_items if self._matches_analysis_date_window(item, analysis_date)]
            supplemental_items = [
                item
                for item in merged_items
                if item not in window_items and self._matches_recent_context_window(item, analysis_date)
            ]
            items = [*window_items, *supplemental_items]
        else:
            items = list(
                self.capture_service.list_recent_items(
                    limit=fetch_limit,
                    analysis_date=None,
                ).get("items", [])
                or []
            )
        items = [item for item in items if self._is_money_relevant_item(item)]
        if not include_stale:
            items = self._restrict_to_latest_window(items)
        return items[: max(1, int(limit))]

    def _build_group_entries(self, items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            group_id = self._group_bucket_key(item)
            grouped_rows.setdefault(group_id, []).append(item)

        grouped_entries: dict[str, list[dict[str, Any]]] = {
            "macro_policy": [],
            "geopolitics": [],
            "equity_and_sector_moves": [],
            "rates_and_fx": [],
            "commodities": [],
            "tech_ai_and_major_companies": [],
        }
        for members in grouped_rows.values():
            entry = self._build_group_entry(members)
            grouped_entries.setdefault(str(entry.get("topic", "")).strip(), []).append(entry)

        for topic, entries in grouped_entries.items():
            grouped_entries[topic] = self._sorted_entries(entries)
        return grouped_entries

    def _build_group_entry(self, members: list[dict[str, Any]]) -> dict[str, Any]:
        ordered_members = sorted(members, key=self._item_sort_key)
        primary = ordered_members[0]
        event_cluster = dict(primary.get("event_cluster", {}) or {})
        topic = self._classify_item_topic(primary, members=ordered_members)
        importance_tier = self._importance_tier(primary, member_count=len(ordered_members))
        source_names = self._unique(
            [str(item.get("source_name", "")).strip() for item in ordered_members if str(item.get("source_name", "")).strip()]
        )
        linked_assets = self._linked_assets(primary, members=ordered_members)
        raw_title = str(primary.get("title", "")).strip()
        raw_summary = self._clean_text(str(primary.get("summary", "")).strip())
        title = self._human_news_title(primary, topic=topic)
        summary = self._human_news_summary(primary, topic=topic, member_count=len(ordered_members))
        why_it_matters = self._clean_text(
            str(primary.get("why_it_matters_cn", "")).strip()
            or str(primary.get("impact_summary", "")).strip()
        )
        if not why_it_matters:
            why_it_matters = self._human_news_why_it_matters(primary, topic=topic)
        return {
            "id": int(primary.get("item_id", 0) or 0),
            "group_id": str(event_cluster.get("cluster_id", "")).strip() or f"item-{int(primary.get('item_id', 0) or 0)}",
            "topic": topic,
            "importance_tier": importance_tier,
            "title": title,
            "summary": summary,
            "why_it_matters": why_it_matters,
            "raw_title": raw_title,
            "raw_summary": raw_summary,
            "direction": self._derive_direction(primary),
            "linked_assets": linked_assets,
            "published_at": self._published_at(primary),
            "published_at_display": str(primary.get("published_at_display", "")).strip() or None,
            "source": {
                "primary_source": str(primary.get("source_name", "")).strip(),
                "coverage_tier": str(primary.get("coverage_tier", "")).strip(),
                "source_count": len(source_names),
                "sources": source_names[:4],
            },
            "confidence": dict(primary.get("source_capture_confidence", {}) or {}).get("level"),
            "member_item_ids": [int(item.get("item_id", 0) or 0) for item in ordered_members],
        }

    def _build_source_headline(
        self,
        *,
        headline_items: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None,
    ) -> str:
        if headline_items:
            titles = [str(item.get("title", "")).strip() for item in headline_items[:3] if str(item.get("title", "")).strip()]
            if titles:
                headline = "；".join(titles)
                board_headline = self._build_market_overview(dict(dict(market_snapshot or {}).get("asset_board", {}) or {}))
                if board_headline:
                    return f"{headline}。市场面上，{board_headline}"
                return headline
        board_headline = self._build_market_overview(dict(dict(market_snapshot or {}).get("asset_board", {}) or {}))
        return board_headline or "当前没有足够的隔夜高信号事件。"

    def _build_source_status(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        source_counter = Counter(
            str(item.get("source_name", "")).strip()
            for item in items
            if str(item.get("source_name", "")).strip()
        )
        registry = list(getattr(self.capture_service, "registry", []) or [])
        repo = getattr(self.capture_service, "repo", None)
        refresh_states: dict[str, dict[str, Any]] = {}
        if repo is not None and hasattr(repo, "list_source_refresh_states") and registry:
            refresh_states = repo.list_source_refresh_states(
                source_ids=[str(getattr(source, "source_id", "")).strip() for source in registry]
            )
        degraded_sources = [
            {
                "source_id": source_id,
                "last_refresh_status": str(state.get("last_refresh_status", "")).strip(),
                "last_error": str(state.get("last_error", "")).strip() or None,
            }
            for source_id, state in refresh_states.items()
            if str(state.get("last_refresh_status", "")).strip() in {"partial", "cooldown", "fail"}
        ]
        return {
            "configured_source_count": len(registry) if registry else None,
            "active_source_count": len(source_counter),
            "degraded_source_count": len(degraded_sources),
            "top_sources": [
                {
                    "label": label,
                    "count": count,
                }
                for label, count in source_counter.most_common(12)
            ],
            "degraded_sources": degraded_sources[:8],
        }

    def _build_world_headline(
        self,
        *,
        source_payload: dict[str, Any],
        asset_board: dict[str, Any],
        risk_signals: dict[str, Any],
    ) -> dict[str, Any]:
        risk_mode = str(risk_signals.get("risk_mode", "")).strip() or "mixed"
        market_headline = str(asset_board.get("headline", "")).strip()
        top_titles = [
            str(item.get("title", "")).strip()
            for item in list(source_payload.get("headline_items", []) or [])[:2]
            if str(item.get("title", "")).strip()
        ]
        if risk_mode == "risk_on":
            title = "昨夜全球资金偏向继续回到风险资产，但地缘和商品线没有退场。"
        elif risk_mode == "risk_off":
            title = "昨夜全球资金更偏防守，避险和敏感资产重新分化。"
        else:
            title = "昨夜全球资金没有走单边，而是在风险资产、利率和商品之间重新分配。"
        summary_parts = [self._build_market_overview(asset_board)] if asset_board else []
        if top_titles:
            summary_parts.append("消息面上，" + "；".join(top_titles))
        return {
            "title": title,
            "summary": " ".join(part for part in summary_parts if part).strip() or title,
            "confidence": "medium" if top_titles and market_headline else "low",
        }

    def _build_market_section(
        self,
        *,
        items: list[dict[str, Any]],
        topic: str,
        max_items: int,
    ) -> list[dict[str, Any]]:
        ranked = sorted(
            [dict(item) for item in items if isinstance(item, dict)],
            key=lambda item: (
                int(item.get("priority", 0) or 0),
                abs(float(item.get("change_pct") or 0.0)),
            ),
            reverse=True,
        )
        return [
            {
                "title": self._market_title(item),
                "summary": self._market_summary(item, topic=topic),
                "why_it_matters": self._market_why_it_matters(item, topic=topic),
                "importance_tier": "must_read" if index < 2 else "important",
                "topic": topic,
                "direction": self._market_direction(item),
                "linked_assets": [str(item.get("symbol", "")).strip()] if str(item.get("symbol", "")).strip() else [],
                "published_at": str(item.get("market_time", "")).strip() or None,
                "source": str(item.get("provider_name", "")).strip() or "market_snapshot",
            }
            for index, item in enumerate(ranked[: max_items])
        ]

    def _build_image_section(
        self,
        *,
        section_id: str,
        title: str,
        takeaway: str,
        items: list[dict[str, Any]],
        chart_hint: str,
    ) -> dict[str, Any]:
        rendered_items = self._dedupe_image_items([self._to_image_item(item) for item in items])
        return {
            "id": section_id,
            "title": title,
            "takeaway": takeaway,
            "item_count": len(rendered_items),
            "items": rendered_items,
            "chart_hint": chart_hint,
        }

    def _build_poster_hero(
        self,
        *,
        story_blocks: list[dict[str, Any]],
        market_board: list[dict[str, Any]],
        risk_signals: dict[str, Any],
    ) -> dict[str, Any]:
        risk_mode = str(risk_signals.get("risk_mode", "")).strip()
        title = "昨夜，全球资金继续换仓。"
        if risk_mode == "risk_on":
            title = "昨夜，风险资产继续走强。"
        elif risk_mode == "risk_off":
            title = "昨夜，避险情绪重新抬头。"
        board_bits = [str(item.get("title", "")).strip() for item in market_board[:5] if str(item.get("title", "")).strip()]
        block_bits = [str(block.get("title", "")).strip() for block in story_blocks[:3] if str(block.get("title", "")).strip()]
        summary_parts: list[str] = []
        if board_bits:
            summary_parts.append("关键数字：" + "；".join(board_bits))
        if block_bits:
            summary_parts.append("重点看：" + "、".join(block_bits))
        return {
            "title": title,
            "summary": " ".join(summary_parts).strip() or title,
            "badges": [],
        }

    def _build_simple_hero(
        self,
        *,
        news_digest: list[dict[str, Any]],
        market_board: list[dict[str, Any]],
        risk_signals: dict[str, Any],
    ) -> dict[str, Any]:
        risk_mode = str(risk_signals.get("risk_mode", "")).strip()
        title = "昨夜，全球市场继续波动。"
        if risk_mode == "risk_on":
            title = "昨夜，风险资产偏强。"
        elif risk_mode == "risk_off":
            title = "昨夜，避险情绪偏强。"
        board_bits = [str(item.get("title", "")).strip() for item in market_board[:6] if str(item.get("title", "")).strip()]
        news_bits = [str(item.get("title", "")).strip() for item in news_digest[:4] if str(item.get("title", "")).strip()]
        summary_parts: list[str] = []
        if news_bits:
            summary_parts.append("新闻：" + "；".join(news_bits))
        if board_bits:
            summary_parts.append("数据：" + "；".join(board_bits))
        return {
            "title": title,
            "summary": " ".join(summary_parts).strip() or title,
            "badges": [],
        }

    def _build_story_blocks(
        self,
        *,
        shipping_news: list[dict[str, Any]],
        tech_news: list[dict[str, Any]],
        trade_news: list[dict[str, Any]],
        gold_news: list[dict[str, Any]],
        options_news: list[dict[str, Any]],
        europe_energy_news: list[dict[str, Any]],
        asset_board: dict[str, Any],
        market_snapshot: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        indexes = list(asset_board.get("indexes", []) or [])
        sectors = list(asset_board.get("sectors", []) or [])
        rates_fx = list(asset_board.get("rates_fx", []) or [])
        metals = list(asset_board.get("precious_metals", []) or [])
        energy = list(asset_board.get("energy", []) or [])
        industrial_metals = list(asset_board.get("industrial_metals", []) or [])
        sentiment = list(asset_board.get("sentiment", []) or [])

        energy_block_items = [
            *[self._to_image_item(item) for item in shipping_news[:3]],
            *[self._to_image_item(item) for item in europe_energy_news[:1]],
            *[self._market_item_to_image(item, topic="commodities") for item in energy[:3]],
        ]
        us_equity_block_items = [
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in indexes[:4]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in sentiment[:1]],
        ]
        tech_block_items = [
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in sectors[:5]],
            *[self._to_image_item(item) for item in tech_news[:3]],
        ]
        macro_block_items = [
            *[self._market_item_to_image(item, topic="rates_and_fx") for item in rates_fx[:6]],
            *[self._market_item_to_image(item, topic="commodities") for item in metals[:2]],
            *[self._to_image_item(item) for item in gold_news[:2]],
        ]
        positioning_block_items = self._build_positioning_items(
            market_snapshot=market_snapshot,
            trade_news=trade_news,
            options_news=options_news,
        )
        trade_block_items = [
            *[self._to_image_item(item) for item in trade_news[:4]],
            *[self._market_item_to_image(item, topic="commodities") for item in industrial_metals[:2]],
        ]

        blocks = [
            {
                "id": "energy_shipping",
                "title": "中东、航运、原油",
                "items": self._dedupe_image_items(energy_block_items)[:7],
            },
            {
                "id": "us_equities",
                "title": "美股指数和风险偏好",
                "items": self._dedupe_image_items(us_equity_block_items)[:6],
            },
            {
                "id": "us_equities_tech",
                "title": "科技、半导体、主要板块",
                "items": self._dedupe_image_items(tech_block_items)[:8],
            },
            {
                "id": "rates_dollar_gold",
                "title": "利率、美元、黄金",
                "items": self._dedupe_image_items(macro_block_items)[:7],
            },
            {
                "id": "positioning_policy",
                "title": "Polymarket、期权、仓位",
                "items": self._dedupe_image_items(positioning_block_items)[:8],
            },
            {
                "id": "trade_supply_chain",
                "title": "贸易、供应链、工业金属",
                "items": self._dedupe_image_items(trade_block_items)[:8],
            },
        ]
        return blocks

    def _build_market_board(
        self,
        *,
        asset_board: dict[str, Any],
        risk_signals: dict[str, Any],
    ) -> list[dict[str, Any]]:
        indexes = list(asset_board.get("indexes", []) or [])
        sectors = list(asset_board.get("sectors", []) or [])
        rates_fx = list(asset_board.get("rates_fx", []) or [])
        metals = list(asset_board.get("precious_metals", []) or [])
        energy = list(asset_board.get("energy", []) or [])
        industrial_metals = list(asset_board.get("industrial_metals", []) or [])
        shipping = list(asset_board.get("shipping", []) or [])
        global_equities = list(asset_board.get("global_equities", []) or [])
        crypto = list(asset_board.get("crypto", []) or [])
        credit = list(asset_board.get("credit", []) or [])
        duration = list(asset_board.get("duration", []) or [])
        sentiment = list(asset_board.get("sentiment", []) or [])
        china_proxies = list(asset_board.get("china_proxies", []) or [])
        china_mapped_futures = list(asset_board.get("china_mapped_futures", []) or [])
        items = [
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in indexes[:4]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in sectors[:4]],
            *[self._market_item_to_image(item, topic="rates_and_fx") for item in rates_fx[:6]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in sentiment[:1]],
            *[self._market_item_to_image(item, topic="commodities") for item in metals[:2]],
            *[self._market_item_to_image(item, topic="commodities") for item in energy[:3]],
            *[self._market_item_to_image(item, topic="commodities") for item in industrial_metals[:2]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in shipping[:3]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in global_equities[:4]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in crypto[:2]],
            *[self._market_item_to_image(item, topic="rates_and_fx") for item in duration[:1]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in credit[:4]],
            *[self._market_item_to_image(item, topic="equity_and_sector_moves") for item in china_proxies[:2]],
            *[self._mapped_future_to_image(item) for item in china_mapped_futures[:4]],
        ]
        if str(risk_signals.get("risk_mode", "")).strip():
            risk_label = {
                "risk_on": "偏进攻",
                "risk_off": "偏防守",
                "mixed": "分化",
            }.get(str(risk_signals.get("risk_mode", "")).strip(), str(risk_signals.get("risk_mode", "")).strip())
            items.insert(
                0,
                {
                    "title": f"风险状态 {risk_label}",
                    "summary": "这是昨夜整体情绪的快速读数。",
                    "why_it_matters": "",
                    "direction": None,
                    "importance_tier": "important",
                    "linked_assets": [],
                    "published_at": None,
                    "source": "market_snapshot",
                },
            )
        return self._dedupe_image_items(items)[:42]

    def _build_side_signals(
        self,
        *,
        market_snapshot: dict[str, Any] | None,
        news_pool: list[dict[str, Any]],
        asset_board: dict[str, Any],
        options_news: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prediction = dict(dict(market_snapshot or {}).get("prediction_markets", {}) or {})
        cftc = dict(dict(market_snapshot or {}).get("cftc_signals", {}) or {})
        fedwatch = dict(dict(market_snapshot or {}).get("fedwatch_signals", {}) or {})
        industrial_metals = list(asset_board.get("industrial_metals", []) or [])
        china_proxies = list(asset_board.get("china_proxies", []) or [])
        items: list[dict[str, Any]] = []
        if prediction:
            status = str(prediction.get("status", "")).strip() or "unknown"
            reason = str(prediction.get("status_reason", "")).strip() or ""
            items.append(self._simple_image_item(
                title=f"Polymarket：{status}",
                summary=reason or "当前没有可用定义。",
                source=str(prediction.get("provider_name", "")).strip() or "Polymarket",
            ))
        if cftc:
            headline = str(cftc.get("headline", "")).strip()
            if headline:
                items.append(self._simple_image_item(
                    title="CFTC 仓位",
                    summary=headline,
                    source=str(cftc.get("provider_name", "")).strip() or "CFTC",
                ))
        if fedwatch:
            items.append(self._simple_image_item(
                title=f"FedWatch：{str(fedwatch.get('status', '')).strip() or 'unknown'}",
                summary=str(fedwatch.get("status_reason", "")).strip() or str(fedwatch.get("error", "")).strip() or "暂无可用数据。",
                source=str(fedwatch.get("provider_name", "")).strip() or "FedWatch",
            ))
        items.extend(self._to_image_item(item) for item in options_news)
        items.extend(self._market_item_to_image(item, topic="commodities") for item in industrial_metals[:2])
        items.extend(self._market_item_to_image(item, topic="equity_and_sector_moves") for item in china_proxies[:2])
        return self._dedupe_image_items(items)[:10]

    def _build_simple_side_signals(
        self,
        *,
        market_snapshot: dict[str, Any] | None,
        news_items: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        asset_board = dict(dict(market_snapshot or {}).get("asset_board", {}) or {})
        prediction = dict(dict(market_snapshot or {}).get("prediction_markets", {}) or {})
        kalshi = dict(dict(market_snapshot or {}).get("kalshi_signals", {}) or {})
        cftc = dict(dict(market_snapshot or {}).get("cftc_signals", {}) or {})
        fedwatch = dict(dict(market_snapshot or {}).get("fedwatch_signals", {}) or {})
        items: list[dict[str, Any]] = []
        if prediction:
            prediction_headline = str(prediction.get("headline", "")).strip()
            items.append(self._simple_image_item(
                title="Polymarket",
                summary=prediction_headline or f"{str(prediction.get('status', '')).strip() or 'unknown'} | {str(prediction.get('status_reason', '')).strip() or '无补充'}",
                source=str(prediction.get("provider_name", "")).strip() or "Polymarket",
            ))
        if cftc:
            items.append(self._simple_image_item(
                title="CFTC 仓位",
                summary=str(cftc.get("headline", "")).strip() or "暂无仓位摘要。",
                source=str(cftc.get("provider_name", "")).strip() or "CFTC",
            ))
        shipping_items = list(asset_board.get("shipping", []) or [])
        if shipping_items:
            items.append(self._simple_image_item(
                title="航运代理",
                summary="；".join(self._market_title(item) for item in shipping_items[:3] if self._market_title(item)),
                source="asset_board",
            ))
        credit_items = [
            *list(asset_board.get("duration", []) or []),
            *list(asset_board.get("credit", []) or []),
        ]
        if credit_items:
            items.append(self._simple_image_item(
                title="债券与信用",
                summary="；".join(self._market_title(item) for item in credit_items[:4] if self._market_title(item)),
                source="asset_board",
            ))
        if kalshi and str(kalshi.get("status", "")).strip() == "ready":
            kalshi_headline = str(kalshi.get("headline", "")).strip()
            items.append(self._simple_image_item(
                title="Kalshi",
                summary=kalshi_headline or f"{str(kalshi.get('status', '')).strip() or 'unknown'} | {str(kalshi.get('status_reason', '')).strip() or '无补充'}",
                source=str(kalshi.get("provider_name", "")).strip() or "Kalshi",
            ))
        if fedwatch and str(fedwatch.get("status", "")).strip() == "ready":
            fedwatch_headline = str(fedwatch.get("headline", "")).strip()
            items.append(self._simple_image_item(
                title="FedWatch",
                summary=fedwatch_headline or str(fedwatch.get("status_reason", "")).strip() or "暂无可用数据。",
                source=str(fedwatch.get("provider_name", "")).strip() or "FedWatch",
            ))
        items.extend(self._build_news_side_signals(news_items=list(news_items or [])))
        return items[:8]

    def _build_news_side_signals(self, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not news_items:
            return []
        channel_events = self._pick_news_side_items(
            news_items,
            keywords=("hormuz", "strait", "shipping", "tanker", "freight", "naval mines", "explosive mines", "blockade"),
            max_items=3,
        )
        sanction_events = self._pick_news_side_items(
            news_items,
            keywords=("ofac", "sanction", "designation", "general license", "waiver", "tariff", "section 301", "critical minerals"),
            max_items=3,
        )
        side_items: list[dict[str, Any]] = []
        if channel_events:
            side_items.append(self._simple_image_item(
                title="航道事件",
                summary="；".join(channel_events),
                source="news_capture",
            ))
        if sanction_events:
            side_items.append(self._simple_image_item(
                title="制裁/贸易事件",
                summary="；".join(sanction_events),
                source="news_capture",
            ))
        return side_items

    def _pick_news_side_items(
        self,
        news_items: list[dict[str, Any]],
        *,
        keywords: tuple[str, ...],
        max_items: int,
    ) -> list[str]:
        picked: list[str] = []
        seen: set[str] = set()
        for item in sorted(news_items, key=self._news_digest_sort_key):
            if not self._is_digest_candidate(item):
                continue
            title = self._rewrite_story_title(item, topic=self._classify_item_topic(item, members=[item]))
            if not title:
                continue
            raw_title = self._clean_news_title(str(item.get("title", "")).strip())
            title_text = f"{title} {raw_title}".lower()
            if not any(keyword in title_text for keyword in keywords):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            source = str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
            label = f"{source}：{title}" if source else title
            picked.append(self._clean_text(label))
            if len(picked) >= max_items:
                break
        return picked

    def _build_news_digest_from_items(self, items: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
        digest: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        source_counts: Counter[str] = Counter()
        for item in sorted(items, key=self._news_digest_sort_key):
            if not self._is_digest_candidate(item):
                continue
            raw_title = str(item.get("title", "")).strip()
            if not raw_title:
                continue
            title = self._clean_news_title(raw_title)
            title_key = title.lower()
            if title_key in seen_titles:
                continue
            source_name = str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
            normalized_source = source_name.lower()
            source_cap = _NEWS_SOURCE_CAP_OVERRIDES.get(normalized_source, 2)
            if source_counts[normalized_source] >= source_cap:
                continue
            seen_titles.add(title_key)
            source_counts[normalized_source] += 1
            raw_summary = self._clean_text(str(item.get("summary", "")).strip())
            digest.append(
                {
                    "title": title,
                    "summary": raw_summary or self._one_line_from_topic(topic=self._classify_item_topic(item, members=[item])),
                    "why_it_matters": "",
                    "direction": None,
                    "importance_tier": None,
                    "linked_assets": [],
                    "published_at": self._published_at(item),
                    "source": source_name or None,
                }
            )
            if len(digest) >= max_items:
                break
        return digest

    def _is_digest_entry_candidate(self, entry: dict[str, Any]) -> bool:
        text = " ".join(
            part
            for part in (
                str(entry.get("title", "")).strip(),
                str(entry.get("raw_title", "")).strip(),
                str(entry.get("summary", "")).strip(),
                str(entry.get("raw_summary", "")).strip(),
            )
            if part
        ).lower()
        if not text:
            return False
        if any(
            marker in text
            for marker in (
                "american dream",
                "grocery",
                "groceries",
                "family of 4",
                "left the u.s. for china",
                "deepen their hold on india's auto market",
                "inside india",
                "america in focus",
                "repair economy",
                "gave him away",
                "while driving a tesla",
                "hollywood production startup",
                "rare type of hearing loss",
            )
        ):
            return False
        return True

    def _news_digest_sort_key(self, item: dict[str, Any]) -> tuple[int, int, int, int, int, float]:
        base_key = self._item_sort_key(item)
        return (-self._news_priority_score(item), *base_key)

    def _news_priority_score(self, item: dict[str, Any]) -> int:
        source_name = str(item.get("source_name", "")).strip().lower()
        text = " ".join(
            part
            for part in (
                source_name,
                str(item.get("title", "")).strip().lower(),
                str(item.get("summary", "")).strip().lower(),
            )
            if part
        )
        score = _NEWS_PRIORITY_SOURCE_SCORES.get(source_name, 0)
        for marker, delta in _NEWS_PRIORITY_MARKERS:
            if marker in text:
                score += delta
        for marker, delta in _NEWS_DEPRIORITIZE_MARKERS:
            if marker in text:
                score += delta
        confidence_score = int(dict(item.get("source_capture_confidence", {}) or {}).get("score", 0) or 0)
        score += min(12, confidence_score // 10)
        priority = int(item.get("priority", 0) or 0)
        score += min(18, priority // 8)
        if self._timestamp(self._published_at(item)) > 0:
            score += 4
        return score

    def _is_digest_candidate(self, item: dict[str, Any]) -> bool:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title:
            return False
        text = f"{title} {summary}".lower()
        if any(marker in text for marker in _CEREMONIAL_EXCLUDE_MARKERS):
            return False
        source_name = str(item.get("source_name", "")).strip().lower()
        if "department of energy articles" in source_name and "fact sheet" in text:
            return False
        if "white house news" in source_name and "fact sheet" in text:
            return False
        if "white house news" in source_name and "presidential message" in text:
            return False
        if "federal reserve news" in source_name and "enforcement action" in text:
            return False
        if "department of energy articles" in source_name and "fact sheet" in text and not self._contains_any_keyword(
            text,
            (
                "oil",
                "gas",
                "pipeline",
                "lng",
                "electricity",
                "power",
                "grid",
                "ai",
                "semiconductor",
                "critical minerals",
            ),
        ):
            return False
        if "technology" in source_name and not self._contains_any_keyword(
            text,
            (
                "ai",
                "chip",
                "semiconductor",
                "nvidia",
                "intel",
                "amd",
                "amazon",
                "meta",
                "google",
                "microsoft",
                "anthropic",
                "openai",
                "earnings",
                "stock",
                "market cap",
                "valuation",
                "revenue",
                "profit",
            ),
        ):
            return False
        if any(
            marker in text
            for marker in (
                "bank robber",
                "killings",
                "granted bond",
                "visually impaired runners",
                "hearing loss",
                "american dream",
                "grocery",
                "groceries",
                "family of 4",
                "rent and $100",
                "left the u.s. for china",
            )
        ):
            return False
        if any(
            marker in text
            for marker in (
                "deepen their hold on india's auto market",
                "we tried out",
                "here's what happened",
                "inside india",
                "america in focus",
                "repair economy",
                "gave him away",
                "week ahead",
                "while driving a tesla",
                "hollywood production startup",
                "rare type of hearing loss",
            )
        ):
            return False
        return True

    def _raw_item_to_image_story(self, item: dict[str, Any]) -> dict[str, Any]:
        topic = self._classify_item_topic(item, members=[item])
        return {
            "title": self._rewrite_story_title(item, topic=topic),
            "summary": self._rewrite_story_summary(item, topic=topic),
            "why_it_matters": self._human_news_why_it_matters(item, topic=topic),
            "direction": self._derive_direction(item),
            "importance_tier": self._importance_tier(item, member_count=1),
            "linked_assets": self._linked_assets(item, members=[item]),
            "published_at": self._published_at(item),
            "source": str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip() or None,
            "raw_title": self._clean_news_title(str(item.get("title", "")).strip()),
            "raw_summary": self._clean_text(str(item.get("summary", "")).strip()),
        }

    def _rewrite_story_title(self, item: dict[str, Any], *, topic: str) -> str:
        raw_title = self._clean_news_title(str(item.get("title", "")).strip())
        if not raw_title:
            return "昨夜有一条值得看的新闻"
        text = " ".join(
            part
            for part in (
                raw_title.lower(),
                str(item.get("summary", "")).strip().lower(),
            )
            if part
        )
        rules: tuple[tuple[tuple[str, ...], str], ...] = (
            (("nvidia", "record", "$5 trillion"), "英伟达收盘创新高，市值站上5万亿美元"),
            (("intel", "leads", "us stock market", "records"), "英特尔大涨带动美股继续刷新纪录"),
            (("intel", "24%", "1987"), "英特尔暴涨24%，创1987年以来最佳单日表现"),
            (("intel", "best day since 1987"), "英特尔创1987年以来最佳单日表现"),
            (("google", "anthropic", "$40 billion"), "Google拟向Anthropic追加最高400亿美元"),
            (("amazon", "meta", "custom chips"), "Meta采用亚马逊自研芯片，AI芯片合作升温"),
            (("chip stocks", "pricey"), "芯片越涨越贵，资金还在继续追高"),
            (("call options", "semiconductor"), "半导体期权继续追价，芯片交易热度不退"),
            (("hormuz", "mines"), "霍尔木兹海峡排雷升级，全球油运继续受扰"),
            (("hormuz", "open the strait"), "美国继续围着霍尔木兹海峡做护航和排险"),
            (("iran", "talks", "oil prices"), "美伊再传会谈消息，油价高位震荡"),
            (("iranian", "russian oil waivers"), "美国称不再续发伊朗和俄罗斯原油豁免"),
            (("currency swaps", "iran war"), "伊朗冲突外溢到金融面，美元互换安排成焦点"),
            (("germany", "energy prices"), "能源价格再起，德国复苏预期被打断"),
            (("critical minerals", "us", "eu"), "美欧加深关键矿产合作，供应链博弈继续加码"),
            (("deepseek", "update"), "DeepSeek发布新一轮模型更新"),
            (("gold", "rangebound"), "黄金高位震荡，市场先等新信号"),
            (("spot gold", "session highs"), "美国通胀预期回落后，黄金重新走高"),
            (("gold and silver", "stonex"), "StoneX称金银仍有上行空间，但波动会继续加大"),
            (("better trade than oil", "etf"), "美伊冲突把能源波动交易推火，一只ETF年内涨超600%"),
            (("talks stumble", "iran"), "美伊谈判再生变数，巴基斯坦会晤未能成行"),
            (("war squeezes global mining",), "伊朗战事外溢到矿业，柴油和酸供应趋紧"),
            (("u.s. stocks pulled back", "brent oil"), "布伦特油价一度冲上107美元，美股从高位回落"),
            (("us stocks fall", "brent oil"), "布伦特油价一度冲上107美元，美股从高位回落"),
            (("wall street", "records", "iran war"), "伊朗战争仍在继续，美股却还在刷新纪录"),
            (("rate cuts", "warsh"), "别急着押降息，Warsh接任美联储也未必马上转鸽"),
            (("20,000 job cuts", "meta", "microsoft"), "Meta和微软裁员超过2万人，AI替代焦虑升温"),
        )
        for keywords, title in rules:
            if all(keyword in text for keyword in keywords):
                return title
        return raw_title

    def _rewrite_story_summary(self, item: dict[str, Any], *, topic: str) -> str:
        text = " ".join(
            part
            for part in (
                str(item.get("title", "")).strip().lower(),
                str(item.get("summary", "")).strip().lower(),
            )
            if part
        )
        rules: tuple[tuple[tuple[str, ...], str], ...] = (
            (("nvidia", "record", "$5 trillion"), "AI龙头在财报前继续吸金，半导体和算力主线还在被资金硬顶。"),
            (("intel", "leads", "us stock market", "records"), "英特尔财报点燃芯片股，美股再创新高，但油价和伊朗风险仍在旁边压着。"),
            (("intel", "24%", "1987"), "财报超预期把老牌CPU股也重新点燃，芯片强势开始往更宽的板块扩散。"),
            (("google", "anthropic", "$40 billion"), "大厂继续把钱和算力往头部模型公司集中，AI生态绑定得更深了。"),
            (("amazon", "meta", "custom chips"), "Meta想减少对英伟达的依赖，亚马逊自研芯片拿到了更重的客户背书。"),
            (("chip stocks", "pricey"), "半导体已经涨出拥挤感，但期权资金还在加仓追涨。"),
            (("hormuz", "mines"), "只要霍尔木兹风险没有彻底消掉，油价、运价和避险资产就会继续反复。"),
            (("iran", "talks", "oil prices"), "谈判预期一松一紧，油价就跟着来回摆，市场暂时还不敢彻底放下中东线。"),
            (("iranian", "russian oil waivers"), "能源供给约束预期没有退，制裁和豁免线还会继续影响原油定价。"),
            (("currency swaps", "iran war"), "战争如果继续拖，风险就不只是油，还会传到美元流动性和区域金融稳定。"),
            (("germany", "energy prices"), "能源成本重新压回欧洲增长故事里，欧洲复苏预期要被重新估。"),
            (("critical minerals", "us", "eu"), "资源安全已经从口号变成动作，后面会直接传到矿业、制造和科技链估值。"),
            (("deepseek", "update"), "模型迭代没有停，国产大模型这条线还在继续往云和应用侧渗透。"),
            (("gold", "rangebound"), "避险情绪还在，但市场先等利率和中东后续，再决定黄金下一步往哪边走。"),
            (("spot gold", "session highs"), "情绪和通胀预期稍一松动，资金还是会先回到黄金这类老避险资产。"),
            (("gold and silver", "stonex"), "贵金属还有上冲空间，但伊朗局势和美联储预期会让价格继续大幅来回。"),
            (("better trade than oil", "etf"), "这说明资金已经不只是在买原油本身，而是在追更高弹性的能源波动交易。"),
            (("talks stumble", "iran"), "会谈反反复复，说明中东线还远没走完。"),
            (("war squeezes global mining",), "地缘扰动已经开始从油运往采矿成本和原料供应继续传导。"),
            (("u.s. stocks pulled back", "brent oil"), "油价重新抬头后，风险资产开始犹豫，股市高位的容错率变低。"),
            (("us stocks fall", "brent oil"), "油价重新抬头后，风险资产开始犹豫，股市高位的容错率变低。"),
            (("wall street", "records", "iran war"), "这说明资金还在押AI和大盘权重股，但战争、油价和消费信心仍是隐患。"),
            (("rate cuts", "warsh"), "美联储接班预期不等于立刻降息，利率交易不能只看人事传闻。"),
            (("20,000 job cuts", "meta", "microsoft"), "大厂一边加码AI，一边压缩人力成本，AI交易开始影响真实就业叙事。"),
        )
        for keywords, summary in rules:
            if all(keyword in text for keyword in keywords):
                return summary
        return self._one_line_from_topic(topic=topic)

    def _clean_news_title(self, raw_title: str) -> str:
        title = str(raw_title or "").strip()
        title = re.sub(r"^(FACT SHEET:|Analysis:)\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def _build_positioning_items(
        self,
        *,
        market_snapshot: dict[str, Any] | None,
        trade_news: list[dict[str, Any]],
        options_news: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        prediction = dict(dict(market_snapshot or {}).get("prediction_markets", {}) or {})
        cftc = dict(dict(market_snapshot or {}).get("cftc_signals", {}) or {})
        fedwatch = dict(dict(market_snapshot or {}).get("fedwatch_signals", {}) or {})
        if prediction:
            items.append(self._simple_image_item(
                title="Polymarket",
                summary=f"状态：{str(prediction.get('status', '')).strip() or 'unknown'}；{str(prediction.get('status_reason', '')).strip() or '无额外说明'}",
                source=str(prediction.get("provider_name", "")).strip() or "Polymarket",
            ))
        if cftc:
            items.append(self._simple_image_item(
                title="CFTC 仓位",
                summary=str(cftc.get("headline", "")).strip() or "暂无仓位摘要。",
                source=str(cftc.get("provider_name", "")).strip() or "CFTC",
            ))
        if fedwatch:
            items.append(self._simple_image_item(
                title="FedWatch",
                summary=str(fedwatch.get("status_reason", "")).strip() or str(fedwatch.get("error", "")).strip() or "暂无可用数据。",
                source=str(fedwatch.get("provider_name", "")).strip() or "FedWatch",
            ))
        items.extend(self._to_image_item(item) for item in options_news[:3])
        items.extend(self._to_image_item(item) for item in trade_news[:3])
        return items

    def _dedupe_entries_by_group(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for entry in self._sorted_entries(entries):
            key = str(entry.get("group_id", "")).strip() or str(entry.get("title", "")).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(entry)
        return result

    def _select_entries_by_keywords(
        self,
        entries: list[dict[str, Any]],
        *,
        keywords: tuple[str, ...],
        max_items: int,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for entry in entries:
            text = " ".join(
                part.lower()
                for part in (
                    str(entry.get("title", "")).strip(),
                    str(entry.get("summary", "")).strip(),
                    str(entry.get("raw_title", "")).strip(),
                    str(entry.get("raw_summary", "")).strip(),
                )
                if part
            )
            if any(keyword.lower() in text for keyword in keywords):
                selected.append(entry)
        return self._dedupe_entries_by_group(selected)[: max_items]

    def _market_item_to_image(self, item: dict[str, Any], *, topic: str) -> dict[str, Any]:
        return {
            "title": self._market_title(item),
            "summary": self._market_summary(item, topic=topic),
            "why_it_matters": self._market_why_it_matters(item, topic=topic),
            "direction": self._market_direction(item),
            "importance_tier": "important",
            "linked_assets": [str(item.get("symbol", "")).strip()] if str(item.get("symbol", "")).strip() else [],
            "published_at": str(item.get("market_time", "")).strip() or None,
            "source": str(item.get("provider_name", "")).strip() or "market_snapshot",
        }

    def _simple_image_item(self, *, title: str, summary: str, source: str) -> dict[str, Any]:
        return {
            "title": title,
            "summary": self._clean_text(summary),
            "why_it_matters": "",
            "direction": None,
            "importance_tier": "important",
            "linked_assets": [],
            "published_at": None,
            "source": source,
        }

    def _mapped_future_to_image(self, item: dict[str, Any]) -> dict[str, Any]:
        future_name = str(item.get("future_name", "")).strip() or str(item.get("future_code", "")).strip()
        watch_direction = str(item.get("watch_direction", "")).strip() or "mixed"
        direction_label = {
            "up": "偏上",
            "down": "偏下",
            "mixed": "震荡",
        }.get(watch_direction, watch_direction)
        return {
            "title": f"{future_name} {direction_label}",
            "summary": self._clean_text(str(item.get("driver_summary", "")).strip() or "跨市场映射信号。"),
            "why_it_matters": "",
            "direction": watch_direction if watch_direction in {"up", "down", "mixed"} else None,
            "importance_tier": "important",
            "linked_assets": list(item.get("driver_symbols", []) or []),
            "published_at": None,
            "source": "asset_board",
        }

    def _build_cross_asset_links(
        self,
        *,
        grouped_items: dict[str, list[dict[str, Any]]],
        asset_board: dict[str, Any],
        risk_signals: dict[str, Any],
    ) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        risk_mode = str(risk_signals.get("risk_mode", "")).strip()
        rates = list(asset_board.get("rates_fx", []) or [])
        sectors = list(asset_board.get("sectors", []) or [])
        strongest_sector = next(
            (item for item in sectors if str(item.get("symbol", "")).strip() == "SOXX"),
            sectors[0] if sectors else None,
        )
        if rates and strongest_sector is not None:
            links.append(
                {
                    "title": "利率和成长板块在同一张图里读",
                    "summary": (
                        f"{str(rates[0].get('display_name', '')).strip()} 和 "
                        f"{str(strongest_sector.get('display_name', '')).strip()} 的组合，"
                        "能直接看出昨夜钱是更偏防守还是更偏进攻。"
                    ),
                    "linked_sections": ["rates_and_fx", "equity_and_sector_moves"],
                }
            )
        if risk_mode and list(grouped_items.get("geopolitics", []) or []):
            links.append(
                {
                    "title": "地缘消息和商品价格要一起看",
                    "summary": "昨夜地缘新闻不是单独存在的，它会先反映到油、金和整体风险偏好上。",
                    "linked_sections": ["geopolitics", "commodities"],
                }
            )
        if list(grouped_items.get("tech_ai_and_major_companies", []) or []) and strongest_sector is not None:
            links.append(
                {
                    "title": "大公司和板块强弱是连着的",
                    "summary": "AI 和大厂新闻通常不是孤立事件，资金会马上用芯片和科技板块去表达态度。",
                    "linked_sections": ["tech_ai_and_major_companies", "equity_and_sector_moves"],
                }
            )
        return links[:4]

    def _build_image_badges(self, *, world_payload: dict[str, Any]) -> list[str]:
        badges: list[str] = []
        headline_text = " ".join(
            [
                str(dict(world_payload.get("global_headline", {}) or {}).get("title", "")).strip().lower(),
                str(dict(world_payload.get("global_headline", {}) or {}).get("summary", "")).strip().lower(),
            ]
        )
        if "risk_on" in headline_text:
            badges.append("risk_on")
        elif "risk_off" in headline_text:
            badges.append("risk_off")
        if any("国债收益率" in str(item.get("title", "")) and str(item.get("direction", "")) == "down" for item in list(world_payload.get("rates_and_fx", []) or [])):
            badges.append("yields_down")
        if any(("原油" in str(item.get("title", "")) or "oil" in str(item.get("title", "")).lower()) and str(item.get("direction", "")) == "up" for item in list(world_payload.get("commodities", []) or [])):
            badges.append("oil_up")
        if any("半导体" in str(item.get("title", "")) and str(item.get("direction", "")) == "up" for item in list(world_payload.get("equity_and_sector_moves", []) or [])):
            badges.append("semis_up")
        return badges or ["mixed"]

    def _build_image_watchpoints(self, *, world_payload: dict[str, Any]) -> list[str]:
        watchpoints: list[str] = []
        if list(world_payload.get("geopolitics", []) or []):
            watchpoints.append("地缘线还没走完，继续盯油价、航运和避险资产有没有二次放大。")
        if any("国债收益率" in str(item.get("title", "")) for item in list(world_payload.get("rates_and_fx", []) or [])):
            watchpoints.append("收益率这条线如果继续下，成长和高估值板块容易继续被资金接。")
        if list(world_payload.get("tech_ai_and_major_companies", []) or []):
            watchpoints.append("芯片和 AI 这条交易线有没有从龙头扩散到更广的科技板块。")
        if not watchpoints:
            watchpoints.append("下一时段先看价格会不会继续确认昨夜这套叙事。")
        return watchpoints[:3]

    def _classify_item_topic(self, item: dict[str, Any], *, members: list[dict[str, Any]]) -> str:
        cluster = dict(item.get("event_cluster", {}) or {})
        item_id = int(item.get("item_id", 0) or 0)
        topic_tags = " ".join(
            str(tag).strip().lower()
            for tag in list(cluster.get("topic_tags", []) or [])
            if str(tag).strip()
        ) if self._is_cluster_groupable(cluster, item_id=item_id) else ""
        source_name = str(item.get("source_name", "")).strip().lower()
        title = str(item.get("title", "")).strip().lower()
        summary = str(item.get("summary", "")).strip().lower()
        member_titles = " ".join(
            str(member.get("title", "")).strip().lower()
            for member in members
            if str(member.get("title", "")).strip()
        )
        text = " ".join(
            part
            for part in (
                topic_tags,
                source_name,
                title,
                summary,
                member_titles,
            )
            if part
        )
        if any(
            token in text
            for token in (
                "iran",
                "israel",
                "ukraine",
                "war",
                "sanction",
                "hormuz",
                "ceasefire",
                "shipping",
                "strait",
                "trade action",
                "critical minerals",
                "section 301",
                "forced labor",
                "export control",
                "supply chain resilience",
                "ustr",
            )
        ):
            return "geopolitics"
        if self._contains_any_keyword(text, ("chip", "chips", "semiconductor", "ai", "nvidia", "intel", "amd")):
            return "tech_ai_and_major_companies"
        if any(
            token in text
            for token in (
                "gold",
                "silver",
                "copper",
                "aluminum",
                "aluminium",
                "oil",
                "crude",
                "natural gas",
                "lng",
                "energy prices",
                "shipping costs",
                "freight",
                "commodity",
            )
        ) and "prediction market" not in text:
            return "commodities"
        if self._contains_any_keyword(text, ("dollar", "usd", "cnh", "yen", "eurusd", "usdjpy", "forex")):
            return "rates_and_fx"
        if any(
            token in text
            for token in (
                "cftc",
                "prediction market",
                "jurisdiction",
                "federal reserve",
                "ecb",
                "central bank",
                "inflation",
                "yield",
                "rate decision",
            )
        ):
            return "macro_policy"
        for topic, keywords in _TOPIC_PATTERNS:
            if any(keyword in text for keyword in keywords):
                return topic
        for member in members:
            implications = list(member.get("market_implications", []) or [])
            for implication in implications:
                direction = str(dict(implication).get("direction", "")).strip()
                if any(token in direction for token in ("油", "金", "铜", "天然气", "gold", "oil", "copper")):
                    return "commodities"
        return "equity_and_sector_moves"

    def _group_bucket_key(self, item: dict[str, Any]) -> str:
        cluster = dict(item.get("event_cluster", {}) or {})
        item_id = int(item.get("item_id", 0) or 0)
        fallback = f"item-{item_id}"
        cluster_id = str(cluster.get("cluster_id", "")).strip()
        if not cluster_id or not self._is_cluster_groupable(cluster, item_id=item_id):
            return fallback
        return cluster_id

    def _is_cluster_groupable(self, cluster: dict[str, Any], *, item_id: int) -> bool:
        cluster_item_count = int(cluster.get("item_count", 0) or 0)
        cluster_source_count = int(cluster.get("source_count", 0) or 0)
        primary_item_id = int(cluster.get("primary_item_id", 0) or 0)
        if cluster_item_count > _GROUP_CLUSTER_MAX_ITEMS or cluster_source_count > _GROUP_CLUSTER_MAX_SOURCES:
            return False
        if primary_item_id and primary_item_id != item_id and cluster_item_count > 2:
            return False
        return True

    def _is_money_relevant_item(self, item: dict[str, Any]) -> bool:
        title = str(item.get("title", "")).strip().lower()
        summary = str(item.get("summary", "")).strip().lower()
        text = f"{title} {summary}".strip()
        source_id = str(item.get("source_id", "")).strip().lower()
        keyword_match = any(self._text_contains_keyword(text, keyword) for keyword in _MONEY_RELEVANCE_KEYWORDS)
        if keyword_match:
            return True
        source_name = str(item.get("source_name", "")).strip().lower()
        coverage_tier = str(item.get("coverage_tier", "")).strip().lower()
        if any(marker in text for marker in _CEREMONIAL_EXCLUDE_MARKERS):
            return False
        source_def = self._source_registry_entry(source_id=source_id)
        if source_def is not None:
            source_class = str(getattr(source_def, "source_class", "")).strip().lower()
            asset_tags = tuple(str(tag).strip().lower() for tag in tuple(getattr(source_def, "asset_tags", ()) or ()) if str(tag).strip())
            if source_class in {"policy", "macro"} and asset_tags:
                return True
            if source_class in {"policy", "macro", "calendar"} and any(
                token in text
                for token in (
                    "trade",
                    "tariff",
                    "sanction",
                    "rates",
                    "yield",
                    "inflation",
                    "cpi",
                    "ppi",
                    "payroll",
                    "employment",
                    "energy",
                    "oil",
                    "gas",
                    "shipping",
                    "technology",
                    "semiconductor",
                    "forecast",
                    "digital euro",
                    "critical minerals",
                    "prediction market",
                )
            ):
                return True
        if coverage_tier == "official_policy" and any(token in source_name for token in ("white house", "congress", "president")):
            return False
        if any(marker in source_name for marker in _BROAD_FINANCE_SOURCE_MARKERS):
            return True
        if any(token in source_name for token in ("cnbc", "reuters", "bloomberg", "wall street", "financial", "market")) and (
            "company" in text or "industry" in text or "economic" in text
        ):
            return True
        return False

    def _source_registry_entry(self, *, source_id: str) -> object | None:
        normalized = str(source_id or "").strip()
        if not normalized:
            return None
        for source in list(getattr(self.capture_service, "registry", []) or []):
            if str(getattr(source, "source_id", "")).strip().lower() == normalized.lower():
                return source
        return None

    def _importance_tier(self, item: dict[str, Any], *, member_count: int) -> str:
        status = str(item.get("analysis_status", "")).strip()
        authority = str(item.get("source_authority", "")).strip()
        confidence = str(dict(item.get("source_capture_confidence", {}) or {}).get("level", "")).strip()
        support_count = int(dict(item.get("cross_source_confirmation", {}) or {}).get("supporting_source_count", 0) or 0)
        priority = int(item.get("priority", 0) or 0)
        if status == "ready" and (authority == "primary_official" or confidence == "high" or support_count >= 1 or member_count >= 2 or priority >= 85):
            return "must_read"
        if status in {"ready", "review"} or confidence in {"high", "medium"}:
            return "important"
        return "watch"

    def _linked_assets(self, item: dict[str, Any], *, members: list[dict[str, Any]]) -> list[str]:
        linked: list[str] = []
        for member in members:
            for implication in list(member.get("market_implications", []) or []):
                direction = str(dict(implication).get("direction", "")).strip()
                if direction:
                    linked.append(direction)
            for tag in list(dict(member.get("event_cluster", {}) or {}).get("topic_tags", []) or []):
                normalized = str(tag).strip()
                if normalized:
                    linked.append(normalized)
        return self._unique(linked)[:6]

    def _derive_direction(self, item: dict[str, Any]) -> str | None:
        implications = list(item.get("market_implications", []) or [])
        stances = {str(dict(implication).get("stance", "")).strip() for implication in implications if str(dict(implication).get("stance", "")).strip()}
        if len(stances) > 1:
            return "mixed"
        if "positive" in stances:
            return "positive"
        if "negative" in stances:
            return "negative"
        if "inflationary" in stances:
            return "inflationary"
        text = " ".join(
            part
            for part in (
                str(item.get("title", "")).strip().lower(),
                str(item.get("summary", "")).strip().lower(),
            )
            if part
        )
        for label, keywords in _DIRECTION_PATTERNS:
            if any(keyword in text for keyword in keywords):
                return label
        return None

    def _item_sort_key(self, item: dict[str, Any]) -> tuple[int, int, int, int, float]:
        status = str(item.get("analysis_status", "")).strip()
        authority = str(item.get("source_authority", "")).strip()
        confidence_score = int(dict(item.get("source_capture_confidence", {}) or {}).get("score", 0) or 0)
        priority = int(item.get("priority", 0) or 0)
        return (
            _STATUS_ORDER.get(status, 99),
            _AUTHORITY_ORDER.get(authority, 99),
            -confidence_score,
            -priority,
            -self._timestamp(item.get("published_at") or item.get("created_at")),
        )

    def _sorted_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tier_order = {"must_read": 0, "important": 1, "watch": 2}
        return sorted(
            entries,
            key=lambda entry: (
                tier_order.get(str(entry.get("importance_tier", "")).strip(), 99),
                -len(list(entry.get("member_item_ids", []) or [])),
                -self._timestamp(entry.get("published_at")),
            ),
        )

    def _merge_section_entries(self, *, entries: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for entry in self._sorted_entries(entries):
            key = str(entry.get("group_id", "")).strip() or str(entry.get("title", "")).strip().lower()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(entry)
        return merged[: max_items]

    def _build_time_window(
        self,
        *,
        analysis_date: str,
        market_snapshot: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        market_times = [
            str(item.get("market_time", "")).strip()
            for item in list(dict(dict(market_snapshot or {}).get("asset_board", {}) or {}).get("indexes", []) or [])
            if str(item.get("market_time", "")).strip()
        ]
        item_times = [self._published_at(item) for item in items if self._published_at(item)]
        start_at = min(market_times + item_times) if (market_times or item_times) else None
        end_at = max(item_times) if item_times else None
        return {
            "label": "美东收盘后到中国早晨",
            "start_at": start_at,
            "end_at": end_at,
            "analysis_date": analysis_date,
        }

    def _resolve_analysis_date(
        self,
        *,
        requested: str | None,
        market_snapshot: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> str:
        candidate = str(requested or "").strip()
        if candidate:
            return candidate
        market_date = str(dict(market_snapshot or {}).get("analysis_date", "")).strip()
        if market_date:
            return market_date
        latest_timestamp = max((self._timestamp(self._published_at(item)) for item in items), default=0.0)
        if latest_timestamp > 0:
            return datetime.fromtimestamp(latest_timestamp, tz=timezone.utc).date().isoformat()
        return datetime.now(timezone.utc).date().isoformat()

    def _get_market_snapshot(self, *, analysis_date: str | None) -> dict[str, Any] | None:
        if self.market_snapshot_service is None:
            return None
        return self.market_snapshot_service.get_daily_snapshot(analysis_date=analysis_date)

    def _market_title(self, item: dict[str, Any]) -> str:
        display_name = str(item.get("display_name", "")).strip() or str(item.get("symbol", "")).strip()
        change_pct_text = str(item.get("change_pct_text", "")).strip()
        if change_pct_text:
            return f"{display_name} {change_pct_text}"
        return display_name

    def _build_market_overview(self, asset_board: dict[str, Any]) -> str:
        indexes = list(asset_board.get("indexes", []) or [])
        rates_fx = list(asset_board.get("rates_fx", []) or [])
        commodities = [
            *list(asset_board.get("precious_metals", []) or []),
            *list(asset_board.get("energy", []) or []),
        ]
        parts: list[str] = []
        lead_indexes = [self._market_title(item) for item in indexes[:2] if self._market_title(item)]
        if lead_indexes:
            parts.append("美股这边 " + "、".join(lead_indexes))
        ten_year = next((item for item in rates_fx if "10年期国债收益率" in str(item.get("display_name", "")).strip()), None)
        if ten_year is not None:
            parts.append(self._market_title(ten_year))
        gold = next((item for item in commodities if "黄金" in str(item.get("display_name", "")).strip()), None)
        oil = next((item for item in commodities if "WTI原油" in str(item.get("display_name", "")).strip()), None)
        commodity_bits = [self._market_title(item) for item in (gold, oil) if item is not None]
        if commodity_bits:
            parts.append("商品上 " + "、".join(commodity_bits))
        return "；".join(part for part in parts if part)

    def _human_news_title(self, item: dict[str, Any], *, topic: str) -> str:
        raw_title = str(item.get("title", "")).strip()
        signals = self._detect_news_signals(item)
        if signals["gold"]:
            return "黄金暂时没走单边，市场先转入观望"
        if signals["iran"] and signals["shipping"]:
            return "中东这条线还在搅动油运和航运"
        if signals["iran"]:
            return "美伊这条线又起变化，市场继续盯中东风险"
        if signals["trade_policy"] and signals["critical_minerals"]:
            return "美欧开始收紧关键矿产和供应链这条线"
        if signals["trade_policy"]:
            return "贸易和供应链规则又有新动作"
        if signals["prediction_market"]:
            return "美国监管继续争预测市场的话语权"
        if signals["chip"]:
            return "芯片这条线越涨越贵，资金还在继续追"
        if signals["gold"]:
            return "黄金暂时没走单边，市场先转入观望"
        if signals["europe_energy"]:
            return "欧洲能源压力又起来了，复苏预期被往下压"
        if topic == "geopolitics":
            return "地缘和贸易这条线还在反复"
        if topic == "commodities":
            return "商品这边先给出了新的信号"
        if topic == "tech_ai_and_major_companies":
            return "AI 和芯片还是最能吸钱的方向之一"
        if topic == "macro_policy":
            return "监管和政策边界还在继续变化"
        return raw_title or "昨夜有一条值得看的新闻"

    def _human_news_summary(self, item: dict[str, Any], *, topic: str, member_count: int) -> str:
        signals = self._detect_news_signals(item)
        if signals["gold"]:
            summary = "黄金没有继续加速，说明避险情绪还在，但市场先进入等信号阶段。"
        elif signals["iran"] and signals["shipping"]:
            summary = "钱不只是在看油价，已经开始顺着航运、运价和中东运输风险往下交易。"
        elif signals["iran"]:
            summary = "中东消息没有结束，原油、黄金和整体风险偏好都还会跟着这条线动。"
        elif signals["trade_policy"] and signals["critical_minerals"]:
            summary = "关键矿产、制造和芯片供应链这条线被重新强调，后面容易继续传到资源和科技链定价上。"
        elif signals["trade_policy"]:
            summary = "贸易和供应链监管预期没有退，出口链和制造链还得继续盯政策动作。"
        elif signals["prediction_market"]:
            summary = "监管边界还没定清，相关交易品种能不能继续做大，要先看谁来管。"
        elif signals["chip"]:
            summary = "半导体已经不便宜了，但资金还在往 AI 硬件这条线挤。"
        elif signals["europe_energy"]:
            summary = "能源成本和地缘扰动又在压欧洲增长，欧洲复苏这条线短期没那么顺了。"
        else:
            summary = self._one_line_from_topic(topic=topic)
        if member_count > 1:
            summary = f"{summary} 这一组里还合并了 {member_count} 条同主题来源。"
        return self._clean_text(summary)

    def _human_news_why_it_matters(self, item: dict[str, Any], *, topic: str) -> str:
        signals = self._detect_news_signals(item)
        if signals["chip"]:
            return "芯片是现在最能代表风险偏好的交易线之一。"
        if signals["gold"] or signals["oil"] or signals["shipping"]:
            return "商品会比股市更早反映地缘、通胀和避险情绪。"
        if signals["trade_policy"] or signals["critical_minerals"]:
            return "贸易和供应链规则一变，制造、资源和科技链都会被重新定价。"
        return self._one_line_from_topic(topic=topic)

    def _one_line_from_topic(self, *, topic: str) -> str:
        mapping = {
            "geopolitics": "地缘和贸易消息不会只停在标题上，通常会顺着商品、航运和风险偏好往下传。",
            "commodities": "商品线经常比别的资产更快把情绪和预期写进价格里。",
            "tech_ai_and_major_companies": "AI 和芯片还是全球资金最爱表达观点的一条线。",
            "macro_policy": "政策和监管边界一动，资金对相关资产的容忍度就会跟着变。",
            "rates_and_fx": "利率和汇率是隔夜定价最底层的方向盘。",
            "equity_and_sector_moves": "股市和板块强弱，是昨夜风险偏好最直接的结果。",
        }
        return mapping.get(topic, "这条消息本身不一定最大，但它能帮助判断昨夜资金到底在想什么。")

    def _detect_news_signals(self, item: dict[str, Any]) -> dict[str, bool]:
        source_name = str(item.get("source_name", "")).strip().lower()
        event_cluster = dict(item.get("event_cluster", {}) or {})
        item_id = int(item.get("item_id", 0) or 0)
        topic_tags = " ".join(
            str(tag).strip().lower()
            for tag in list(event_cluster.get("topic_tags", []) or [])
            if str(tag).strip()
        ) if self._is_cluster_groupable(event_cluster, item_id=item_id) else ""
        text = " ".join(
            part for part in (
                source_name,
                str(item.get("title", "")).strip().lower(),
                str(item.get("summary", "")).strip().lower(),
                topic_tags,
            ) if part
        )
        return {
            "iran": any(token in text for token in ("iran", "hormuz", "blockade", "ceasefire", "middle east")),
            "shipping": any(token in text for token in ("shipping", "tanker", "freight", "cargo", "maritime", "strait")),
            "trade_policy": any(token in text for token in ("trade", "tariff", "section 301", "ustr", "export control", "forced labor", "supply chain")),
            "critical_minerals": any(token in text for token in ("critical minerals", "minerals", "rare earth")),
            "prediction_market": any(token in text for token in ("prediction market", "jurisdiction", "cftc")),
            "chip": any(token in text for token in ("chip", "chips", "semiconductor", "nvidia", "intel", "amd", "smh")),
            "gold": any(token in text for token in ("gold", "bullion", "precious metal")),
            "oil": any(token in text for token in ("oil", "crude", "brent", "wti", "energy")),
            "europe_energy": any(token in text for token in ("germany", "europe", "euro area")) and any(token in text for token in ("energy", "gas", "oil", "power")),
        }

    def _market_summary(self, item: dict[str, Any], *, topic: str) -> str:
        display_name = str(item.get("display_name", "")).strip() or str(item.get("symbol", "")).strip()
        change_pct_text = str(item.get("change_pct_text", "")).strip()
        if topic == "rates_and_fx":
            return f"{display_name}{change_pct_text or ''}，这条线在告诉你资金对利率和汇率的态度。"
        if topic == "commodities":
            return f"{display_name}{change_pct_text or ''}，地缘、通胀和避险情绪先从这里反应。"
        return f"{display_name}{change_pct_text or ''}，这是昨夜风险偏好最直接的价格表达。"

    def _market_why_it_matters(self, item: dict[str, Any], *, topic: str) -> str:
        symbol = str(item.get("symbol", "")).strip()
        if topic == "rates_and_fx":
            if symbol == "^TNX":
                return "利率先变，估值和风险偏好通常会跟着变。"
            if symbol == "DX-Y.NYB":
                return "美元方向会影响全球风险资产和商品定价。"
            return "汇率和利率是隔夜资金重新定价的底层变量。"
        if topic == "commodities":
            return "商品价格会把地缘、供需和通胀预期一起压缩进一行价格里。"
        return "这是昨夜市场最直观的价格表达。"

    def _market_direction(self, item: dict[str, Any]) -> str:
        change_pct = float(item.get("change_pct") or 0.0)
        if change_pct > 0.15:
            return "up"
        if change_pct < -0.15:
            return "down"
        return "mixed"

    def _published_at(self, item: dict[str, Any]) -> str | None:
        for key in ("published_at", "created_at"):
            value = str(item.get(key, "")).strip()
            if value:
                return value
        return None

    def _restrict_to_latest_window(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest_timestamp = max((self._timestamp(self._published_at(item)) for item in items), default=0.0)
        if latest_timestamp <= 0:
            return items
        cutoff = latest_timestamp - timedelta(hours=72).total_seconds()
        filtered = [
            item
            for item in items
            if self._timestamp(self._published_at(item)) >= cutoff
        ]
        return filtered or items

    def _matches_analysis_date_window(self, item: dict[str, Any], analysis_date: str) -> bool:
        target = str(analysis_date or "").strip()
        if not target:
            return True
        item_dt = self._published_at_local_dt(item)
        if item_dt is None:
            return False
        target_date = datetime.fromisoformat(f"{target}T00:00:00").date()
        window_start = datetime.combine(target_date - timedelta(days=1), datetime.min.time(), tzinfo=self._shanghai_tz).replace(hour=18)
        window_end = datetime.combine(target_date, datetime.max.time(), tzinfo=self._shanghai_tz)
        return window_start <= item_dt <= window_end

    def _matches_recent_context_window(self, item: dict[str, Any], analysis_date: str) -> bool:
        target = str(analysis_date or "").strip()
        if not target:
            return True
        item_dt = self._published_at_local_dt(item)
        if item_dt is None:
            return False
        target_date = datetime.fromisoformat(f"{target}T00:00:00").date()
        window_start = datetime.combine(target_date - timedelta(days=3), datetime.min.time(), tzinfo=self._shanghai_tz)
        window_end = datetime.combine(target_date, datetime.max.time(), tzinfo=self._shanghai_tz)
        return window_start <= item_dt <= window_end

    def _dedupe_items_by_id(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[int] = set()
        result: list[dict[str, Any]] = []
        for item in items:
            item_id = int(item.get("item_id", 0) or 0)
            if item_id and item_id in seen:
                continue
            if item_id:
                seen.add(item_id)
            result.append(item)
        return result

    def _timestamp(self, value: object) -> float:
        candidate = str(value or "").strip()
        if not candidate:
            return 0.0
        try:
            normalized = candidate.replace("Z", "+00:00")
            if re.search(r"[+-]\d{4}$", normalized):
                normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return 0.0

    def _published_at_local_dt(self, item: dict[str, Any]) -> datetime | None:
        timestamp = self._timestamp(self._published_at(item))
        if timestamp <= 0:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(self._shanghai_tz)

    def _text_contains_keyword(self, text: str, keyword: str) -> bool:
        if not text or not keyword:
            return False
        return re.search(r"\b" + re.escape(keyword) + r"\b", text, flags=re.IGNORECASE) is not None

    def _contains_any_keyword(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(self._text_contains_keyword(text, keyword) for keyword in keywords)

    def _is_news_entry(self, entry: dict[str, Any]) -> bool:
        return isinstance(entry.get("source"), dict)

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _clean_text(self, value: str) -> str:
        compact = re.sub(r"\s+", " ", value or "").strip()
        return compact[:220] if len(compact) > 220 else compact

    def _to_image_item(self, item: dict[str, Any]) -> dict[str, Any]:
        source = item.get("source")
        if isinstance(source, dict):
            source_label = str(source.get("primary_source", "")).strip()
        else:
            source_label = str(source or "").strip()
        return {
            "title": str(item.get("title", "")).strip(),
            "summary": self._clean_text(str(item.get("summary", "")).strip()),
            "why_it_matters": self._clean_text(str(item.get("why_it_matters", "")).strip()),
            "direction": str(item.get("direction", "")).strip() or None,
            "importance_tier": str(item.get("importance_tier", "")).strip() or None,
            "linked_assets": list(item.get("linked_assets", []) or []),
            "published_at": str(item.get("published_at", "")).strip() or None,
            "source": source_label or None,
        }

    def _dedupe_image_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for item in items:
            title = str(item.get("title", "")).strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            deduped.append(item)
        return deduped
