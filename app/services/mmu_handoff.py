# -*- coding: utf-8 -*-
"""Structured staged payload builders for downstream MMU calls."""

from __future__ import annotations

from typing import Any


class MMUHandoffService:
    def build_bundle(
        self,
        *,
        handoff: dict[str, Any],
        analysis_report: dict[str, Any] | None = None,
        item_limit: int = 8,
        access_tier: str = "free",
    ) -> dict[str, Any]:
        market_snapshot = dict(handoff.get("market_snapshot", {}) or {})
        market_board = dict(market_snapshot.get("asset_board", {}) or {})
        analysis_date = (
            str(market_snapshot.get("analysis_date", "")).strip()
            or str(handoff.get("analysis_date", "")).strip()
            or str(handoff.get("generated_at", "")).strip()[:10]
        )
        mainlines = list(handoff.get("mainlines", []) or [])
        event_groups = list(handoff.get("event_groups", []) or [])
        market_regimes = list(handoff.get("market_regimes", []) or [])
        secondary_event_groups = list(handoff.get("secondary_event_groups", []) or [])
        mainline_bucket_by_event = self._mainline_bucket_by_event(mainlines)

        market_attribution = self.build_market_attribution(
            analysis_date=analysis_date,
            market_board=market_board,
            mainlines=mainlines,
            event_groups=event_groups,
            market_regimes=market_regimes,
            secondary_event_groups=secondary_event_groups,
        )
        return {
            "analysis_date": analysis_date,
            "access_tier": access_tier,
            "market_regimes": market_regimes,
            "secondary_event_groups": secondary_event_groups,
            "single_item_understanding": [
                self.build_single_item_understanding(analysis_date=analysis_date, item=item)
                for item in list(handoff.get("items", []) or [])[: max(1, int(item_limit))]
            ],
            "event_consolidation": [
                self.build_event_consolidation(
                    analysis_date=analysis_date,
                    event_group=event_group,
                    mainline_bucket_hint=mainline_bucket_by_event.get(
                        str(event_group.get("cluster_id", "")).strip(),
                        "",
                    ),
                )
                for event_group in event_groups
            ],
            "market_attribution": market_attribution,
            "premium_recommendation": (
                self.build_premium_recommendation(
                    analysis_date=analysis_date,
                    market_attribution=market_attribution,
                    china_mapping_context=self._china_mapping_context(analysis_report),
                    ticker_enrichments=list(dict(analysis_report or {}).get("ticker_enrichments", []) or []),
                )
                if access_tier == "premium" and str(dict(analysis_report or {}).get("access_tier", "")).strip() == "premium"
                else self.build_unavailable_premium_recommendation(analysis_date=analysis_date)
            ),
        }

    def build_single_item_understanding(
        self,
        *,
        analysis_date: str,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "handoff_type": "single_item_understanding",
            "analysis_date": analysis_date,
            "item": {
                "item_id": int(item.get("item_id", 0) or 0),
                "source_id": str(item.get("source_id", "")).strip(),
                "source_name": str(item.get("source_name", "")).strip(),
                "source_group": str(item.get("source_group", "")).strip(),
                "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                "published_at": item.get("published_at"),
                "published_at_display": item.get("published_at_display"),
                "title": str(item.get("title", "")).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "canonical_url": str(item.get("canonical_url", "")).strip(),
                "excerpt_source": str(item.get("excerpt_source", "")).strip(),
                "document_type": str(item.get("document_type", "")).strip(),
                "entities": list(item.get("entities", []) or []),
                "numeric_facts": list(item.get("numeric_facts", []) or []),
                "evidence_points": list(item.get("evidence_points", []) or []),
                "source_capture_confidence": dict(item.get("source_capture_confidence", {}) or {}),
                "source_integrity": dict(item.get("source_integrity", {}) or {}),
                "key_numbers": list(item.get("key_numbers", []) or []),
            },
            "instructions": {
                "max_output_facts": 8,
                "must_not_give_investment_advice": True,
            },
        }

    def build_event_consolidation(
        self,
        *,
        analysis_date: str,
        event_group: dict[str, Any],
        mainline_bucket_hint: str,
    ) -> dict[str, Any]:
        items = [
            {
                "item_id": int(item.get("item_id", 0) or 0),
                "source_name": str(item.get("source_name", "")).strip(),
                "coverage_tier": str(item.get("coverage_tier", "")).strip(),
                "published_at_display": item.get("published_at_display"),
                "title": str(item.get("title", "")).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "canonical_url": str(item.get("canonical_url", "")).strip(),
                "key_numbers": list(item.get("key_numbers", []) or []),
                "evidence_points": list(item.get("evidence_points", []) or []),
            }
            for item in list(event_group.get("items", []) or [])[:5]
        ]
        return {
            "handoff_type": "event_consolidation",
            "analysis_date": analysis_date,
            "cluster_candidate": {
                "cluster_id": str(event_group.get("cluster_id", "")).strip(),
                "item_ids": [int(item.get("item_id", 0) or 0) for item in items],
                "mainline_bucket_hint": mainline_bucket_hint,
                "items": items,
            },
            "instructions": {
                "prefer_official_primary_source": True,
                "max_sources_per_event": 5,
            },
        }

    def build_market_attribution(
        self,
        *,
        analysis_date: str,
        market_board: dict[str, Any],
        mainlines: list[dict[str, Any]],
        event_groups: list[dict[str, Any]],
        market_regimes: list[dict[str, Any]] | None = None,
        secondary_event_groups: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        event_by_id = {
            str(group.get("cluster_id", "")).strip(): group
            for group in event_groups
            if str(group.get("cluster_id", "")).strip()
        }
        main_candidate_events: list[dict[str, Any]] = []
        for mainline in list(mainlines or [])[:12]:
            for event_id in list(mainline.get("linked_event_ids", []) or []):
                group = event_by_id.get(str(event_id).strip())
                if group is None:
                    continue
                main_candidate_events.append(
                    {
                        "cluster_id": str(group.get("cluster_id", "")).strip(),
                        "event_title": str(group.get("headline", "")).strip(),
                        "mainline_bucket": str(mainline.get("mainline_bucket", "")).strip(),
                        "primary_source_name": str(group.get("primary_source_name", "")).strip(),
                        "canonical_event_summary_cn": str(group.get("headline", "")).strip(),
                        "affected_assets": self._event_group_affected_assets(group),
                        "confidence": self._event_confidence(group),
                    }
                )
        return {
            "handoff_type": "market_attribution",
            "analysis_date": analysis_date,
            "market_mainline_summary_cn": self._market_mainline_summary(mainlines),
            "market_regimes": list(market_regimes or []),
            "mainlines": list(mainlines or []),
            "secondary_event_groups": list(secondary_event_groups or []),
            "market_board": {
                "headline": str(market_board.get("headline", "")).strip(),
                "indexes": list(market_board.get("indexes", []) or []),
                "sectors": list(market_board.get("sectors", []) or []),
                "rates_fx": list(market_board.get("rates_fx", []) or []),
                "precious_metals": list(market_board.get("precious_metals", []) or []),
                "energy": list(market_board.get("energy", []) or []),
                "industrial_metals": list(market_board.get("industrial_metals", []) or []),
                "china_mapped_futures": list(market_board.get("china_mapped_futures", []) or []),
            },
            "main_candidate_events": main_candidate_events,
            "instructions": {
                "max_mainlines": 12,
                "must_start_from_market_results": True,
            },
        }

    def build_premium_recommendation(
        self,
        *,
        analysis_date: str,
        market_attribution: dict[str, Any],
        china_mapping_context: dict[str, Any],
        ticker_enrichments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        confirmed_mainlines = [
            dict(mainline)
            for mainline in list(dict(market_attribution.get("market_attribution", {}) or {}).get("mainlines", []) or [])
        ]
        if not confirmed_mainlines:
            confirmed_mainlines = [
                dict(mainline)
                for mainline in list(market_attribution.get("mainlines", []) or [])
                if str(mainline.get("confidence", "")).strip() in {"high", "medium"}
            ]
        return {
            "handoff_type": "premium_recommendation",
            "analysis_date": analysis_date,
            "market_regimes": list(market_attribution.get("market_regimes", []) or []),
            "secondary_event_groups": list(market_attribution.get("secondary_event_groups", []) or []),
            "ticker_enrichments": list(ticker_enrichments or []),
            "market_attribution": {
                "market_mainline_summary_cn": str(
                    market_attribution.get("market_mainline_summary_cn")
                    or "基于昨夜市场结果与主线事件进行中国映射。"
                ).strip(),
                "mainlines": confirmed_mainlines,
            },
            "china_mapping_context": {
                "sector_direction_map": list(china_mapping_context.get("sector_direction_map", []) or []),
                "commodity_direction_map": list(china_mapping_context.get("commodity_direction_map", []) or []),
                "candidate_stock_pool": list(china_mapping_context.get("candidate_stock_pool", []) or []),
            },
            "instructions": {
                "max_stock_recommendations": 25,
                "must_include_risk_points": True,
            },
        }

    def build_unavailable_premium_recommendation(self, *, analysis_date: str) -> dict[str, Any]:
        return {
            "handoff_type": "premium_recommendation",
            "analysis_date": analysis_date,
            "status": "unavailable",
            "reason": "premium_tier_required",
        }

    def _event_group_affected_assets(self, group: dict[str, Any]) -> list[str]:
        affected_assets: list[str] = []
        for item in list(group.get("items", []) or []):
            for implication in list(item.get("market_implications", []) or []):
                direction = str(implication.get("direction", "")).strip()
                if direction:
                    affected_assets.append(direction)
        return list(dict.fromkeys(affected_assets))

    def _event_confidence(self, group: dict[str, Any]) -> str:
        official_source_count = int(group.get("official_source_count", 0) or 0)
        cluster_status = str(group.get("cluster_status", "")).strip()
        if official_source_count >= 1 and cluster_status == "confirmed":
            return "high"
        if official_source_count >= 1 or cluster_status in {"confirmed", "conflicted"}:
            return "medium"
        return "low"

    def _mainline_bucket_by_event(self, mainlines: list[dict[str, Any]]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for mainline in mainlines:
            bucket = str(mainline.get("mainline_bucket", "")).strip()
            for event_id in list(mainline.get("linked_event_ids", []) or []):
                normalized_event_id = str(event_id).strip()
                if normalized_event_id and bucket and normalized_event_id not in mapping:
                    mapping[normalized_event_id] = bucket
        return mapping

    def _china_mapping_context(self, analysis_report: dict[str, Any] | None) -> dict[str, Any]:
        report = dict(analysis_report or {})
        direction_calls = list(report.get("direction_calls", []) or [])
        stock_calls = list(report.get("stock_calls", []) or [])
        return {
            "sector_direction_map": [
                {
                    "direction": str(call.get("direction", "")).strip(),
                    "stance": str(call.get("stance", "")).strip(),
                    "evidence_mainline_ids": list(call.get("evidence_mainline_ids", []) or []),
                }
                for call in direction_calls
                if str(call.get("direction", "")).strip()
            ],
            "commodity_direction_map": [
                {
                    "commodity_direction": str(call.get("direction", "")).strip(),
                    "confidence": str(call.get("confidence", "")).strip(),
                    "evidence_mainline_ids": list(call.get("evidence_mainline_ids", []) or []),
                }
                for call in direction_calls
                if str(call.get("signal_type", "")).strip() == "price_up"
            ],
            "candidate_stock_pool": [
                {
                    "ticker": str(call.get("ticker", "")).strip(),
                    "name": str(call.get("name", "")).strip(),
                }
                for call in stock_calls
                if str(call.get("ticker", "")).strip()
            ],
        }

    def _market_mainline_summary(self, mainlines: list[dict[str, Any]]) -> str:
        if not mainlines:
            return "昨夜主线待进一步归因。"
        headlines = [
            str(mainline.get("headline", "")).strip()
            for mainline in list(mainlines or [])[:3]
            if str(mainline.get("headline", "")).strip()
        ]
        if not headlines:
            return "昨夜主线待进一步归因。"
        return "昨夜主线聚焦：" + "；".join(headlines) + "。"
