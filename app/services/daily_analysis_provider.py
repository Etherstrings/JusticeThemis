# -*- coding: utf-8 -*-
"""Provider abstraction and default rule-based daily analysis generation."""

from __future__ import annotations

from collections import Counter
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

    def generate_report(
        self,
        *,
        analysis_date: str,
        access_tier: str,
        items: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None = None,
        mainlines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        scored_items = [self._score_item(item) for item in items]
        scored_items.sort(key=lambda item: item["signal_score"], reverse=True)
        market_snapshot = dict(market_snapshot or {})
        mainlines = list(mainlines or [])
        market_regimes = list(market_snapshot.get("market_regimes", []) or [])
        direction_calls = self._build_direction_calls(
            scored_items,
            mainlines=mainlines,
            market_regimes=market_regimes,
        )
        stock_calls = self._build_stock_calls(direction_calls) if access_tier == "premium" else []
        risk_watchpoints = self._collect_watchpoints(scored_items)
        supporting_items = self._build_supporting_items(scored_items)
        headline_news = self._build_headline_news(scored_items)
        narratives = self._build_narratives(
            analysis_date=analysis_date,
            access_tier=access_tier,
            scored_items=scored_items,
            direction_calls=direction_calls,
            risk_watchpoints=risk_watchpoints,
            market_snapshot=market_snapshot or None,
            mainlines=mainlines,
            market_regimes=market_regimes,
        )

        return {
            "summary": self._build_summary(
                analysis_date=analysis_date,
                scored_items=scored_items,
                direction_calls=direction_calls,
                market_snapshot=market_snapshot or None,
                mainlines=mainlines,
                market_regimes=market_regimes,
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
            "mainlines": mainlines,
            "direction_calls": direction_calls,
            "stock_calls": stock_calls,
            "risk_watchpoints": risk_watchpoints,
            "supporting_items": supporting_items,
            "headline_news": headline_news,
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

    def _collect_watchpoints(self, scored_items: list[dict[str, Any]]) -> list[str]:
        watchpoints: list[str] = []
        for scored_item in scored_items:
            item = scored_item["item"]
            for watchpoint in list(item.get("follow_up_checks", []) or []):
                candidate = str(watchpoint).strip()
                if not candidate or candidate in watchpoints:
                    continue
                watchpoints.append(candidate)
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
            selected.append(
                {
                    "item_id": item_id,
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
                }
            )
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
            selected.append(
                {
                    "item_id": item_id,
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
                }
            )
            selected_item_ids.add(item_id)
            source_counts[source_id] += 1
            if len(selected) >= 8:
                break

        return selected

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
            mainline_clause = self._confirmed_mainline_clause(mainlines=mainlines, market_regimes=market_regimes)
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
        mainline_clause = self._confirmed_mainline_clause(mainlines=mainlines, market_regimes=market_regimes)
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

        core_view = (
            f"本日报告基于 {len(scored_items)} 条输入生成，其中官方源 {official_count} 条，"
            f"媒体源 {editorial_count} 条。"
            f"{' 同时纳入了美股收盘快照。' if market_snapshot else ' 暂未纳入美股收盘快照。'}"
            " 方向结论按固定公式聚合并缓存。"
        )
        if confirmed_mainline_headlines:
            core_view += f" 已确认市场主线 {len(mainlines)} 条，首要主线为 {confirmed_mainline_headlines[0]}。"
        regime_keys = [
            str(regime.get("regime_key", "")).strip()
            for regime in list(market_regimes or [])[:3]
            if str(regime.get("regime_key", "")).strip()
        ]
        if regime_keys:
            core_view += f" 触发 regime：{'、'.join(dict.fromkeys(regime_keys))}。"

        return {
            "report_type": "daily_fixed",
            "analysis_date": analysis_date,
            "headline": "；".join(headline_parts) + "。",
            "core_view": core_view,
            "confidence": confidence,
        }

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

        indexes = list(market_snapshot.get("indexes", []) or [])
        spx = next((item for item in indexes if item.get("symbol") == "^GSPC"), indexes[0] if indexes else None)
        ndx = next((item for item in indexes if item.get("symbol") == "^IXIC"), None)
        volatility = dict(market_snapshot.get("risk_signals", {}) or {}).get("volatility_proxy")

        market_bits: list[str] = []
        if spx is not None:
            market_bits.append(f"{spx.get('display_name', '标普500')} {self._format_pct(spx.get('change_pct'))}")
        if ndx is not None:
            market_bits.append(f"{ndx.get('display_name', '纳指')} {self._format_pct(ndx.get('change_pct'))}")
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

    def _confirmed_mainline_clause(
        self,
        *,
        mainlines: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]],
    ) -> str:
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
