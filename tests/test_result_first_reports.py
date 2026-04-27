# -*- coding: utf-8 -*-
"""Tests for result-first desk/group report products."""

from __future__ import annotations

from app.services.result_first_reports import build_result_first_reports


def _news_item(
    *,
    item_id: int,
    source_name: str,
    source_id: str,
    title: str,
    user_brief_cn: str,
    why_it_matters_cn: str,
    coverage_tier: str = "official_data",
    signal_score: int = 16,
    supporting_source_count: int = 2,
    beneficiary_directions: list[str] | None = None,
    pressured_directions: list[str] | None = None,
    price_up_signals: list[str] | None = None,
    topic_tags: list[str] | None = None,
    evidence_points: list[str] | None = None,
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "source_name": source_name,
        "source_id": source_id,
        "title": title,
        "coverage_tier": coverage_tier,
        "signal_score": signal_score,
        "user_brief_cn": user_brief_cn,
        "why_it_matters_cn": why_it_matters_cn,
        "impact_summary": user_brief_cn,
        "llm_ready_brief": user_brief_cn,
        "beneficiary_directions": list(beneficiary_directions or []),
        "pressured_directions": list(pressured_directions or []),
        "price_up_signals": list(price_up_signals or []),
        "evidence_points": list(evidence_points or []),
        "cross_source_confirmation": {
            "level": "moderate" if supporting_source_count >= 1 else "single_source",
            "supporting_source_count": supporting_source_count,
        },
        "event_cluster": {
            "cluster_id": f"cluster_{item_id}",
            "topic_tags": list(topic_tags or []),
        },
    }


