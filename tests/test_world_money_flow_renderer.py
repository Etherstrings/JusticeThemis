# -*- coding: utf-8 -*-

from __future__ import annotations

from PIL import Image, ImageStat

from app.services.world_money_flow_renderer import render_world_money_flow_png


def test_render_world_money_flow_png(tmp_path):
    payload = {
        "meta": {"source_count": 3},
        "image_blocks": {
            "title_block": {
                "title": "昨天世界钱往哪里",
                "date": "2026-04-25",
                "conclusion": "昨夜，风险资产偏强。",
                "summary": "新闻看：AI和中东线都在动；价格看：纳指上涨，原油回落。",
            },
            "news_block": {
                "items": [
                    {
                        "title": "英伟达收盘创新高，市值站上5万亿美元",
                        "summary": "AI龙头继续吸金。",
                        "source": "CNBC Technology",
                    },
                    {
                        "title": "霍尔木兹海峡排雷升级，全球油运继续受扰",
                        "summary": "油价、运价和避险资产继续反复。",
                        "source": "AP World",
                    },
                ]
            },
            "data_block": {
                "groups": [
                    {"label": "股市和板块", "items": [{"title": "纳指综指 +1.63%"}, {"title": "半导体板块 +4.67%"}]},
                    {"label": "利率和汇率", "items": [{"title": "美国10年期国债收益率 -0.69%"}]},
                    {"label": "商品、航运、信用", "items": [{"title": "WTI原油 -1.72%"}, {"title": "黄金 +0.51%"}]},
                    {"label": "全球和加密", "items": [{"title": "比特币 -1.10%"}]},
                ]
            },
            "mapping_block": {
                "items": [
                    {"title": "AI和芯片新闻", "summary": "先看半导体、科技板块和纳指。"},
                    {"title": "中东和航道新闻", "summary": "先看原油、黄金、航运和VIX。"},
                ]
            },
        },
    }

    output = tmp_path / "poster.png"
    render_world_money_flow_png(payload, output)

    image = Image.open(output)
    assert image.size[0] == 1242
    assert image.size[1] >= 2208
    stat = ImageStat.Stat(image.convert("L"))
    assert stat.stddev[0] > 5
