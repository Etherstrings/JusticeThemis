# -*- coding: utf-8 -*-
"""Provider abstraction and default rule-based daily analysis generation."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any, Protocol


class DailyAnalysisProvider(Protocol):
    name: str
    model: str | None

    def generate_report(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        items: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None = None,
        mainlines: list[dict[str, Any]] | None = None,
        mainline_coverage: dict[str, Any] | None = None,
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a fixed daily analysis report."""


class RuleBasedDailyAnalysisProvider:
    name = "rule_based"
    model = None

    STATUS_SCORES = {
        "ready": 6,
        "review": 3,
        "background": 1,
    }
    COVERAGE_SCORES = {
        "official_policy": 4,
        "official_data": 3,
        "editorial_media": 1,
    }
    RELEVANCE_SCORES = {
        "high": 4,
        "medium": 2,
        "low": 0,
    }
    CONFIDENCE_SCORES = {
        "high": 2,
        "medium": 1,
        "low": 0,
    }
    STOCK_DIRECTION_MAP: dict[str, tuple[dict[str, str], ...]] = {
        "银行/保险": (
            {"ticker": "601398.SH", "name": "工商银行"},
            {"ticker": "601318.SH", "name": "中国平安"},
        ),
        "高股息防御": (
            {"ticker": "600900.SH", "name": "长江电力"},
            {"ticker": "601088.SH", "name": "中国神华"},
        ),
        "油气开采": (
            {"ticker": "600938.SH", "name": "中国海油"},
            {"ticker": "601857.SH", "name": "中国石油"},
        ),
        "油服": (
            {"ticker": "600583.SH", "name": "海油工程"},
            {"ticker": "600871.SH", "name": "石化油服"},
        ),
        "航运港口景气跟踪": (
            {"ticker": "601919.SH", "name": "中远海控"},
            {"ticker": "600018.SH", "name": "上港集团"},
        ),
        "自主可控半导体链": (
            {"ticker": "688981.SH", "name": "中芯国际"},
            {"ticker": "603986.SH", "name": "兆易创新"},
        ),
        "航空与燃油敏感运输链": (
            {"ticker": "601111.SH", "name": "中国国航"},
            {"ticker": "600029.SH", "name": "南方航空"},
        ),
    }
    DIRECTION_FAMILY_MAP: dict[str, str] = {
        "油服": "energy_upstream_positive",
        "油气开采": "energy_upstream_positive",
        "原油/燃料油": "energy_cost_inflation",
        "天然气/LNG": "energy_cost_inflation",
        "化工下游成本敏感链": "fuel_cost_sensitive_negative",
        "航空与燃油敏感运输链": "fuel_cost_sensitive_negative",
    }
    CONFIDENCE_ORDER = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }
    _AUDIT_STYLE_PATTERN = re.compile(
        r"\b(?:item_id=|authority=|capture=|cross_source=|conflict_count=|a_share=|watch=|facts=)\b",
        re.IGNORECASE,
    )

    def generate_report(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        items: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None = None,
        mainlines: list[dict[str, Any]] | None = None,
        mainline_coverage: dict[str, Any] | None = None,
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scored_items = [self._score_item(item) for item in items]
        scored_items.sort(key=lambda item: item["signal_score"], reverse=True)
        market_snapshot = dict(market_snapshot or {})
        mainlines = list(mainlines or [])
        market_regimes = list(market_snapshot.get("market_regimes", []) or [])
        market_context = dict(market_context or self._build_market_context(market_snapshot))
        mainline_coverage = dict(
            mainline_coverage or self._default_mainline_coverage(mainlines=mainlines, market_regimes=market_regimes, market_context=market_context)
        )
        direction_calls = self._compress_direction_calls(
            self._build_direction_calls(
                scored_items,
                mainlines=mainlines,
                market_regimes=market_regimes,
            )
        )
        stock_calls = self._build_stock_calls(direction_calls) if access_tier == "premium" else []
        risk_watchpoints = self._collect_watchpoints(
            scored_items,
            market_context=market_context,
            mainline_coverage=mainline_coverage,
        )
        supporting_items = self._build_supporting_items(scored_items)
        headline_news = self._build_headline_news(scored_items)
        market_move_brief = self._build_market_move_brief(
            market_snapshot=market_snapshot or None,
            market_context=market_context,
        )
        event_drivers = self._build_event_drivers(headline_news)
        editorial_chain_cn = self._build_editorial_chain_cn(
            market_move_brief=market_move_brief,
            event_drivers=event_drivers,
            direction_calls=direction_calls,
            market_context=market_context,
        )
        narratives = self._build_narratives(
            analysis_date=analysis_date,
            access_tier=access_tier,
            scored_items=scored_items,
            direction_calls=direction_calls,
            risk_watchpoints=risk_watchpoints,
            market_snapshot=market_snapshot or None,
            mainlines=mainlines,
            market_regimes=market_regimes,
            mainline_coverage=mainline_coverage,
            market_context=market_context,
        )

        return {
            "summary": self._build_summary(
                analysis_date=analysis_date,
                scored_items=scored_items,
                direction_calls=direction_calls,
                market_snapshot=market_snapshot or None,
                mainlines=mainlines,
                market_regimes=market_regimes,
                mainline_coverage=mainline_coverage,
                market_context=market_context,
            ),
            "narratives": narratives,
            "scoring_method": {
                "item_signal_formula": (
                    "signal_score = analysis_status + coverage_tier + a_share_relevance + "
                    "analysis_confidence + priority_bonus + source_capture_confidence_bonus + "
                    "cross_source_confirmation_bonus + timeliness_bonus - blocker_penalty - "
                    "fact_conflict_penalty - staleness_penalty"
                ),
                "direction_aggregation": (
                    "Direction scores sum the strongest contributing item per event cluster, "
                    "while preserving all supporting evidence item ids."
                ),
            },
            "input_snapshot": {
                "item_count": len(scored_items),
                "event_cluster_count": len(
                    {
                        self._event_cluster_id(item["item"])
                        for item in scored_items
                    }
                ),
                "mainline_count": len(mainlines),
                "market_regime_count": len(market_regimes),
                "official_count": sum(
                    1 for item in scored_items if item["item"].get("coverage_tier") in {"official_policy", "official_data"}
                ),
                "editorial_count": sum(1 for item in scored_items if item["item"].get("coverage_tier") == "editorial_media"),
                "market_snapshot_available": bool(market_snapshot),
                "analysis_status_counts": dict(
                    Counter(str(item["item"].get("analysis_status", "")).strip() for item in scored_items)
                ),
            },
            "market_snapshot": market_snapshot,
            "market_context": market_context,
            "mainlines": mainlines,
            "mainline_coverage": mainline_coverage,
            "direction_calls": direction_calls,
            "stock_calls": stock_calls,
            "risk_watchpoints": risk_watchpoints,
            "supporting_items": supporting_items,
            "headline_news": headline_news,
            "market_move_brief": market_move_brief,
            "event_drivers": event_drivers,
            "editorial_chain_cn": editorial_chain_cn,
        }

    def _score_item(self, item: dict[str, Any]) -> dict[str, Any]:
        analysis_status = str(item.get("analysis_status", "")).strip()
        coverage_tier = str(item.get("coverage_tier", "")).strip()
        relevance = str(item.get("a_share_relevance", "")).strip()
        analysis_confidence = str(item.get("analysis_confidence", "")).strip()
        blockers = list(item.get("analysis_blockers", []) or [])
        priority_bonus = min(4, max(0, int(item.get("priority", 0) or 0) // 25))
        blocker_penalty = min(3, len(blockers))
        source_capture_confidence_bonus = self._source_capture_confidence_bonus(item)
        cross_source_confirmation_bonus = self._cross_source_confirmation_bonus(item)
        fact_conflict_penalty = self._fact_conflict_penalty(item)
        timeliness_bonus = self._timeliness_bonus(item)
        staleness_penalty = self._staleness_penalty(item)
        score_breakdown = {
            "analysis_status_score": self.STATUS_SCORES.get(analysis_status, 0),
            "coverage_tier_score": self.COVERAGE_SCORES.get(coverage_tier, 0),
            "a_share_relevance_score": self.RELEVANCE_SCORES.get(relevance, 0),
            "analysis_confidence_score": self.CONFIDENCE_SCORES.get(analysis_confidence, 0),
            "priority_bonus": priority_bonus,
            "source_capture_confidence_bonus": source_capture_confidence_bonus,
            "cross_source_confirmation_bonus": cross_source_confirmation_bonus,
            "timeliness_bonus": timeliness_bonus,
            "blocker_penalty": blocker_penalty,
            "fact_conflict_penalty": fact_conflict_penalty,
            "staleness_penalty": staleness_penalty,
        }
        signal_score = max(
            1,
            score_breakdown["analysis_status_score"]
            + score_breakdown["coverage_tier_score"]
            + score_breakdown["a_share_relevance_score"]
            + score_breakdown["analysis_confidence_score"]
            + priority_bonus
            + source_capture_confidence_bonus
            + cross_source_confirmation_bonus
            + timeliness_bonus
            - blocker_penalty
            - fact_conflict_penalty
            - staleness_penalty,
        )
        score_breakdown["final_score"] = signal_score
        return {
            "item": item,
            "signal_score": signal_score,
            "score_breakdown": score_breakdown,
        }

    def _build_direction_calls(
        self,
        scored_items: list[dict[str, Any]],
        *,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        aggregates: dict[tuple[str, str], dict[str, Any]] = {}
        mainline_ids_by_cluster = self._mainline_ids_by_cluster(mainlines)
        mainline_regime_ids_by_cluster = self._mainline_regime_ids_by_cluster(mainlines)
        for scored_item in scored_items:
            item = scored_item["item"]
            signal_score = int(scored_item["signal_score"])
            source_bucket = "official" if item.get("coverage_tier") in {"official_policy", "official_data"} else "editorial"
            cluster_id = self._event_cluster_id(item)
            for signal_type, directions, stance in (
                ("beneficiary", list(item.get("beneficiary_directions", []) or []), "positive"),
                ("pressured", list(item.get("pressured_directions", []) or []), "negative"),
                ("price_up", list(item.get("price_up_signals", []) or []), "inflationary"),
            ):
                for direction in directions:
                    key = (signal_type, str(direction))
                    if key not in aggregates:
                        aggregates[key] = self._empty_direction_aggregate(
                            signal_type=signal_type,
                            direction=str(direction),
                            stance=stance,
                        )
                    aggregate = aggregates[key]
                    item_id = int(item.get("item_id", 0) or 0)
                    source_id = str(item.get("source_id", "")).strip()
                    aggregate["cluster_scores"][cluster_id] = max(
                        int(aggregate["cluster_scores"].get(cluster_id, 0) or 0),
                        signal_score,
                    )
                    aggregate["evidence_item_ids"].append(item_id)
                    aggregate["source_ids"].append(source_id)
                    aggregate["source_mix_sets"][source_bucket].add(source_id or f"item_{item_id}")
                    aggregate["top_titles"].append(str(item.get("title", "")).strip())
                    aggregate["evidence_points"].extend(list(item.get("evidence_points", []) or []))
                    aggregate["follow_up_checks"].extend(list(item.get("follow_up_checks", []) or []))
                    aggregate["evidence_mainline_ids"].extend(mainline_ids_by_cluster.get(cluster_id, []))
                    aggregate["evidence_regime_ids"].extend(mainline_regime_ids_by_cluster.get(cluster_id, []))
                    if int(dict(item.get("cross_source_confirmation", {}) or {}).get("supporting_source_count", 0) or 0) > 0:
                        aggregate["confirmed_item_ids"].append(item_id)
                    if list(item.get("fact_conflicts", []) or []):
                        aggregate["conflicted_item_ids"].append(item_id)

        for hint in self._synthesized_mainline_direction_hints(
            mainlines=mainlines,
            market_regimes=market_regimes,
        ):
            key = (str(hint["signal_type"]), str(hint["direction"]))
            if key not in aggregates:
                aggregate = self._empty_direction_aggregate(
                    signal_type=str(hint["signal_type"]),
                    direction=str(hint["direction"]),
                    stance=str(hint["stance"]),
                )
                aggregate["cluster_scores"][str(hint["score_key"])] = int(hint["score"])
                aggregates[key] = aggregate
            aggregate = aggregates[key]
            aggregate["top_titles"].append(str(hint["headline"]).strip())
            aggregate["evidence_points"].extend(list(hint.get("evidence_points", []) or []))
            aggregate["evidence_mainline_ids"].extend(list(hint.get("evidence_mainline_ids", []) or []))
            aggregate["evidence_regime_ids"].extend(list(hint.get("evidence_regime_ids", []) or []))
            aggregate["follow_up_checks"].extend(list(hint.get("follow_up_checks", []) or []))

        direction_calls: list[dict[str, Any]] = []
        for aggregate in aggregates.values():
            score = sum(int(value or 0) for value in aggregate["cluster_scores"].values())
            confirmed_item_count = len(set(aggregate["confirmed_item_ids"]))
            conflicted_item_count = len(set(aggregate["conflicted_item_ids"]))
            source_mix = {
                "official_count": len(aggregate["source_mix_sets"]["official"]),
                "editorial_count": len(aggregate["source_mix_sets"]["editorial"]),
            }
            event_cluster_ids = list(aggregate["cluster_scores"].keys())
            event_cluster_count = len(event_cluster_ids)
            confidence = (
                "high"
                if score >= 18
                and source_mix["official_count"] >= 1
                and confirmed_item_count >= 1
                and conflicted_item_count == 0
                else "medium"
            )
            if score < 8:
                confidence = "low"
            rationale_titles = "；".join(dict.fromkeys(aggregate["top_titles"][:2]))
            rationale = (
                f"由 {rationale_titles} 支撑；官方源 {source_mix['official_count']} 条，"
                f"媒体源 {source_mix['editorial_count']} 条；"
                f"事件簇 {event_cluster_count} 个；"
                f"交叉确认 {confirmed_item_count} 条，冲突 {conflicted_item_count} 条。"
            )
            direction_calls.append(
                {
                    "signal_type": aggregate["signal_type"],
                    "direction": aggregate["direction"],
                    "stance": aggregate["stance"],
                    "score": score,
                    "confidence": confidence,
                    "evidence_item_ids": list(dict.fromkeys(aggregate["evidence_item_ids"])),
                    "source_ids": list(dict.fromkeys(aggregate["source_ids"])),
                    "source_mix": source_mix,
                    "supporting_titles": list(dict.fromkeys(aggregate["top_titles"]))[:3],
                    "evidence_points": list(dict.fromkeys(aggregate["evidence_points"]))[:4],
                    "evidence_mainline_ids": list(dict.fromkeys(aggregate["evidence_mainline_ids"])),
                    "evidence_regime_ids": list(dict.fromkeys(aggregate["evidence_regime_ids"])),
                    "follow_up_checks": list(dict.fromkeys(aggregate["follow_up_checks"]))[:4],
                    "event_cluster_count": event_cluster_count,
                    "event_cluster_ids": event_cluster_ids,
                    "confirmed_item_count": confirmed_item_count,
                    "conflicted_item_count": conflicted_item_count,
                    "rationale": rationale,
                }
            )

        direction_calls.sort(
            key=lambda item: (
                -int(item["score"]),
                {"beneficiary": 0, "price_up": 1, "pressured": 2}.get(str(item["signal_type"]), 99),
                str(item["direction"]),
            )
        )
        return direction_calls[:8]

    def _compress_direction_calls(self, direction_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            list(direction_calls or []),
            key=lambda item: (
                -int(item.get("score", 0) or 0),
                self.CONFIDENCE_ORDER.get(str(item.get("confidence", "")).strip(), 99),
                -int(dict(item.get("source_mix", {}) or {}).get("official_count", 0) or 0),
                str(item.get("direction", "")).strip(),
            ),
        )
        kept: list[dict[str, Any]] = []
        for candidate in ordered:
            if any(self._is_near_duplicate_direction(candidate, existing) for existing in kept):
                continue
            kept.append(candidate)
        return kept[:8]

    def _is_near_duplicate_direction(self, candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
        if str(candidate.get("signal_type", "")).strip() != str(existing.get("signal_type", "")).strip():
            return False
        if str(candidate.get("stance", "")).strip() != str(existing.get("stance", "")).strip():
            return False
        if self._direction_family(str(candidate.get("direction", "")).strip()) != self._direction_family(
            str(existing.get("direction", "")).strip()
        ):
            return False
        return self._direction_overlap(candidate, existing) > 0.5

    def _direction_family(self, direction: str) -> str:
        return self.DIRECTION_FAMILY_MAP.get(str(direction).strip(), str(direction).strip())

    def _direction_overlap(self, left: dict[str, Any], right: dict[str, Any]) -> float:
        left_sets = [
            set(str(item).strip() for item in list(left.get("event_cluster_ids", []) or []) if str(item).strip()),
            set(str(item).strip() for item in list(left.get("evidence_mainline_ids", []) or []) if str(item).strip()),
            set(str(item).strip() for item in list(left.get("evidence_regime_ids", []) or []) if str(item).strip()),
        ]
        right_sets = [
            set(str(item).strip() for item in list(right.get("event_cluster_ids", []) or []) if str(item).strip()),
            set(str(item).strip() for item in list(right.get("evidence_mainline_ids", []) or []) if str(item).strip()),
            set(str(item).strip() for item in list(right.get("evidence_regime_ids", []) or []) if str(item).strip()),
        ]
        overlaps: list[float] = []
        for left_set, right_set in zip(left_sets, right_sets):
            if not left_set or not right_set:
                continue
            overlaps.append(len(left_set & right_set) / float(min(len(left_set), len(right_set))))
        if overlaps:
            return max(overlaps)
        left_items = set(int(item) for item in list(left.get("evidence_item_ids", []) or []) if int(item or 0))
        right_items = set(int(item) for item in list(right.get("evidence_item_ids", []) or []) if int(item or 0))
        if not left_items or not right_items:
            return 0.0
        return len(left_items & right_items) / float(min(len(left_items), len(right_items)))

    def _build_stock_calls(self, direction_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stock_calls: list[dict[str, Any]] = []
        for direction_call in direction_calls:
            direction = str(direction_call["direction"])
            mapped_stocks = self.STOCK_DIRECTION_MAP.get(direction, ())
            if not mapped_stocks or direction_call["confidence"] == "low":
                continue
            for stock in mapped_stocks:
                stock_calls.append(
                    {
                        "ticker": stock["ticker"],
                        "name": stock["name"],
                        "direction": direction,
                        "stance": direction_call["stance"],
                        "confidence": direction_call["confidence"],
                        "action": "buy_watchlist" if direction_call["stance"] == "positive" else "avoid_or_reduce",
                        "action_label": "偏多关注" if direction_call["stance"] == "positive" else "回避/减仓",
                        "mapping_basis": "direction_proxy",
                        "evidence_item_ids": list(direction_call["evidence_item_ids"]),
                        "linked_mainline_ids": list(direction_call.get("evidence_mainline_ids", [])),
                        "linked_regime_ids": list(direction_call.get("evidence_regime_ids", [])),
                        "reason": f"{direction_call['rationale']} 个股作为该方向的代表性映射。",
                    }
                )
        return stock_calls[:12]

    def _mainline_ids_by_cluster(self, mainlines: list[dict[str, Any]]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for mainline in mainlines:
            mainline_id = str(mainline.get("mainline_id", "")).strip()
            if not mainline_id:
                continue
            for cluster_id in list(mainline.get("linked_event_ids", []) or []):
                normalized_cluster_id = str(cluster_id).strip()
                if not normalized_cluster_id:
                    continue
                mapping.setdefault(normalized_cluster_id, []).append(mainline_id)
        return {
            cluster_id: list(dict.fromkeys(mainline_ids))
            for cluster_id, mainline_ids in mapping.items()
        }

    def _mainline_regime_ids_by_cluster(self, mainlines: list[dict[str, Any]]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for mainline in mainlines:
            regime_ids = [
                str(regime_id).strip()
                for regime_id in list(mainline.get("regime_ids", []) or [])
                if str(regime_id).strip()
            ]
            if not regime_ids:
                continue
            for cluster_id in list(mainline.get("linked_event_ids", []) or []):
                normalized_cluster_id = str(cluster_id).strip()
                if not normalized_cluster_id:
                    continue
                mapping.setdefault(normalized_cluster_id, []).extend(regime_ids)
        return {
            cluster_id: list(dict.fromkeys(regime_ids))
            for cluster_id, regime_ids in mapping.items()
        }

    def _empty_direction_aggregate(self, *, signal_type: str, direction: str, stance: str) -> dict[str, Any]:
        return {
            "signal_type": signal_type,
            "direction": direction,
            "stance": stance,
            "evidence_item_ids": [],
            "source_ids": [],
            "source_mix_sets": {"official": set(), "editorial": set()},
            "top_titles": [],
            "evidence_points": [],
            "follow_up_checks": [],
            "confirmed_item_ids": [],
            "conflicted_item_ids": [],
            "cluster_scores": {},
            "evidence_mainline_ids": [],
            "evidence_regime_ids": [],
        }

    def _synthesized_mainline_direction_hints(
        self,
        *,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        regime_by_id = {
            str(regime.get("regime_id", "")).strip(): dict(regime)
            for regime in list(market_regimes or [])
            if str(regime.get("regime_id", "")).strip()
        }
        hints: list[dict[str, Any]] = []
        for mainline in list(mainlines or []):
            mainline_id = str(mainline.get("mainline_id", "")).strip()
            bucket = str(mainline.get("mainline_bucket", "")).strip()
            headline = str(mainline.get("headline", "")).strip()
            market_effect = str(mainline.get("market_effect", "")).strip()
            regime_ids = [
                str(regime_id).strip()
                for regime_id in list(mainline.get("regime_ids", []) or [])
                if str(regime_id).strip()
            ]
            regime_keys = [
                str(regime_by_id.get(regime_id, {}).get("regime_key", "")).strip()
                for regime_id in regime_ids
                if str(regime_by_id.get(regime_id, {}).get("regime_key", "")).strip()
            ]
            confidence = str(mainline.get("confidence", "")).strip() or "medium"

            direction_specs: list[tuple[str, str, str]]
            if bucket == "tech_semiconductor":
                direction_specs = [
                    ("pressured", "自主可控半导体链", "negative")
                    if "承压" in headline or "承压" in market_effect
                    else ("beneficiary", "自主可控半导体链", "positive")
                ]
            elif bucket == "rates_liquidity":
                if "缓和" in headline or "缓和" in market_effect:
                    direction_specs = [("beneficiary", "高估值成长链", "positive")]
                else:
                    direction_specs = [
                        ("beneficiary", "银行/保险", "positive"),
                        ("pressured", "高估值成长链", "negative"),
                    ]
            elif bucket == "geopolitics_energy":
                if "缓和" in headline or "缓和" in market_effect:
                    direction_specs = [("beneficiary", "航空与燃油敏感运输链", "positive")]
                else:
                    direction_specs = [("beneficiary", "油气开采", "positive")]
            else:
                direction_specs = []

            if not direction_specs:
                continue

            score = 14 if confidence == "high" else 10 if confidence == "medium" else 7
            evidence_point = f"已确认主线：{headline}" if headline else f"已确认主线 bucket：{bucket}"
            if regime_keys:
                evidence_point += f"；对应 regime：{'、'.join(dict.fromkeys(regime_keys[:2]))}"
            for signal_type, direction, stance in direction_specs:
                hints.append(
                    {
                        "signal_type": signal_type,
                        "direction": direction,
                        "stance": stance,
                        "headline": headline,
                        "score": score,
                        "score_key": f"mainline:{mainline_id or bucket}",
                        "evidence_points": [evidence_point],
                        "evidence_mainline_ids": [mainline_id] if mainline_id else [],
                        "evidence_regime_ids": regime_ids,
                        "follow_up_checks": [],
                    }
                )
        return hints

    def _collect_watchpoints(
        self,
        scored_items: list[dict[str, Any]],
        *,
        market_context: dict[str, Any] | None = None,
        mainline_coverage: dict[str, Any] | None = None,
    ) -> list[str]:
        watchpoints: list[str] = []
        for scored_item in scored_items:
            item = scored_item["item"]
            for watchpoint in list(item.get("follow_up_checks", []) or []):
                candidate = str(watchpoint).strip()
                if not candidate or candidate in watchpoints:
                    continue
                watchpoints.append(candidate)
        market_context = dict(market_context or {})
        mainline_coverage = dict(mainline_coverage or {})
        if list(market_context.get("core_missing_symbols", []) or []):
            watchpoints.insert(0, "市场快照核心板块仍有缺口，需补齐后再确认主线强度。")
        if str(mainline_coverage.get("status", "")).strip() == "degraded":
            watchpoints.append("当前市场主线仍处于降级确认状态，需继续跟踪后续市场和政策信号。")
        watchpoints = list(dict.fromkeys(watchpoints))
        return watchpoints[:8]

    def _build_supporting_items(self, scored_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for scored_item in scored_items[:8]:
            item = scored_item["item"]
            items.append(
                {
                    "item_id": int(item.get("item_id", 0) or 0),
                    "source_id": str(item.get("source_id", "")).strip(),
                    "source_name": str(item.get("source_name", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                    "analysis_status": str(item.get("analysis_status", "")).strip(),
                    "analysis_confidence": str(item.get("analysis_confidence", "")).strip(),
                    "a_share_relevance": str(item.get("a_share_relevance", "")).strip(),
                    "signal_score": int(scored_item["signal_score"]),
                    "signal_score_breakdown": dict(scored_item["score_breakdown"]),
                    "impact_summary": str(item.get("impact_summary", "")).strip(),
                    "timeliness": dict(item.get("timeliness", {}) or {}),
                    "source_capture_confidence": dict(item.get("source_capture_confidence", {}) or {}),
                    "cross_source_confirmation": dict(item.get("cross_source_confirmation", {}) or {}),
                    "fact_conflicts": list(item.get("fact_conflicts", []) or []),
                    "event_cluster": dict(item.get("event_cluster", {}) or {}),
                    "llm_ready_brief": str(item.get("llm_ready_brief", "")).strip(),
                    "beneficiary_directions": list(item.get("beneficiary_directions", []) or []),
                    "pressured_directions": list(item.get("pressured_directions", []) or []),
                    "price_up_signals": list(item.get("price_up_signals", []) or []),
                    "follow_up_checks": list(item.get("follow_up_checks", []) or []),
                    "evidence_points": list(item.get("evidence_points", []) or []),
                    "key_numbers": list(item.get("key_numbers", []) or []),
                    "fact_table": list(item.get("fact_table", []) or []),
                    "source_context": dict(item.get("source_context", {}) or {}),
                }
            )
        return items

    def _build_headline_news(self, scored_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        selected_item_ids: set[int] = set()
        source_counts: Counter[str] = Counter()
        bucket_counts: Counter[str] = Counter()
        bucket_caps = {
            "official": 4,
            "editorial": 4,
        }

        def bucket_for(item: dict[str, Any]) -> str:
            coverage_tier = str(item.get("coverage_tier", "")).strip()
            if coverage_tier in {"official_policy", "official_data"}:
                return "official"
            if coverage_tier == "editorial_media":
                return "editorial"
            return "other"

        def append_item(scored_item: dict[str, Any]) -> bool:
            item = scored_item["item"]
            item_id = int(item.get("item_id", 0) or 0)
            source_id = str(item.get("source_id", "")).strip() or f"item_{item_id}"
            bucket = bucket_for(item)
            if item_id in selected_item_ids:
                return False
            if source_counts[source_id] >= 2:
                return False
            if bucket in bucket_caps and bucket_counts[bucket] >= bucket_caps[bucket]:
                return False
            selected.append(self._headline_news_item(scored_item))
            selected_item_ids.add(item_id)
            source_counts[source_id] += 1
            if bucket in bucket_caps:
                bucket_counts[bucket] += 1
            return True

        for scored_item in scored_items:
            append_item(scored_item)
            if len(selected) >= 8:
                return selected

        for scored_item in scored_items:
            item = scored_item["item"]
            item_id = int(item.get("item_id", 0) or 0)
            source_id = str(item.get("source_id", "")).strip() or f"item_{item_id}"
            if item_id in selected_item_ids or source_counts[source_id] >= 2:
                continue
            selected.append(self._headline_news_item(scored_item))
            selected_item_ids.add(item_id)
            source_counts[source_id] += 1
            if len(selected) >= 8:
                break

        return selected

    def _headline_news_item(self, scored_item: dict[str, Any]) -> dict[str, Any]:
        item = scored_item["item"]
        user_brief_cn, brief_source, why_it_matters_cn = self._build_user_headline_brief(item)
        return {
            "item_id": int(item.get("item_id", 0) or 0),
            "source_id": str(item.get("source_id", "")).strip(),
            "source_name": str(item.get("source_name", "")).strip(),
            "title": str(item.get("title", "")).strip(),
            "coverage_tier": str(item.get("coverage_tier", "")).strip(),
            "signal_score": int(scored_item["signal_score"]),
            "analysis_status": str(item.get("analysis_status", "")).strip(),
            "analysis_confidence": str(item.get("analysis_confidence", "")).strip(),
            "published_at": item.get("published_at"),
            "impact_summary": str(item.get("impact_summary", "")).strip(),
            "llm_ready_brief": str(item.get("llm_ready_brief", "")).strip(),
            "evidence_points": list(item.get("evidence_points", []) or []),
            "user_brief_cn": user_brief_cn,
            "brief_source": brief_source,
            "why_it_matters_cn": why_it_matters_cn,
            "key_numbers": list(item.get("key_numbers", []) or []),
            "fact_table": list(item.get("fact_table", []) or []),
            "source_context": dict(item.get("source_context", {}) or {}),
        }

    def _build_user_headline_brief(self, item: dict[str, Any]) -> tuple[str, str, str]:
        title = str(item.get("title", "")).strip()
        impact_summary = str(item.get("impact_summary", "")).strip()
        llm_ready_brief = str(item.get("llm_ready_brief", "")).strip()
        evidence_points = [str(value).strip() for value in list(item.get("evidence_points", []) or []) if str(value).strip()]
        follow_up_checks = [str(value).strip() for value in list(item.get("follow_up_checks", []) or []) if str(value).strip()]

        clean_existing = self._sanitize_user_facing_brief(impact_summary or llm_ready_brief)
        if clean_existing and not self._looks_like_audit_brief(clean_existing):
            brief = self._ensure_sentence(clean_existing)
            return brief, "existing_brief", self._why_it_matters_cn(item)

        if title and evidence_points:
            source = "synthesized_cn" if impact_summary or llm_ready_brief else "evidence_points"
            brief = self._ensure_sentence(f"{title}：{evidence_points[0]}")
            return brief, source, self._why_it_matters_cn(item)

        if title:
            source = "synthesized_cn" if impact_summary or llm_ready_brief else "title"
            return self._ensure_sentence(title), source, self._why_it_matters_cn(item)

        if evidence_points:
            return self._ensure_sentence(evidence_points[0]), "evidence_points", self._why_it_matters_cn(item)

        if follow_up_checks:
            return self._ensure_sentence(f"继续关注：{follow_up_checks[0]}"), "follow_up_checks", self._why_it_matters_cn(item)

        return "需继续跟踪后续披露。", "fallback", self._why_it_matters_cn(item)

    def _sanitize_user_facing_brief(self, value: str) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            return ""
        return re.sub(r"\s+", " ", candidate).strip()

    def _looks_like_audit_brief(self, value: str) -> bool:
        return bool(self._AUDIT_STYLE_PATTERN.search(str(value or "").strip()))

    def _why_it_matters_cn(self, item: dict[str, Any]) -> str:
        directions = [
            str(value).strip()
            for field in ("beneficiary_directions", "pressured_directions", "price_up_signals")
            for value in list(item.get(field, []) or [])
            if str(value).strip()
        ]
        if directions:
            return f"关注方向：{'、'.join(dict.fromkeys(directions[:2]))}。"
        follow_up_checks = [str(value).strip() for value in list(item.get("follow_up_checks", []) or []) if str(value).strip()]
        if follow_up_checks:
            return self._ensure_sentence(f"后续关注：{follow_up_checks[0]}")
        return "需继续跟踪后续市场与政策细节。"

    def _ensure_sentence(self, value: str) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            return ""
        if candidate.endswith(("。", "！", "？", ".", "!", "?")):
            return candidate
        return candidate + "。"

    def _build_market_move_brief(
        self,
        *,
        market_snapshot: dict[str, Any] | None,
        market_context: dict[str, Any],
    ) -> dict[str, Any]:
        market_board = self._market_board(market_snapshot)
        headline = str(market_board.get("headline", "") or dict(market_snapshot or {}).get("headline", "")).strip()
        cross_asset_moves = self._collect_cross_asset_moves(market_board)
        key_moves = dict(market_board.get("key_moves", {}) or {})
        strongest_move = self._market_move_card(key_moves.get("strongest_move"))
        weakest_move = self._market_move_card(key_moves.get("weakest_move"))
        china_futures_watch = [
            {
                "future_name": str(item.get("future_name", "")).strip(),
                "watch_direction": str(item.get("watch_direction", "")).strip(),
                "driver_summary": str(item.get("driver_summary", "")).strip(),
            }
            for item in list(market_board.get("china_mapped_futures", []) or [])[:4]
            if isinstance(item, dict) and str(item.get("future_name", "")).strip()
        ]

        market_data_note = ""
        if str(market_context.get("market_data_status", "")).strip() == "partial":
            market_data_note = "当前市场板块数据不完整，部分板块仍需补齐。"
        elif str(market_context.get("market_data_status", "")).strip() == "missing":
            market_data_note = "当前缺少完整市场快照，部分跨资产判断仍需保留。"

        return {
            "headline": headline,
            "cross_asset_moves": cross_asset_moves,
            "strongest_move": strongest_move,
            "weakest_move": weakest_move,
            "china_futures_watch": china_futures_watch,
            "market_data_note": market_data_note,
        }

    def _build_event_drivers(self, headline_news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        drivers: list[dict[str, Any]] = []
        for item in list(headline_news or [])[:4]:
            detail_facts = self._driver_detail_facts(item)
            drivers.append(
                {
                    "source_name": str(item.get("source_name", "")).strip() or str(item.get("source_id", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "user_brief_cn": str(item.get("user_brief_cn", "")).strip(),
                    "why_it_matters_cn": str(item.get("why_it_matters_cn", "")).strip(),
                    "detail_facts": detail_facts,
                    "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                }
            )
        return drivers

    def _build_editorial_chain_cn(
        self,
        *,
        market_move_brief: dict[str, Any],
        event_drivers: list[dict[str, Any]],
        direction_calls: list[dict[str, Any]],
        market_context: dict[str, Any],
    ) -> str:
        bits: list[str] = []
        move_bits = [
            f"{str(item.get('label', '')).strip()} {str(item.get('change_pct', '')).strip()}"
            for item in list(market_move_brief.get("cross_asset_moves", []) or [])[:3]
            if str(item.get("label", "")).strip() and str(item.get("change_pct", "")).strip()
        ]
        if move_bits:
            bits.append(f"市场先交易{'、'.join(move_bits)}")

        if event_drivers:
            lead_driver = dict(event_drivers[0])
            source_name = str(lead_driver.get("source_name", "")).strip()
            title = str(lead_driver.get("title", "")).strip()
            if source_name and title:
                bits.append(f"随后需要用 {source_name} 的《{title}》解释价格动作")
            elif source_name:
                bits.append(f"随后需要用 {source_name} 的最新消息解释价格动作")

        top_positive = next((call for call in direction_calls if call.get("stance") == "positive"), None)
        top_negative = next((call for call in direction_calls if call.get("stance") == "negative"), None)
        top_price_up = next((call for call in direction_calls if call.get("signal_type") == "price_up"), None)
        direction_bits: list[str] = []
        if isinstance(top_positive, dict):
            direction_bits.append(f"先看 {str(top_positive.get('direction', '')).strip()}")
        if isinstance(top_negative, dict):
            direction_bits.append(f"承压链关注 {str(top_negative.get('direction', '')).strip()}")
        if isinstance(top_price_up, dict):
            direction_bits.append(f"涨价链留意 {str(top_price_up.get('direction', '')).strip()}")
        if direction_bits:
            bits.append("落到 A 股映射则" + "，".join(direction_bits))

        market_data_note = str(market_move_brief.get("market_data_note", "")).strip()
        if market_data_note:
            bits.append(market_data_note)
        elif str(market_context.get("market_data_status", "")).strip() == "partial":
            bits.append("当前市场板块数据不完整，结论仍需结合后续补齐情况复核")

        return self._ensure_sentence("，".join(bit for bit in bits if bit))

    def _driver_detail_facts(self, item: dict[str, Any]) -> list[str]:
        facts: list[str] = []
        for key_number in list(item.get("key_numbers", []) or [])[:3]:
            if not isinstance(key_number, dict):
                continue
            metric = str(key_number.get("metric", "")).strip()
            value_text = str(key_number.get("value_text", "")).strip()
            subject = str(key_number.get("subject", "")).strip()
            if not metric or not value_text:
                continue
            fact = f"{metric}={value_text}"
            if subject:
                fact += f"({subject})"
            facts.append(fact)
        for fact_row in list(item.get("fact_table", []) or [])[:2]:
            if not isinstance(fact_row, dict):
                continue
            text = str(fact_row.get("text", "")).strip()
            if text:
                facts.append(text)
        for evidence in list(item.get("evidence_points", []) or [])[:2]:
            text = str(evidence).strip()
            if text:
                facts.append(text)
        return list(dict.fromkeys(facts))[:4]

    def _market_board(self, market_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        snapshot = dict(market_snapshot or {})
        market_board = dict(snapshot.get("asset_board", {}) or {})
        return market_board or snapshot

    def _collect_cross_asset_moves(self, market_board: dict[str, Any]) -> list[dict[str, str]]:
        preferred_groups = ("energy", "precious_metals", "rates_fx", "indexes", "sectors")
        preferred_symbols = {
            "energy": ("BZ=F", "CL=F", "NG=F"),
            "precious_metals": ("GC=F", "SI=F"),
            "rates_fx": ("^TNX", "DX-Y.NYB"),
            "indexes": ("^GSPC", "^IXIC", "^DJI"),
            "sectors": ("XLE", "XLK", "XLF"),
        }
        selected: list[dict[str, str]] = []
        seen_labels: set[str] = set()
        for group in preferred_groups:
            items = [item for item in list(market_board.get(group, []) or []) if isinstance(item, dict)]
            ranked: list[dict[str, Any]] = []
            for symbol in preferred_symbols.get(group, ()):
                ranked.extend(item for item in items if str(item.get("symbol", "")).strip() == symbol)
            ranked.extend(
                item
                for item in sorted(items, key=lambda entry: int(entry.get("priority", 0) or 0), reverse=True)
                if item not in ranked
            )
            for item in ranked:
                label = str(item.get("display_name", "")).strip() or str(item.get("symbol", "")).strip()
                if not label or label in seen_labels:
                    continue
                selected.append(
                    {
                        "label": label,
                        "change_pct": self._format_pct(item.get("change_pct")),
                        "bucket": group,
                    }
                )
                seen_labels.add(label)
                break
        return selected[:6]

    def _market_move_card(self, item: Any) -> dict[str, str]:
        if not isinstance(item, dict):
            return {}
        label = str(item.get("display_name", "")).strip() or str(item.get("symbol", "")).strip()
        if not label:
            return {}
        return {
            "label": label,
            "change_pct": self._format_pct(item.get("change_pct")),
        }

    def _build_narratives(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        scored_items: list[dict[str, Any]],
        direction_calls: list[dict[str, Any]],
        risk_watchpoints: list[str],
        market_snapshot: dict[str, Any] | None,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        mainline_coverage: dict[str, Any],
        market_context: dict[str, Any],
    ) -> dict[str, str]:
        if not scored_items:
            market_view = "当日没有足够输入，无法形成固定市场观点。"
            if market_snapshot:
                market_view = self._build_market_view_text(
                    analysis_date=analysis_date,
                    market_snapshot=market_snapshot,
                    top_positive=None,
                    top_negative=None,
                )
            mainline_clause = self._mainline_clause(
                mainlines=mainlines,
                market_regimes=market_regimes,
                mainline_coverage=mainline_coverage,
            )
            return {
                "market_view": f"{market_view}{mainline_clause}" if mainline_clause else market_view,
                "policy_view": "当日没有可归纳的政策与数据主线。",
                "sector_view": mainline_clause.strip() if mainline_clause else "暂无方向级结论。",
                "risk_view": "暂无待跟踪风险点。",
                "execution_view": "等待有效新闻输入后再生成固定日报。",
            }

        top_positive = next((call for call in direction_calls if call["stance"] == "positive"), None)
        top_negative = next((call for call in direction_calls if call["stance"] == "negative"), None)
        top_price_up = next((call for call in direction_calls if call["signal_type"] == "price_up"), None)
        official_items = [
            scored_item for scored_item in scored_items if scored_item["item"].get("coverage_tier") in {"official_policy", "official_data"}
        ]
        editorial_items = [
            scored_item for scored_item in scored_items if scored_item["item"].get("coverage_tier") == "editorial_media"
        ]

        market_view = self._build_market_view_text(
            analysis_date=analysis_date,
            market_snapshot=market_snapshot,
            top_positive=top_positive,
            top_negative=top_negative,
        )
        if str(market_context.get("market_data_status", "")).strip() == "partial":
            market_view += " 当前市场板块数据不完整。"
        mainline_clause = self._mainline_clause(
            mainlines=mainlines,
            market_regimes=market_regimes,
            mainline_coverage=mainline_coverage,
        )
        if mainline_clause:
            market_view = f"{market_view}{mainline_clause}"
        policy_titles = "；".join(
            dict.fromkeys(str(item["item"].get("title", "")).strip() for item in official_items[:2])
        )
        policy_view = (
            f"官方层面的主导输入来自 {policy_titles}。"
            if policy_titles
            else "当前没有足够官方条目来归纳政策主线。"
        )
        if mainline_clause:
            policy_view = f"{policy_view}{mainline_clause}"
        sector_bits: list[str] = []
        confirmed_mainline_headlines = [
            str(mainline.get("headline", "")).strip()
            for mainline in list(mainlines or [])[:2]
            if str(mainline.get("headline", "")).strip()
        ]
        if confirmed_mainline_headlines:
            sector_bits.append(f"已确认主线为 {'；'.join(confirmed_mainline_headlines)}")
        if top_positive:
            sector_bits.append(f"偏多方向优先看 {top_positive['direction']}")
        if top_negative:
            sector_bits.append(f"承压方向优先看 {top_negative['direction']}")
        if top_price_up:
            sector_bits.append(f"成本/涨价链关注 {top_price_up['direction']}")
        sector_view = "；".join(sector_bits) + "。" if sector_bits else "暂无足够行业主线。"
        risk_view = "；".join(risk_watchpoints[:3]) + "。" if risk_watchpoints else "暂无额外待确认风险点。"

        execution_tail = "免费层只输出方向，不输出具体个股建议。"
        if access_tier == "premium":
            execution_tail = "付费层允许输出个股映射，但仍需回到 supporting_items 和 evidence_points 做复核。"
        execution_view = (
            f"当前官方输入 {len(official_items)} 条，媒体补充 {len(editorial_items)} 条。{execution_tail}"
        )
        return {
            "market_view": market_view,
            "policy_view": policy_view,
            "sector_view": sector_view,
            "risk_view": risk_view,
            "execution_view": execution_view,
        }

    def _build_summary(
        self,
        *,
        analysis_date: str,
        scored_items: list[dict[str, Any]],
        direction_calls: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        mainline_coverage: dict[str, Any],
        market_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not scored_items:
            return {
                "report_type": "daily_fixed",
                "analysis_date": analysis_date,
                "headline": "当日没有可用于生成固定结论的新闻输入。",
                "core_view": "当前数据库在该日期下没有捕获到可分析条目。",
                "confidence": "low",
            }

        top_positive = next((call for call in direction_calls if call["stance"] == "positive"), None)
        top_negative = next((call for call in direction_calls if call["stance"] == "negative"), None)
        headline_parts: list[str] = []
        confirmed_mainline_headlines = [
            str(mainline.get("headline", "")).strip()
            for mainline in list(mainlines or [])[:2]
            if str(mainline.get("headline", "")).strip()
        ]
        if confirmed_mainline_headlines:
            headline_parts.append(f"确认主线：{confirmed_mainline_headlines[0]}")
        if top_positive is not None:
            headline_parts.append(f"偏多方向：{top_positive['direction']}")
        if top_negative is not None:
            headline_parts.append(f"承压方向：{top_negative['direction']}")
        if not headline_parts:
            headline_parts.append("以跟踪和待确认为主，暂不宜给强结论")

        official_count = sum(
            1 for item in scored_items if item["item"].get("coverage_tier") in {"official_policy", "official_data"}
        )
        editorial_count = sum(1 for item in scored_items if item["item"].get("coverage_tier") == "editorial_media")
        confidence = "high" if (official_count >= 2 and direction_calls) or (mainlines and market_regimes) else "medium"
        if not direction_calls and not (mainlines and market_regimes):
            confidence = "low"
        elif not direction_calls:
            confidence = "medium"
        confidence = self._apply_market_confidence_cap(
            confidence=confidence,
            market_context=market_context,
            mainline_coverage=mainline_coverage,
            has_direction_calls=bool(direction_calls),
        )

        core_view = (
            f"本日报告基于 {len(scored_items)} 条输入生成，其中官方源 {official_count} 条，"
            f"媒体源 {editorial_count} 条。"
            f"{' 同时纳入了美股收盘快照。' if market_snapshot else ' 暂未纳入美股收盘快照。'}"
            " 方向结论按固定公式聚合并缓存。"
        )
        if str(market_context.get("market_data_status", "")).strip() == "partial":
            core_view += " 当前市场快照存在核心缺口，市场板块并不完整。"
        if confirmed_mainline_headlines:
            core_view += f" 已确认市场主线 {len(mainlines)} 条，首要主线为 {confirmed_mainline_headlines[0]}。"
        regime_keys = [
            str(regime.get("regime_key", "")).strip()
            for regime in list(market_regimes or [])[:3]
            if str(regime.get("regime_key", "")).strip()
        ]
        if regime_keys:
            core_view += f" 触发 regime：{'、'.join(dict.fromkeys(regime_keys))}。"
        if str(mainline_coverage.get("status", "")).strip() != "confirmed":
            core_view += f" 暂未确认市场主线，原因包括：{self._suppression_reasons_text(mainline_coverage)}。"

        return {
            "report_type": "daily_fixed",
            "analysis_date": analysis_date,
            "headline": "；".join(headline_parts) + "。",
            "core_view": core_view,
            "confidence": confidence,
        }

    def _build_market_context(self, market_snapshot: dict[str, Any]) -> dict[str, Any]:
        capture_summary = dict(market_snapshot.get("capture_summary", {}) or {})
        capture_status = str(capture_summary.get("capture_status", "")).strip() or "complete"
        missing_symbols = [str(symbol).strip() for symbol in list(capture_summary.get("missing_symbols", []) or []) if str(symbol).strip()]
        core_missing_symbols = [
            str(symbol).strip()
            for symbol in list(capture_summary.get("core_missing_symbols", []) or [])
            if str(symbol).strip()
        ]
        market_data_status = "complete"
        if capture_status == "partial" or core_missing_symbols:
            market_data_status = "partial"
        elif capture_status in {"missing", "error"}:
            market_data_status = "missing"
        return {
            "capture_status": capture_status,
            "market_data_status": market_data_status,
            "missing_symbols": missing_symbols,
            "core_missing_symbols": core_missing_symbols,
            "captured_instrument_count": int(capture_summary.get("captured_instrument_count", 0) or 0),
        }

    def _default_mainline_coverage(
        self,
        *,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        market_context: dict[str, Any],
    ) -> dict[str, Any]:
        suppression_reasons: list[str] = []
        market_data_status = str(market_context.get("market_data_status", "")).strip() or "complete"
        if list(market_context.get("core_missing_symbols", []) or []):
            suppression_reasons.append("core_market_gap")
        if not market_regimes:
            suppression_reasons.append("no_triggered_regime")
        if not mainlines:
            suppression_reasons.append("no_linked_event_group")
        status = "confirmed" if (mainlines or market_regimes) else "degraded" if market_data_status != "complete" else "unavailable"
        return {
            "status": status,
            "market_data_status": market_data_status,
            "suppression_reasons": list(dict.fromkeys(suppression_reasons)),
            "secondary_group_count": 0,
        }

    def _apply_market_confidence_cap(
        self,
        *,
        confidence: str,
        market_context: dict[str, Any],
        mainline_coverage: dict[str, Any],
        has_direction_calls: bool,
    ) -> str:
        resolved = str(confidence or "").strip() or "medium"
        if list(market_context.get("core_missing_symbols", []) or []) and resolved == "high":
            resolved = "medium"
        if list(market_context.get("core_missing_symbols", []) or []) and str(mainline_coverage.get("status", "")).strip() != "confirmed" and not has_direction_calls:
            resolved = "low"
        return resolved

    def _build_market_view_text(
        self,
        *,
        analysis_date: str,
        market_snapshot: dict[str, Any] | None,
        top_positive: dict[str, Any] | None,
        top_negative: dict[str, Any] | None,
    ) -> str:
        direction_clause = (
            f"新闻主线偏向 {top_positive['direction'] if top_positive else '继续观察'}；"
            f"当前最明确的承压方向是 {top_negative['direction'] if top_negative else '暂未形成明确承压方向'}。"
        )
        if not market_snapshot:
            return f"{analysis_date} 的固定日报显示，{direction_clause}"

        market_board = self._market_board(market_snapshot)
        indexes = list(market_board.get("indexes", []) or [])
        energy = list(market_board.get("energy", []) or [])
        precious_metals = list(market_board.get("precious_metals", []) or [])
        rates_fx = list(market_board.get("rates_fx", []) or [])
        spx = next((item for item in indexes if item.get("symbol") == "^GSPC"), indexes[0] if indexes else None)
        ndx = next((item for item in indexes if item.get("symbol") == "^IXIC"), None)
        brent = next((item for item in energy if item.get("symbol") == "BZ=F"), energy[0] if energy else None)
        gold = next((item for item in precious_metals if item.get("symbol") == "GC=F"), precious_metals[0] if precious_metals else None)
        rates = next((item for item in rates_fx if item.get("symbol") == "^TNX"), rates_fx[0] if rates_fx else None)
        risk_signals = dict(market_board.get("risk_signals", {}) or dict(market_snapshot.get("risk_signals", {}) or {}))
        volatility = dict(risk_signals.get("volatility_proxy", {}) or {})

        market_bits: list[str] = []
        if spx is not None:
            market_bits.append(f"{spx.get('display_name', '标普500')} {self._format_pct(spx.get('change_pct'))}")
        if ndx is not None:
            market_bits.append(f"{ndx.get('display_name', '纳指')} {self._format_pct(ndx.get('change_pct'))}")
        if brent is not None:
            market_bits.append(f"{brent.get('display_name', '布伦特原油')} {self._format_pct(brent.get('change_pct'))}")
        if gold is not None:
            market_bits.append(f"{gold.get('display_name', '黄金')} {self._format_pct(gold.get('change_pct'))}")
        if rates is not None:
            market_bits.append(f"{rates.get('display_name', '美国10年期国债收益率')} {self._format_pct(rates.get('change_pct'))}")
        if isinstance(volatility, dict) and volatility:
            market_bits.append(f"{volatility.get('display_name', 'VIX')} {self._format_pct(volatility.get('change_pct'))}")
        market_prefix = "；".join(market_bits) if market_bits else "美股收盘快照暂无主要指数摘要"
        return f"{analysis_date} 对应的美股收盘表现为 {market_prefix}；{direction_clause}"

    def _format_pct(self, value: Any) -> str:
        try:
            return f"{float(value):+.2f}%"
        except (TypeError, ValueError):
            return "持平"

    def _source_capture_confidence_bonus(self, item: dict[str, Any]) -> int:
        confidence = dict(item.get("source_capture_confidence", {}) or {})
        level = str(confidence.get("level", "")).strip()
        score = int(confidence.get("score", 0) or 0)
        if level == "high" or score >= 80:
            return 3
        if level == "medium" or score >= 60:
            return 2
        if score >= 45:
            return 1
        return 0

    def _cross_source_confirmation_bonus(self, item: dict[str, Any]) -> int:
        confirmation = dict(item.get("cross_source_confirmation", {}) or {})
        level = str(confirmation.get("level", "")).strip()
        supporting_source_count = int(confirmation.get("supporting_source_count", 0) or 0)
        if level == "strong" or supporting_source_count >= 2:
            return 2
        if level == "moderate" or supporting_source_count == 1:
            return 1
        return 0

    def _fact_conflict_penalty(self, item: dict[str, Any]) -> int:
        return min(2, len(list(item.get("fact_conflicts", []) or [])))

    def _timeliness_bonus(self, item: dict[str, Any]) -> int:
        timeliness = dict(item.get("timeliness", {}) or {})
        freshness_bucket = str(timeliness.get("freshness_bucket", "")).strip()
        if freshness_bucket == "breaking":
            return 3
        if freshness_bucket == "overnight":
            return 2
        if freshness_bucket == "recent":
            return 1
        return 0

    def _staleness_penalty(self, item: dict[str, Any]) -> int:
        timeliness = dict(item.get("timeliness", {}) or {})
        flags = {
            str(flag).strip()
            for flag in list(timeliness.get("timeliness_flags", []) or [])
            if str(flag).strip()
        }
        penalty = 0
        if str(timeliness.get("freshness_bucket", "")).strip() == "stale":
            penalty += 1
        if "delayed_capture" in flags:
            penalty += 1
        return min(2, penalty)

    def _event_cluster_id(self, item: dict[str, Any]) -> str:
        event_cluster = dict(item.get("event_cluster", {}) or {})
        cluster_id = str(event_cluster.get("cluster_id", "")).strip()
        if cluster_id:
            return cluster_id
        return f"item_{int(item.get('item_id', 0) or 0)}"

    def _mainline_clause(
        self,
        *,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
        mainline_coverage: dict[str, Any],
    ) -> str:
        if str(mainline_coverage.get("status", "")).strip() != "confirmed":
            reasons = self._suppression_reasons_text(mainline_coverage)
            return f" 暂未确认市场主线，原因包括：{reasons}。"
        headlines = [
            str(mainline.get("headline", "")).strip()
            for mainline in list(mainlines or [])[:2]
            if str(mainline.get("headline", "")).strip()
        ]
        regime_keys = [
            str(regime.get("regime_key", "")).strip()
            for regime in list(market_regimes or [])[:2]
            if str(regime.get("regime_key", "")).strip()
        ]
        bits: list[str] = []
        if headlines:
            bits.append(f"已确认主线：{'；'.join(headlines)}")
        if regime_keys:
            bits.append(f"触发 regime：{'、'.join(dict.fromkeys(regime_keys))}")
        if not bits:
            return ""
        return " " + "；".join(bits) + "。"

    def _suppression_reasons_text(self, mainline_coverage: dict[str, Any]) -> str:
        mapping = {
            "core_market_gap": "核心市场板块缺口",
            "market_snapshot_missing": "缺少市场快照",
            "market_board_missing": "缺少可用市场面板",
            "no_triggered_regime": "未触发明确 regime",
            "no_linked_event_group": "缺少可确认的事件链接",
            "no_relevant_event_group": "缺少可归纳的事件组",
        }
        reasons = [
            mapping.get(str(reason).strip(), str(reason).strip())
            for reason in list(mainline_coverage.get("suppression_reasons", []) or [])
            if str(reason).strip()
        ]
        return "、".join(dict.fromkeys(reasons)) or "缺少足够确认条件"