def test_build_result_first_reports_enforces_bucket_order_and_style_contract() -> None:
    us_items = [
        _news_item(
            item_id=1,
            source_name="NASDAQ Desk",
            source_id="nasdaq_desk",
            title="Nasdaq jumps as AI chip names lead again",
            user_brief_cn="纳指和芯片股继续往上冲。",
            why_it_matters_cn="这条能对上半导体和纳指暴涨。",
            topic_tags=["tech_equity"],
            beneficiary_directions=["自主可控半导体链"],
            evidence_points=["Nasdaq closes up more than 4%。"],
        ),
        _news_item(
            item_id=2,
            source_name="Reuters",
            source_id="reuters",
            title="Chip exporters rally after fresh demand read",
            user_brief_cn="芯片链景气预期又被抬了一脚。",
            why_it_matters_cn="这条能对上 SOXX 暴涨。",
            coverage_tier="editorial_media",
            topic_tags=["semiconductor_supply_chain"],
            beneficiary_directions=["自主可控半导体链"],
            evidence_points=["SOXX closes sharply higher。"],
        ),
        _news_item(
            item_id=3,
            source_name="Bloomberg",
            source_id="bloomberg",
            title="Banks follow equities higher into the close",
            user_brief_cn="金融股跟着大盘一起抬。",
            why_it_matters_cn="这条能对上 XLF 大涨。",
            coverage_tier="editorial_media",
            topic_tags=["equity_market"],
            evidence_points=["Financial sector closes higher。"],
        ),
        _news_item(
            item_id=4,
            source_name="CNBC",
            source_id="cnbc",
            title="Wall Street keeps piling into technology stocks",
            user_brief_cn="资金还在往科技票里扑。",
            why_it_matters_cn="这条能对上 XLK 大涨。",
            coverage_tier="editorial_media",
            topic_tags=["technology_risk"],
            evidence_points=["Technology stocks keep rallying。"],
        ),
    ]
    energy_items = [
        _news_item(
            item_id=10,
            source_name="Reuters Energy",
            source_id="reuters_energy",
            title="Brent falls after supply headlines calm down",
            user_brief_cn="布油先砸下去。",
            why_it_matters_cn="这条能对上布油大跌。",
            topic_tags=["energy_supply"],
            price_up_signals=["原油/燃料油"],
            evidence_points=["Brent drops almost 4%。"],
        ),
        _news_item(
            item_id=11,
            source_name="AP Business",
            source_id="ap_business",
            title="WTI drops as traders unwind war premium",
            user_brief_cn="WTI 把昨晚的溢价吐回去了。",
            why_it_matters_cn="这条能对上 WTI 暴跌。",
            coverage_tier="editorial_media",
            topic_tags=["oil_market"],
            evidence_points=["WTI drops more than 4%。"],
        ),
        _news_item(
            item_id=12,
            source_name="Shipping Ledger",
            source_id="shipping_ledger",
            title="Freight rates cool as tanker stress eases",
            user_brief_cn="运价先松一口气。",
            why_it_matters_cn="这条能对上能源运输这桶一起往下。",
            coverage_tier="editorial_media",
            topic_tags=["shipping_transport"],
            evidence_points=["Shipping costs cool down。"],
        ),
        _news_item(
            item_id=13,
            source_name="OPEC Monitor",
            source_id="opec_monitor",
            title="Oil traders see weaker near-term squeeze risk",
            user_brief_cn="油市挤仓线先松。",
            why_it_matters_cn="这条能对上原油大跌。",
            topic_tags=["energy_supply"],
            evidence_points=["Squeeze risk looks softer。"],
        ),
        _news_item(
            item_id=14,
            source_name="Gas Daily",
            source_id="gas_daily",
            title="Natural gas falls as weather premium fades",
            user_brief_cn="天然气也在掉。",
            why_it_matters_cn="这条能对上天然气大跌。",
            topic_tags=["energy_supply"],
            evidence_points=["Natural gas falls sharply。"],
        ),
        _news_item(
            item_id=99,
            source_name="Hot rumor desk",
            source_id="rumor_desk",
            title="Rumor says oil will surge after emergency strike",
            user_brief_cn="群里都在喊油价要飙。",
            why_it_matters_cn="这条说油价会暴涨。",
            coverage_tier="editorial_media",
            supporting_source_count=0,
            topic_tags=["energy_supply"],
            evidence_points=["Oil could surge on strike rumor。"],
        ),
    ]

    report = {
        "analysis_date": "2026-04-23",
        "access_tier": "premium",
        "version": 3,
        "summary": {"headline": "纳指和原油一上一下。"},
        "mainline_coverage": {"status": "confirmed"},
        "market_snapshot": {
            "analysis_date": "2026-04-23",
            "market_date": "2026-04-22",
            "capture_summary": {
                "capture_status": "partial",
                "core_missing_symbols": ["GC=F"],
            },
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指", "change_pct": 4.2, "change_pct_text": "+4.20%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": 2.1, "change_pct_text": "+2.10%", "priority": 98},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": 5.1, "change_pct_text": "+5.10%", "priority": 96},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 6.0, "change_pct_text": "+6.00%", "priority": 95},
                    {"symbol": "XLF", "display_name": "金融板块", "change_pct": 2.3, "change_pct_text": "+2.30%", "priority": 94},
                ],
                "sentiment": [
                    {"symbol": "^VIX", "display_name": "VIX", "change_pct": -12.0, "change_pct_text": "-12.00%", "priority": 93},
                ],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -3.3, "change_pct_text": "-3.30%", "priority": 90},
                    {"symbol": "DX-Y.NYB", "display_name": "美元指数", "change_pct": -0.8, "change_pct_text": "-0.80%", "priority": 89},
                    {"symbol": "CNH=X", "display_name": "美元/离岸人民币", "change_pct": -0.4, "change_pct_text": "-0.40%", "priority": 88},
                ],
                "precious_metals": [],
                "energy": [
                    {"symbol": "CL=F", "display_name": "WTI", "change_pct": -4.1, "change_pct_text": "-4.10%", "priority": 85},
                    {"symbol": "BZ=F", "display_name": "布油", "change_pct": -3.8, "change_pct_text": "-3.80%", "priority": 84},
                    {"symbol": "NG=F", "display_name": "天然气", "change_pct": -2.2, "change_pct_text": "-2.20%", "priority": 83},
                ],
                "industrial_metals": [
                    {"symbol": "HG=F", "display_name": "铜", "change_pct": 1.4, "change_pct_text": "+1.40%", "priority": 82},
                    {"symbol": "ALI=F", "display_name": "铝", "change_pct": 0.9, "change_pct_text": "+0.90%", "priority": 81},
                ],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": 2.0, "change_pct_text": "+2.00%", "priority": 80},
                    {"symbol": "FXI", "display_name": "富时中国50", "change_pct": 1.2, "change_pct_text": "+1.20%", "priority": 79},
                ],
                "china_mapped_futures": [
                    {"future_code": "pta", "future_name": "PTA", "watch_score": -1.2},
                    {"future_code": "industrial_silicon", "future_name": "工业硅", "watch_score": 1.1},
                ],
            },
        },
        "product_view": {
            "follow_up_panel": {
                "data_gaps": ["市场快照核心缺口：GC=F"],
            },
            "external_signal_panel": {
                "provider_statuses": {
                    "polymarket": "ready",
                    "kalshi": "ready",
                    "cme_fedwatch": "ready",
                    "cftc": "delayed",
                },
                "providers": {
                    "polymarket": {"status": "ready", "headline": "Polymarket 还在押降息路径。", "signal_count": 2},
                    "kalshi": {"status": "ready", "headline": "Kalshi 继续押大盘偏热。", "signal_count": 2},
                    "cme_fedwatch": {"status": "ready", "headline": "FedWatch 显示两场会议都有分歧。", "meeting_count": 2},
                    "cftc": {"status": "delayed", "headline": "CFTC 仓位更新慢半拍。", "signal_count": 1},
                },
            },
        },
        "direction_calls": [
            {"direction": "自主可控半导体链", "stance": "positive"},
            {"direction": "油气开采", "stance": "negative"},
        ],
        "stock_calls": [{"ticker": "688981.SH", "name": "中芯国际"}],
        "supporting_items": us_items + energy_items,
        "headline_news": us_items[:4] + energy_items,
    }

    products = build_result_first_reports(report, source_audit_pack={"event_group_count": 6, "included_item_count": 10})
    group_report = products["group_report"]
    desk_report = products["desk_report"]

    assert group_report["section_order"] == ["一句定盘", "结果数据层", "新闻/信息层", "昨晚市场没认的消息", "A股今天怎么打"]
    assert [bucket["bucket_label"] for bucket in group_report["result_data"]["buckets"]] == [
        "美股指数与板块",
        "利率汇率",
        "能源运输",
        "工业品",
        "国内资产映射",
        "概率市场",
    ]
    assert [bucket["bucket_label"] for bucket in desk_report["result_data"]["buckets"]] == [
        "美股指数与板块",
        "利率汇率",
        "能源运输",
        "贵金属",
        "工业品",
        "国内资产映射",
        "概率市场",
    ]

    first_line = group_report["result_data"]["buckets"][0]["rows"][0]["line"]
    assert "暴涨" in first_line
    assert "+4.20%" in first_line

    energy_news = next(bucket for bucket in group_report["news_layer"]["buckets"] if bucket["bucket_label"] == "能源运输")
    assert 4 <= len(energy_news["entries"]) <= 6
    assert energy_news["primary_entries"]
    assert energy_news["background_entries"]
    assert all(entry["news_role"] == "primary" for entry in energy_news["primary_entries"])
    assert all(entry["news_role"] == "background" for entry in energy_news["background_entries"])
    assert any("Hot rumor desk" in entry["line"] for entry in group_report["ignored_heat"]["entries"])

    precious_bucket = next(bucket for bucket in desk_report["result_data"]["buckets"] if bucket["bucket_label"] == "贵金属")
    assert precious_bucket["status"] == "empty"
    assert precious_bucket["placeholder"] == "当前没货"
    assert desk_report["a_share_mapping"]["segments"][0]["why"]
    energy_attr = next(bucket for bucket in desk_report["attribution_layer"]["buckets"] if bucket["bucket_label"] == "能源运输")
    assert energy_attr["explains"]
    assert energy_attr["backgrounds"]

    for banned in ("risk-on", "risk-off", "受益", "承压", "主情景", "次情景", "失效条件"):
        assert banned not in group_report["markdown"]
        assert banned not in desk_report["markdown"]
    assert "互校：" not in group_report["markdown"]


