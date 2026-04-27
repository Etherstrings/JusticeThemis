# -*- coding: utf-8 -*-
"""Build result-first desk/group report products from cached daily analysis."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


BUCKET_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "us_equities",
        "label": "美股指数与板块",
        "board_keys": ("indexes", "sectors", "sentiment"),
        "preferred_symbols": ("^IXIC", "^GSPC", "^DJI", "^RUT", "^VIX", "XLK", "SOXX", "XLF", "XLE"),
        "hard_keywords": (
            "nasdaq",
            "s&p",
            "dow",
            "russell",
            "vix",
            "wall street",
            "stock",
            "stocks",
            "equity",
            "equities",
            "share",
            "shares",
            "tech",
            "technology",
            "semiconductor",
            "chip",
            "chips",
            "ai",
            "earnings",
            "纳指",
            "标普",
            "道指",
            "罗素",
            "科技",
            "半导体",
            "芯片",
            "财报",
        ),
        "keywords": (
            "nasdaq",
            "s&p",
            "dow",
            "russell",
            "vix",
            "equity",
            "stock",
            "tech",
            "technology",
            "semiconductor",
            "chip",
            "ai",
            "bank",
            "financial",
            "earnings",
            "纳指",
            "标普",
            "道指",
            "罗素",
            "vix",
            "科技",
            "半导体",
            "芯片",
            "银行",
            "金融",
        ),
        "source_bonus_ids": ("ap_financial_markets", "cnbc_markets", "cnbc_technology", "ap_technology", "kitco_news"),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "rates_fx",
        "label": "利率汇率",
        "board_keys": ("rates_fx",),
        "preferred_symbols": ("^TNX", "DX-Y.NYB", "CNH=X"),
        "hard_keywords": (
            "treasury",
            "yield",
            "yields",
            "rate",
            "rates",
            "bond",
            "bonds",
            "fx",
            "dollar",
            "yuan",
            "cnh",
            "fed",
            "fomc",
            "inflation",
            "cpi",
            "ppi",
            "payroll",
            "employment",
            "central bank",
            "就业",
            "通胀",
            "美债",
            "收益率",
            "汇率",
            "美元",
            "离岸人民币",
            "人民币",
            "美联储",
            "央行",
        ),
        "keywords": (
            "treasury",
            "yield",
            "rate",
            "rates",
            "bond",
            "fx",
            "dollar",
            "yuan",
            "cnh",
            "fed",
            "fomc",
            "inflation",
            "cpi",
            "ppi",
            "payroll",
            "就业",
            "通胀",
            "美债",
            "收益率",
            "汇率",
            "美元",
            "离岸人民币",
            "人民币",
            "美联储",
        ),
        "source_bonus_ids": (
            "fed_news",
            "newyorkfed_news",
            "ecb_press",
            "census_economic_indicators",
            "bls_news_releases",
            "bls_release_schedule",
            "bea_news",
            "kitco_news",
            "ap_financial_markets",
            "cme_fedwatch",
            "cnbc_markets",
        ),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "energy_transport",
        "label": "能源运输",
        "board_keys": ("energy",),
        "preferred_symbols": ("CL=F", "BZ=F", "NG=F"),
        "hard_keywords": (
            "oil",
            "crude",
            "brent",
            "wti",
            "natural gas",
            "lng",
            "opec",
            "shipping",
            "tanker",
            "freight",
            "transport",
            "hormuz",
            "diesel",
            "gasoline",
            "jet fuel",
            "pipeline",
            "refinery",
            "原油",
            "布伦特",
            "天然气",
            "lng",
            "航运",
            "运价",
            "油轮",
            "霍尔木兹",
            "运输",
            "燃油",
            "成品油",
            "管道",
        ),
        "keywords": (
            "oil",
            "crude",
            "brent",
            "wti",
            "natural gas",
            "lng",
            "opec",
            "shipping",
            "tanker",
            "freight",
            "transport",
            "hormuz",
            "diesel",
            "gasoline",
            "原油",
            "布伦特",
            "wti",
            "天然气",
            "lng",
            "航运",
            "运价",
            "油轮",
            "霍尔木兹",
            "运输",
        ),
        "source_bonus_ids": (
            "eia_pressroom",
            "iea_news",
            "doe_articles",
            "oilprice_world_news",
            "ap_business",
            "ap_world",
            "cnbc_world",
            "cnbc_markets",
            "ofac_recent_actions",
        ),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "precious_metals",
        "label": "贵金属",
        "board_keys": ("precious_metals",),
        "preferred_symbols": ("GC=F", "SI=F"),
        "hard_keywords": (
            "gold",
            "silver",
            "bullion",
            "precious",
            "黄金",
            "白银",
            "贵金属",
        ),
        "keywords": (
            "gold",
            "silver",
            "bullion",
            "precious",
            "kitco",
            "黄金",
            "白银",
            "贵金属",
        ),
        "source_bonus_ids": ("kitco_news", "cftc_general_press_releases", "cftc_enforcement_press_releases", "ap_financial_markets"),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "industrial_metals",
        "label": "工业品",
        "board_keys": ("industrial_metals",),
        "preferred_symbols": ("HG=F", "ALI=F"),
        "hard_keywords": (
            "copper",
            "aluminum",
            "aluminium",
            "critical minerals",
            "mining",
            "minerals",
            "mineral",
            "nickel",
            "zinc",
            "steel",
            "iron ore",
            "smelter",
            "sulfuric acid",
            "sx-ew",
            "warehouse",
            "metal",
            "铜",
            "铝",
            "镍",
            "锌",
            "钢",
            "铁矿",
            "冶炼",
            "矿",
            "工业金属",
        ),
        "keywords": (
            "copper",
            "aluminum",
            "aluminium",
            "critical minerals",
            "mining",
            "minerals",
            "industrial metal",
            "lme",
            "warehouse",
            "smelter",
            "sulfuric acid",
            "sx-ew",
            "铜",
            "铝",
            "工业金属",
            "库存",
            "冶炼",
        ),
        "source_bonus_ids": ("iea_news", "worldbank_news", "spglobal_commodity_insights", "mining_com_markets", "fastmarkets_markets", "ustr_press_releases"),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "china_proxy",
        "label": "国内资产映射",
        "board_keys": ("china_proxies", "china_mapped_futures"),
        "preferred_symbols": ("KWEB", "FXI"),
        "hard_keywords": (
            "china",
            "chinese",
            "beijing",
            "hong kong",
            "hong kong stocks",
            "hong kong stock",
            "hong kong stocks",
            "hong kong shares",
            "hang seng",
            "hang seng index",
            "hang seng tech",
            "mainland chinese",
            "mainland china",
            "china stocks",
            "china stock",
            "china shares",
            "kweb",
            "fxi",
            "china adr",
            "china adrs",
            "china tech",
            "china technology",
            "china internet",
            "h shares",
            "pboc",
            "property",
            "stimulus",
            "adr",
            "中国",
            "港股",
            "北京",
            "香港",
            "中概",
            "央行",
            "地产",
            "政策刺激",
            "平台经济",
        ),
        "keywords": (
            "china",
            "chinese",
            "beijing",
            "hong kong",
            "hong kong stocks",
            "hong kong shares",
            "hang seng",
            "hang seng tech",
            "mainland chinese",
            "mainland china",
            "china stocks",
            "china shares",
            "kweb",
            "fxi",
            "china adr",
            "china adrs",
            "china tech",
            "china technology",
            "china internet",
            "h shares",
            "pboc",
            "property",
            "stimulus",
            "中国",
            "港股",
            "北京",
            "香港",
            "央行",
            "地产",
            "政策刺激",
            "平台经济",
        ),
        "source_bonus_ids": ("scmp_markets", "tradingeconomics_hk", "ap_business", "ap_world", "reuters_topics", "cnbc_world", "ustr_press_releases"),
        "source_penalty_ids": ("ap_politics",),
    },
    {
        "key": "probability_markets",
        "label": "概率市场",
        "board_keys": ("external_signal_panel",),
        "preferred_symbols": (),
        "hard_keywords": ("polymarket", "kalshi", "fedwatch", "cftc", "probability", "odds", "概率", "押注"),
        "keywords": (
            "polymarket",
            "kalshi",
            "fedwatch",
            "cftc",
            "probability",
            "odds",
            "概率",
            "押注",
        ),
    },
)

BUCKET_SPEC_BY_KEY = {spec["key"]: spec for spec in BUCKET_SPECS}

BUCKET_ALLOWED_SOURCE_IDS: dict[str, tuple[str, ...]] = {
    "rates_fx": (
        "fed_news",
        "newyorkfed_news",
        "ecb_press",
        "census_economic_indicators",
        "bls_news_releases",
        "bls_release_schedule",
        "bea_news",
        "kitco_news",
        "ap_financial_markets",
        "cme_fedwatch",
        "cnbc_markets",
        "cnbc_world",
        "ap_business",
        "ap_world",
    ),
    "precious_metals": (
        "kitco_news",
        "ap_financial_markets",
        "cftc_general_press_releases",
        "cftc_enforcement_press_releases",
        "cnbc_markets",
    ),
        "industrial_metals": (
            "mining_com_markets",
            "fastmarkets_markets",
            "ustr_press_releases",
            "spglobal_commodity_insights",
            "worldbank_news",
        "iea_news",
        "kitco_news",
        "ap_business",
        "ap_world",
    ),
}

SPECIFIC_TOPIC_BUCKET_HINTS: dict[str, str] = {
    "tech_equity": "us_equities",
    "equity_market": "us_equities",
    "technology_risk": "us_equities",
    "semiconductor_supply_chain": "us_equities",
    "oil_market": "energy_transport",
    "energy_supply": "energy_transport",
    "shipping_transport": "energy_transport",
    "gold_market": "precious_metals",
    "silver_market": "precious_metals",
    "precious_metals_safe_haven": "precious_metals",
    "industrial_metals": "industrial_metals",
    "copper_market": "industrial_metals",
    "aluminum_market": "industrial_metals",
    "china_policy": "china_proxy",
    "china_property": "china_proxy",
    "china_internet": "china_proxy",
    "hong_kong_market": "china_proxy",
    "currency_fx": "rates_fx",
    "yield_curve": "rates_fx",
    "inflation": "rates_fx",
}

SOFT_TOPIC_BUCKET_HINTS: dict[str, str] = {
    "rates_macro": "rates_fx",
    "macro_data": "rates_fx",
    "energy_shipping": "energy_transport",
    "shipping_logistics": "energy_transport",
    "trade_policy": "china_proxy",
}

DIRECTION_BUCKET_HINTS: dict[str, str] = {
    "自主可控半导体链": "us_equities",
    "高估值成长链": "us_equities",
    "银行/保险": "rates_fx",
    "高股息防御": "rates_fx",
    "油气开采": "energy_transport",
    "油服": "energy_transport",
    "原油/燃料油": "energy_transport",
    "天然气/LNG": "energy_transport",
    "航空与燃油敏感运输链": "energy_transport",
    "航运港口景气跟踪": "energy_transport",
}

BUCKET_PRIORITY = {spec["key"]: index for index, spec in enumerate(BUCKET_SPECS)}

BANNED_STYLE_TERMS = ("risk-on", "risk off", "risk-off", "risk_on", "risk_off", "受益", "承压", "主情景", "次情景", "失效条件")
MIN_BUCKET_NEWS_RELEVANCE = 6
MIN_GROUP_NEWS_BUCKET_ENTRIES = 2
THIN_BUT_REAL_GROUP_BUCKET_KEYS = {"china_proxy", "precious_metals", "industrial_metals"}

RATES_FX_OFFICIAL_MACRO_SOURCES = (
    "fed_news",
    "newyorkfed_news",
    "bls_news_releases",
    "bls_release_schedule",
    "bea_news",
    "census_economic_indicators",
)

RATES_FX_OFFICIAL_MACRO_TITLE_HINTS = (
    "advance monthly sales",
    "monthly sales",
    "retail sales",
    "food services",
    "inventories and sales",
    "trade inventories",
    "advance economic indicators",
    "employment situation",
    "consumer price index",
    "producer price index",
    "personal consumption expenditures",
    "pce",
    "job openings",
    "payroll",
    "unemployment",
    "inflation",
)


def build_result_first_reports(
    report: dict[str, Any],
    *,
    source_audit_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builder = ResultFirstReportBuilder(report=report, source_audit_pack=source_audit_pack)
    return {
        "desk_report": builder.build_desk_report(),
        "group_report": builder.build_group_report(),
    }


class ResultFirstReportBuilder:
    def __init__(
        self,
        *,
        report: dict[str, Any],
        source_audit_pack: dict[str, Any] | None = None,
    ) -> None:
        self.report = dict(report or {})
        self.analysis_date = str(self.report.get("analysis_date", "")).strip()
        self.access_tier = str(self.report.get("access_tier", "")).strip() or "free"
        self.report_version = int(self.report.get("version", 0) or 0)
        self.market_snapshot = dict(self.report.get("market_snapshot", {}) or {})
        self.asset_board = dict(self.market_snapshot.get("asset_board", {}) or self.market_snapshot or {})
        self.product_view = dict(self.report.get("product_view", {}) or {})
        self.follow_up_panel = dict(self.product_view.get("follow_up_panel", {}) or {})
        self.external_signal_panel = dict(self.product_view.get("external_signal_panel", {}) or {})
        self.summary = dict(self.report.get("summary", {}) or {})
        self.mainline_coverage = dict(self.report.get("mainline_coverage", {}) or {})
        self.source_audit_pack = dict(source_audit_pack or {})
        self.result_first_materials = [
            dict(item or {})
            for item in list(self.report.get("result_first_materials", []) or [])
            if isinstance(item, dict)
        ]
        self.direction_calls = [
            dict(item or {})
            for item in list(self.report.get("direction_calls", []) or [])
            if isinstance(item, dict)
        ]
        self.stock_calls = [
            dict(item or {})
            for item in list(self.report.get("stock_calls", []) or [])
            if isinstance(item, dict)
        ]
        self.items = self._merge_news_items()
        self.bucket_results = self._build_bucket_results()
        self.selected_bucket_news = self._build_bucket_news()
        self.ignored_messages = self._build_ignored_messages()
        self.asset_misses = self._build_asset_misses()
        self.playbook = self._build_a_share_playbook()

    def build_group_report(self) -> dict[str, Any]:
        opening = {
            "title": "一句定盘",
            "sentences": self._build_opening_sentences(max_sentences=2),
        }
        result_buckets = [bucket for bucket in self.bucket_results if bucket["rows"]]
        news_buckets: list[dict[str, Any]] = []
        for bucket_key, entries in self.selected_bucket_news.items():
            if len(entries) < MIN_GROUP_NEWS_BUCKET_ENTRIES and not self._allow_thin_group_bucket(bucket_key, entries):
                continue
            bucket = self._bucket_by_key(bucket_key)
            news_buckets.append(self._news_bucket_payload(bucket, entry_limit=6))
        ignored = {
            **self._ignored_heat_payload(message_limit=4, asset_limit=4),
        }
        playbook = {
            "title": "A股今天怎么打",
            "segments": [
                {key: value for key, value in segment.items() if key != "why"}
                for segment in self.playbook
            ],
        }
        section_order = ["一句定盘", "结果数据层", "新闻/信息层", "昨晚市场没认的消息", "A股今天怎么打"]
        payload = {
            "report_type": "group_report",
            "analysis_date": self.analysis_date,
            "access_tier": self.access_tier,
            "report_version": self.report_version,
            "bucket_order": [spec["label"] for spec in BUCKET_SPECS],
            "section_order": section_order,
            "opening": opening,
            "result_data": {
                "title": "结果数据层",
                "buckets": result_buckets,
            },
            "news_layer": {
                "title": "新闻/信息层",
                "buckets": news_buckets,
            },
            "ignored_heat": ignored,
            "a_share_playbook": playbook,
            "metadata": self._metadata_payload(),
        }
        payload["markdown"] = self._render_group_markdown(payload)
        return payload

    def _allow_thin_group_bucket(self, bucket_key: str, entries: list[dict[str, Any]]) -> bool:
        if bucket_key not in THIN_BUT_REAL_GROUP_BUCKET_KEYS:
            return False
        if len(entries) != 1:
            return False
        bucket = self._bucket_by_key(bucket_key)
        if not list(bucket.get("rows", []) or []):
            return False
        primary_entries, _ = self._split_bucket_entries(bucket_key, entries)
        return len(primary_entries) == 1

    def build_desk_report(self) -> dict[str, Any]:
        result_buckets = [self._desk_bucket(bucket) for bucket in self.bucket_results]
        news_buckets = [
            self._desk_news_bucket(bucket)
            for bucket in self.bucket_results
        ]
        attribution = {
            "title": "归因层",
            "buckets": [self._build_attribution_bucket(bucket) for bucket in self.bucket_results],
        }
        data_gaps = {
            "title": "数据缺口层",
            "items": self._build_data_gap_items(),
        }
        playbook = {
            "title": "A股映射层",
            "segments": self.playbook,
        }
        continuation_check = {
            "title": "盘后续线验证",
            "items": self._build_continuation_check_items(),
        }
        section_order = ["一句定盘", "结果数据层", "新闻/信息层", "归因层", "数据缺口层", "A股映射层"]
        payload = {
            "report_type": "desk_report",
            "analysis_date": self.analysis_date,
            "access_tier": self.access_tier,
            "report_version": self.report_version,
            "bucket_order": [spec["label"] for spec in BUCKET_SPECS],
            "section_order": section_order,
            "opening": {
                "title": "一句定盘",
                "sentences": self._build_opening_sentences(max_sentences=3),
            },
            "result_data": {
                "title": "结果数据层",
                "buckets": result_buckets,
            },
            "news_layer": {
                "title": "新闻/信息层",
                "buckets": news_buckets,
            },
            "attribution_layer": attribution,
            "data_gap_layer": data_gaps,
            "a_share_mapping": playbook,
            "continuation_check": continuation_check,
            "ignored_heat": {
                **self._ignored_heat_payload(message_limit=6, asset_limit=6),
            },
            "metadata": self._metadata_payload(),
        }
        payload["markdown"] = self._render_desk_markdown(payload)
        return payload

    def _metadata_payload(self) -> dict[str, Any]:
        at_a_glance = dict(self.product_view.get("at_a_glance", {}) or {})
        return {
            "market_date": str(self.market_snapshot.get("market_date", "")).strip() or str(at_a_glance.get("market_date", "")).strip(),
            "window_label": str(at_a_glance.get("window_label", "")).strip(),
            "mainline_status": str(at_a_glance.get("mainline_status", "")).strip() or str(self.mainline_coverage.get("status", "")).strip(),
            "market_data_status": str(at_a_glance.get("market_data_status", "")).strip() or str(self.follow_up_panel.get("market_data_status", "")).strip(),
            "event_group_count": int(self.source_audit_pack.get("event_group_count", 0) or 0),
            "included_item_count": int(self.source_audit_pack.get("included_item_count", 0) or 0),
        }

    def _merge_news_items(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in self.result_first_materials:
            item_id = self._item_key(item)
            merged[item_id] = {
                **dict(item),
                "_is_headline": False,
                "_is_result_first_material": True,
            }
        for item in list(self.report.get("supporting_items", []) or []):
            if not isinstance(item, dict):
                continue
            item_id = self._item_key(item)
            merged[item_id] = {
                **dict(item),
                **merged.get(item_id, {}),
                "_is_headline": False,
                "_is_result_first_material": bool(merged.get(item_id, {}).get("_is_result_first_material")),
            }
        for item in list(self.report.get("headline_news", []) or []):
            if not isinstance(item, dict):
                continue
            item_id = self._item_key(item)
            merged[item_id] = {
                **merged.get(item_id, {}),
                **dict(item),
                "_is_headline": True,
                "_is_result_first_material": bool(merged.get(item_id, {}).get("_is_result_first_material")),
            }
        items = list(merged.values())
        items.sort(
            key=lambda item: (
                0 if bool(item.get("_is_headline")) else 1,
                0 if bool(item.get("_is_result_first_material")) else 1,
                -int(item.get("signal_score", 0) or 0),
                self._official_bonus(item) * -1,
                self._item_id(item),
            )
        )
        return items

    def _build_bucket_results(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for spec in BUCKET_SPECS:
            rows: list[dict[str, Any]]
            if spec["key"] == "probability_markets":
                rows = self._build_probability_rows()
            elif spec["key"] == "china_proxy":
                rows = self._build_china_proxy_rows(spec)
            else:
                rows = self._build_market_rows(spec)
            texture = self._build_bucket_texture(spec["key"], rows)
            results.append(
                {
                    "bucket_key": spec["key"],
                    "bucket_label": spec["label"],
                    "rows": rows,
                    "texture": texture,
                    "status": "ready" if rows else "empty",
                    "dominant_sign": self._dominant_sign(rows),
                    "news_sign": self._bucket_news_sign(spec["key"], rows),
                    "lead_line": rows[0]["line"] if rows else "",
                }
            )
        return results

    def _build_bucket_texture(self, bucket_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {}
        if bucket_key == "us_equities":
            return self._build_us_equities_texture(rows)
        if bucket_key == "china_proxy":
            return self._build_china_proxy_texture(rows)
        return {}

    def _build_us_equities_texture(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        core_rows = self._rows_for_symbols(
            rows,
            symbols=("^IXIC", "^GSPC", "^DJI", "^RUT", "XLK", "SOXX", "XLF", "XLE"),
        )
        if not core_rows:
            return {}
        market_shape = self._us_equities_market_shape(core_rows)
        leaders = self._texture_side_rows(core_rows, positive=True)
        laggards = self._texture_side_rows(core_rows, positive=False)

        if market_shape == "结构分化":
            if leaders and laggards:
                texture_line = (
                    f"昨夜不是普涨也不是普跌，{self._texture_rows_phrase(leaders)}在硬撑，"
                    f"{self._texture_rows_phrase(laggards)}在拖，盘面是结构分化。"
                )
            elif leaders:
                texture_line = f"昨夜美股有分化，{self._texture_rows_phrase(leaders)}单独偏强，其余没全跟。"
            elif laggards:
                texture_line = f"昨夜美股有分化，{self._texture_rows_phrase(laggards)}单独偏弱，其余没一起掉。"
            else:
                texture_line = "昨夜美股这桶在分化，但还没分到能一句话喊满。"
        elif market_shape == "普涨":
            if leaders:
                texture_line = f"昨夜更像普涨，{self._texture_rows_phrase(leaders)}在领涨，没看到明显拖累。"
            else:
                texture_line = "昨夜更像普涨，但谁在带头还不够清楚。"
        elif market_shape == "普跌":
            if laggards:
                texture_line = f"昨夜更像普跌，{self._texture_rows_phrase(laggards)}在带头往下，没看到谁能单独扛住。"
            else:
                texture_line = "昨夜更像普跌，但谁在带头往下还不够清楚。"
        elif leaders and laggards:
            texture_line = (
                f"昨夜美股有点裂，{self._texture_rows_phrase(leaders)}偏强，"
                f"{self._texture_rows_phrase(laggards)}偏弱。"
            )
        elif leaders:
            texture_line = f"昨夜美股不是普涨，{self._texture_rows_phrase(leaders)}更强，其余一般。"
        elif laggards:
            texture_line = f"昨夜美股不是普跌，{self._texture_rows_phrase(laggards)}更弱，其余没一起掉。"
        else:
            texture_line = "昨夜美股这桶还不够整，先认结果，别把结构脑补满。"

        return {
            "market_shape": market_shape,
            "leaders": leaders,
            "laggards": laggards,
            "texture_line": self._clean_line(texture_line),
        }

    def _build_china_proxy_texture(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        core_rows = self._rows_for_symbols(rows, symbols=("KWEB", "FXI"))
        if not core_rows:
            return {}
        market_shape = self._china_proxy_market_shape(core_rows)
        leaders = self._texture_side_rows(core_rows, positive=True)
        laggards = self._texture_side_rows(core_rows, positive=False)
        dominant_sign = self._dominant_sign(core_rows)

        if market_shape == "结构分化":
            if leaders and laggards:
                texture_line = (
                    f"国内资产映射昨夜不是一边倒，{self._texture_rows_phrase(leaders)}在撑，"
                    f"{self._texture_rows_phrase(laggards)}在拖。"
                )
            elif leaders:
                texture_line = f"国内资产映射昨夜有分化，{self._texture_rows_phrase(leaders)}单独偏强，其余没跟。"
            elif laggards:
                texture_line = f"国内资产映射昨夜有分化，{self._texture_rows_phrase(laggards)}单独偏弱，其余没一起掉。"
            else:
                texture_line = "国内资产映射昨夜有分化，但还没分到能一句话喊满。"
        elif market_shape == "普涨":
            if leaders:
                texture_line = f"国内资产映射昨夜整体偏强，{self._texture_rows_phrase(leaders)}都在抬，盘面先认的是港股和中概回暖。"
            else:
                texture_line = "国内资产映射昨夜整体偏强，但谁在带头还不够清楚。"
        elif market_shape == "普跌":
            if laggards:
                texture_line = f"国内资产映射昨夜整体偏弱，{self._texture_rows_phrase(laggards)}都在掉，盘面先认的是中概和港股映射压力。"
            else:
                texture_line = "国内资产映射昨夜整体偏弱，但谁在拖还不够清楚。"
        elif laggards or dominant_sign < 0:
            detail = self._texture_rows_phrase(laggards) if laggards else "KWEB/FXI 都没怎么抬头"
            texture_line = f"国内资产映射昨夜偏弱，{detail}没跟上，盘面先认的是中概和港股映射压力。"
        elif leaders or dominant_sign > 0:
            detail = self._texture_rows_phrase(leaders) if leaders else "KWEB/FXI 都在抬"
            texture_line = f"国内资产映射昨夜偏强，{detail}在抬，盘面先认的是港股和中概回暖。"
        else:
            texture_line = "国内资产映射昨夜整体一般，但还没有足够细的结构料去证明是谁在拖。"

        watch_clause = self._china_watch_texture_clause(rows, dominant_sign=dominant_sign)
        if watch_clause:
            texture_line = f"{texture_line.rstrip('。')}，{watch_clause}。"

        return {
            "market_shape": market_shape,
            "leaders": leaders,
            "laggards": laggards,
            "texture_line": self._clean_line(texture_line),
        }

    def _rows_for_symbols(self, rows: list[dict[str, Any]], *, symbols: tuple[str, ...]) -> list[dict[str, Any]]:
        symbol_set = set(symbols)
        return [
            row
            for row in rows
            if str(row.get("symbol", "")).strip() in symbol_set and _to_float(row.get("numeric_value")) is not None
        ]

    def _us_equities_market_shape(self, rows: list[dict[str, Any]]) -> str:
        positive_count, negative_count = self._texture_move_counts(rows)
        if positive_count > 0 and negative_count > 0:
            return "结构分化"
        if positive_count >= 3 and negative_count == 0:
            return "普涨"
        if negative_count >= 3 and positive_count == 0:
            return "普跌"
        return "一般"

    def _china_proxy_market_shape(self, rows: list[dict[str, Any]]) -> str:
        positive_count, negative_count = self._texture_move_counts(rows)
        if positive_count > 0 and negative_count > 0:
            return "结构分化"
        if rows and positive_count == len(rows):
            return "普涨"
        if rows and negative_count == len(rows):
            return "普跌"
        return "一般"

    def _texture_move_counts(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        positive_count = 0
        negative_count = 0
        for row in rows:
            numeric = _to_float(row.get("numeric_value"))
            if numeric is None:
                continue
            if float(numeric) >= 0.35:
                positive_count += 1
            elif float(numeric) <= -0.35:
                negative_count += 1
        return positive_count, negative_count

    def _texture_side_rows(self, rows: list[dict[str, Any]], *, positive: bool, limit: int = 2) -> list[dict[str, Any]]:
        threshold = 0.35
        filtered: list[dict[str, Any]] = []
        for row in rows:
            numeric = _to_float(row.get("numeric_value"))
            if numeric is None:
                continue
            if positive and float(numeric) >= threshold:
                filtered.append(row)
            elif not positive and float(numeric) <= -threshold:
                filtered.append(row)
        filtered.sort(key=lambda entry: float(_to_float(entry.get("numeric_value")) or 0.0), reverse=positive)
        return [
            {
                "symbol": str(row.get("symbol", "")).strip(),
                "label": str(row.get("label", "")).strip(),
                "direction_word": str(row.get("direction_word", "")).strip(),
                "value_text": str(row.get("value_text", "")).strip(),
                "numeric_value": _to_float(row.get("numeric_value")),
                "line": str(row.get("line", "")).strip(),
            }
            for row in filtered[:limit]
        ]

    def _texture_rows_phrase(self, rows: list[dict[str, Any]]) -> str:
        return "、".join(str(row.get("line", "")).strip() for row in rows if str(row.get("line", "")).strip())

    def _china_watch_texture_clause(self, rows: list[dict[str, Any]], *, dominant_sign: int) -> str:
        watch_rows = [
            row
            for row in rows
            if str(row.get("symbol", "")).strip() not in {"KWEB", "FXI"} and _to_float(row.get("numeric_value")) is not None
        ]
        if not watch_rows:
            return ""
        focus = max(watch_rows, key=lambda row: abs(float(_to_float(row.get("numeric_value")) or 0.0)))
        focus_value = float(_to_float(focus.get("numeric_value")) or 0.0)
        if abs(focus_value) < 0.8:
            return ""
        focus_line = str(focus.get("line", "")).strip()
        if not focus_line:
            return ""
        if dominant_sign < 0:
            if focus_value <= -0.8:
                return f"映射期货里 {focus_line} 也没跟上"
            return f"但映射期货里 {focus_line} 还没一起转弱"
        if dominant_sign > 0:
            if focus_value >= 0.8:
                return f"映射期货里 {focus_line} 也在抬"
            return f"但映射期货里 {focus_line} 还没一起转强"
        if focus_value >= 0.8:
            return f"映射期货里 {focus_line} 更强"
        return f"映射期货里 {focus_line} 更弱"

    def _build_market_rows(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        seen_symbols: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for board_key in spec["board_keys"]:
            candidates.extend(
                item
                for item in list(self.asset_board.get(board_key, []) or [])
                if isinstance(item, dict)
            )
        ordered: list[dict[str, Any]] = []
        for symbol in spec["preferred_symbols"]:
            ordered.extend(
                item
                for item in candidates
                if str(item.get("symbol", "")).strip() == symbol
            )
        ordered.extend(
            item
            for item in sorted(candidates, key=lambda entry: int(entry.get("priority", 0) or 0), reverse=True)
            if item not in ordered
        )
        for item in ordered:
            symbol = str(item.get("symbol", "")).strip()
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            row = self._price_row(
                label=str(item.get("display_name", "")).strip() or symbol,
                value=item.get("change_pct"),
                value_text=str(item.get("change_pct_text", "")).strip(),
                symbol=symbol,
            )
            if row:
                rows.append(row)
        return rows

    def _build_china_proxy_rows(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        proxies = [
            item
            for item in list(self.asset_board.get("china_proxies", []) or self.market_snapshot.get("china_proxies", []) or [])
            if isinstance(item, dict)
        ]
        seen_symbols: set[str] = set()
        ordered: list[dict[str, Any]] = []
        for symbol in spec["preferred_symbols"]:
            ordered.extend(item for item in proxies if str(item.get("symbol", "")).strip() == symbol)
        ordered.extend(
            item
            for item in sorted(proxies, key=lambda entry: int(entry.get("priority", 0) or 0), reverse=True)
            if item not in ordered
        )
        for item in ordered:
            symbol = str(item.get("symbol", "")).strip()
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            row = self._price_row(
                label=str(item.get("display_name", "")).strip() or symbol,
                value=item.get("change_pct"),
                value_text=str(item.get("change_pct_text", "")).strip(),
                symbol=symbol,
            )
            if row:
                rows.append(row)

        futures_watch = [
            item
            for item in list(self.asset_board.get("china_mapped_futures", []) or self.market_snapshot.get("china_mapped_futures", []) or [])
            if isinstance(item, dict)
        ]
        for item in futures_watch[:4]:
            score = item.get("watch_score")
            direction_word = self._move_word(score)
            value_text = self._format_signed_number(score, fallback="watch")
            label = str(item.get("future_name", "")).strip()
            if not label:
                continue
            rows.append(
                {
                    "symbol": str(item.get("future_code", "")).strip(),
                    "label": label,
                    "direction_word": direction_word,
                    "value_text": value_text,
                    "numeric_value": _to_float(score),
                    "line": f"{label} {direction_word}（watch {value_text}）",
                }
            )
        return rows

    def _build_probability_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        providers = dict(self.external_signal_panel.get("providers", {}) or {})
        provider_order = (
            ("polymarket", "Polymarket", "signal_count"),
            ("kalshi", "Kalshi", "signal_count"),
            ("cme_fedwatch", "CME FedWatch", "meeting_count"),
            ("cftc", "CFTC", "signal_count"),
        )
        for provider_key, label, count_key in provider_order:
            provider = dict(providers.get(provider_key, {}) or {})
            status = str(provider.get("status", "")).strip()
            count = int(provider.get(count_key, 0) or 0)
            headline = str(provider.get("headline", "")).strip()
            if not status and not count and not headline:
                continue
            value_text = f"{count} 条"
            if provider_key == "cme_fedwatch":
                value_text = f"{count} 场"
            rows.append(
                {
                    "symbol": provider_key,
                    "label": label,
                    "direction_word": "一般",
                    "value_text": f"{status or 'unknown'} / {value_text}",
                    "numeric_value": float(count),
                    "line": f"{label} 一般（{status or 'unknown'} / {value_text}）",
                }
            )
        return rows

    def _price_row(
        self,
        *,
        label: str,
        value: object,
        value_text: str,
        symbol: str,
    ) -> dict[str, Any]:
        numeric = _to_float(value)
        if numeric is None:
            return {}
        resolved_text = value_text.strip() or f"{numeric:+.2f}%"
        direction_word = self._move_word(numeric)
        return {
            "symbol": symbol,
            "label": label,
            "direction_word": direction_word,
            "value_text": resolved_text,
            "numeric_value": numeric,
            "line": f"{label} {direction_word}（{resolved_text}）",
        }

    def _build_bucket_news(self) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for bucket in self.bucket_results:
            bucket_key = bucket["bucket_key"]
            if bucket_key == "probability_markets":
                entries = self._build_probability_news_entries()
            else:
                entries = self._select_news_for_bucket(bucket_key)
            result[bucket_key] = entries
        return result

    def _build_probability_news_entries(self) -> list[dict[str, Any]]:
        providers = dict(self.external_signal_panel.get("providers", {}) or {})
        entries: list[dict[str, Any]] = []
        provider_order = (
            ("polymarket", "Polymarket", "signal_count"),
            ("kalshi", "Kalshi", "signal_count"),
            ("cme_fedwatch", "CME FedWatch", "meeting_count"),
            ("cftc", "CFTC", "signal_count"),
        )
        for provider_key, label, count_key in provider_order:
            provider = dict(providers.get(provider_key, {}) or {})
            status = str(provider.get("status", "")).strip()
            headline = str(provider.get("headline", "")).strip()
            count = int(provider.get(count_key, 0) or 0)
            if not status and not headline and not count:
                continue
            why = f"这条只能说明场外怎么摆概率，昨晚收盘到底认不认还得看前面的结果桶。"
            event = headline or f"{label} 当前 {status or 'unknown'}，挂了 {count} 条信号。"
            entries.append(
                {
                    "source": label,
                    "event": event,
                    "why": why,
                    "news_role": "primary",
                    "line": self._clean_line(f"{label} | {event} | {why}"),
                }
            )
        return entries

    def _select_news_for_bucket(self, bucket_key: str) -> list[dict[str, Any]]:
        bucket = self._bucket_by_key(bucket_key)
        dominant_sign = self._bucket_alignment_sign(bucket_key, bucket)
        candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        for item in self.items:
            if not self._source_allowed_for_bucket(item, bucket_key):
                continue
            relevance_detail = self._bucket_relevance_breakdown(item, bucket_key)
            relevance = int(relevance_detail.get("score", 0) or 0)
            if relevance < MIN_BUCKET_NEWS_RELEVANCE:
                continue
            if int(relevance_detail.get("hard_signal_count", 0) or 0) <= 0:
                continue
            alignment = self._alignment_score(item, bucket_key, dominant_sign)
            if alignment < 0:
                continue
            score = (
                relevance * 10
                + int(relevance_detail.get("hard_signal_count", 0) or 0) * 8
                + alignment * 6
                + self._official_bonus(item) * 4
                + self._confirmation_strength(item) * 3
                + (2 if bool(item.get("_is_headline")) else 0)
                + (1 if bool(item.get("_is_result_first_material")) else 0)
                + min(6, int(item.get("signal_score", 0) or 0) // 3)
            )
            candidates.append((score, item, relevance_detail))

        candidates.sort(key=lambda pair: (-pair[0], -int(pair[2].get("hard_signal_count", 0) or 0), self._item_id(pair[1])))
        selected: list[dict[str, Any]] = []
        seen_items: set[int] = set()
        seen_signatures: set[str] = set()
        source_counts: Counter[str] = Counter()
        for _, item, relevance_detail in candidates:
            item_id = self._item_id(item)
            signature = self._item_signature(item)
            source_signature = self._source_signature(item)
            if item_id and item_id in seen_items:
                continue
            if signature and signature in seen_signatures:
                continue
            if source_signature and source_counts[source_signature] >= 2:
                continue
            why = self._item_bucket_why(item, bucket_key, bucket, relevance_detail=relevance_detail)
            selected.append(
                {
                    "item_id": item_id,
                    "source": str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip() or "未知来源",
                    "event": str(item.get("title", "")).strip() or self._item_event_summary(item),
                    "why": why,
                    "match_score": relevance,
                    "hard_signal_count": int(relevance_detail.get("hard_signal_count", 0) or 0),
                    "selection_score": score,
                    "line": self._clean_line(
                        f"{str(item.get('source_name', '')).strip() or str(item.get('source_id', '')).strip() or '未知来源'} | "
                        f"{str(item.get('title', '')).strip() or self._item_event_summary(item)} | "
                        f"{why}"
                    ),
                }
            )
            if item_id:
                seen_items.add(item_id)
            if signature:
                seen_signatures.add(signature)
            if source_signature:
                source_counts[source_signature] += 1
            if len(selected) >= 8:
                break
        return selected

    def _source_allowed_for_bucket(self, item: dict[str, Any], bucket_key: str) -> bool:
        allowed = BUCKET_ALLOWED_SOURCE_IDS.get(bucket_key)
        if not allowed:
            return True
        source_id = str(item.get("source_id", "")).strip()
        if not source_id:
            return True
        if source_id in allowed:
            return True
        tags = set(self._item_topic_tags(item))
        if bucket_key == "industrial_metals":
            return bool(tags & {"industrial_metals", "copper_market", "aluminum_market"})
        if bucket_key == "precious_metals":
            return bool(tags & {"gold_market", "silver_market", "precious_metals_safe_haven"})
        return False

    def _news_bucket_payload(self, bucket: dict[str, Any], *, entry_limit: int) -> dict[str, Any]:
        bucket_key = str(bucket.get("bucket_key", "")).strip()
        entries = list(self.selected_bucket_news.get(bucket_key, []) or [])[:entry_limit]
        primary_entries, background_entries = self._split_bucket_entries(bucket_key, entries)
        return {
            "bucket_key": bucket_key,
            "bucket_label": bucket["bucket_label"],
            "entries": primary_entries + background_entries,
            "primary_entries": primary_entries,
            "background_entries": background_entries,
        }

    def _split_bucket_entries(
        self,
        bucket_key: str,
        entries: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not entries:
            return [], []
        if bucket_key == "probability_markets":
            return [self._entry_with_role(entry, "primary") for entry in entries], []

        top_match = int(entries[0].get("match_score", 0) or 0)
        top_hard = int(entries[0].get("hard_signal_count", 0) or 0)
        primary: list[dict[str, Any]] = []
        background: list[dict[str, Any]] = []
        for index, entry in enumerate(entries):
            match_score = int(entry.get("match_score", 0) or 0)
            hard_signal_count = int(entry.get("hard_signal_count", 0) or 0)
            same_strength_band = match_score >= max(MIN_BUCKET_NEWS_RELEVANCE + 2, top_match - 4)
            same_hard_band = hard_signal_count >= max(1, min(2, top_hard))
            front_rank = index <= 1 and match_score >= max(MIN_BUCKET_NEWS_RELEVANCE + 1, top_match - 2)
            is_primary = index == 0 or (same_strength_band and same_hard_band) or front_rank
            if is_primary and len(primary) < 3:
                primary.append(self._entry_with_role(entry, "primary"))
            else:
                background.append(
                    self._entry_with_role(
                        entry,
                        "background",
                        top_entry=entries[0],
                        top_match=top_match,
                        top_hard=top_hard,
                    )
                )

        if not primary and background:
            first = background.pop(0)
            primary.append({**first, "news_role": "primary"})
        return primary, background

    def _entry_with_role(
        self,
        entry: dict[str, Any],
        role: str,
        *,
        top_entry: dict[str, Any] | None = None,
        top_match: int = 0,
        top_hard: int = 0,
    ) -> dict[str, Any]:
        payload = {
            **entry,
            "news_role": role,
        }
        if role == "background":
            payload["background_reason"] = self._background_reason(entry, top_match=top_match, top_hard=top_hard)
            payload["event_cluster_overlap"] = self._event_cluster_overlap(entry, top_entry or {})
        return payload

    def _background_reason(self, entry: dict[str, Any], *, top_match: int, top_hard: int) -> str:
        match_score = int(entry.get("match_score", 0) or 0)
        hard_signal_count = int(entry.get("hard_signal_count", 0) or 0)
        reasons: list[str] = []
        if match_score < top_match:
            reasons.append(f"匹配分低于主因 {top_match - match_score} 分")
        if hard_signal_count < top_hard:
            reasons.append("硬锚点少于主因")
        if not reasons:
            reasons.append("同主题但排序靠后，先放背景层")
        return self._clean_line("，".join(reasons))

    def _event_cluster_overlap(self, entry: dict[str, Any], top_entry: dict[str, Any]) -> dict[str, Any]:
        entry_cluster = self._entry_cluster_payload(entry)
        top_cluster = self._entry_cluster_payload(top_entry)
        entry_tags = set(entry_cluster.get("topic_tags", []))
        top_tags = set(top_cluster.get("topic_tags", []))
        shared_tags = sorted(entry_tags & top_tags)
        entry_cluster_id = str(entry_cluster.get("cluster_id", "")).strip()
        top_cluster_id = str(top_cluster.get("cluster_id", "")).strip()
        return {
            "entry_cluster_id": entry_cluster_id,
            "primary_cluster_id": top_cluster_id,
            "same_cluster": bool(entry_cluster_id and entry_cluster_id == top_cluster_id),
            "shared_topic_tags": shared_tags,
        }

    def _entry_cluster_payload(self, entry: dict[str, Any]) -> dict[str, Any]:
        item = self._find_item(int(entry.get("item_id", 0) or 0))
        cluster = dict(item.get("event_cluster", {}) or {})
        return {
            "cluster_id": str(cluster.get("cluster_id", "")).strip(),
            "topic_tags": [str(tag).strip() for tag in list(cluster.get("topic_tags", []) or []) if str(tag).strip()],
        }

    def _bucket_relevance(self, item: dict[str, Any], bucket_key: str) -> int:
        return int(self._bucket_relevance_breakdown(item, bucket_key).get("score", 0) or 0)

    def _bucket_relevance_breakdown(self, item: dict[str, Any], bucket_key: str) -> dict[str, Any]:
        spec = BUCKET_SPEC_BY_KEY[bucket_key]
        title_text = self._item_title_text(item)
        evidence_text = self._item_evidence_text(item)
        full_text = self._item_text(item)
        score = 0
        title_hits = self._count_keyword_hits(title_text, spec.get("hard_keywords", ()))
        evidence_hits = self._count_keyword_hits(evidence_text, spec.get("hard_keywords", ()))
        soft_hits = self._count_keyword_hits(full_text, spec["keywords"])
        macro_title_hits = self._official_macro_title_hits(item, bucket_key=bucket_key)
        score += title_hits * 4
        score += evidence_hits * 2
        score += soft_hits
        score += macro_title_hits * 5
        symbol_hits = 0
        for row in self._bucket_by_key(bucket_key).get("rows", []):
            symbol = str(row.get("symbol", "")).strip().lower()
            label = str(row.get("label", "")).strip().lower()
            if symbol and symbol in title_text:
                symbol_hits += 1
                score += 5
            elif symbol and symbol in full_text:
                score += 2
            if label and label in title_text:
                symbol_hits += 1
                score += 4
            elif label and label in full_text:
                score += 2
        specific_topic_hits = 0
        soft_topic_hits = 0
        for tag in self._item_topic_tags(item):
            mapped_bucket = self._topic_tag_bucket(tag)
            if mapped_bucket == bucket_key:
                specific_topic_hits += 1
                score += 3
                continue
            soft_bucket = self._soft_topic_tag_bucket(tag)
            if soft_bucket == bucket_key:
                soft_topic_hits += 1
                score += 1
        direction_hits = 0
        for direction in self._item_directions(item):
            if DIRECTION_BUCKET_HINTS.get(direction) == bucket_key:
                direction_hits += 1
                score += 1
        source_bonus = self._source_bucket_bonus(item, bucket_key)
        score += source_bonus
        hard_signal_count = 0
        if title_hits > 0:
            hard_signal_count += 1
        if macro_title_hits > 0:
            hard_signal_count += 1
        if symbol_hits > 0:
            hard_signal_count += 1
        if specific_topic_hits > 0:
            hard_signal_count += 1
        if hard_signal_count == 0:
            score = max(0, score - 5)
        return {
            "score": score,
            "title_hits": title_hits,
            "evidence_hits": evidence_hits,
            "soft_hits": soft_hits,
            "macro_title_hits": macro_title_hits,
            "symbol_hits": symbol_hits,
            "specific_topic_hits": specific_topic_hits,
            "soft_topic_hits": soft_topic_hits,
            "direction_hits": direction_hits,
            "source_bonus": source_bonus,
            "hard_signal_count": hard_signal_count,
        }

    def _alignment_score(self, item: dict[str, Any], bucket_key: str, dominant_sign: int) -> int:
        if bucket_key == "probability_markets":
            return 0
        item_sign = self._item_market_sign(item, bucket_key)
        if bucket_key == "china_proxy" and item_sign != 0 and self._is_china_followthrough_market_item(item):
            return 0
        if dominant_sign == 0 or item_sign == 0:
            return 0
        if dominant_sign == item_sign:
            return 1
        return -1

    def _is_china_followthrough_market_item(self, item: dict[str, Any]) -> bool:
        text = self._item_text(item)
        return any(
            self._keyword_in_text(text, keyword)
            for keyword in ("hong kong stocks", "hong kong shares", "hang seng", "hang seng tech", "china stocks", "mainland chinese")
        )

    def _item_market_sign(self, item: dict[str, Any], bucket_key: str) -> int:
        text = self._item_market_text(item)
        positive_hits = sum(text.count(token) for token in (" surge ", " jump ", " rise ", " rose ", " rally ", " gain ", " higher ", " 上涨", " 走高", " 拉升", " 大涨", " 暴涨"))
        negative_hits = sum(text.count(token) for token in (" fall ", " fell ", " drop ", " slump ", " decline ", " lower ", " down ", " 下跌", " 走低", " 大跌", " 暴跌", " 回落"))
        if positive_hits > negative_hits:
            return 1
        if negative_hits > positive_hits:
            return -1
        if bucket_key == "energy_transport" and any(direction in {"油气开采", "油服", "原油/燃料油", "天然气/LNG"} for direction in self._item_directions(item)):
            return 1
        return 0

    def _build_ignored_messages(self) -> list[dict[str, Any]]:
        selected_ids = {
            int(entry.get("item_id", 0) or 0)
            for entries in self.selected_bucket_news.values()
            for entry in entries
            if int(entry.get("item_id", 0) or 0)
        }
        selected_signatures = {
            self._clean_line(
                f"{str(entry.get('source', '')).strip()}|{str(entry.get('event', '')).strip()}"
            ).lower()
            for entries in self.selected_bucket_news.values()
            for entry in entries
            if str(entry.get("source", "")).strip() or str(entry.get("event", "")).strip()
        }
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for item in self.items:
            item_id = self._item_id(item)
            signature = self._item_signature(item)
            if item_id and item_id in selected_ids:
                continue
            if signature and signature in selected_signatures:
                continue
            bucket_key, relevance = self._best_bucket_for_item(item)
            headline_bonus = 2 if bool(item.get("_is_headline")) else 0
            heat_score = int(item.get("signal_score", 0) or 0) + headline_bonus * 3
            confirmation = self._confirmation_strength(item)
            item_sign = self._item_market_sign(item, bucket_key)
            bucket_sign = self._bucket_alignment_sign(bucket_key, self._bucket_by_key(bucket_key)) if bucket_key else 0
            mismatch = bool(bucket_key and item_sign and bucket_sign and item_sign != bucket_sign)
            weak_confirmation = confirmation <= 0
            weak_chain = relevance < 5
            if not (bool(item.get("_is_headline")) or heat_score >= 6):
                continue
            if not (mismatch or weak_confirmation or weak_chain):
                continue
            reason = "消息很热，但还没进强证据链。"
            if mismatch:
                reason = "消息很热，但昨晚盘面方向没按这条线走。"
            elif weak_confirmation:
                reason = "消息很热，但交叉确认还不够。"
            score = heat_score * 5 + (8 if mismatch else 0) + (5 if weak_confirmation else 0) + (3 if weak_chain else 0)
            candidates.append((score, item, reason))

        candidates.sort(key=lambda row: (-row[0], self._item_id(row[1])))
        results: list[dict[str, Any]] = []
        used_ids: set[int] = set()
        used_signatures: set[str] = set()
        for _, item, reason in candidates:
            item_id = self._item_id(item)
            signature = self._item_signature(item)
            if item_id and item_id in used_ids:
                continue
            if signature and signature in used_signatures:
                continue
            source = str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip() or "未知来源"
            event = str(item.get("title", "")).strip() or self._item_event_summary(item)
            line = self._clean_line(f"{source} | {event} | {reason}")
            results.append(
                {
                    "item_id": item_id,
                    "kind": "message_miss",
                    "category": "消息没认",
                    "source": source,
                    "event": event,
                    "reason": reason,
                    "line": line,
                }
            )
            if item_id:
                used_ids.add(item_id)
            if signature:
                used_signatures.add(signature)
            if len(results) >= 8:
                break
        return results

    def _build_asset_misses(self) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []

        oil_move = self._avg_change(("CL=F", "BZ=F"))
        gold_move = self._avg_change(("GC=F", "SI=F"))
        broad_us_move = self._avg_change(("^IXIC", "^GSPC", "^DJI", "^RUT"))
        tech_move = self._avg_change(("^IXIC", "XLK", "SOXX"))
        soxx_move = self._symbol_change("SOXX")
        china_move = self._avg_change(("KWEB", "FXI"))
        yield_move = self._avg_change(("^TNX",))
        dollar_move = self._symbol_change("DX-Y.NYB")
        cnh_move = self._symbol_change("CNH=X")

        energy_bucket = self._bucket_by_key("energy_transport")
        us_bucket = self._bucket_by_key("us_equities")
        precious_bucket = self._bucket_by_key("precious_metals")
        china_bucket = self._bucket_by_key("china_proxy")
        rates_bucket = self._bucket_by_key("rates_fx")

        if oil_move >= 2.0 and precious_bucket.get("rows") and gold_move <= 0.15:
            candidates.append(
                (
                    abs(oil_move) + max(0.5, abs(gold_move)),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('CL=F', 'BZ=F'))}，但 {self._rows_phrase_by_symbols(('GC=F', 'SI=F'))}",
                        reason="这说明昨夜先认的是供给和运输冲击，不是全面避险一起发酵。",
                        related_buckets=("energy_transport", "precious_metals"),
                        strength=abs(oil_move) + max(0.5, abs(gold_move)),
                        observed_symbols=("CL=F", "BZ=F", "GC=F", "SI=F"),
                    ),
                )
            )

        if oil_move <= -2.0 and precious_bucket.get("rows") and gold_move >= 0.5:
            candidates.append(
                (
                    abs(oil_move) + abs(gold_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('CL=F', 'BZ=F'))}，但 {self._rows_phrase_by_symbols(('GC=F', 'SI=F'))}",
                        reason="这说明原油在认供需松动，但贵金属没有跟着放松，盘面还有避险或利率以外的支撑。",
                        related_buckets=("energy_transport", "precious_metals"),
                        strength=abs(oil_move) + abs(gold_move),
                        observed_symbols=("CL=F", "BZ=F", "GC=F", "SI=F"),
                    ),
                )
            )

        if oil_move >= 2.0 and us_bucket.get("rows") and broad_us_move >= -0.3:
            candidates.append(
                (
                    abs(oil_move) + max(0.5, abs(broad_us_move)),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('CL=F', 'BZ=F'))}，但 {self._rows_phrase_by_symbols(('^IXIC', '^GSPC'))}",
                        reason="这说明油价先被市场认了，但美股没有按全面避险一起砸。",
                        related_buckets=("energy_transport", "us_equities"),
                        strength=abs(oil_move) + max(0.5, abs(broad_us_move)),
                        observed_symbols=("CL=F", "BZ=F", "^IXIC", "^GSPC"),
                    ),
                )
            )

        if soxx_move >= 2.0 and china_bucket.get("rows") and china_move <= -0.8:
            candidates.append(
                (
                    abs(soxx_move) + abs(china_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('SOXX',))}，但 {self._rows_phrase_by_symbols(('KWEB', 'FXI'))}",
                        reason="这说明昨夜只有硬科技这根线被认了，不是所有科技和中概一起强。",
                        related_buckets=("us_equities", "china_proxy"),
                        strength=abs(soxx_move) + abs(china_move),
                        observed_symbols=("SOXX", "KWEB", "FXI"),
                    ),
                )
            )

        if tech_move <= -1.0 and china_bucket.get("rows") and china_move >= 0.8:
            candidates.append(
                (
                    abs(tech_move) + abs(china_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('^IXIC', 'SOXX'))}，但 {self._rows_phrase_by_symbols(('KWEB', 'FXI'))}",
                        reason="这说明昨夜中概不是简单跟着美股科技跌，资金在国内资产映射里认了另一条线。",
                        related_buckets=("us_equities", "china_proxy"),
                        strength=abs(tech_move) + abs(china_move),
                        observed_symbols=("^IXIC", "SOXX", "KWEB", "FXI"),
                    ),
                )
            )

        if yield_move >= 0.5 and soxx_move >= 2.0 and rates_bucket.get("rows") and us_bucket.get("rows"):
            candidates.append(
                (
                    abs(yield_move) + abs(soxx_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('^TNX', 'DX-Y.NYB'))}，但 {self._rows_phrase_by_symbols(('SOXX',))}",
                        reason="这说明收益率上行没有压掉芯片线，昨夜先认的是硬件景气。",
                        related_buckets=("rates_fx", "us_equities"),
                        strength=abs(yield_move) + abs(soxx_move),
                        observed_symbols=("^TNX", "DX-Y.NYB", "SOXX"),
                    ),
                )
            )

        if yield_move <= -0.5 and tech_move <= -1.0 and rates_bucket.get("rows") and us_bucket.get("rows"):
            candidates.append(
                (
                    abs(yield_move) + abs(tech_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('^TNX', 'DX-Y.NYB'))}，但 {self._rows_phrase_by_symbols(('^IXIC', 'SOXX'))}",
                        reason="这说明利率这边给了喘息，但科技股没有接，昨夜压科技的不是单纯利率线。",
                        related_buckets=("rates_fx", "us_equities"),
                        strength=abs(yield_move) + abs(tech_move),
                        observed_symbols=("^TNX", "DX-Y.NYB", "^IXIC", "SOXX"),
                    ),
                )
            )

        if yield_move >= 0.5 and precious_bucket.get("rows") and gold_move >= 1.0:
            candidates.append(
                (
                    abs(yield_move) + abs(gold_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('^TNX', 'DX-Y.NYB'))}，但 {self._rows_phrase_by_symbols(('GC=F', 'SI=F'))}",
                        reason="这说明昨夜黄金没有完全按利率线交易，还有别的力量在托着。",
                        related_buckets=("rates_fx", "precious_metals"),
                        strength=abs(yield_move) + abs(gold_move),
                        observed_symbols=("^TNX", "DX-Y.NYB", "GC=F", "SI=F"),
                    ),
                )
            )

        if dollar_move >= 0.5 and china_bucket.get("rows") and china_move >= 0.8:
            candidates.append(
                (
                    abs(dollar_move) + abs(china_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('DX-Y.NYB', 'CNH=X'))}，但 {self._rows_phrase_by_symbols(('KWEB', 'FXI'))}",
                        reason="这说明美元线没有直接压住国内资产映射，昨夜中国资产里还有独立支撑。",
                        related_buckets=("rates_fx", "china_proxy"),
                        strength=abs(dollar_move) + abs(china_move),
                        observed_symbols=("DX-Y.NYB", "CNH=X", "KWEB", "FXI"),
                    ),
                )
            )

        if cnh_move >= 0.5 and china_bucket.get("rows") and china_move <= -0.8:
            candidates.append(
                (
                    abs(cnh_move) + abs(china_move),
                    self._asset_miss_entry(
                        event=f"{self._rows_phrase_by_symbols(('CNH=X',))}，但 {self._rows_phrase_by_symbols(('KWEB', 'FXI'))}",
                        reason="这说明离岸人民币走弱没有被单独定价，昨夜国内资产映射还叠了股权风险。",
                        related_buckets=("rates_fx", "china_proxy"),
                        strength=abs(cnh_move) + abs(china_move),
                        observed_symbols=("CNH=X", "KWEB", "FXI"),
                    ),
                )
            )

        candidates.sort(key=lambda row: -row[0])
        results: list[dict[str, Any]] = []
        seen_events: set[str] = set()
        for _, entry in candidates:
            event = str(entry.get("event", "")).strip()
            if not event or event in seen_events:
                continue
            seen_events.add(event)
            results.append(entry)
            if len(results) >= 4:
                break
        return results

    def _asset_miss_entry(
        self,
        *,
        event: str,
        reason: str,
        related_buckets: tuple[str, ...],
        strength: float,
        observed_symbols: tuple[str, ...],
    ) -> dict[str, Any]:
        source = "盘面矩阵"
        clean_event = self._clean_line(event)
        clean_reason = self._clean_line(reason)
        observed_rows = [dict(row) for row in (self._symbol_row(symbol) for symbol in observed_symbols) if row.get("line")]
        primary_context = self._primary_context_for_related_buckets(related_buckets)
        conflict_check = self._asset_miss_conflict_check(primary_context)
        return {
            "kind": "asset_miss",
            "category": "资产没认",
            "source": source,
            "event": clean_event,
            "reason": clean_reason,
            "strength": round(float(strength), 4),
            "observed_rows": observed_rows,
            "primary_context": primary_context,
            "conflict_check": conflict_check,
            "audit_line": self._asset_miss_audit_line(conflict_check),
            "related_buckets": list(related_buckets),
            "line": self._clean_line(f"{source} | {clean_event} | {clean_reason}"),
        }

    def _primary_context_for_related_buckets(self, bucket_keys: tuple[str, ...]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        for bucket_key in bucket_keys:
            bucket = self._bucket_by_key(bucket_key)
            entries = list(self.selected_bucket_news.get(bucket_key, []) or [])[:8]
            primary_entries, _ = self._split_bucket_entries(bucket_key, entries)
            primary_lines = [str(entry.get("line", "")).strip() for entry in primary_entries[:2] if str(entry.get("line", "")).strip()]
            primary_item_ids = [int(entry.get("item_id", 0) or 0) for entry in primary_entries[:2] if int(entry.get("item_id", 0) or 0)]
            contexts.append(
                {
                    "bucket_key": bucket_key,
                    "bucket_label": str(bucket.get("bucket_label", bucket_key)).strip() or bucket_key,
                    "primary_item_ids": primary_item_ids,
                    "primary_lines": primary_lines,
                    "has_primary_context": bool(primary_lines),
                }
            )
        return contexts

    def _asset_miss_conflict_check(self, primary_context: list[dict[str, Any]]) -> dict[str, Any]:
        checked_buckets = [
            str(context.get("bucket_key", "")).strip()
            for context in primary_context
            if context.get("has_primary_context") and str(context.get("bucket_key", "")).strip()
        ]
        if checked_buckets:
            return {
                "status": "checked_with_primary_news",
                "checked_buckets": checked_buckets,
                "note": "这条资产没认来自价格行错位，已附相关桶主因上下文，避免把主因新闻当成没认。",
            }
        return {
            "status": "no_primary_news_context",
            "checked_buckets": [],
            "note": "相关桶暂时没有可用于互相校验的主因新闻。",
        }

    def _asset_miss_audit_line(self, conflict_check: dict[str, Any]) -> str:
        status = str(conflict_check.get("status", "")).strip()
        checked_buckets = [str(item).strip() for item in list(conflict_check.get("checked_buckets", []) or []) if str(item).strip()]
        if status == "checked_with_primary_news" and checked_buckets:
            return self._clean_line(f"互校：已对照主因桶 {', '.join(checked_buckets)}，这条仍按价格错位保留。")
        return self._clean_line("互校：相关桶暂时没有主因新闻可对照，这条只按价格错位保留。")

    def _rows_phrase_by_symbols(self, symbols: tuple[str, ...], *, limit: int = 2) -> str:
        parts: list[str] = []
        for symbol in symbols:
            row = self._symbol_row(symbol)
            line = str(row.get("line", "")).strip()
            if line:
                parts.append(line)
            if len(parts) >= limit:
                break
        return "、".join(parts) or "相关资产没给出足够结果"

    def _ignored_heat_payload(self, *, message_limit: int, asset_limit: int) -> dict[str, Any]:
        message_misses = list(self.ignored_messages[:message_limit])
        asset_misses = list(self.asset_misses[:asset_limit])
        return {
            "title": "昨晚市场没认的消息",
            "message_misses": message_misses,
            "asset_misses": asset_misses,
            "entries": message_misses + asset_misses,
        }

    def _best_bucket_for_item(self, item: dict[str, Any]) -> tuple[str, int]:
        ranked = sorted(
            (
                (bucket["bucket_key"], self._bucket_relevance(item, bucket["bucket_key"]))
                for bucket in self.bucket_results
                if bucket["bucket_key"] != "probability_markets"
            ),
            key=lambda row: (-row[1], BUCKET_PRIORITY.get(row[0], 99)),
        )
        if not ranked:
            return "", 0
        return ranked[0]

    def _bucket_alignment_sign(self, bucket_key: str, bucket: dict[str, Any]) -> int:
        sign = int(bucket.get("news_sign", bucket.get("dominant_sign", 0)) or 0)
        if bucket_key == "us_equities" and self._bucket_has_mixed_core_moves(
            list(bucket.get("rows", []) or []),
            symbols=("SOXX", "XLK", "^IXIC", "^GSPC", "^DJI", "^RUT"),
        ):
            return 0
        if bucket_key == "china_proxy" and self._china_proxy_allows_mixed_news_flow(bucket):
            return 0
        return sign

    def _china_proxy_allows_mixed_news_flow(self, bucket: dict[str, Any]) -> bool:
        rows = list(bucket.get("rows", []) or [])
        if self._bucket_has_mixed_core_moves(rows, symbols=("KWEB", "FXI")):
            return True
        texture_line = str(dict(bucket.get("texture", {}) or {}).get("texture_line", "")).strip()
        return "分化" in texture_line

    def _bucket_has_mixed_core_moves(self, rows: list[dict[str, Any]], *, symbols: tuple[str, ...]) -> bool:
        has_positive = False
        has_negative = False
        for symbol in symbols:
            for row in rows:
                if str(row.get("symbol", "")).strip() != symbol:
                    continue
                numeric = _to_float(row.get("numeric_value"))
                if numeric is None:
                    continue
                if float(numeric) >= 0.35:
                    has_positive = True
                elif float(numeric) <= -0.35:
                    has_negative = True
                break
        return has_positive and has_negative

    def _source_bucket_bonus(self, item: dict[str, Any], bucket_key: str) -> int:
        spec = BUCKET_SPEC_BY_KEY.get(bucket_key, {})
        source_id = str(item.get("source_id", "")).strip()
        if source_id and source_id in tuple(spec.get("source_penalty_ids", ()) or ()):
            return -3
        if source_id and source_id in tuple(spec.get("source_bonus_ids", ()) or ()):
            return 1
        return 0

    def _official_macro_title_hits(self, item: dict[str, Any], *, bucket_key: str) -> int:
        if bucket_key != "rates_fx":
            return 0
        source_id = str(item.get("source_id", "")).strip()
        if source_id not in RATES_FX_OFFICIAL_MACRO_SOURCES:
            return 0
        title_text = self._item_title_text(item)
        return sum(1 for hint in RATES_FX_OFFICIAL_MACRO_TITLE_HINTS if self._keyword_in_text(title_text, hint))

    def _count_keyword_hits(self, text: str, keywords: tuple[str, ...]) -> int:
        normalized_text = str(text or "").strip().lower()
        if not normalized_text:
            return 0
        return sum(1 for keyword in keywords if self._keyword_in_text(normalized_text, str(keyword).strip().lower()))

    def _keyword_in_text(self, text: str, keyword: str) -> bool:
        normalized_keyword = str(keyword or "").strip().lower()
        if not normalized_keyword:
            return False
        if re.fullmatch(r"[a-z0-9]+", normalized_keyword):
            pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
            return bool(re.search(pattern, text))
        return normalized_keyword in text

    def _item_signature(self, item: dict[str, Any]) -> str:
        source = str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip()
        title = str(item.get("title", "")).strip()
        if not source and not title:
            return ""
        return self._clean_line(f"{source}|{title}").lower()

    def _source_signature(self, item: dict[str, Any]) -> str:
        return (str(item.get("source_id", "")).strip() or str(item.get("source_name", "")).strip()).lower()

    def _build_opening_sentences(self, *, max_sentences: int) -> list[str]:
        us_bucket = self._bucket_by_key("us_equities")
        rates_bucket = self._bucket_by_key("rates_fx")
        energy_bucket = self._bucket_by_key("energy_transport")
        ixic_move = self._symbol_change("^IXIC")
        soxx_move = self._symbol_change("SOXX")
        kweb_move = self._symbol_change("KWEB")
        oil_move = self._symbol_change("CL=F")
        lead_lines = [bucket["lead_line"] for bucket in (us_bucket, rates_bucket, energy_bucket) if bucket.get("lead_line")]
        first_sentence = "昨夜先看结果，" + "，".join(lead_lines[:3]) + "。"
        if not lead_lines:
            first_sentence = "昨夜结果还不够整，先别把一句话喊满。"
        elif abs(ixic_move) < 0.6 and soxx_move >= 2.0 and kweb_move <= -1.0:
            first_sentence = "昨夜不是普涨，纳指没怎么动，但半导体单独大涨，中概互联网反而在跌。"
        elif ixic_move >= 2.0 and soxx_move >= 3.0:
            first_sentence = "昨夜纳指和半导体一起往上冲，外盘先把科技情绪点起来了。"
        elif oil_move >= 2.0:
            first_sentence = "昨夜油价又被往上顶，先别假装成本线没事。"

        playbook_signal = self._playbook_hint_sentence()
        sentences = [self._clean_line(first_sentence)]
        if playbook_signal:
            sentences.append(self._clean_line(playbook_signal))
        return sentences[:max_sentences]

    def _playbook_hint_sentence(self) -> str:
        tech_strength = self._avg_change(("^IXIC", "XLK", "SOXX"))
        soxx_move = self._symbol_change("SOXX")
        oil_move = self._avg_change(("CL=F", "BZ=F", "NG=F"))
        yield_move = self._avg_change(("^TNX",))
        kweb_move = self._symbol_change("KWEB")
        china_move = self._avg_change(("KWEB", "FXI"))
        if soxx_move >= 2.0 and kweb_move <= -1.0:
            return "半导体昨夜单独起飞，但 KWEB 在挨打，A股先看硬科技，港股互联网映射先别一起脑补。"
        if tech_strength >= 2.0:
            tail = "A股科技今天更容易起飞。"
            if yield_move <= -0.3:
                tail = "A股科技今天更容易直接起飞。"
            return f"纳指和半导体都在往上冲，{tail}"
        if oil_move <= -2.0:
            return "原油昨晚砸得很凶，A股成本链和航空运输更容易先冲。"
        if china_move >= 1.0:
            return "国内资产映射也在拉，A股互联网和情绪票更容易跟着抬头。"
        if yield_move >= 0.5:
            return "利率往上拱，A股先看银行红利，纯情绪科技别急着梭哈。"
        return "先把昨夜结果摆在这，A股开盘先看谁先跟。"

    def _build_a_share_playbook(self) -> list[dict[str, str]]:
        tech_strength = self._avg_change(("^IXIC", "XLK", "SOXX"))
        ixic_move = self._symbol_change("^IXIC")
        soxx_move = self._symbol_change("SOXX")
        xlk_move = self._symbol_change("XLK")
        broad_strength = self._avg_change(("^GSPC", "^DJI", "^RUT"))
        yield_move = self._avg_change(("^TNX",))
        dollar_move = self._avg_change(("DX-Y.NYB",))
        oil_move = self._avg_change(("CL=F", "BZ=F", "NG=F"))
        gold_move = self._avg_change(("GC=F", "SI=F"))
        industrial_move = self._avg_change(("HG=F", "ALI=F"))
        kweb_move = self._symbol_change("KWEB")
        fxi_move = self._symbol_change("FXI")
        china_move = self._avg_change(("KWEB", "FXI"))

        segments: list[dict[str, str]] = []
        a_big = "外盘昨晚收得不差，A股大盘更像先冲再分化。"
        if abs(broad_strength) < 0.5 and soxx_move >= 2.0 and china_move <= -1.0:
            a_big = "外盘昨晚是结构分化，不是全场一起涨，A股大盘更像指数一般、题材自己找方向。"
        elif broad_strength <= -0.8:
            a_big = "外盘昨晚先挨打，A股大盘开盘先别一把梭，先看谁还能扛。"
        elif broad_strength >= 0.8 or china_move >= 0.8:
            a_big = "外盘昨晚先把情绪抬起来了，A股大盘更容易高开一脚。"
        segments.append(
            {
                "label": "A股大盘",
                "text": self._clean_line(a_big),
                "why": self._clean_line(
                    f"因为昨夜 {self._bucket_by_key('us_equities').get('lead_line') or '美股结果一般'}，"
                    f"{self._bucket_by_key('china_proxy').get('lead_line') or '国内资产映射还不够强'}。"
                ),
            }
        )

        style_text = "风格先别喊死，边走边看。"
        if soxx_move >= 2.0 and kweb_move <= -1.0:
            style_text = "半导体昨夜单独起飞，但中概互联网在挨打，A股先看硬科技，不要把港股互联一起脑补上去。"
        elif tech_strength >= 1.8 and yield_move <= 0:
            style_text = "纳指暴涨，半导体也猛拉，A股科技今天更容易起飞。"
        elif yield_move >= 0.5:
            style_text = "利率往上拱，红利和银行更像主线，纯情绪科技先别梭哈。"
        elif kweb_move >= 1.0 or fxi_move >= 1.0:
            style_text = "国内资产映射在抬头，港股互联网映射和情绪票更容易先起飞。"
        segments.append(
            {
                "label": "风格怎么打",
                "text": self._clean_line(style_text),
                "why": self._clean_line(
                    f"昨夜利率汇率这桶是 {self._bucket_by_key('rates_fx').get('lead_line') or '一般'}，"
                    f"美股指数与板块这桶是 {self._bucket_by_key('us_equities').get('lead_line') or '一般'}。"
                ),
            }
        )

        takeoff = self._takeoff_text(
            tech_strength=tech_strength,
            soxx_move=soxx_move,
            xlk_move=xlk_move,
            oil_move=oil_move,
            industrial_move=industrial_move,
            china_move=china_move,
            kweb_move=kweb_move,
        )
        segments.append(
            {
                "label": "起飞",
                "text": self._clean_line(takeoff),
                "why": self._clean_line(
                    self._takeoff_why(
                        tech_strength=tech_strength,
                        soxx_move=soxx_move,
                        oil_move=oil_move,
                        industrial_move=industrial_move,
                        china_move=china_move,
                    )
                ),
            }
        )

        run_text = self._run_text(
            tech_strength=tech_strength,
            yield_move=yield_move,
            oil_move=oil_move,
            dollar_move=dollar_move,
            china_move=china_move,
        )
        segments.append(
            {
                "label": "快跑",
                "text": self._clean_line(run_text),
                "why": self._clean_line(
                    self._run_why(
                        tech_strength=tech_strength,
                        yield_move=yield_move,
                        oil_move=oil_move,
                        dollar_move=dollar_move,
                        china_move=china_move,
                    )
                ),
            }
        )

        watch_text = "再看看：昨夜有些桶没给满，先别把没数据的方向吹成主线。"
        if gold_move >= 1.0:
            watch_text = "再看看：贵金属在拉，但这条更像防守线，不一定会变成 A 股最强攻击线。"
        elif industrial_move >= 1.0 and tech_strength < 1.0:
            watch_text = "再看看：工业品在抬头，但要不要扩到顺周期，还得看开盘谁来接。"
        segments.append(
            {
                "label": "再看看",
                "text": self._clean_line(watch_text),
                "why": self._clean_line(
                    f"贵金属这桶是 {self._bucket_by_key('precious_metals').get('lead_line') or '当前没货'}，"
                    f"工业品这桶是 {self._bucket_by_key('industrial_metals').get('lead_line') or '当前没货'}。"
                ),
            }
        )

        alternate = "另一种走法：如果 A 股自己更认内资线，那就算外盘热，盘面也可能先拉银行红利再说。"
        if china_move >= 1.0:
            alternate = "另一种走法：如果港股映射继续跟，今天也可能不是银行红利，而是互联网和科技一起拉。"
        segments.append(
            {
                "label": "另一种走法",
                "text": self._clean_line(alternate),
                "why": self._clean_line(
                    f"国内资产映射这桶是 {self._bucket_by_key('china_proxy').get('lead_line') or '当前缺口'}，"
                    f"利率汇率这桶是 {self._bucket_by_key('rates_fx').get('lead_line') or '一般'}。"
                ),
            }
        )

        wrong_text = self._wrong_when_text(
            tech_strength=tech_strength,
            soxx_move=soxx_move,
            oil_move=oil_move,
            china_move=china_move,
            kweb_move=kweb_move,
            ixic_move=ixic_move,
        )
        segments.append(
            {
                "label": "什么时候判断错了",
                "text": self._clean_line(wrong_text),
                "why": self._clean_line("判断错不看嘴，直接看昨夜最强那几根线今天开盘还能不能续上。"),
            }
        )
        return segments

    def _takeoff_text(
        self,
        *,
        tech_strength: float,
        soxx_move: float,
        xlk_move: float,
        oil_move: float,
        industrial_move: float,
        china_move: float,
        kweb_move: float,
    ) -> str:
        picks: list[str] = []
        if soxx_move >= 2.0:
            picks.append("半导体和算力硬件更容易直接起飞")
        elif tech_strength >= 1.8 or xlk_move >= 1.8:
            picks.append("科技映射更容易直接起飞")
        if oil_move <= -2.0:
            picks.append("航空与燃油敏感运输链也更容易起飞")
        elif oil_move >= 2.0:
            picks.append("油气开采和油服更容易起飞")
        if industrial_move >= 1.0:
            picks.append("工业金属链可以一起看")
        if china_move >= 1.0 and kweb_move >= 0.8:
            picks.append("港股互联网映射也能看")
        if not picks:
            top_positive = next((call for call in self.direction_calls if str(call.get("stance", "")).strip() == "positive"), {})
            direction = str(top_positive.get("direction", "")).strip()
            if direction:
                picks.append(f"{direction} 先看有没有起飞机会")
        if not picks:
            return "起飞：先别乱点火，等最强那桶自己把方向打出来。"
        return "起飞：" + "，".join(picks[:3]) + "。"

    def _takeoff_why(self, *, tech_strength: float, soxx_move: float, oil_move: float, industrial_move: float, china_move: float) -> str:
        reasons: list[str] = []
        if tech_strength >= 1.8 or soxx_move >= 2.0:
            reasons.append(self._bucket_by_key("us_equities").get("lead_line") or "")
        if oil_move <= -2.0 or oil_move >= 2.0:
            reasons.append(self._bucket_by_key("energy_transport").get("lead_line") or "")
        if industrial_move >= 1.0:
            reasons.append(self._bucket_by_key("industrial_metals").get("lead_line") or "")
        if china_move >= 1.0:
            reasons.append(self._bucket_by_key("china_proxy").get("lead_line") or "")
        if not any(reason for reason in reasons):
            return "当前没有足够硬的结果去支撑这条，先看开盘反馈。"
        return "因为 " + "，".join(reason for reason in reasons if reason) + "。"

    def _run_text(self, *, tech_strength: float, yield_move: float, oil_move: float, dollar_move: float, china_move: float) -> str:
        calls: list[str] = []
        if oil_move >= 2.0:
            calls.append("航空与燃油敏感运输链先快跑")
        elif oil_move <= -2.0:
            calls.append("油气开采和油服先别梭哈")
        if china_move <= -1.0:
            calls.append("港股互联网映射先快跑")
        if yield_move >= 0.5 and tech_strength <= 1.0:
            calls.append("高估值成长链快跑")
        if dollar_move >= 0.5:
            calls.append("纯外需弹性票先别冲太满")
        top_negative = next((call for call in self.direction_calls if str(call.get("stance", "")).strip() == "negative"), {})
        direction = str(top_negative.get("direction", "")).strip()
        if direction and all(direction not in call for call in calls):
            calls.append(f"{direction} 先快跑")
        if not calls:
            return "快跑：没看到一边倒的快跑线，别自己脑补。"
        return "快跑：" + "，".join(calls[:3]) + "。"

    def _run_why(self, *, tech_strength: float, yield_move: float, oil_move: float, dollar_move: float, china_move: float) -> str:
        reasons: list[str] = []
        if oil_move >= 2.0 or oil_move <= -2.0:
            reasons.append(self._bucket_by_key("energy_transport").get("lead_line") or "")
        if yield_move >= 0.5 or dollar_move >= 0.5:
            reasons.append(self._bucket_by_key("rates_fx").get("lead_line") or "")
        if china_move <= -1.0:
            reasons.append(self._bucket_by_key("china_proxy").get("lead_line") or "")
        if tech_strength <= 1.0:
            reasons.append(self._bucket_by_key("us_equities").get("lead_line") or "")
        if not any(reason for reason in reasons):
            return "当前没有明显快跑线，先看竞价和盘面反馈。"
        return "因为 " + "，".join(reason for reason in reasons if reason) + "。"

    def _wrong_when_text(
        self,
        *,
        tech_strength: float,
        soxx_move: float,
        oil_move: float,
        china_move: float,
        kweb_move: float,
        ixic_move: float,
    ) -> str:
        checks: list[str] = []
        if tech_strength >= 1.8 or soxx_move >= 2.0:
            checks.append("如果科技竞价不强，半导体开盘也续不上，那就别硬追科技")
        if oil_move <= -2.0:
            checks.append("如果油价盘前又被拉回去，成本链这条就别当真")
        if china_move >= 1.0:
            checks.append("如果 KWEB/FXI 这条映射开盘不跟，港股互联网映射就先放一边")
        elif kweb_move <= -1.0 and ixic_move >= -0.5:
            checks.append("如果中概互联网一开盘就被硬拉，而半导体反而续不上，昨夜那种分化就不成立了")
        if not checks:
            checks.append("如果昨夜最强那桶开盘就掉线，今天的判断就得立刻改")
        return "什么时候判断错了：" + "；".join(checks[:3]) + "。"

    def _build_attribution_bucket(self, bucket: dict[str, Any]) -> dict[str, Any]:
        news_payload = self._news_bucket_payload(bucket, entry_limit=8)
        explains = [entry["line"] for entry in list(news_payload.get("primary_entries", []) or [])[:4]]
        backgrounds = [self._background_attribution_line(entry) for entry in list(news_payload.get("background_entries", []) or [])[:4]]
        misses = [
            entry["line"]
            for entry in self.ignored_messages
            if self._bucket_relevance(self._find_item(entry.get("item_id", 0)), bucket["bucket_key"]) > 0
        ][:3]
        if not explains:
            explains = ["当前没找到能稳稳对上这桶价格动作的硬新闻。"]
        if not backgrounds:
            backgrounds = ["当前没看到需要单独留在背景层的同主题消息。"]
        if not misses:
            misses = ["暂时没看到明显对不上但被市场硬炒的同桶消息。"]
        return {
            "bucket_key": bucket["bucket_key"],
            "bucket_label": bucket["bucket_label"],
            "explains": explains,
            "backgrounds": backgrounds,
            "does_not_explain": misses,
        }

    def _background_attribution_line(self, entry: dict[str, Any]) -> str:
        line = str(entry.get("line", "")).strip()
        reason = str(entry.get("background_reason", "")).strip()
        if not reason:
            return line
        return self._clean_line(f"{line}；背景原因：{reason}")

    def _build_data_gap_items(self) -> list[str]:
        items = [
            str(value).strip()
            for value in list(self.follow_up_panel.get("data_gaps", []) or [])
            if str(value).strip()
        ]
        capture_summary = dict(self.market_snapshot.get("capture_summary", {}) or {})
        core_missing = [
            str(value).strip()
            for value in list(capture_summary.get("core_missing_symbols", []) or [])
            if str(value).strip()
        ]
        if core_missing:
            items.append(f"core market gap：{', '.join(core_missing)}")
        provider_statuses = dict(self.external_signal_panel.get("provider_statuses", {}) or {})
        for provider_name, status in provider_statuses.items():
            normalized = str(status).strip()
            if normalized and normalized != "ready":
                items.append(f"provider {provider_name} 当前 {normalized}")
        if not items:
            items.append("当前没缺口，核心结果桶和外部信号都还能看。")
        return list(dict.fromkeys(self._clean_line(item) for item in items if item))

    def _desk_bucket(self, bucket: dict[str, Any]) -> dict[str, Any]:
        if bucket["rows"]:
            return bucket
        return {
            **bucket,
            "placeholder": "当前没货" if bucket["bucket_key"] != "probability_markets" else "当前缺口",
        }

    def _desk_news_bucket(self, bucket: dict[str, Any]) -> dict[str, Any]:
        payload = self._news_bucket_payload(bucket, entry_limit=8)
        entries = list(payload.get("entries", []) or [])
        if entries:
            return payload
        return {
            "bucket_key": bucket["bucket_key"],
            "bucket_label": bucket["bucket_label"],
            "entries": [],
            "primary_entries": [],
            "background_entries": [],
            "placeholder": "当前没货" if bucket["rows"] else "当前缺口",
        }

    def _render_group_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# 群发中长版",
            "",
            f"- Analysis Date: {self.analysis_date}",
            f"- Access Tier: {self.access_tier}",
            "",
            "## 一句定盘",
            "",
        ]
        lines.extend(f"- {sentence}" for sentence in list(payload.get("opening", {}).get("sentences", []) or []) if sentence)
        lines.extend(["", "## 结果数据层", ""])
        for bucket in list(payload.get("result_data", {}).get("buckets", []) or []):
            lines.append(f"### {bucket['bucket_label']}")
            lines.append("")
            lines.extend(f"- {row['line']}" for row in list(bucket.get("rows", []) or []))
            texture_line = str(dict(bucket.get("texture", {}) or {}).get("texture_line", "")).strip()
            if texture_line:
                lines.append(f"- 盘面纹理：{texture_line}")
            lines.append("")
        lines.extend(["## 新闻/信息层", ""])
        news_buckets = list(payload.get("news_layer", {}).get("buckets", []) or [])
        if not news_buckets:
            lines.append("- 当前没货。")
            lines.append("")
        else:
            for bucket in news_buckets:
                lines.append(f"### {bucket['bucket_label']}")
                lines.append("")
                primary_entries = list(bucket.get("primary_entries", []) or [])
                background_entries = list(bucket.get("background_entries", []) or [])
                if primary_entries:
                    lines.append("主因：")
                    lines.extend(f"- {entry['line']}" for entry in primary_entries)
                if background_entries:
                    lines.append("背景：")
                    lines.extend(f"- {entry['line']}" for entry in background_entries)
                lines.append("")
        lines.extend(self._render_ignored_heat_markdown(dict(payload.get("ignored_heat", {}) or {}), include_asset_audit=False))
        lines.extend(["", "## A股今天怎么打", ""])
        for segment in list(payload.get("a_share_playbook", {}).get("segments", []) or []):
            lines.append(f"### {segment['label']}")
            lines.append("")
            lines.append(str(segment.get("text", "")).strip() or "还不清楚。")
            lines.append("")
        return self._clean_markdown("\n".join(lines).strip() + "\n")

    def _render_desk_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# 内参长版",
            "",
            f"- Analysis Date: {self.analysis_date}",
            f"- Access Tier: {self.access_tier}",
            f"- Report Version: {self.report_version}",
            "",
            "## 一句定盘",
            "",
        ]
        lines.extend(f"- {sentence}" for sentence in list(payload.get("opening", {}).get("sentences", []) or []) if sentence)
        lines.extend(["", "## 结果数据层", ""])
        for bucket in list(payload.get("result_data", {}).get("buckets", []) or []):
            lines.append(f"### {bucket['bucket_label']}")
            lines.append("")
            rows = list(bucket.get("rows", []) or [])
            if rows:
                lines.extend(f"- {row['line']}" for row in rows)
                texture_line = str(dict(bucket.get("texture", {}) or {}).get("texture_line", "")).strip()
                if texture_line:
                    lines.append(f"- 盘面纹理：{texture_line}")
            else:
                lines.append(f"- {bucket.get('placeholder', '当前没货')}")
            lines.append("")
        lines.extend(["## 新闻/信息层", ""])
        for bucket in list(payload.get("news_layer", {}).get("buckets", []) or []):
            lines.append(f"### {bucket['bucket_label']}")
            lines.append("")
            entries = list(bucket.get("entries", []) or [])
            if entries:
                primary_entries = list(bucket.get("primary_entries", []) or [])
                background_entries = list(bucket.get("background_entries", []) or [])
                if primary_entries:
                    lines.append("主因：")
                    lines.extend(f"- {entry['line']}" for entry in primary_entries)
                if background_entries:
                    lines.append("背景：")
                    lines.extend(f"- {entry['line']}" for entry in background_entries)
            else:
                lines.append(f"- {bucket.get('placeholder', '当前没货')}")
            lines.append("")
        lines.extend(["## 归因层", ""])
        for bucket in list(payload.get("attribution_layer", {}).get("buckets", []) or []):
            lines.append(f"### {bucket['bucket_label']}")
            lines.append("")
            lines.append("主因：")
            lines.extend(f"- {line}" for line in list(bucket.get("explains", []) or []))
            lines.append("背景：")
            lines.extend(f"- {line}" for line in list(bucket.get("backgrounds", []) or []))
            lines.append("没认：")
            lines.extend(f"- {line}" for line in list(bucket.get("does_not_explain", []) or []))
            lines.append("")
        lines.extend(["## 数据缺口层", ""])
        lines.extend(f"- {item}" for item in list(payload.get("data_gap_layer", {}).get("items", []) or []))
        lines.append("")
        lines.extend(self._render_ignored_heat_markdown(dict(payload.get("ignored_heat", {}) or {}), include_asset_audit=True))
        lines.extend(["", "## A股映射层", ""])
        for segment in list(payload.get("a_share_mapping", {}).get("segments", []) or []):
            lines.append(f"### {segment['label']}")
            lines.append("")
            lines.append(str(segment.get("text", "")).strip() or "还不清楚。")
            why = str(segment.get("why", "")).strip()
            if why:
                lines.append(f"- 为什么：{why}")
            lines.append("")
        continuation = dict(payload.get("continuation_check", {}) or {})
        if continuation.get("items"):
            lines.extend(["## 盘后续线验证", ""])
            for item in list(continuation.get("items", []) or []):
                lines.append(f"- {item}")
            lines.append("")
        return self._clean_markdown("\n".join(lines).strip() + "\n")

    def _render_ignored_heat_markdown(self, payload: dict[str, Any], *, include_asset_audit: bool = False) -> list[str]:
        lines = ["## 昨晚市场没认的消息", ""]
        message_misses = list(payload.get("message_misses", []) or [])
        asset_misses = list(payload.get("asset_misses", []) or [])
        fallback_entries = list(payload.get("entries", []) or [])
        if not message_misses and not asset_misses and not fallback_entries:
            lines.append("- 当前没货。")
            return lines
        if message_misses:
            lines.append("### 消息没认")
            lines.append("")
            lines.extend(f"- {entry['line']}" for entry in message_misses)
            lines.append("")
        if asset_misses:
            lines.append("### 资产没认")
            lines.append("")
            for entry in asset_misses:
                lines.append(f"- {entry['line']}")
                audit_line = str(entry.get("audit_line", "")).strip()
                if include_asset_audit and audit_line:
                    lines.append(f"  - {audit_line}")
            lines.append("")
        if not message_misses and not asset_misses:
            lines.extend(f"- {entry['line']}" for entry in fallback_entries)
        elif lines[-1] == "":
            lines.pop()
        return lines

    def _build_continuation_check_items(self) -> list[str]:
        items: list[str] = []
        futures_watch = [
            item
            for item in list(self.asset_board.get("china_mapped_futures", []) or self.market_snapshot.get("china_mapped_futures", []) or [])
            if isinstance(item, dict)
        ]
        if futures_watch:
            lines = []
            for item in futures_watch[:4]:
                future_name = str(item.get("future_name", "")).strip()
                watch_score = item.get("watch_score")
                if not future_name or watch_score is None:
                    continue
                lines.append(f"{future_name} {self._move_word(watch_score)}（watch {self._format_signed_number(watch_score, fallback='watch')}）")
            if lines:
                items.append("中国映射期货：" + "；".join(lines))
            else:
                items.append("中国映射期货当前没有足够清楚的 watch 行。")
        else:
            items.append("中国映射期货当前缺口，没法判断昨夜主线有没有续到盘后。")

        provider_statuses = dict(self.external_signal_panel.get("provider_statuses", {}) or {})
        continuation_statuses = []
        for provider_name in ("polymarket", "kalshi", "cme_fedwatch", "cftc"):
            status = str(provider_statuses.get(provider_name, "")).strip()
            if not status:
                continue
            continuation_statuses.append(f"{provider_name}={status}")
        if continuation_statuses:
            items.append("盘后概率信号：" + "；".join(continuation_statuses))
        else:
            items.append("盘后概率信号当前没有足够稳定的状态可用。")

        if not items:
            items.append("当前没法做盘后续线验证。")
        return items

    def _bucket_by_key(self, bucket_key: str) -> dict[str, Any]:
        return next((bucket for bucket in self.bucket_results if bucket["bucket_key"] == bucket_key), {"bucket_key": bucket_key, "rows": []})

    def _avg_change(self, symbols: tuple[str, ...]) -> float:
        values = [
            _to_float(row.get("numeric_value"))
            for bucket in self.bucket_results
            for row in list(bucket.get("rows", []) or [])
            if str(row.get("symbol", "")).strip() in symbols and _to_float(row.get("numeric_value")) is not None
        ]
        numeric_values = [float(value) for value in values if value is not None]
        if not numeric_values:
            return 0.0
        return sum(numeric_values) / len(numeric_values)

    def _symbol_row(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").strip()
        if not normalized:
            return {}
        for bucket in self.bucket_results:
            for row in list(bucket.get("rows", []) or []):
                if str(row.get("symbol", "")).strip() == normalized:
                    return row
        return {}

    def _symbol_change(self, symbol: str) -> float:
        row = self._symbol_row(symbol)
        if row:
            numeric = _to_float(row.get("numeric_value"))
            if numeric is not None:
                return float(numeric)
        return 0.0

    def _dominant_sign(self, rows: list[dict[str, Any]]) -> int:
        values = [float(value) for value in (_to_float(row.get("numeric_value")) for row in rows) if value is not None]
        if not values:
            return 0
        average = sum(values) / len(values)
        if average > 0.15:
            return 1
        if average < -0.15:
            return -1
        return 0

    def _bucket_news_sign(self, bucket_key: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        if bucket_key == "energy_transport":
            oil_sign = self._sign_from_symbols(rows, ("CL=F", "BZ=F"))
            if oil_sign != 0:
                return oil_sign
        if bucket_key == "us_equities":
            strongest = self._strongest_move_sign(rows, symbols=("SOXX", "XLK", "^IXIC", "^GSPC"))
            if strongest != 0:
                return strongest
        if bucket_key == "rates_fx":
            rates_sign = self._sign_from_symbols(rows, ("^TNX", "DX-Y.NYB", "CNH=X"))
            if rates_sign != 0:
                return rates_sign
        if bucket_key == "china_proxy":
            if self._bucket_has_mixed_core_moves(rows, symbols=("KWEB", "FXI")):
                return 0
            china_sign = self._sign_from_symbols(rows, ("KWEB", "FXI"))
            if china_sign != 0:
                return china_sign
        return self._dominant_sign(rows)

    def _sign_from_symbols(self, rows: list[dict[str, Any]], symbols: tuple[str, ...]) -> int:
        values: list[float] = []
        for symbol in symbols:
            for row in rows:
                if str(row.get("symbol", "")).strip() != symbol:
                    continue
                numeric = _to_float(row.get("numeric_value"))
                if numeric is not None:
                    values.append(float(numeric))
                    break
        if not values:
            return 0
        average = sum(values) / len(values)
        if average > 0.15:
            return 1
        if average < -0.15:
            return -1
        return 0

    def _strongest_move_sign(self, rows: list[dict[str, Any]], *, symbols: tuple[str, ...]) -> int:
        best_abs = 0.0
        best_sign = 0
        for symbol in symbols:
            for row in rows:
                if str(row.get("symbol", "")).strip() != symbol:
                    continue
                numeric = _to_float(row.get("numeric_value"))
                if numeric is None:
                    continue
                absolute = abs(float(numeric))
                if absolute <= best_abs:
                    continue
                best_abs = absolute
                if float(numeric) > 0.15:
                    best_sign = 1
                elif float(numeric) < -0.15:
                    best_sign = -1
                else:
                    best_sign = 0
        return best_sign

    def _move_word(self, value: object) -> str:
        numeric = _to_float(value)
        if numeric is None:
            return "一般"
        if numeric >= 4.0:
            return "暴涨"
        if numeric <= -4.0:
            return "暴跌"
        if numeric >= 2.0:
            return "大涨"
        if numeric <= -2.0:
            return "大跌"
        if numeric >= 0.35:
            return "小涨"
        if numeric <= -0.35:
            return "小跌"
        return "一般"

    def _confirmation_strength(self, item: dict[str, Any]) -> int:
        confirmation = dict(item.get("cross_source_confirmation", {}) or {})
        level = str(confirmation.get("level", "")).strip()
        supporting = int(confirmation.get("supporting_source_count", 0) or 0)
        if level in {"strong", "high"} or supporting >= 2:
            return 2
        if level in {"moderate", "medium"} or supporting >= 1:
            return 1
        return 0

    def _official_bonus(self, item: dict[str, Any]) -> int:
        coverage_tier = str(item.get("coverage_tier", "")).strip()
        if coverage_tier in {"official_policy", "official_data"}:
            return 2
        if coverage_tier == "editorial_media":
            return 1
        return 0

    def _item_event_summary(self, item: dict[str, Any]) -> str:
        for field in ("user_brief_cn", "impact_summary", "llm_ready_brief"):
            candidate = str(item.get(field, "")).strip()
            if candidate:
                return candidate
        evidence_points = [str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip()]
        if evidence_points:
            return evidence_points[0]
        return "这条消息还没浓缩出一句硬结论。"

    def _item_bucket_why(
        self,
        item: dict[str, Any],
        bucket_key: str,
        bucket: dict[str, Any],
        *,
        relevance_detail: dict[str, Any] | None = None,
    ) -> str:
        relevance_detail = dict(relevance_detail or {})
        lead = str(bucket.get("lead_line", "")).strip()
        bucket_specific_snippet = self._bucket_specific_why_snippet(item, bucket_key=bucket_key)
        field_candidates = (
            bucket_specific_snippet,
            str(item.get("user_brief_cn", "")).strip(),
            str(item.get("impact_summary", "")).strip(),
            str(item.get("why_it_matters_cn", "")).strip(),
            str(item.get("llm_ready_brief", "")).strip(),
        )
        snippet = next((candidate for candidate in field_candidates if candidate and not self._looks_like_generic_bucket_snippet(candidate)), "")
        title_hits = int(relevance_detail.get("title_hits", 0) or 0)
        symbol_hits = int(relevance_detail.get("symbol_hits", 0) or 0)
        topic_hits = int(relevance_detail.get("specific_topic_hits", 0) or 0)
        if symbol_hits > 0:
            why_tail = "标题直接点到这桶资产，能对上上面这根线。"
        elif title_hits > 0:
            why_tail = "标题就在讲这桶主驱动，能对上上面这根线。"
        elif topic_hits > 0:
            why_tail = "事件簇标签和这桶是一条线，能对上上面这根线。"
        else:
            why_tail = "这条和上面结果桶能对上。"
        if lead:
            why_tail = why_tail.replace("上面这根线", f"上面 {lead} 这根线")
        if snippet:
            return self._clean_line(f"{snippet}，{why_tail}")
        return self._clean_line(why_tail)

    def _bucket_specific_why_snippet(self, item: dict[str, Any], *, bucket_key: str) -> str:
        text = self._item_text(item)
        title = self._item_title_text(item)
        source_id = str(item.get("source_id", "")).strip()
        if bucket_key == "us_equities":
            if any(self._keyword_in_text(text, keyword) for keyword in ("nvidia", "intel", "tsmc", "semiconductor", "chip", "ai")):
                return "芯片和 AI 龙头在带节奏，先把美股科技内部拉出分化。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("earnings", "profit", "guidance", "capital spending", "ipo")):
                return "财报、指引和资本开支预期在改定价，美股先认公司层面的分化。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("stocks", "wall street", "nasdaq", "s&p 500")):
                return "这条就是在写昨夜美股怎么走，能直接拿来解释指数和板块分化。"
        if bucket_key == "rates_fx":
            if any(self._keyword_in_text(text, keyword) for keyword in ("fed", "powell", "warsh", "rate cuts", "fomc")):
                return "美联储路径和主席人选预期还在晃，先压着利率预期和美元定价。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("inflation", "cpi", "ppi", "consumer sentiment", "payroll", "employment")):
                return "通胀和就业预期一变，先动的就是美债收益率、美元和离岸人民币。"
        if bucket_key == "energy_transport":
            if any(self._keyword_in_text(text, keyword) for keyword in ("hormuz", "strait of hormuz", "tanker", "shipping", "pirates", "mine")):
                return "航道和运力一旦出事，油价先把运输风险和供应扰动打进去。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("oil", "crude", "brent", "wti", "refinery", "opec")):
                return "原油供给、炼厂和油轮这几根线一动，能源桶就会先反应。"
        if bucket_key == "precious_metals":
            if any(self._keyword_in_text(text, keyword) for keyword in ("gold", "bullion", "silver", "safe haven", "real yields")):
                return "金银这桶主要看避险和实际利率怎么拉扯，这条就在讲这个。"
            if source_id == "kitco_news" or self._keyword_in_text(title, "kitco"):
                return "贵金属交易盘常先盯金银现货和美债预期，这条就是同一条线。"
        if bucket_key == "industrial_metals":
            if any(self._keyword_in_text(text, keyword) for keyword in ("sulfuric acid", "sx-ew", "copper supply")):
                return "矿山投入品和酸供应收紧，先顶到铜供应和冶炼端。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("smelter", "smelter restart", "curtailment")):
                return "冶炼端的复产、减产和利润变化，直接影响铜铝这条线。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("copper", "aluminum", "aluminium", "warehouse", "inventory", "stockpile", "nickel", "zinc")):
                return "铜铝镍锌这些工业金属先看库存、矿山和冶炼环节有没有收紧。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("critical minerals", "mining", "minerals")):
                return "关键矿产和矿山供给一旦收紧，工业金属先看上游供给链怎么变。"
        if bucket_key == "china_proxy":
            if any(self._keyword_in_text(text, keyword) for keyword in ("deepseek", "china ai", "china technology", "china internet", "china tech")):
                return "中概和港股科技先看 AI 与平台股情绪，这条就在往这根线上打。"
            if any(self._keyword_in_text(text, keyword) for keyword in ("hong kong stocks", "hang seng", "hang seng tech", "china stocks", "kweb", "fxi")):
                return "港股和中概映射先动，A 股这边通常会先看国内资产映射怎么接。"
        return ""

    def _looks_like_generic_bucket_snippet(self, value: str) -> bool:
        candidate = str(value or "").strip()
        if not candidate:
            return True
        return any(
            token in candidate
            for token in (
                "当前只确认这是需要跟踪的消息",
                "需继续跟踪后续市场与政策细节",
                "关注方向：",
                "后续关注：",
                "item_id=",
                "authority=",
                "capture=",
                "cross_source=",
                "conflict_count=",
                "facts=",
                "watch=",
                "贸易/关税/供应链",
                "油气与航运扰动可能向成本线传导",
                "偏紧的利率/通胀信号可能先影响估值切换",
            )
        )

    def _item_text(self, item: dict[str, Any]) -> str:
        parts: list[str] = [
            str(item.get("title", "")).strip(),
            str(item.get("user_brief_cn", "")).strip(),
            str(item.get("why_it_matters_cn", "")).strip(),
            str(item.get("impact_summary", "")).strip(),
            str(item.get("llm_ready_brief", "")).strip(),
        ]
        parts.extend(str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip())
        parts.extend(str(value).strip() for value in list(item.get("follow_up_checks", []) or []) if str(value).strip())
        parts.extend(str(dict(value).get("text", "")).strip() for value in list(item.get("fact_table", []) or []) if isinstance(value, dict))
        parts.extend(str(tag).strip() for tag in self._item_topic_tags(item))
        return f" {' '.join(part.lower() for part in parts if part)} "

    def _item_title_text(self, item: dict[str, Any]) -> str:
        title = str(item.get("title", "")).strip().lower()
        return f" {title} " if title else " "

    def _item_evidence_text(self, item: dict[str, Any]) -> str:
        parts: list[str] = [
            str(item.get("user_brief_cn", "")).strip(),
            str(item.get("impact_summary", "")).strip(),
        ]
        parts.extend(str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip())
        parts.extend(str(dict(value).get("text", "")).strip() for value in list(item.get("fact_table", []) or []) if isinstance(value, dict))
        return f" {' '.join(part.lower() for part in parts if part)} "

    def _item_market_text(self, item: dict[str, Any]) -> str:
        parts: list[str] = [
            str(item.get("title", "")).strip(),
            str(item.get("user_brief_cn", "")).strip(),
            str(item.get("impact_summary", "")).strip(),
        ]
        parts.extend(str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip())
        return f" {' '.join(part.lower() for part in parts if part)} "

    def _item_directions(self, item: dict[str, Any]) -> list[str]:
        directions = []
        for field in ("beneficiary_directions", "pressured_directions", "price_up_signals"):
            directions.extend(str(value).strip() for value in list(item.get(field, []) or []) if str(value).strip())
        return list(dict.fromkeys(directions))

    def _item_topic_tags(self, item: dict[str, Any]) -> list[str]:
        event_cluster = dict(item.get("event_cluster", {}) or {})
        return [
            str(value).strip()
            for value in list(event_cluster.get("topic_tags", []) or [])
            if str(value).strip()
        ]

    def _topic_tag_bucket(self, topic_tag: str) -> str:
        normalized = str(topic_tag).strip().lower()
        return SPECIFIC_TOPIC_BUCKET_HINTS.get(normalized, "")

    def _soft_topic_tag_bucket(self, topic_tag: str) -> str:
        normalized = str(topic_tag).strip().lower()
        return SOFT_TOPIC_BUCKET_HINTS.get(normalized, "")

    def _find_item(self, item_id: int) -> dict[str, Any]:
        normalized = int(item_id or 0)
        return next((item for item in self.items if self._item_id(item) == normalized), {})

    def _item_key(self, item: dict[str, Any]) -> str:
        item_id = self._item_id(item)
        if item_id:
            return str(item_id)
        return str(item.get("source_id", "")).strip() or str(item.get("title", "")).strip()

    def _item_id(self, item: dict[str, Any]) -> int:
        try:
            return int(item.get("item_id", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _format_signed_number(self, value: object, *, fallback: str = "") -> str:
        numeric = _to_float(value)
        if numeric is None:
            return fallback
        return f"{numeric:+.2f}"

    def _clean_markdown(self, markdown: str) -> str:
        cleaned = markdown
        for banned in BANNED_STYLE_TERMS:
            cleaned = cleaned.replace(banned, "")
            cleaned = cleaned.replace(banned.title(), "")
            cleaned = cleaned.replace(banned.upper(), "")
        cleaned = cleaned.replace("  ", " ")
        cleaned = cleaned.replace("。。", "。")
        return cleaned

    def _clean_line(self, value: str) -> str:
        candidate = " ".join(str(value or "").split()).strip()
        return self._clean_markdown(candidate)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
