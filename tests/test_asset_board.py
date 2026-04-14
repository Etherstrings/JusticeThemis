# -*- coding: utf-8 -*-
"""Tests for cross-asset Market Board formatting."""

from __future__ import annotations

from app.services.asset_board import AssetBoardService


def _row(
    *,
    symbol: str,
    display_name: str,
    bucket: str,
    change_pct: float,
    priority: int,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "display_name": display_name,
        "bucket": bucket,
        "priority": priority,
        "change_pct": change_pct,
        "change_pct_text": f"{change_pct:+.2f}%",
        "change_direction": "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
    }


def test_asset_board_service_builds_cross_asset_watchlists() -> None:
    service = AssetBoardService()

    board = service.build(
        analysis_date="2026-04-07",
        market_date="2026-04-06",
        indexes=[
            _row(symbol="^GSPC", display_name="标普500", bucket="index", change_pct=2.0, priority=100),
            _row(symbol="^IXIC", display_name="纳指综指", bucket="index", change_pct=3.0, priority=99),
        ],
        sectors=[
            _row(symbol="XLK", display_name="科技板块", bucket="sector", change_pct=5.0, priority=95),
            _row(symbol="SOXX", display_name="半导体板块", bucket="sector", change_pct=6.0, priority=94),
            _row(symbol="XLE", display_name="能源板块", bucket="sector", change_pct=-3.0, priority=90),
        ],
        sentiment=[
            _row(symbol="^VIX", display_name="VIX", bucket="sentiment", change_pct=-12.0, priority=98),
        ],
        rates_fx=[
            _row(symbol="^TNX", display_name="美国10年期国债收益率", bucket="rates_fx", change_pct=-4.5, priority=88),
            _row(symbol="DX-Y.NYB", display_name="美元指数", bucket="rates_fx", change_pct=-0.7, priority=87),
        ],
        precious_metals=[
            _row(symbol="GC=F", display_name="黄金", bucket="precious_metals", change_pct=1.2, priority=85),
            _row(symbol="SI=F", display_name="白银", bucket="precious_metals", change_pct=1.0, priority=84),
        ],
        energy=[
            _row(symbol="CL=F", display_name="WTI原油", bucket="energy", change_pct=-4.9, priority=83),
            _row(symbol="BZ=F", display_name="布伦特原油", bucket="energy", change_pct=-4.1, priority=82),
            _row(symbol="NG=F", display_name="天然气", bucket="energy", change_pct=-2.0, priority=81),
        ],
        industrial_metals=[
            _row(symbol="HG=F", display_name="铜", bucket="industrial_metals", change_pct=1.5, priority=80),
            _row(symbol="ALI=F", display_name="铝", bucket="industrial_metals", change_pct=0.8, priority=79),
        ],
        risk_signals={
            "risk_mode": "risk_on",
        },
    )

    assert board["headline"].startswith("纳指综指 +3.00%")
    assert board["key_moves"]["strongest_move"]["symbol"] == "SOXX"
    assert board["key_moves"]["weakest_move"]["symbol"] == "CL=F"

    futures_by_code = {
        item["future_code"]: item
        for item in board["china_mapped_futures"]
    }
    assert futures_by_code["methanol"]["watch_direction"] == "down"
    assert futures_by_code["ethylene_glycol"]["watch_direction"] == "down"
    assert futures_by_code["px"]["watch_direction"] == "down"
    assert futures_by_code["pta"]["watch_direction"] == "down"
    assert futures_by_code["soda_ash"]["watch_direction"] == "down"
    assert futures_by_code["glass"]["watch_direction"] == "down"
    assert futures_by_code["lithium_carbonate"]["watch_direction"] == "up"
    assert futures_by_code["industrial_silicon"]["watch_direction"] == "up"
    assert futures_by_code["px"]["driver_symbols"] == ["CL=F", "BZ=F", "NG=F"]
    assert futures_by_code["industrial_silicon"]["driver_symbols"] == ["SOXX", "XLK", "HG=F"]