def test_group_report_omits_bucket_when_only_weak_keyword_noise_exists() -> None:
    weak_equity_noise = [
        _news_item(
            item_id=200 + index,
            source_name="Noise Wire",
            source_id=f"noise_{index}",
            title=f"AI policy sidebar {index}",
            user_brief_cn="这条更像泛消息，不够解释收盘结果。",
            why_it_matters_cn="还不够硬，先别往结果桶里塞。",
            coverage_tier="editorial_media",
            supporting_source_count=0,
            topic_tags=["macro_misc"],
        )
        for index in range(1, 5)
    ]

    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "free",
        "version": 1,
        "summary": {"headline": "纳指一般，先看结果。"},
        "mainline_coverage": {"status": "confirmed"},
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指", "change_pct": -0.29, "change_pct_text": "-0.29%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": -0.05, "change_pct_text": "-0.05%", "priority": 99},
                ],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": weak_equity_noise,
        "headline_news": weak_equity_noise,
    }

    products = build_result_first_reports(report)
    group_report = products["group_report"]

    bucket_labels = [bucket["bucket_label"] for bucket in group_report["news_layer"]["buckets"]]
    assert "美股指数与板块" not in bucket_labels


def test_build_result_first_reports_uses_result_first_materials_and_filters_generic_direction_noise() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 5,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指", "change_pct": -0.29, "change_pct_text": "-0.29%", "priority": 100},
                ],
                "sectors": [
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 3.2, "change_pct_text": "+3.20%", "priority": 99},
                ],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -0.7, "change_pct_text": "-0.70%", "priority": 95},
                ],
                "energy": [
                    {"symbol": "CL=F", "display_name": "WTI", "change_pct": 1.6, "change_pct_text": "+1.60%", "priority": 92},
                ],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": -2.1, "change_pct_text": "-2.10%", "priority": 88},
                ],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [
            _news_item(
                item_id=1,
                source_name="AP Politics",
                source_id="ap_politics",
                title="What Hispanic adults think of Trump, according to a new poll",
                user_brief_cn="油气与航运扰动可能向成本线传导。",
                why_it_matters_cn="关注方向：油气开采、油服。",
                coverage_tier="editorial_media",
                topic_tags=["rates_macro", "energy_shipping"],
                beneficiary_directions=["油气开采", "油服"],
                pressured_directions=["航空与燃油敏感运输链"],
                price_up_signals=["原油/燃料油"],
                supporting_source_count=0,
            )
        ],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=11,
                source_name="AP World",
                source_id="ap_world",
                title="Trump orders US military to 'shoot and kill' Iranian small boats choking Strait of Hormuz",
                user_brief_cn="霍尔木兹风险还在，油运线继续紧。",
                why_it_matters_cn="这条能解释油价和运价为什么还会被抬。",
                coverage_tier="editorial_media",
                topic_tags=["energy_supply"],
                evidence_points=["Hormuz chokepoint risk remains active."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=12,
                source_name="AP Financial Markets",
                source_id="ap_financial_markets",
                title="How Wall Street is setting records even with the Iran war still going on",
                user_brief_cn="美股没全面塌，说明资金还在挑着打。",
                why_it_matters_cn="这条能解释为什么指数没大跌但结构分化很大。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["Wall Street stays resilient while oil swings."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=13,
                source_name="Kitco News",
                source_id="kitco_news",
                title="Warsh confirmation hearing reveals regime change for Fed's approach to rates and inflation",
                user_brief_cn="利率和通胀预期又被拿出来讨论。",
                why_it_matters_cn="这条能解释为什么利率线没法轻松。",
                coverage_tier="editorial_media",
                topic_tags=["inflation"],
                evidence_points=["Rates and inflation remain central to the market debate."],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]

    news_by_label = {bucket["bucket_label"]: bucket["entries"] for bucket in desk_report["news_layer"]["buckets"] if bucket["entries"]}
    assert "能源运输" in news_by_label
    assert any("Hormuz" in entry["event"] for entry in news_by_label["能源运输"])
    assert all("AP Politics" not in entry["line"] for entries in news_by_label.values() for entry in entries)
    assert "美股指数与板块" not in news_by_label or all("Hormuz" not in entry["event"] for entry in news_by_label["美股指数与板块"])
    assert "利率汇率" not in news_by_label or all("AP Politics" not in entry["line"] for entry in news_by_label["利率汇率"])
    assert all("Hormuz" not in entry["line"] for entry in desk_report["ignored_heat"]["entries"])


