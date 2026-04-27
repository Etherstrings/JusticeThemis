# -*- coding: utf-8 -*-
"""Cross-asset Market Board formatting and China futures watch mapping."""

from __future__ import annotations

from typing import Any


class AssetBoardService:
    FUTURE_MAP: tuple[dict[str, object], ...] = (
        {
            "future_code": "methanol",
            "future_name": "甲醇",
            "driver_symbols": ("CL=F", "BZ=F", "NG=F"),
        },
        {
            "future_code": "ethylene_glycol",
            "future_name": "乙二醇",
            "driver_symbols": ("CL=F", "BZ=F", "NG=F"),
        },
        {
            "future_code": "px",
            "future_name": "PX",
            "driver_symbols": ("CL=F", "BZ=F", "NG=F"),
        },
        {
            "future_code": "pta",
            "future_name": "PTA",
            "driver_symbols": ("CL=F", "BZ=F", "NG=F"),
        },
        {
            "future_code": "soda_ash",
            "future_name": "纯碱",
            "driver_symbols": ("NG=F", "CL=F", "BZ=F"),
        },
        {
            "future_code": "glass",
            "future_name": "玻璃",
            "driver_symbols": ("NG=F", "CL=F", "BZ=F"),
        },
        {
            "future_code": "lithium_carbonate",
            "future_name": "碳酸锂",
            "driver_symbols": ("SOXX", "XLK", "HG=F"),
        },
        {
            "future_code": "industrial_silicon",
            "future_name": "工业硅",
            "driver_symbols": ("SOXX", "XLK", "HG=F"),
        },
    )

    def build(
        self,
        *,
        analysis_date: str,
        market_date: str,
        indexes: list[dict[str, Any]],
        sectors: list[dict[str, Any]],
        sentiment: list[dict[str, Any]],
        rates_fx: list[dict[str, Any]],
        precious_metals: list[dict[str, Any]],
        energy: list[dict[str, Any]],
        industrial_metals: list[dict[str, Any]],
        shipping: list[dict[str, Any]] | None = None,
        global_equities: list[dict[str, Any]] | None = None,
        crypto: list[dict[str, Any]] | None = None,
        credit: list[dict[str, Any]] | None = None,
        duration: list[dict[str, Any]] | None = None,
        china_proxies: list[dict[str, Any]] | None = None,
        risk_signals: dict[str, Any],
    ) -> dict[str, Any]:
        china_proxies = list(china_proxies or [])
        shipping = list(shipping or [])
        global_equities = list(global_equities or [])
        crypto = list(crypto or [])
        credit = list(credit or [])
        duration = list(duration or [])
        tracked_groups = [
            indexes,
            sectors,
            rates_fx,
            precious_metals,
            energy,
            industrial_metals,
            shipping,
            global_equities,
            crypto,
            credit,
            duration,
        ]
        tracked_items = [item for group in tracked_groups for item in group]
        symbol_map = {str(item.get("symbol")): item for item in tracked_items if str(item.get("symbol")).strip()}

        return {
            "analysis_date": analysis_date,
            "market_date": market_date,
            "headline": self._build_headline(symbol_map=symbol_map, risk_signals=risk_signals),
            "indexes": indexes,
            "sectors": sectors,
            "sentiment": sentiment,
            "rates_fx": rates_fx,
            "precious_metals": precious_metals,
            "energy": energy,
            "industrial_metals": industrial_metals,
            "shipping": shipping,
            "global_equities": global_equities,
            "crypto": crypto,
            "credit": credit,
            "duration": duration,
            "china_proxies": china_proxies,
            "china_mapped_futures": self._build_china_mapped_futures(symbol_map=symbol_map),
            "key_moves": {
                "strongest_move": self._pick_extreme(tracked_items, reverse=True),
                "weakest_move": self._pick_extreme(tracked_items, reverse=False),
            },
            "risk_signals": risk_signals,
        }

    def _build_headline(
        self,
        *,
        symbol_map: dict[str, dict[str, Any]],
        risk_signals: dict[str, Any],
    ) -> str:
        headline_symbols = ("^IXIC", "^GSPC", "^TNX", "CL=F", "GC=F")
        parts = [
            f"{item['display_name']} {self._format_change_pct(item.get('change_pct'))}"
            for symbol in headline_symbols
            if (item := symbol_map.get(symbol)) is not None
        ]
        risk_mode = str(risk_signals.get("risk_mode", "")).strip()
        if risk_mode:
            parts.append(f"风险状态 {risk_mode}")
        return "；".join(parts) + "。" if parts else "暂无可用的跨资产市场板。"

    def _build_china_mapped_futures(
        self,
        *,
        symbol_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for definition in self.FUTURE_MAP:
            driver_symbols = [symbol for symbol in definition["driver_symbols"] if symbol in symbol_map]
            driver_items = [symbol_map[symbol] for symbol in driver_symbols]
            score = self._average_change_pct(driver_items)
            rows.append(
                {
                    "future_code": definition["future_code"],
                    "future_name": definition["future_name"],
                    "watch_direction": self._watch_direction(score),
                    "watch_score": round(score, 4),
                    "driver_symbols": driver_symbols,
                    "driver_display_names": [str(item.get("display_name", item.get("symbol", ""))) for item in driver_items],
                    "driver_summary": self._driver_summary(driver_items),
                }
            )
        return rows

    def _driver_summary(self, driver_items: list[dict[str, Any]]) -> str:
        if not driver_items:
            return "缺少足够的跨资产驱动数据。"
        parts = [
            f"{item['display_name']} {self._format_change_pct(item.get('change_pct'))}"
            for item in driver_items
        ]
        return "；".join(parts) + "。"

    def _average_change_pct(self, items: list[dict[str, Any]]) -> float:
        scores = [
            numeric
            for item in items
            if (numeric := _to_float(item.get("change_pct"))) is not None
        ]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _watch_direction(self, score: float) -> str:
        if score >= 0.35:
            return "up"
        if score <= -0.35:
            return "down"
        return "mixed"

    def _pick_extreme(self, items: list[dict[str, Any]], *, reverse: bool) -> dict[str, Any] | None:
        if not items:
            return None
        ranked_items = [
            item
            for item in items
            if _to_float(item.get("change_pct")) is not None
        ]
        if not ranked_items:
            return None

        best_value = max(_to_float(item.get("change_pct")) or 0.0 for item in ranked_items)
        if not reverse:
            best_value = min(_to_float(item.get("change_pct")) or 0.0 for item in ranked_items)

        tied_items = [
            item
            for item in ranked_items
            if abs((_to_float(item.get("change_pct")) or 0.0) - best_value) <= 0.25
        ]
        return sorted(
            tied_items,
            key=lambda item: int(item.get("priority", 0) or 0),
            reverse=True,
        )[0]

    def _format_change_pct(self, value: object) -> str:
        numeric = _to_float(value)
        if numeric is None:
            return "持平"
        return f"{numeric:+.2f}%"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
