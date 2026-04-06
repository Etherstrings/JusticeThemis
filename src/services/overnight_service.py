# -*- coding: utf-8 -*-
"""Service layer for overnight brief API endpoints."""

from __future__ import annotations

from dataclasses import replace
import re
from collections import Counter
from typing import Any
from urllib.parse import unquote, urlparse

from src.config import get_config
from src.overnight.brief_builder import MorningExecutiveBrief, RankedEvent, build_morning_brief
from src.overnight.runner import OvernightRunner
from src.overnight.source_registry import build_default_source_registry
from src.notification import NotificationService
from src.repositories.overnight_repo import OvernightRepository
from src.services.overnight_judgment_service import OvernightJudgmentService
from src.services.overnight_source_capture_service import OvernightSourceCaptureService
from src.services.overnight_source_excerpt_service import OvernightSourceExcerptService


class OvernightBriefNotFoundError(LookupError):
    """Raised when no overnight brief can be produced yet."""


class OvernightEventNotFoundError(LookupError):
    """Raised when the requested overnight event is not present."""


class OvernightService:
    """Provide overnight brief and event detail payloads for API consumers."""

    HISTORY_AGGREGATION_LIMIT = 180
    VALID_FEEDBACK_TYPES = {
        "useful",
        "not_useful",
        "too_repetitive",
        "priority_too_high",
        "should_be_higher",
        "conclusion_too_strong",
        "missed_big_event",
    }
    VALID_FEEDBACK_STATUSES = {
        "pending_review",
        "reviewed",
        "dismissed",
    }
    TOPIC_HISTORY_CONFIG = {
        "beneficiaries": {
            "title": "可能受益方向",
            "field_name": "likely_beneficiaries",
        },
        "price-pressure": {
            "title": "可能涨价/更贵的方向",
            "field_name": "what_may_get_more_expensive",
        },
        "policy-radar": {
            "title": "政策雷达",
            "field_name": "policy_radar",
        },
        "macro-radar": {
            "title": "宏观雷达",
            "field_name": "macro_radar",
        },
        "sector-transmission": {
            "title": "市场传导",
            "field_name": "sector_transmission",
        },
        "risk-board": {
            "title": "风险板",
            "field_name": "risk_board",
        },
        "cross-asset": {
            "title": "跨资产快照",
            "field_name": "cross_asset_snapshot",
        },
        "pressure-points": {
            "title": "承压方向",
            "field_name": "likely_pressure_points",
        },
    }

    def __init__(
        self,
        runner: OvernightRunner | None = None,
        repo: OvernightRepository | None = None,
        judgment_service: OvernightJudgmentService | None = None,
        source_excerpt_service: OvernightSourceExcerptService | None = None,
        source_capture_service: OvernightSourceCaptureService | None = None,
    ) -> None:
        self.runner = runner or OvernightRunner()
        self.repo = repo or OvernightRepository()
        self.judgment_service = judgment_service or OvernightJudgmentService()
        self.source_excerpt_service = source_excerpt_service or OvernightSourceExcerptService(repo=self.repo)
        self.source_capture_service = source_capture_service or OvernightSourceCaptureService(repo=self.repo)

    def get_latest_brief(self) -> MorningExecutiveBrief:
        latest = self.repo.get_latest_morning_brief()
        if latest is not None and latest.top_events:
            return self._upgrade_legacy_watchlist_shape(latest)

        config = get_config()
        result = self.runner.run_digest(
            cutoff_time=config.overnight_digest_cutoff,
            send_notification=False,
        )
        brief = result.morning_brief
        if not brief.top_events:
            raise OvernightBriefNotFoundError("No overnight brief is available yet.")
        return self._upgrade_legacy_watchlist_shape(brief)

    def get_brief_by_id(self, brief_id: str) -> MorningExecutiveBrief:
        brief = self.repo.get_morning_brief(brief_id)
        if brief is None:
            raise OvernightBriefNotFoundError(f"Overnight brief not found: {brief_id}")
        return self._upgrade_legacy_watchlist_shape(brief)

    def get_event_detail(self, event_id: str, brief_id: str | None = None) -> dict[str, Any]:
        brief = self.get_brief_by_id(brief_id) if brief_id else self.get_latest_brief()
        for event in brief.top_events:
            if str(event.get("event_id")) == event_id:
                source_links = self._extract_event_source_links(brief, event_id, event)
                evidence_items = self._build_event_evidence_items(
                    event=event,
                    source_links=source_links,
                )
                judgment = self.judgment_service.build_judgment(
                    brief=brief,
                    event=event,
                    evidence_items=evidence_items,
                )
                return {
                    "event_id": event_id,
                    "priority_level": str(event.get("priority_level", "")),
                    "core_fact": str(event.get("core_fact", "")),
                    "summary": str(event.get("summary", "")),
                    "why_it_matters": str(event.get("why_it_matters", "")),
                    "confidence": float(event.get("confidence", 0.0) or 0.0),
                    "source_links": source_links,
                    "evidence_items": evidence_items,
                    "judgment_summary": judgment.summary,
                    "judgment_mode": judgment.mode,
                }

        raise OvernightEventNotFoundError(event_id)

    def get_brief_delta(self, brief_id: str | None = None) -> dict[str, Any]:
        current = self.get_brief_by_id(brief_id) if brief_id else self.get_latest_brief()
        previous = self.repo.get_previous_morning_brief(current.brief_id)

        current_events = list(current.top_events or [])
        previous_events = list(previous.top_events or []) if previous is not None else []
        current_map = {
            self._build_history_event_key(str(event.get("core_fact", ""))): event
            for event in current_events
            if str(event.get("core_fact", "")).strip()
        }
        previous_map = {
            self._build_history_event_key(str(event.get("core_fact", ""))): event
            for event in previous_events
            if str(event.get("core_fact", "")).strip()
        }

        new_events = [
            self._build_delta_item(
                event_key=event_key,
                current_event=current_event,
                previous_event=None,
                delta_type="new",
            )
            for event_key, current_event in current_map.items()
            if event_key not in previous_map
        ]
        dropped_events = [
            self._build_delta_item(
                event_key=event_key,
                current_event=None,
                previous_event=previous_event,
                delta_type="dropped",
            )
            for event_key, previous_event in previous_map.items()
            if event_key not in current_map
        ]

        intensified_events: list[dict[str, Any]] = []
        steady_events: list[dict[str, Any]] = []
        cooling_events: list[dict[str, Any]] = []
        for event_key, current_event in current_map.items():
            previous_event = previous_map.get(event_key)
            if previous_event is None:
                continue
            delta_type = self._classify_delta_type(current_event, previous_event)
            item = self._build_delta_item(
                event_key=event_key,
                current_event=current_event,
                previous_event=previous_event,
                delta_type=delta_type,
            )
            if delta_type == "intensified":
                intensified_events.append(item)
            elif delta_type == "cooling":
                cooling_events.append(item)
            else:
                steady_events.append(item)

        new_events.sort(key=self._delta_sort_key)
        intensified_events.sort(key=self._delta_sort_key)
        steady_events.sort(key=self._delta_sort_key)
        cooling_events.sort(key=self._delta_sort_key)
        dropped_events.sort(key=self._delta_sort_key)

        return {
            "brief_id": current.brief_id,
            "digest_date": current.digest_date,
            "previous_brief_id": previous.brief_id if previous is not None else None,
            "previous_digest_date": previous.digest_date if previous is not None else None,
            "summary": self._build_delta_summary(
                current=current,
                previous=previous,
                new_events=new_events,
                intensified_events=intensified_events,
                steady_events=steady_events,
                cooling_events=cooling_events,
                dropped_events=dropped_events,
            ),
            "new_events": new_events,
            "intensified_events": intensified_events,
            "steady_events": steady_events,
            "cooling_events": cooling_events,
            "dropped_events": dropped_events,
        }

    def list_history(self, *, page: int, limit: int, q: str | None = None) -> dict[str, Any]:
        history = self.repo.list_morning_briefs(page=page, limit=limit)
        if int(history.get("total", 0) or 0) > 0:
            if not self._normalize_query(q):
                return history
            all_history = self.repo.list_morning_briefs(
                page=1,
                limit=self.HISTORY_AGGREGATION_LIMIT,
            )
            items = [
                item
                for item in all_history.get("items", [])
                if self._matches_query(
                    q,
                    [
                        item.get("brief_id"),
                        item.get("digest_date"),
                        item.get("cutoff_time"),
                        item.get("topline"),
                    ],
                )
            ]
            return self._paginate_items(items, page=page, limit=limit)

        # Fallback to generating the latest brief once, then reloading persisted history.
        self.get_latest_brief()
        history = self.repo.list_morning_briefs(page=page, limit=limit)
        if int(history.get("total", 0) or 0) > 0:
            if not self._normalize_query(q):
                return history
            all_history = self.repo.list_morning_briefs(
                page=1,
                limit=self.HISTORY_AGGREGATION_LIMIT,
            )
            items = [
                item
                for item in all_history.get("items", [])
                if self._matches_query(
                    q,
                    [
                        item.get("brief_id"),
                        item.get("digest_date"),
                        item.get("cutoff_time"),
                        item.get("topline"),
                    ],
                )
            ]
            return self._paginate_items(items, page=page, limit=limit)

        raise OvernightBriefNotFoundError("No overnight brief history is available yet.")

    def _upgrade_legacy_watchlist_shape(
        self,
        brief: MorningExecutiveBrief,
    ) -> MorningExecutiveBrief:
        watchlist = list(brief.today_watchlist or [])
        if not watchlist:
            return brief

        first_bucket = watchlist[0]
        if isinstance(first_bucket, dict) and first_bucket.get("bucket_key"):
            return brief

        rebuilt = build_morning_brief(
            events=[
                RankedEvent(
                    event_id=str(event.get("event_id", "")).strip(),
                    core_fact=str(event.get("core_fact", "")).strip(),
                    priority_level=str(event.get("priority_level", "")).strip(),
                    summary=str(event.get("summary", "")).strip(),
                    why_it_matters=str(event.get("why_it_matters", "")).strip(),
                    confidence=float(event.get("confidence", 0.0) or 0.0),
                    market_reaction=str(event.get("market_reaction", "")).strip(),
                    source_links=[
                        str(link).strip()
                        for link in (event.get("source_links", []) or [])
                        if str(link).strip()
                    ],
                )
                for event in brief.top_events or []
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date=brief.digest_date,
            cutoff_time=brief.cutoff_time,
            generated_at=brief.generated_at,
        )
        return replace(brief, today_watchlist=rebuilt.today_watchlist)

    def list_event_history(self, *, page: int, limit: int, q: str | None = None) -> dict[str, Any]:
        briefs = self._load_history_briefs_for_aggregation()
        grouped: dict[str, dict[str, Any]] = {}

        for brief in briefs:
            for event in brief.top_events or []:
                core_fact = str(event.get("core_fact", "")).strip()
                if not core_fact:
                    continue

                event_key = self._build_history_event_key(core_fact)
                confidence = float(event.get("confidence", 0.0) or 0.0)
                occurrence = {
                    "brief_id": brief.brief_id,
                    "digest_date": brief.digest_date,
                    "event_id": str(event.get("event_id", "")).strip(),
                    "priority_level": str(event.get("priority_level", "")).strip(),
                    "confidence": confidence,
                }

                bucket = grouped.get(event_key)
                if bucket is None:
                    bucket = {
                        "event_key": event_key,
                        "core_fact": core_fact,
                        "occurrence_count": 0,
                        "latest_brief_id": brief.brief_id,
                        "latest_digest_date": brief.digest_date,
                        "latest_event_id": occurrence["event_id"] or None,
                        "latest_priority_level": occurrence["priority_level"],
                        "average_confidence": 0.0,
                        "occurrences": [],
                        "_confidence_sum": 0.0,
                    }
                    grouped[event_key] = bucket

                bucket["occurrence_count"] += 1
                bucket["_confidence_sum"] += confidence
                bucket["occurrences"].append(occurrence)

        items = []
        for bucket in grouped.values():
            occurrence_count = int(bucket["occurrence_count"] or 0)
            confidence_sum = float(bucket.pop("_confidence_sum", 0.0) or 0.0)
            bucket["average_confidence"] = (
                confidence_sum / occurrence_count
                if occurrence_count > 0
                else 0.0
            )
            bucket["occurrences"] = bucket["occurrences"][:5]
            items.append(bucket)

        items.sort(
            key=lambda item: (
                int(item.get("occurrence_count", 0) or 0),
                str(item.get("latest_digest_date", "") or ""),
                -self._priority_sort_value(str(item.get("latest_priority_level", "") or "")),
            ),
            reverse=True,
        )
        normalized_query = self._normalize_query(q)
        if normalized_query:
            items = [
                item
                for item in items
                if self._matches_query(
                    normalized_query,
                    [
                        item.get("event_key"),
                        item.get("core_fact"),
                        item.get("latest_digest_date"),
                        item.get("latest_priority_level"),
                    ],
                )
            ]
        return self._paginate_items(items, page=page, limit=limit)

    def list_topic_history(self, *, page: int, limit: int, q: str | None = None) -> dict[str, Any]:
        briefs = self._load_history_briefs_for_aggregation()
        grouped: dict[str, dict[str, Any]] = {}

        for brief in briefs:
            for topic_key, config in self.TOPIC_HISTORY_CONFIG.items():
                field_name = str(config["field_name"])
                cards = list(getattr(brief, field_name) or [])
                item_count = len(cards)
                if item_count <= 0:
                    continue

                occurrence = {
                    "brief_id": brief.brief_id,
                    "digest_date": brief.digest_date,
                    "item_count": item_count,
                }
                bucket = grouped.get(topic_key)
                if bucket is None:
                    bucket = {
                        "topic_key": topic_key,
                        "title": str(config["title"]),
                        "occurrence_count": 0,
                        "total_item_count": 0,
                        "latest_brief_id": brief.brief_id,
                        "latest_digest_date": brief.digest_date,
                        "latest_item_count": item_count,
                        "recent_briefs": [],
                    }
                    grouped[topic_key] = bucket

                bucket["occurrence_count"] += 1
                bucket["total_item_count"] += item_count
                bucket["recent_briefs"].append(occurrence)

        items = list(grouped.values())
        for item in items:
            item["recent_briefs"] = item["recent_briefs"][:5]

        items.sort(
            key=lambda item: (
                int(item.get("occurrence_count", 0) or 0),
                int(item.get("total_item_count", 0) or 0),
                str(item.get("latest_digest_date", "") or ""),
            ),
            reverse=True,
        )
        normalized_query = self._normalize_query(q)
        if normalized_query:
            items = [
                item
                for item in items
                if self._matches_query(
                    normalized_query,
                    [
                        item.get("topic_key"),
                        item.get("title"),
                        item.get("latest_digest_date"),
                    ],
                )
            ]
        return self._paginate_items(items, page=page, limit=limit)

    def list_sources(self) -> dict[str, Any]:
        sources = build_default_source_registry()
        enabled_source_ids = self._get_enabled_source_ids(sources)

        return {
            "total": len(sources),
            "mission_critical": sum(1 for source in sources if source.is_mission_critical),
            "items": [
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "organization_type": source.organization_type,
                    "source_class": source.source_class,
                    "entry_type": source.entry_type,
                    "entry_urls": list(source.entry_urls),
                    "priority": source.priority,
                    "poll_interval_seconds": source.poll_interval_seconds,
                    "is_mission_critical": source.is_mission_critical,
                    "is_enabled": source.source_id in enabled_source_ids,
                    "coverage_tier": source.coverage_tier,
                    "region_focus": source.region_focus,
                    "coverage_focus": source.coverage_focus,
                }
                for source in sources
            ],
        }

    def list_recent_source_items(self, *, limit: int = 20) -> dict[str, Any]:
        return self.source_capture_service.list_recent_items(limit=limit)

    def refresh_source_items(
        self,
        *,
        limit_per_source: int = 2,
        max_sources: int = 10,
        recent_limit: int = 20,
    ) -> dict[str, Any]:
        return self.source_capture_service.refresh(
            limit_per_source=limit_per_source,
            max_sources=max_sources,
            recent_limit=recent_limit,
        )

    def get_health_summary(self) -> dict[str, Any]:
        sources = build_default_source_registry()
        enabled_source_ids = self._get_enabled_source_ids(sources)
        enabled_sources = [
            source for source in sources if str(source.source_id) in enabled_source_ids
        ]
        latest_brief = self.repo.get_latest_morning_brief()
        history = self.repo.list_morning_briefs(page=1, limit=1)
        notification_service = NotificationService()
        configured_channels = [
            channel.value
            for channel in notification_service.get_available_channels()
        ]
        coverage_tier_counts = Counter(
            source.coverage_tier
            for source in enabled_sources
            if str(source.coverage_tier).strip()
        )
        source_class_counts = Counter(
            source.source_class
            for source in enabled_sources
            if str(source.source_class).strip()
        )

        return {
            "source_health": {
                "total_sources": len(sources),
                "mission_critical_sources": sum(
                    1 for source in sources if source.is_mission_critical
                ),
                "whitelisted_sources": len(enabled_source_ids),
                "enabled_mission_critical_sources": sum(
                    1 for source in enabled_sources if source.is_mission_critical
                ),
                "coverage_tier_counts": dict(coverage_tier_counts),
                "source_class_counts": dict(source_class_counts),
                "coverage_gaps": self._build_source_coverage_gaps(
                    enabled_sources=enabled_sources,
                    coverage_tier_counts=coverage_tier_counts,
                    source_class_counts=source_class_counts,
                ),
            },
            "pipeline_health": {
                "brief_count": int(history.get("total", 0) or 0),
                "latest_brief_id": latest_brief.brief_id if latest_brief is not None else None,
                "latest_digest_date": latest_brief.digest_date if latest_brief is not None else None,
                "latest_generated_at": latest_brief.generated_at if latest_brief is not None else None,
            },
            "content_quality": self._build_content_quality_summary(latest_brief),
            "delivery_health": {
                "notification_available": notification_service.is_available(),
                "configured_channels": configured_channels,
                "channel_names": notification_service.get_channel_names(),
                "overnight_brief_enabled": get_config().overnight_brief_enabled,
            },
        }

    def _get_enabled_source_ids(self, sources: list[Any]) -> set[str]:
        whitelist = {
            item.strip()
            for item in get_config().overnight_source_whitelist.split(",")
            if item.strip()
        }
        if not whitelist:
            return {str(source.source_id) for source in sources}
        return {
            str(source.source_id)
            for source in sources
            if str(source.source_id) in whitelist
        }

    def _build_content_quality_summary(
        self,
        brief: MorningExecutiveBrief | None,
    ) -> dict[str, Any]:
        if brief is None:
            return {
                "top_event_count": 0,
                "average_confidence": 0.0,
                "events_needing_confirmation": 0,
                "events_with_primary_sources": 0,
                "events_without_primary_sources": 0,
                "duplicate_core_fact_count": 0,
                "minimum_evidence_gate_passed": False,
                "duplication_gate_passed": True,
            }

        top_events = list(brief.top_events or [])
        event_ids = {
            str(item.get("event_id", ""))
            for item in top_events
            if str(item.get("event_id", "")).strip()
        }
        source_event_ids = {
            str(item.get("event_id", ""))
            for item in (brief.primary_sources or [])
            if str(item.get("event_id", "")).strip() and item.get("links")
        }
        confidence_values = [
            float(item.get("confidence", 0.0) or 0.0)
            for item in top_events
        ]
        core_facts = [
            str(item.get("core_fact", "")).strip()
            for item in top_events
            if str(item.get("core_fact", "")).strip()
        ]

        top_event_count = len(top_events)
        events_with_primary_sources = len(event_ids & source_event_ids)
        duplicate_core_fact_count = len(core_facts) - len(set(core_facts))

        return {
            "top_event_count": top_event_count,
            "average_confidence": (
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else 0.0
            ),
            "events_needing_confirmation": len(brief.need_confirmation or []),
            "events_with_primary_sources": events_with_primary_sources,
            "events_without_primary_sources": max(top_event_count - events_with_primary_sources, 0),
            "duplicate_core_fact_count": max(duplicate_core_fact_count, 0),
            "minimum_evidence_gate_passed": top_event_count > 0 and events_with_primary_sources == top_event_count,
            "duplication_gate_passed": duplicate_core_fact_count == 0,
        }

    def _build_source_coverage_gaps(
        self,
        *,
        enabled_sources: list[Any],
        coverage_tier_counts: Counter[str],
        source_class_counts: Counter[str],
    ) -> list[str]:
        gaps: list[str] = []
        if coverage_tier_counts.get("official_policy", 0) < 3:
            gaps.append("官方政策源覆盖仍偏薄")
        if coverage_tier_counts.get("official_data", 0) < 2:
            gaps.append("官方数据源覆盖不足")
        if coverage_tier_counts.get("editorial_media", 0) < 2:
            gaps.append("当前只覆盖少量主流媒体入口")
        if source_class_counts.get("calendar", 0) == 0:
            gaps.append("当前没有日历型 mission-critical 源")
        if not any(source.is_mission_critical for source in enabled_sources):
            gaps.append("当前没有启用 mission-critical 源")
        return gaps

    def _extract_event_source_links(
        self,
        brief: MorningExecutiveBrief,
        event_id: str,
        event: dict[str, Any],
    ) -> list[str]:
        embedded_links = [
            str(link).strip()
            for link in (event.get("source_links", []) or [])
            if str(link).strip()
        ]
        if embedded_links:
            return embedded_links

        for item in brief.primary_sources or []:
            if str(item.get("event_id", "")).strip() != event_id:
                continue
            return [
                str(link).strip()
                for link in (item.get("links", []) or [])
                if str(link).strip()
            ]
        return []

    def _build_event_evidence_items(
        self,
        *,
        event: dict[str, Any],
        source_links: list[str],
    ) -> list[dict[str, Any]]:
        if not source_links:
            return []

        registry = build_default_source_registry()
        fallback_headline = str(event.get("core_fact", "")).strip() or "Overnight evidence"

        return [
            {
                "headline": (
                    stored_item.title.strip()
                    if stored_item is not None and stored_item.title.strip()
                    else self._derive_evidence_headline(link, fallback=fallback_headline)
                ),
                "source_name": matched.display_name if matched is not None else self._read_hostname(link) or "未知来源",
                "url": link,
                "summary": self._build_evidence_summary(event, matched, stored_item=stored_item),
                "source_type": self._derive_source_type(matched),
                "coverage_tier": matched.coverage_tier if matched is not None else "",
                "source_class": matched.source_class if matched is not None else "",
            }
            for link in source_links
            for matched in [self._match_registry_source(link, registry)]
            for stored_item in [
                self.source_excerpt_service.resolve(
                    url=link,
                    fallback_title=fallback_headline,
                    source_id=matched.source_id if matched is not None else self._read_hostname(link) or "event_detail_fetch",
                )
            ]
        ]

    def _match_registry_source(self, url: str, registry: list[Any]) -> Any | None:
        hostname = self._normalize_hostname(self._read_hostname(url))
        if not hostname:
            return None

        for source in registry:
            entry_hostnames = [
                self._normalize_hostname(self._read_hostname(entry_url))
                for entry_url in source.entry_urls
            ]
            if hostname in entry_hostnames:
                return source
            if hostname.endswith("reuters.com") and "Reuters" in source.display_name:
                return source
            if hostname.endswith("apnews.com") and source.display_name.startswith("AP"):
                return source
            if hostname.endswith("cnbc.com") and source.display_name.startswith("CNBC"):
                return source
        return None

    def _build_evidence_summary(
        self,
        event: dict[str, Any],
        matched_source: Any | None,
        *,
        stored_item: Any | None = None,
    ) -> str:
        parts: list[str] = []
        stored_summary = str(getattr(stored_item, "summary", "") or "").strip()
        if stored_summary:
            parts.append(stored_summary)
        summary = str(event.get("summary", "")).strip()
        why_it_matters = str(event.get("why_it_matters", "")).strip()
        if summary and summary not in parts:
            parts.append(summary)
        if why_it_matters and why_it_matters not in parts:
            parts.append(why_it_matters)
        if matched_source is not None and matched_source.coverage_focus:
            parts.append(f"来源定位: {matched_source.coverage_focus}")

        combined = " ".join(part for part in parts if part).strip()
        if not combined:
            return "当前只有链接证据，仍需结合开盘反馈确认。"
        if len(combined) > 220:
            return f"{combined[:217].rstrip()}..."
        return combined

    def _derive_evidence_headline(self, url: str, *, fallback: str) -> str:
        try:
            path = [part for part in urlparse(url).path.split("/") if part]
            if not path:
                return fallback
            candidate = unquote(path[-1]).strip()
            candidate = re.sub(r"\.[A-Za-z0-9]+$", "", candidate)
            candidate = re.sub(r"[-_]+", " ", candidate).strip()
            if len(candidate) < 6:
                return fallback
            return re.sub(r"\b\w", lambda match: match.group(0).upper(), candidate)
        except Exception:
            return fallback

    def _derive_source_type(self, matched_source: Any | None) -> str:
        if matched_source is None:
            return "unknown"
        if str(matched_source.coverage_tier).startswith("official") or str(matched_source.organization_type).startswith("official"):
            return "official"
        if matched_source.coverage_tier == "editorial_media" or matched_source.organization_type in {"wire_media", "editorial_media"}:
            return "media"
        return "unknown"

    def _read_hostname(self, url: str) -> str:
        try:
            return urlparse(url).hostname or ""
        except ValueError:
            return ""

    def _normalize_hostname(self, value: str) -> str:
        return value.replace("www.", "").strip().lower()

    def submit_feedback(
        self,
        *,
        target_type: str,
        target_id: str,
        brief_id: str | None,
        event_id: str | None,
        feedback_type: str,
        comment: str,
    ) -> dict[str, Any]:
        normalized_target_type = target_type.strip().lower()
        normalized_feedback_type = feedback_type.strip().lower()
        normalized_target_id = target_id.strip()

        if normalized_target_type not in {"brief", "event"}:
            raise ValueError("target_type must be 'brief' or 'event'.")
        if not normalized_target_id:
            raise ValueError("target_id is required.")
        if normalized_feedback_type not in self.VALID_FEEDBACK_TYPES:
            raise ValueError(f"Unsupported feedback_type: {feedback_type}")

        feedback_id = self.repo.save_feedback(
            target_type=normalized_target_type,
            target_id=normalized_target_id,
            brief_id=brief_id.strip() if isinstance(brief_id, str) and brief_id.strip() else None,
            event_id=event_id.strip() if isinstance(event_id, str) and event_id.strip() else None,
            feedback_type=normalized_feedback_type,
            comment=comment.strip(),
        )

        items = self.repo.list_feedback(
            page=1,
            limit=1,
            target_type=None,
            status=None,
        ).get("items", [])
        if items:
            latest = items[0]
            if int(latest.get("feedback_id", 0) or 0) == feedback_id:
                return latest

        return {
            "feedback_id": feedback_id,
            "target_type": normalized_target_type,
            "target_id": normalized_target_id,
            "brief_id": brief_id,
            "event_id": event_id,
            "feedback_type": normalized_feedback_type,
            "comment": comment.strip(),
            "status": "pending_review",
            "created_at": None,
        }

    def list_feedback(
        self,
        *,
        page: int,
        limit: int,
        target_type: str | None,
        status: str | None,
    ) -> dict[str, Any]:
        normalized_target_type = (
            target_type.strip().lower()
            if isinstance(target_type, str) and target_type.strip()
            else None
        )
        normalized_status = (
            status.strip().lower()
            if isinstance(status, str) and status.strip()
            else None
        )

        if normalized_target_type is not None and normalized_target_type not in {"brief", "event"}:
            raise ValueError("target_type must be 'brief' or 'event'.")

        return self.repo.list_feedback(
            page=page,
            limit=limit,
            target_type=normalized_target_type,
            status=normalized_status,
        )

    def update_feedback_status(
        self,
        feedback_id: int,
        *,
        status: str,
    ) -> dict[str, Any]:
        normalized_status = status.strip().lower()

        if not normalized_status:
            raise ValueError("status is required.")
        if normalized_status not in self.VALID_FEEDBACK_STATUSES:
            raise ValueError(
                "status must be one of: pending_review, reviewed, dismissed."
            )

        item = self.repo.update_feedback_status(
            feedback_id,
            status=normalized_status,
        )
        if item is None:
            raise LookupError(f"Overnight feedback not found: {feedback_id}")
        return item

    def _load_history_briefs_for_aggregation(self) -> list[MorningExecutiveBrief]:
        history = self.repo.list_morning_briefs(
            page=1,
            limit=self.HISTORY_AGGREGATION_LIMIT,
        )
        if int(history.get("total", 0) or 0) <= 0:
            self.get_latest_brief()
            history = self.repo.list_morning_briefs(
                page=1,
                limit=self.HISTORY_AGGREGATION_LIMIT,
            )

        brief_ids = [
            str(item.get("brief_id", "")).strip()
            for item in history.get("items", [])
            if str(item.get("brief_id", "")).strip()
        ]
        briefs = [
            brief
            for brief_id in brief_ids
            for brief in [self.repo.get_morning_brief(brief_id)]
            if brief is not None
        ]
        if briefs:
            return briefs

        raise OvernightBriefNotFoundError("No overnight brief history is available yet.")

    def _build_history_event_key(self, core_fact: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", core_fact.strip().lower())
        normalized = normalized.strip("-")
        return normalized or "event"

    def _paginate_items(
        self,
        items: list[dict[str, Any]],
        *,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        offset = max(page - 1, 0) * limit
        return {
            "page": page,
            "limit": limit,
            "total": len(items),
            "items": items[offset : offset + limit],
        }

    def _normalize_query(self, q: str | None) -> str | None:
        if not isinstance(q, str):
            return None
        normalized = q.strip().lower()
        return normalized or None

    def _matches_query(self, q: str | None, values: list[Any]) -> bool:
        normalized_query = self._normalize_query(q)
        if normalized_query is None:
            return True
        haystack = " ".join(
            str(value).strip().lower()
            for value in values
            if value is not None and str(value).strip()
        )
        return normalized_query in haystack

    def _priority_sort_value(self, priority_level: str) -> int:
        ranking = {
            "P0": 0,
            "P1": 1,
            "P2": 2,
            "P3": 3,
        }
        return ranking.get(priority_level.upper(), 9)

    def _classify_delta_type(
        self,
        current_event: dict[str, Any],
        previous_event: dict[str, Any],
    ) -> str:
        current_priority = self._priority_sort_value(str(current_event.get("priority_level", "") or ""))
        previous_priority = self._priority_sort_value(str(previous_event.get("priority_level", "") or ""))
        current_confidence = float(current_event.get("confidence", 0.0) or 0.0)
        previous_confidence = float(previous_event.get("confidence", 0.0) or 0.0)

        if current_priority < previous_priority or current_confidence >= previous_confidence + 0.08:
            return "intensified"
        if current_priority > previous_priority or current_confidence + 0.08 <= previous_confidence:
            return "cooling"
        return "steady"

    def _build_delta_item(
        self,
        *,
        event_key: str,
        current_event: dict[str, Any] | None,
        previous_event: dict[str, Any] | None,
        delta_type: str,
    ) -> dict[str, Any]:
        current_priority_level = str((current_event or {}).get("priority_level", "") or "")
        previous_priority_level = str((previous_event or {}).get("priority_level", "") or "")
        current_confidence = float((current_event or {}).get("confidence", 0.0) or 0.0)
        previous_confidence = float((previous_event or {}).get("confidence", 0.0) or 0.0)
        core_fact = str(
            (current_event or {}).get("core_fact")
            or (previous_event or {}).get("core_fact")
            or ""
        ).strip()

        return {
            "event_key": event_key,
            "core_fact": core_fact,
            "current_event_id": str((current_event or {}).get("event_id", "") or "") or None,
            "previous_event_id": str((previous_event or {}).get("event_id", "") or "") or None,
            "current_priority_level": current_priority_level,
            "previous_priority_level": previous_priority_level,
            "current_confidence": current_confidence,
            "previous_confidence": previous_confidence,
            "delta_type": delta_type,
            "delta_summary": self._build_delta_item_summary(
                delta_type=delta_type,
                current_priority_level=current_priority_level,
                previous_priority_level=previous_priority_level,
                current_confidence=current_confidence,
                previous_confidence=previous_confidence,
            ),
        }

    def _build_delta_item_summary(
        self,
        *,
        delta_type: str,
        current_priority_level: str,
        previous_priority_level: str,
        current_confidence: float,
        previous_confidence: float,
    ) -> str:
        if delta_type == "new":
            return "First appearance in the current brief."
        if delta_type == "dropped":
            return "Present in the previous brief but not in the current one."
        if delta_type == "steady":
            return "Priority and confidence stayed broadly unchanged."
        if current_priority_level and previous_priority_level and current_priority_level != previous_priority_level:
            return f"Priority moved from {previous_priority_level} to {current_priority_level}."
        return (
            f"Confidence moved from {int(round(previous_confidence * 100))}% "
            f"to {int(round(current_confidence * 100))}%."
        )

    def _build_delta_summary(
        self,
        *,
        current: MorningExecutiveBrief,
        previous: MorningExecutiveBrief | None,
        new_events: list[dict[str, Any]],
        intensified_events: list[dict[str, Any]],
        steady_events: list[dict[str, Any]],
        cooling_events: list[dict[str, Any]],
        dropped_events: list[dict[str, Any]],
    ) -> str:
        if previous is None:
            return (
                f"No previous brief exists before {current.digest_date}; "
                f"treat the current top events as the first visible baseline."
            )
        return (
            "Compared with the previous brief: "
            f"{len(new_events)} new, "
            f"{len(intensified_events)} intensified, "
            f"{len(steady_events)} steady, "
            f"{len(cooling_events)} cooling, "
            f"{len(dropped_events)} dropped."
        )

    def _delta_sort_key(self, item: dict[str, Any]) -> tuple[int, float, str]:
        priority = str(item.get("current_priority_level") or item.get("previous_priority_level") or "")
        confidence = float(item.get("current_confidence") or item.get("previous_confidence") or 0.0)
        return (
            self._priority_sort_value(priority),
            -confidence,
            str(item.get("core_fact", "") or ""),
        )