def test_build_result_first_reports_keeps_us_equities_news_on_mixed_close() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 6,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": -0.29, "change_pct_text": "-0.29%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": -0.05, "change_pct_text": "-0.05%", "priority": 99},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": -0.40, "change_pct_text": "-0.40%", "priority": 98},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 3.20, "change_pct_text": "+3.20%", "priority": 97},
                ],
                "sentiment": [
                    {"symbol": "^VIX", "display_name": "VIX", "change_pct": 0.61, "change_pct_text": "+0.61%", "priority": 96},
                ],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=31,
                source_name="AP Business",
                source_id="ap_business",
                title="US stocks rally to records, but Brent oil also tops $100 on worries about the Iran war",
                user_brief_cn="美股整体没塌，但油价也在拱。",
                why_it_matters_cn="这条能解释为什么指数没深跌，但并不是全场一起嗨。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["The Nasdaq rose earlier but the close was choppy."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=32,
                source_name="AP Financial Markets",
                source_id="ap_financial_markets",
                title="US stocks hang around their record highs as oil prices swing",
                user_brief_cn="指数还挂在高位，但油价在搅局。",
                why_it_matters_cn="这条能解释为什么收盘看起来不差，但资金明显在挑着打。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["US stocks hovered around records into the close."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=33,
                source_name="AP Financial Markets",
                source_id="ap_financial_markets",
                title="How Wall Street is setting records even with the Iran war still going on",
                user_brief_cn="市场没崩，但估值压力没消失。",
                why_it_matters_cn="这条能解释为什么大盘没深跌，可成长估值还是被挑着砍。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["Investors kept weighing rates and fear against earnings."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=34,
                source_name="CNBC Technology",
                source_id="cnbc_technology",
                title="Tesla shares fall after results. But this market speculation may keep the stock afloat for a while",
                user_brief_cn="科技龙头不是一起涨，内部还在分化。",
                why_it_matters_cn="这条能解释为什么纳指没深跌，但科技板块也没走成普涨。",
                coverage_tier="editorial_media",
                topic_tags=["technology_risk"],
                evidence_points=["Tesla shares fell after earnings while chip names held up."],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    group_report = products["group_report"]

    us_bucket = next(bucket for bucket in group_report["news_layer"]["buckets"] if bucket["bucket_label"] == "美股指数与板块")
    us_result_bucket = next(bucket for bucket in group_report["result_data"]["buckets"] if bucket["bucket_label"] == "美股指数与板块")

    assert len(us_bucket["entries"]) == 4
    assert any("Tesla shares fall after results" in entry["event"] for entry in us_bucket["entries"])
    assert any("Wall Street is setting records" in entry["event"] for entry in us_bucket["entries"])
    assert us_result_bucket["texture"]["market_shape"] == "结构分化"
    assert us_result_bucket["texture"]["leaders"][0]["symbol"] == "SOXX"
    assert us_result_bucket["texture"]["laggards"][0]["symbol"] == "XLK"
    assert "盘面纹理：" in group_report["markdown"]
    assert "结构分化" in us_result_bucket["texture"]["texture_line"]


def test_build_result_first_reports_adds_china_proxy_texture_when_only_results_exist() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 7,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": -2.10, "change_pct_text": "-2.10%", "priority": 100},
                    {"symbol": "FXI", "display_name": "富时中国50", "change_pct": -1.40, "change_pct_text": "-1.40%", "priority": 99},
                ],
                "china_mapped_futures": [
                    {"future_code": "pta", "future_name": "PTA", "watch_score": -1.20},
                    {"future_code": "industrial_silicon", "future_name": "工业硅", "watch_score": 1.10},
                ],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]

    china_bucket = next(bucket for bucket in desk_report["result_data"]["buckets"] if bucket["bucket_label"] == "国内资产映射")

    assert china_bucket["texture"]["market_shape"] == "普跌"
    assert [row["symbol"] for row in china_bucket["texture"]["laggards"]] == ["KWEB", "FXI"]
    assert "整体偏弱" in china_bucket["texture"]["texture_line"]
    assert "映射期货里 PTA 小跌" in china_bucket["texture"]["texture_line"]
    assert "盘面纹理：" in desk_report["markdown"]


