# -*- coding: utf-8 -*-
"""Result-first overnight mainline ranking."""

from __future__ import annotations

from typing import Any


class MainlineEngine:
    TOPIC_TO_BUCKET = {
        "semiconductor_supply_chain": "tech_semiconductor",
        "energy_shipping": "geopolitics_energy",
        "rates_macro": "rates_liquidity",
        "trade_policy": "trade_export_control",
    }
    REGIME_TO_BUCKET = {
        "technology_risk_on": "tech_semiconductor",
        "energy_inflation_impulse": "geopolitics_energy",
        "rates_pressure": "rates_liquidity",
        "usd_strengthening": "rates_liquidity",
    }
    BUCKET_TO_REGIME_KEYS = {
        "tech_semiconductor": ("technology_risk_on",),
        "geopolitics_energy": ("energy_inflation_impulse",),
        "rates_liquidity": ("rates_pressure", "usd_strengthening"),
    }

    BUCKET_ASSET_SYMBOLS = {
        "tech_semiconductor": ("SOXX", "XLK", "^IXIC"),
        "geopolitics_energy": ("CL=F", "BZ=F", "NG=F", "XLE"),
        "rates_liquidity": ("^TNX", "DX-Y.NYB", "CNH=X"),
        "trade_export_control": ("XLI",),
    }

    def build(
        self,
        *,
        market_board: dict[str, Any],
        events: list[dict[str, Any]],
        max_mainlines: int = 12,
    ) -> list[dict[str, Any]]:
        bucket_events: dict[str, list[dict[str, Any]]] = {}
        symbol_map = self._market_symbol_map(market_board)

        for event in events:
            bucket = self._resolve_bucket(event)
            if not bucket:
                continue
            linkage = self._asset_linkage_score(bucket=bucket, symbol_map=symbol_map)
            if linkage["score"] <= 0:
                continue
            bucket_events.setdefault(bucket, []).append(
                {
                    "event": event,
                    "linkage": linkage,
                    "priority_score": self._event_priority_score(event),
                }
            )

        mainlines: list[dict[str, Any]] = []
        for bucket, entries in bucket_events.items():
            ordered_entries = sorted(
                entries,
                key=lambda entry: (
                    entry["priority_score"],
                    entry["linkage"]["score"],
                    str(entry["event"].get("event_id", "")),
                ),
                reverse=True,
            )
            primary_event = dict(ordered_entries[0]["event"])
            direction_score = self._bucket_direction_score(bucket=bucket, symbol_map=symbol_map)
            mainlines.append(
                {
                    "mainline_id": f"{bucket}__{str(market_board.get('analysis_date', '')).strip() or 'undated'}",
                    "headline": self._headline(bucket=bucket, direction_score=direction_score),
                    "mainline_bucket": bucket,
                    "primary_event_id": str(primary_event.get("event_id", "")).strip(),
                    "linked_event_ids": [
                        str(entry["event"].get("event_id", "")).strip()
                        for entry in ordered_entries
                    ],
                    "affected_assets": list(ordered_entries[0]["linkage"]["linked_assets"]),
                    "market_effect": self._market_effect(bucket=bucket, direction_score=direction_score),
                    "confidence": self._confidence(primary_event),
                    "official_source_count": max(
                        int(entry["event"].get("official_source_count", 0) or 0)
                        for entry in ordered_entries
                    ),
                    "_score": max((entry["linkage"]["score"] * 3.0) + entry["priority_score"] for entry in ordered_entries),
                }
            )

        ranked = sorted(
            mainlines,
            key=lambda item: (
                float(item.get("_score", 0.0) or 0.0),
                str(item.get("mainline_bucket", "")),
            ),
            reverse=True,
        )[: max(1, int(max_mainlines))]

        for index, item in enumerate(ranked, start=1):
            item["importance_rank"] = index
            item.pop("_score", None)
        return ranked

    def build_result(
        self,
        *,
        market_board: dict[str, Any],
        market_regimes: list[dict[str, Any]],
        market_regime_evaluations: list[dict[str, Any]],
        event_groups: list[dict[str, Any]],
        max_mainlines: int = 12,
    ) -> dict[str, Any]:
        symbol_map = self._market_symbol_map(market_board)
        ordered_regimes = sorted(
            [
                dict(regime)
                for regime in list(market_regimes or [])
                if bool(regime.get("triggered", True))
            ],
            key=lambda item: (
                float(item.get("strength", 0.0) or 0.0),
                str(item.get("regime_key", "")),
            ),
            reverse=True,
        )
        event_groups = [dict(group) for group in list(event_groups or [])]
        evaluations_by_key = {
            str(item.get("regime_key", "")).strip(): dict(item)
            for item in list(market_regime_evaluations or [])
            if str(item.get("regime_key", "")).strip()
        }

        best_regime_by_bucket: dict[str, dict[str, Any]] = {}
        for regime in ordered_regimes:
            bucket = self.REGIME_TO_BUCKET.get(str(regime.get("regime_key", "")).strip(), "")
            if not bucket or bucket in best_regime_by_bucket:
                continue
            best_regime_by_bucket[bucket] = regime

        used_event_group_ids: set[str] = set()
        mainlines: list[dict[str, Any]] = []
        for bucket, regime in best_regime_by_bucket.items():
            linked_groups = [
                group
                for group in event_groups
                if self._resolve_event_group_bucket(group) == bucket
            ]
            linked_groups.sort(key=self._event_group_priority_score, reverse=True)
            used_event_group_ids.update(
                str(group.get("cluster_id", "")).strip()
                for group in linked_groups
                if str(group.get("cluster_id", "")).strip()
            )
            direction_score = self._bucket_direction_score(bucket=bucket, symbol_map=symbol_map)
            primary_group = linked_groups[0] if linked_groups else {}
            mainlines.append(
                {
                    "mainline_id": f"{bucket}__{str(market_board.get('analysis_date', '')).strip() or 'undated'}",
                    "headline": self._headline(bucket=bucket, direction_score=direction_score),
                    "mainline_bucket": bucket,
                    "primary_event_id": str(primary_group.get("cluster_id", "")).strip(),
                    "linked_event_ids": [
                        str(group.get("cluster_id", "")).strip()
                        for group in linked_groups
                        if str(group.get("cluster_id", "")).strip()
                    ],
                    "supporting_event_group_ids": [
                        str(group.get("cluster_id", "")).strip()
                        for group in linked_groups
                        if str(group.get("cluster_id", "")).strip()
                    ],
                    "regime_ids": [
                        str(regime.get("regime_id", "")).strip()
                        for _item in [regime]
                        if str(regime.get("regime_id", "")).strip()
                    ],
                    "affected_assets": self._asset_linkage_score(bucket=bucket, symbol_map=symbol_map)["linked_assets"],
                    "market_effect": self._market_effect(bucket=bucket, direction_score=direction_score),
                    "narrative_status": "confirmed",
                    "confidence": self._mainline_confidence(regime=regime, linked_groups=linked_groups),
                    "official_source_count": max(
                        [int(group.get("official_source_count", 0) or 0) for group in linked_groups] or [0]
                    ),
                    "_score": float(regime.get("strength", 0.0) or 0.0) * 10.0 + float(len(linked_groups)),
                }
            )

        ranked = sorted(
            mainlines,
            key=lambda item: (
                float(item.get("_score", 0.0) or 0.0),
                str(item.get("mainline_bucket", "")),
            ),
            reverse=True,
        )[: max(1, int(max_mainlines))]
        for index, item in enumerate(ranked, start=1):
            item["importance_rank"] = index
            item.pop("_score", None)

        secondary_event_groups = [
            {
                "cluster_id": str(group.get("cluster_id", "")).strip(),
                "headline": str(group.get("headline", "")).strip(),
                "primary_source_name": str(group.get("primary_source_name", "")).strip(),
                "topic_tags": list(group.get("topic_tags", []) or []),
                "official_source_count": int(group.get("official_source_count", 0) or 0),
                "source_count": int(group.get("source_count", 0) or 0),
                "item_ids": list(group.get("item_ids", []) or []),
                "mainline_bucket_hint": self._resolve_event_group_bucket(group),
                "downgrade_reason": self._secondary_reason(
                    group=group,
                    evaluations_by_key=evaluations_by_key,
                ),
            }
            for group in event_groups
            if str(group.get("cluster_id", "")).strip()
            and str(group.get("cluster_id", "")).strip() not in used_event_group_ids
        ]
        secondary_event_groups.sort(
            key=lambda group: (
                int(group.get("official_source_count", 0) or 0),
                int(group.get("source_count", 0) or 0),
                str(group.get("cluster_id", "")),
            ),
            reverse=True,
        )

        return {
            "mainlines": ranked,
            "secondary_event_groups": secondary_event_groups,
        }

    def _resolve_bucket(self, event: dict[str, Any]) -> str:
        for topic in list(event.get("topic_tags", []) or []):
            bucket = self.TOPIC_TO_BUCKET.get(str(topic).strip())
            if bucket:
                return bucket
        return ""

    def _resolve_event_group_bucket(self, group: dict[str, Any]) -> str:
        return self._resolve_bucket(group)

    def _event_priority_score(self, event: dict[str, Any]) -> float:
        status = str(event.get("event_status", "") or event.get("cluster_status", "")).strip()
        status_bonus = {
            "confirmed": 3.0,
            "conflicted": 1.5,
            "single_source": 1.0,
        }.get(status, 0.5)
        return (
            float(int(event.get("official_source_count", 0) or 0) * 2)
            + float(int(event.get("source_count", 0) or 0) * 0.5)
            + status_bonus
        )

    def _market_symbol_map(self, market_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
        groups = (
            "indexes",
            "sectors",
            "rates_fx",
            "precious_metals",
            "energy",
            "industrial_metals",
        )
        rows = [
            row
            for group in groups
            for row in list(market_board.get(group, []) or [])
            if isinstance(row, dict)
        ]
        return {
            str(row.get("symbol", "")).strip(): row
            for row in rows
            if str(row.get("symbol", "")).strip()
        }

    def _asset_linkage_score(
        self,
        *,
        bucket: str,
        symbol_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        symbols = self.BUCKET_ASSET_SYMBOLS.get(bucket, ())
        linked_rows = [symbol_map[symbol] for symbol in symbols if symbol in symbol_map]
        return {
            "score": max(
                (
                    abs(float(row.get("change_pct", 0.0) or 0.0))
                    for row in linked_rows
                ),
                default=0.0,
            ),
            "linked_assets": [str(row.get("symbol", "")).strip() for row in linked_rows],
        }

    def _event_group_priority_score(self, group: dict[str, Any]) -> float:
        return (
            float(int(group.get("official_source_count", 0) or 0) * 3)
            + float(int(group.get("source_count", 0) or 0))
        )

    def _bucket_direction_score(
        self,
        *,
        bucket: str,
        symbol_map: dict[str, dict[str, Any]],
    ) -> float:
        symbols = self.BUCKET_ASSET_SYMBOLS.get(bucket, ())
        values = [
            float(symbol_map[symbol].get("change_pct", 0.0) or 0.0)
            for symbol in symbols
            if symbol in symbol_map
        ]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _headline(self, *, bucket: str, direction_score: float) -> str:
        if bucket == "tech_semiconductor":
            return "科技/半导体主线走强" if direction_score >= 0 else "科技/半导体主线承压"
        if bucket == "geopolitics_energy":
            return "油气与运输风险缓和" if direction_score < 0 else "油气与运输风险升温"
        if bucket == "rates_liquidity":
            return "利率流动性压力缓和" if direction_score < 0 else "利率流动性压力抬升"
        if bucket == "trade_export_control":
            return "贸易与出口管制主线升温"
        return bucket

    def _market_effect(self, *, bucket: str, direction_score: float) -> str:
        if bucket == "tech_semiconductor":
            return "科技偏多" if direction_score >= 0 else "科技承压"
        if bucket == "geopolitics_energy":
            return "能源压力缓和" if direction_score < 0 else "能源再通胀压力升温"
        if bucket == "rates_liquidity":
            return "利率压力缓和" if direction_score < 0 else "利率压力抬升"
        if bucket == "trade_export_control":
            return "贸易链波动加大"
        return "待判断"

    def _confidence(self, event: dict[str, Any]) -> str:
        official_count = int(event.get("official_source_count", 0) or 0)
        status = str(event.get("event_status", "") or event.get("cluster_status", "")).strip()
        if official_count >= 1 and status == "confirmed":
            return "high"
        if official_count >= 1 or status in {"confirmed", "conflicted"}:
            return "medium"
        return "low"

    def _mainline_confidence(
        self,
        *,
        regime: dict[str, Any],
        linked_groups: list[dict[str, Any]],
    ) -> str:
        regime_confidence = str(regime.get("confidence", "")).strip()
        if regime_confidence == "high" and any(int(group.get("official_source_count", 0) or 0) > 0 for group in linked_groups):
            return "high"
        if regime_confidence in {"high", "medium"}:
            return "medium"
        return "low"

    def _secondary_reason(
        self,
        *,
        group: dict[str, Any],
        evaluations_by_key: dict[str, dict[str, Any]],
    ) -> str:
        bucket = self._resolve_event_group_bucket(group)
        candidate_regime_keys = self.BUCKET_TO_REGIME_KEYS.get(bucket, ())
        if not candidate_regime_keys:
            return "no_regime_match"
        for regime_key in candidate_regime_keys:
            evaluation = evaluations_by_key.get(regime_key)
            if evaluation is None:
                continue
            suppressed_by = [str(item).strip() for item in list(evaluation.get("suppressed_by", []) or []) if str(item).strip()]
            for reason in (
                "missing_required_observations",
                "stale_market_inputs",
                "insufficient_market_strength",
                "competing_regime_dominates",
                "conflicting_observations",
            ):
                if reason in suppressed_by:
                    return reason
        return "no_regime_match"