def test_build_result_first_reports_selects_overseas_china_proxy_market_sources() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 9,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": -2.2, "change_pct_text": "-2.20%", "priority": 100},
                    {"symbol": "FXI", "display_name": "富时中国50", "change_pct": -1.1, "change_pct_text": "-1.10%", "priority": 99},
                ],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=501,
                source_name="SCMP Markets",
                source_id="scmp_markets",
                title="Hong Kong stocks fall as China tech ADRs weaken overnight",
                user_brief_cn="港股和中概科技同步走弱。",
                why_it_matters_cn="这条能解释 KWEB 和 FXI 为什么一起挨打。",
                topic_tags=["hong_kong_market", "china_internet"],
                evidence_points=["Hong Kong shares fell as China technology ADRs weakened."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=502,
                source_name="TradingEconomics Hong Kong",
                source_id="tradingeconomics_hk",
                title="Hong Kong shares decline on China internet and property pressure",
                user_brief_cn="香港市场被互联网和地产线拖住。",
                why_it_matters_cn="这条能补充国内资产映射弱势的市场解释。",
                topic_tags=["hong_kong_market", "china_property"],
                evidence_points=["China internet and property shares pressured Hong Kong stocks."],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]
    china_bucket = next(bucket for bucket in desk_report["news_layer"]["buckets"] if bucket["bucket_label"] == "国内资产映射")

    assert china_bucket["primary_entries"]
    assert any("SCMP Markets" in entry["line"] for entry in china_bucket["entries"])
    assert any("TradingEconomics Hong Kong" in entry["line"] for entry in china_bucket["entries"])


def test_build_result_first_reports_keeps_china_proxy_news_when_hk_followthrough_and_us_proxy_diverge() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 10,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中国互联网ETF", "change_pct": -2.1, "change_pct_text": "-2.10%", "priority": 100},
                    {"symbol": "FXI", "display_name": "中国大型股ETF", "change_pct": -0.8, "change_pct_text": "-0.80%", "priority": 99},
                ],
                "china_mapped_futures": [
                    {"future_code": "pta", "future_name": "PTA", "watch_score": 0.6},
                ],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=601,
                source_name="SCMP Markets",
                source_id="scmp_markets",
                title="Hong Kong stocks jump into 2026 with biggest surge since May",
                user_brief_cn="港股早盘强反弹。",
                why_it_matters_cn="这条能补国内资产映射的亚洲延续结构。",
                coverage_tier="editorial_media",
                topic_tags=["hong_kong_market", "china_internet"],
                evidence_points=["Hang Seng Tech climbed in Asia trading。"],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=602,
                source_name="AP Business",
                source_id="ap_business",
                title="US imposes sanctions on a China-based oil refinery and 40 shippers over Iranian oil",
                user_brief_cn="涉中资炼厂的制裁继续发酵。",
                why_it_matters_cn="这条能解释国内资产映射压力。",
                coverage_tier="editorial_media",
                topic_tags=["trade_policy"],
                evidence_points=["China-based refinery sanctions added pressure。"],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]
    china_bucket = next(bucket for bucket in desk_report["news_layer"]["buckets"] if bucket["bucket_label"] == "国内资产映射")

    assert any("Hong Kong stocks jump into 2026" in entry["event"] for entry in china_bucket["entries"])


def test_build_result_first_reports_splits_ignored_heat_into_message_and_asset_misses() -> None:
    rumor_item = _news_item(
        item_id=401,
        source_name="Hot rumor desk",
        source_id="rumor_desk",
        title="Viral desk says a secret ceasefire headline is circulating everywhere",
        user_brief_cn="群里都在传突然停火。",
        why_it_matters_cn="这条很热，但昨夜盘面并没有直接按它走。",
        coverage_tier="editorial_media",
        supporting_source_count=0,
        topic_tags=["macro_misc"],
        evidence_points=["The rumor spread fast, but no hard confirmation followed."],
    )

    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 8,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指", "change_pct": -0.20, "change_pct_text": "-0.20%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": 0.05, "change_pct_text": "+0.05%", "priority": 99},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": -0.40, "change_pct_text": "-0.40%", "priority": 98},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 2.80, "change_pct_text": "+2.80%", "priority": 97},
                ],
                "sentiment": [],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": 0.70, "change_pct_text": "+0.70%", "priority": 96},
                ],
                "energy": [
                    {"symbol": "CL=F", "display_name": "WTI", "change_pct": 4.30, "change_pct_text": "+4.30%", "priority": 95},
                    {"symbol": "BZ=F", "display_name": "布油", "change_pct": 4.00, "change_pct_text": "+4.00%", "priority": 94},
                ],
                "precious_metals": [
                    {"symbol": "GC=F", "display_name": "黄金", "change_pct": -0.70, "change_pct_text": "-0.70%", "priority": 93},
                    {"symbol": "SI=F", "display_name": "白银", "change_pct": -2.90, "change_pct_text": "-2.90%", "priority": 92},
                ],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": -2.40, "change_pct_text": "-2.40%", "priority": 91},
                    {"symbol": "FXI", "display_name": "富时中国50", "change_pct": -1.30, "change_pct_text": "-1.30%", "priority": 90},
                ],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [rumor_item],
        "headline_news": [rumor_item],
        "result_first_materials": [],
    }

    products = build_result_first_reports(report)
    group_report = products["group_report"]

    ignored = group_report["ignored_heat"]
    message_misses = ignored["message_misses"]
    asset_misses = ignored["asset_misses"]

    assert any(entry["kind"] == "message_miss" for entry in message_misses)
    assert any("Hot rumor desk" in entry["line"] for entry in message_misses)
    assert any(entry["kind"] == "asset_miss" for entry in asset_misses)
    assert any("WTI 暴涨（+4.30%）" in entry["event"] and "白银 大跌（-2.90%）" in entry["event"] for entry in asset_misses)
    assert any("半导体板块 大涨（+2.80%）" in entry["event"] and "中概互联网 大跌（-2.40%）" in entry["event"] for entry in asset_misses)
    assert all(isinstance(entry.get("strength"), float) for entry in asset_misses)
    assert all(entry.get("observed_rows") for entry in asset_misses)
    assert all(isinstance(entry.get("primary_context"), list) for entry in asset_misses)
    assert all(isinstance(entry.get("conflict_check"), dict) for entry in asset_misses)
    assert all(entry.get("audit_line") for entry in asset_misses)
    assert any(entry["kind"] == "asset_miss" for entry in ignored["entries"])
    assert "### 消息没认" in group_report["markdown"]
    assert "### 资产没认" in group_report["markdown"]
    assert "互校：" not in group_report["markdown"]
    assert "互校：" in products["desk_report"]["markdown"]


def test_build_result_first_reports_adds_deeper_asset_miss_matrix_cases() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 9,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指", "change_pct": -1.80, "change_pct_text": "-1.80%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": -0.90, "change_pct_text": "-0.90%", "priority": 99},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": -1.30, "change_pct_text": "-1.30%", "priority": 98},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": -2.60, "change_pct_text": "-2.60%", "priority": 97},
                ],
                "sentiment": [],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": -0.80, "change_pct_text": "-0.80%", "priority": 96},
                    {"symbol": "DX-Y.NYB", "display_name": "美元指数", "change_pct": 0.70, "change_pct_text": "+0.70%", "priority": 95},
                    {"symbol": "CNH=X", "display_name": "离岸人民币", "change_pct": -0.20, "change_pct_text": "-0.20%", "priority": 94},
                ],
                "energy": [
                    {"symbol": "CL=F", "display_name": "WTI", "change_pct": -3.10, "change_pct_text": "-3.10%", "priority": 93},
                    {"symbol": "BZ=F", "display_name": "布油", "change_pct": -2.70, "change_pct_text": "-2.70%", "priority": 92},
                ],
                "precious_metals": [
                    {"symbol": "GC=F", "display_name": "黄金", "change_pct": 1.20, "change_pct_text": "+1.20%", "priority": 91},
                    {"symbol": "SI=F", "display_name": "白银", "change_pct": 0.80, "change_pct_text": "+0.80%", "priority": 90},
                ],
                "industrial_metals": [],
                "china_proxies": [
                    {"symbol": "KWEB", "display_name": "中概互联网", "change_pct": 1.40, "change_pct_text": "+1.40%", "priority": 89},
                    {"symbol": "FXI", "display_name": "富时中国50", "change_pct": 1.00, "change_pct_text": "+1.00%", "priority": 88},
                ],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [],
    }

    products = build_result_first_reports(report)
    asset_misses = products["group_report"]["ignored_heat"]["asset_misses"]

    assert any("WTI 大跌（-3.10%）" in entry["event"] and "黄金 小涨（+1.20%）" in entry["event"] for entry in asset_misses)
    assert any("美国10年期国债收益率 小跌（-0.80%）" in entry["event"] and "半导体板块 大跌（-2.60%）" in entry["event"] for entry in asset_misses)
    assert any("纳指 小跌（-1.80%）" in entry["event"] and "中概互联网 小涨（+1.40%）" in entry["event"] for entry in asset_misses)
    assert any("美元指数 小涨（+0.70%）" in entry["event"] and "富时中国50 小涨（+1.00%）" in entry["event"] for entry in asset_misses)
    assert all(entry["observed_rows"] for entry in asset_misses)
    assert all(entry["conflict_check"]["status"] in {"checked_with_primary_news", "no_primary_news_context"} for entry in asset_misses)


def test_build_result_first_reports_splits_news_bucket_into_primary_and_background() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 9,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [
                    {"symbol": "^IXIC", "display_name": "纳指综指", "change_pct": -0.29, "change_pct_text": "-0.29%", "priority": 100},
                    {"symbol": "^GSPC", "display_name": "标普500", "change_pct": -0.05, "change_pct_text": "-0.05%", "priority": 99},
                ],
                "sectors": [
                    {"symbol": "XLK", "display_name": "科技板块", "change_pct": -0.40, "change_pct_text": "-0.40%", "priority": 98},
                    {"symbol": "SOXX", "display_name": "半导体板块", "change_pct": 3.20, "change_pct_text": "+3.20%", "priority": 97},
                ],
                "sentiment": [
                    {"symbol": "^VIX", "display_name": "VIX", "change_pct": 0.61, "change_pct_text": "+0.61%", "priority": 96},
                ],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=31,
                source_name="AP Business",
                source_id="ap_business",
                title="US stocks rally to records, but Brent oil also tops $100 on worries about the Iran war",
                user_brief_cn="美股整体没塌，但油价也在拱。",
                why_it_matters_cn="这条能解释为什么指数没深跌，但并不是全场一起嗨。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["The Nasdaq rose earlier but the close was choppy."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=32,
                source_name="AP Financial Markets",
                source_id="ap_financial_markets",
                title="US stocks hang around their record highs as oil prices swing",
                user_brief_cn="指数还挂在高位，但油价在搅局。",
                why_it_matters_cn="这条能解释为什么收盘看起来不差，但资金明显在挑着打。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["US stocks hovered around records into the close."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=33,
                source_name="AP Financial Markets",
                source_id="ap_financial_markets",
                title="How Wall Street is setting records even with the Iran war still going on",
                user_brief_cn="市场没崩，但估值压力没消失。",
                why_it_matters_cn="这条能解释为什么大盘没深跌，可成长估值还是被挑着砍。",
                coverage_tier="editorial_media",
                topic_tags=["equity_market"],
                evidence_points=["Investors kept weighing rates and fear against earnings."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=34,
                source_name="CNBC Technology",
                source_id="cnbc_technology",
                title="Tesla shares fall after results. But this market speculation may keep the stock afloat for a while",
                user_brief_cn="科技龙头不是一起涨，内部还在分化。",
                why_it_matters_cn="这条能解释为什么纳指没深跌，但科技板块也没走成普涨。",
                coverage_tier="editorial_media",
                topic_tags=["technology_risk"],
                evidence_points=["Tesla shares fell after earnings while chip names held up."],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]

    us_bucket = next(bucket for bucket in desk_report["news_layer"]["buckets"] if bucket["bucket_label"] == "美股指数与板块")
    us_attr = next(bucket for bucket in desk_report["attribution_layer"]["buckets"] if bucket["bucket_label"] == "美股指数与板块")

    assert len(us_bucket["entries"]) == 4
    assert us_bucket["primary_entries"]
    assert us_bucket["background_entries"]
    assert all(entry["news_role"] == "primary" for entry in us_bucket["primary_entries"])
    assert all(entry["news_role"] == "background" for entry in us_bucket["background_entries"])
    assert all(entry.get("background_reason") for entry in us_bucket["background_entries"])
    assert all(isinstance(entry.get("event_cluster_overlap"), dict) for entry in us_bucket["background_entries"])
    assert all("primary_cluster_id" in entry["event_cluster_overlap"] for entry in us_bucket["background_entries"])
    assert us_attr["backgrounds"]
    assert any("背景原因：" in line for line in us_attr["backgrounds"])
    assert "主因：" in desk_report["markdown"]
    assert "背景：" in desk_report["markdown"]


def test_build_result_first_reports_treats_official_macro_release_titles_as_rates_hard_signals() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "free",
        "version": 2,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [
                    {"symbol": "^TNX", "display_name": "美国10年期国债收益率", "change_pct": 0.4, "change_pct_text": "+0.40%", "priority": 100},
                    {"symbol": "DX-Y.NYB", "display_name": "美元指数", "change_pct": 0.2, "change_pct_text": "+0.20%", "priority": 99},
                ],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=21,
                source_name="Census Economic Indicators",
                source_id="census_economic_indicators",
                title="Advance Monthly Sales for Retail and Food Services",
                user_brief_cn="零售销售超预期，利率线不好太松。",
                why_it_matters_cn="这条能解释利率为什么更容易往上顶。",
                topic_tags=[],
                evidence_points=["Retail sales rose 1.7% month over month."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=22,
                source_name="BLS News Releases",
                source_id="bls_news_releases",
                title="Consumer Price Index",
                user_brief_cn="CPI 这类标题本来就该直接进利率桶。",
                why_it_matters_cn="这条能解释通胀和收益率预期。",
                topic_tags=[],
                evidence_points=["Consumer price index remains elevated."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=23,
                source_name="Noise Wire",
                source_id="noise_wire",
                title="Macro desk recap",
                user_brief_cn="宏观线还在。",
                why_it_matters_cn="先别乱塞。",
                coverage_tier="editorial_media",
                topic_tags=["macro_misc"],
                supporting_source_count=0,
            ),
        ],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]
    rates_bucket = next(bucket for bucket in desk_report["news_layer"]["buckets"] if bucket["bucket_label"] == "利率汇率")

    assert any("Retail and Food Services" in entry["event"] for entry in rates_bucket["entries"])
    assert any("Consumer Price Index" in entry["event"] for entry in rates_bucket["entries"])
    assert all("Noise Wire" not in entry["line"] for entry in rates_bucket["entries"])


def test_build_result_first_reports_adds_desk_only_continuation_check_from_existing_watch_fields() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 9,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [
                    {"future_code": "pta", "future_name": "PTA", "watch_score": -1.2},
                    {"future_code": "pp", "future_name": "聚丙烯", "watch_score": 0.6},
                ],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {
                "provider_statuses": {"polymarket": "ready", "kalshi": "error"},
                "providers": {},
            },
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [],
    }

    products = build_result_first_reports(report)
    desk_report = products["desk_report"]
    continuation = desk_report["continuation_check"]

    assert continuation["items"]
    assert any("中国映射期货：" in item for item in continuation["items"])
    assert any("盘后概率信号：" in item for item in continuation["items"])
    assert "## 盘后续线验证" in desk_report["markdown"]
    assert "PTA 小跌（watch -1.20）" in desk_report["markdown"]
    assert "聚丙烯 小涨（watch +0.60）" in desk_report["markdown"]


def test_group_report_keeps_thin_but_direct_bucket_news_when_result_bucket_has_data() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 1,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [
                    {"symbol": "GC=F", "display_name": "黄金", "change_pct": -0.31, "change_pct_text": "-0.31%", "priority": 90},
                    {"symbol": "SI=F", "display_name": "白银", "change_pct": -2.45, "change_pct_text": "-2.45%", "priority": 89},
                ],
                "industrial_metals": [],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=201,
                source_name="Kitco News",
                source_id="kitco_news",
                title="Gold softens as traders wait for central bank decisions",
                user_brief_cn="黄金昨晚偏弱。",
                why_it_matters_cn="这条能对上黄金回落。",
                coverage_tier="editorial_media",
                topic_tags=["gold_market"],
                evidence_points=["Gold closes lower。"],
            ),
            _news_item(
                item_id=202,
                source_name="Kitco News Second",
                source_id="kitco_news_second",
                title="Silver slides as bullion traders trim risk",
                user_brief_cn="白银跌得更猛。",
                why_it_matters_cn="这条能对上白银大跌。",
                coverage_tier="editorial_media",
                topic_tags=["silver_market"],
                evidence_points=["Silver closes sharply lower。"],
            ),
        ],
    }

    products = build_result_first_reports(report)
    group_report = products["group_report"]
    bucket_labels = [bucket["bucket_label"] for bucket in group_report["news_layer"]["buckets"]]

    assert "贵金属" in bucket_labels


def test_build_result_first_reports_uses_industrial_specific_why_for_mining_supply_squeeze() -> None:
    report = {
        "analysis_date": "2026-04-24",
        "access_tier": "premium",
        "version": 12,
        "market_snapshot": {
            "analysis_date": "2026-04-24",
            "market_date": "2026-04-23",
            "asset_board": {
                "indexes": [],
                "rates_fx": [],
                "energy": [],
                "precious_metals": [],
                "industrial_metals": [
                    {"symbol": "HG=F", "display_name": "铜", "change_pct": -0.77, "change_pct_text": "-0.77%", "priority": 90},
                    {"symbol": "ALI=F", "display_name": "铝", "change_pct": 1.28, "change_pct_text": "+1.28%", "priority": 89},
                ],
                "china_proxies": [],
                "china_mapped_futures": [],
            },
        },
        "product_view": {
            "follow_up_panel": {"data_gaps": []},
            "external_signal_panel": {"provider_statuses": {}, "providers": {}},
        },
        "direction_calls": [],
        "stock_calls": [],
        "supporting_items": [],
        "headline_news": [],
        "result_first_materials": [
            _news_item(
                item_id=701,
                source_name="MINING.COM Markets",
                source_id="mining_com_markets",
                title="War squeezes global mining as diesel and acid supplies tighten",
                user_brief_cn="矿山投入品和酸供应在收紧。",
                why_it_matters_cn="这条应该回到铜供应和冶炼端，而不是泛泛地讲贸易。",
                coverage_tier="editorial_media",
                topic_tags=["industrial_metals"],
                evidence_points=["Sulfuric acid and SX-EW processing pressure are starting to hit copper supply."],
                supporting_source_count=1,
            ),
            _news_item(
                item_id=702,
                source_name="USTR Press Releases",
                source_id="ustr_press_releases",
                title="Ambassador Jamieson Greer Announces United States-European Union Action Plan for Critical Minerals Supply Chain Resilience",
                user_brief_cn="关键矿产合作继续加码。",
                why_it_matters_cn="这条能补工业品上游政策线。",
                topic_tags=["industrial_metals"],
                evidence_points=["Critical minerals action plan."],
                supporting_source_count=1,
            ),
        ],
    }

    products = build_result_first_reports(report)
    group_report = products["group_report"]
    industrial_bucket = next(bucket for bucket in group_report["news_layer"]["buckets"] if bucket["bucket_label"] == "工业品")
    mining_entry = next(entry for entry in industrial_bucket["entries"] if "MINING.COM Markets" in entry["line"])

    assert "铜供应" in mining_entry["why"] or "冶炼" in mining_entry["why"] or "酸" in mining_entry["why"]
