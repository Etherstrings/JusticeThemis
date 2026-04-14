# -*- coding: utf-8 -*-
"""Standalone overnight event construction from normalized items."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Any


_TRADE_TOPIC_PATTERN = re.compile(
    r"\b(?:tariff|trade action|trade representative|ustr|export control|import restriction|sanction|procurement|supply chain)\b",
    re.IGNORECASE,
)
_RATES_TOPIC_PATTERN = re.compile(
    r"\b(?:inflation|rate|rates|fomc|yield|yields|treasury|cpi|ppi|employment|payroll)\b",
    re.IGNORECASE,
)
_ENERGY_TOPIC_PATTERN = re.compile(
    r"\b(?:oil|crude|shipping|freight|hormuz|lng|natural gas|energy)\b",
    re.IGNORECASE,
)
_SEMICONDUCTOR_TOPIC_PATTERN = re.compile(
    r"\b(?:semiconductor|chip|chips|wafer|gpu|critical mineral)\b",
    re.IGNORECASE,
)
_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("trade_policy", _TRADE_TOPIC_PATTERN),
    ("rates_macro", _RATES_TOPIC_PATTERN),
    ("energy_shipping", _ENERGY_TOPIC_PATTERN),
    ("semiconductor_supply_chain", _SEMICONDUCTOR_TOPIC_PATTERN),
)
_EVENT_KEYWORD_PATTERN = re.compile(r"[a-z0-9]+")
_EVENT_KEYWORD_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "from",
        "into",
        "while",
        "said",
        "says",
        "say",
        "official",
        "officials",
        "statement",
        "statements",
        "release",
        "releases",
        "reported",
        "report",
        "reports",
        "could",
        "would",
        "after",
        "before",
        "remain",
        "remains",
        "place",
        "policy",
        "policies",
        "update",
        "updates",
        "news",
        "white",
        "house",
        "federal",
        "reserve",
        "ustr",
        "press",
        "business",
        "about",
        "their",
        "there",
        "where",
        "which",
        "this",
        "have",
        "been",
        "still",
        "next",
        "path",
        "markets",
        "market",
    }
)
_EVENT_IDENTITY_STOPWORDS = frozenset(
    {
        "agencies",
        "agency",
        "billion",
        "chains",
        "chain",
        "decrease",
        "decreased",
        "decreases",
        "deficit",
        "discussion",
        "discussed",
        "export",
        "exports",
        "import",
        "imports",
        "increase",
        "increased",
        "increases",
        "keep",
        "keeps",
        "review",
        "studies",
        "study",
        "supply",
        "under",
        "widened",
        "widens",
    }
)
_EVENT_CLUSTER_COVERAGE_ORDER = {
    "official_policy": 0,
    "official_data": 1,
    "editorial_media": 2,
}
_EVENT_CLUSTER_AUTHORITY_ORDER = {
    "primary_official": 0,
    "editorial_context": 1,
    "other": 2,
}


class EventEngine:
    def build(self, items: list[dict[str, object]]) -> dict[str, object]:
        item_by_id = {
            int(item.get("item_id", 0) or 0): item
            for item in items
            if int(item.get("item_id", 0) or 0)
        }
        adjacency: dict[int, set[int]] = {item_id: set() for item_id in item_by_id}
        ordered_ids = sorted(item_by_id)

        for index, item_id in enumerate(ordered_ids):
            item = item_by_id[item_id]
            for other_id in ordered_ids[index + 1 :]:
                other_item = item_by_id[other_id]
                if self.items_belong_to_same_event(item, other_item):
                    adjacency[item_id].add(other_id)
                    adjacency[other_id].add(item_id)

        item_event_index: dict[int, dict[str, object]] = {}
        events: list[dict[str, object]] = []
        visited: set[int] = set()
        for item_id in ordered_ids:
            if item_id in visited:
                continue
            stack = [item_id]
            component_ids: list[int] = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component_ids.append(current)
                for neighbor in sorted(adjacency.get(current, set()), reverse=True):
                    if neighbor not in visited:
                        stack.append(neighbor)
            members = [item_by_id[current_id] for current_id in component_ids]
            event = self._event_record(members)
            events.append(event)
            cluster_payload = self._cluster_payload(event)
            for current_id in component_ids:
                item_event_index[current_id] = dict(cluster_payload)

        return {
            "events": events,
            "item_event_index": item_event_index,
        }

    def build_item_event_index(self, items: list[dict[str, object]]) -> dict[int, dict[str, object]]:
        return dict(self.build(items)["item_event_index"])

    def items_belong_to_same_event(
        self,
        item: dict[str, object],
        other_item: dict[str, object],
    ) -> bool:
        if not self._event_time_is_close(item, other_item):
            return False
        shared_topics = self.item_topics(item) & self.item_topics(other_item)
        shared_fact_signatures = self._item_fact_signatures(item) & self._item_fact_signatures(other_item)
        shared_identity_keywords = self._item_identity_keywords(item) & self._item_identity_keywords(other_item)
        shared_entities = self._item_entity_names(item) & self._item_entity_names(other_item)
        shared_directions = self.item_direction_signatures(item) & self.item_direction_signatures(other_item)
        if shared_topics and shared_fact_signatures:
            return True
        if shared_topics and len(shared_identity_keywords) >= 2:
            return True
        if shared_topics and shared_entities and shared_identity_keywords:
            return True
        if shared_fact_signatures and shared_entities:
            return True
        if shared_fact_signatures and len(shared_identity_keywords) >= 2:
            return True
        if shared_topics and shared_directions and shared_identity_keywords:
            return True
        return False

    def item_topics(self, item: dict[str, object]) -> set[str]:
        text = " ".join(
            part
            for part in (
                str(item.get("source_id", "")).strip(),
                str(item.get("title", "")).strip(),
                str(item.get("summary", "")).strip(),
                str(item.get("impact_summary", "")).strip(),
            )
            if part
        )
        topics: set[str] = set()
        for topic, pattern in _TOPIC_PATTERNS:
            if pattern.search(text):
                topics.add(topic)
        return topics

    def item_direction_signatures(self, item: dict[str, object]) -> set[tuple[str, str]]:
        signatures: set[tuple[str, str]] = set()
        for implication in list(item.get("market_implications", []) or []):
            implication_type = str(implication.get("implication_type", "")).strip()
            direction = str(implication.get("direction", "")).strip()
            if implication_type and direction:
                signatures.add((implication_type, direction))
        return signatures

    def item_key_number_index(self, item: dict[str, object]) -> dict[tuple[str, str], dict[str, str]]:
        index: dict[tuple[str, str], dict[str, str]] = {}
        for key_number in list(item.get("key_numbers", []) or []):
            metric = str(key_number.get("metric", "")).strip()
            if not metric:
                continue
            subject = str(key_number.get("subject", "") or "").strip()
            if not self._numeric_fact_is_compare_ready(metric=metric, subject=subject):
                continue
            index[(metric, subject)] = {
                "value_text": str(key_number.get("value_text", "")).strip(),
            }
        return index

    def _event_record(self, members: list[dict[str, object]]) -> dict[str, object]:
        ordered_members = sorted(members, key=self._event_cluster_member_sort_key)
        primary_item = ordered_members[0]
        member_item_ids = [int(item.get("item_id", 0) or 0) for item in ordered_members]
        member_source_ids = self._unique_preserving_order(
            [str(item.get("source_id", "")).strip() for item in ordered_members]
        )
        topic_tags = self._unique_preserving_order(
            [topic for item in ordered_members for topic in sorted(self.item_topics(item))]
        )
        fact_signatures = self._unique_preserving_order(
            [signature for item in ordered_members for signature in sorted(self._item_fact_signatures(item))]
        )
        event_id = self._event_cluster_id(
            topic_tags=topic_tags,
            fact_signatures=fact_signatures,
            members=ordered_members,
        )
        official_source_ids = {
            str(item.get("source_id", "")).strip()
            for item in ordered_members
            if str(item.get("coverage_tier", "")).strip() in {"official_policy", "official_data"}
        }
        return {
            "event_id": event_id,
            "cluster_id": event_id,
            "event_status": self._event_cluster_status(ordered_members),
            "cluster_status": self._event_cluster_status(ordered_members),
            "primary_item_id": int(primary_item.get("item_id", 0) or 0),
            "supporting_item_ids": member_item_ids[1:],
            "member_item_ids": member_item_ids,
            "member_source_ids": member_source_ids,
            "item_count": len(member_item_ids),
            "source_count": len(member_source_ids),
            "official_source_count": len(official_source_ids),
            "latest_published_at": self._latest_published_at(ordered_members),
            "topic_tags": topic_tags[:4],
            "fact_signatures": fact_signatures[:4],
            "affected_assets": self._affected_assets(ordered_members),
            "key_facts": self._event_key_facts(ordered_members),
        }

    def _cluster_payload(self, event: dict[str, object]) -> dict[str, object]:
        return {
            "cluster_id": str(event.get("event_id", "")).strip(),
            "cluster_status": str(event.get("event_status", "")).strip(),
            "primary_item_id": int(event.get("primary_item_id", 0) or 0),
            "item_count": int(event.get("item_count", 0) or 0),
            "source_count": int(event.get("source_count", 0) or 0),
            "official_source_count": int(event.get("official_source_count", 0) or 0),
            "member_item_ids": list(event.get("member_item_ids", []) or []),
            "member_source_ids": list(event.get("member_source_ids", []) or []),
            "latest_published_at": event.get("latest_published_at"),
            "topic_tags": list(event.get("topic_tags", []) or []),
            "fact_signatures": list(event.get("fact_signatures", []) or []),
        }

    def _event_key_facts(self, members: list[dict[str, object]]) -> list[str]:
        facts: list[str] = []
        for item in members:
            for key_number in list(item.get("key_numbers", []) or []):
                metric = str(key_number.get("metric", "")).strip()
                value_text = str(key_number.get("value_text", "")).strip()
                subject = str(key_number.get("subject", "") or "").strip()
                if not metric or not value_text:
                    continue
                fact = f"{metric}: {value_text}"
                if subject:
                    fact += f" on {subject}"
                facts.append(fact)
        return self._unique_preserving_order(facts)[:6]

    def _affected_assets(self, members: list[dict[str, object]]) -> list[str]:
        assets: list[str] = []
        for item in members:
            for implication in list(item.get("market_implications", []) or []):
                direction = str(implication.get("direction", "")).strip()
                if direction:
                    assets.append(direction)
            for field in ("beneficiary_directions", "pressured_directions", "price_up_signals"):
                for direction in list(item.get(field, []) or []):
                    candidate = str(direction).strip()
                    if candidate:
                        assets.append(candidate)
        return self._unique_preserving_order(assets)[:8]

    def _event_cluster_member_sort_key(self, item: dict[str, object]) -> tuple[int, int, int, int]:
        coverage_tier = str(item.get("coverage_tier", "")).strip()
        authority = str(item.get("source_authority", "")).strip()
        priority = int(item.get("priority", 0) or 0)
        item_id = int(item.get("item_id", 0) or 0)
        return (
            _EVENT_CLUSTER_COVERAGE_ORDER.get(coverage_tier, 99),
            _EVENT_CLUSTER_AUTHORITY_ORDER.get(authority, 99),
            -priority,
            item_id,
        )

    def _event_cluster_status(self, members: list[dict[str, object]]) -> str:
        if len(members) <= 1:
            return "single_source"
        if self._event_cluster_has_conflict(members):
            return "conflicted"
        return "confirmed"

    def _event_cluster_has_conflict(self, members: list[dict[str, object]]) -> bool:
        numeric_values: dict[str, set[str]] = {}
        for item in members:
            for signature, payload in self.item_key_number_index(item).items():
                cluster_signature = f"{signature[0]}:{signature[1] or 'general'}"
                value_text = str(payload.get("value_text", "")).strip()
                if not value_text:
                    continue
                numeric_values.setdefault(cluster_signature, set()).add(value_text)
        if any(len(values) > 1 for values in numeric_values.values()):
            return True

        direction_stances: dict[str, set[str]] = {}
        for item in members:
            for implication in list(item.get("market_implications", []) or []):
                direction = str(implication.get("direction", "")).strip()
                implication_type = str(implication.get("implication_type", "")).strip()
                if not direction or not implication_type:
                    continue
                direction_stances.setdefault(direction, set()).add(implication_type)
        return any(len(stances) > 1 for stances in direction_stances.values())

    def _event_cluster_id(
        self,
        *,
        topic_tags: list[str],
        fact_signatures: list[str],
        members: list[dict[str, object]],
    ) -> str:
        topic = topic_tags[0] if topic_tags else "general_event"
        primary_item_id = int(members[0].get("item_id", 0) or 0)
        if fact_signatures:
            metric, _separator, subject = fact_signatures[0].partition(":")
            subject_part = self._slug(subject or "general")
            return f"{self._slug(topic)}__{self._slug(metric)}__{subject_part}__{primary_item_id}"
        keywords = self._unique_preserving_order(
            [keyword for item in members for keyword in sorted(self._item_event_keywords(item))]
        )
        if len(keywords) >= 2:
            return f"{self._slug(topic)}__{self._slug(keywords[0])}__{self._slug(keywords[1])}__{primary_item_id}"
        if keywords:
            return f"{self._slug(topic)}__{self._slug(keywords[0])}__{primary_item_id}"
        return f"{self._slug(topic)}__item_{primary_item_id}"

    def _item_fact_signatures(self, item: dict[str, object]) -> set[str]:
        signatures: set[str] = set()
        for metric, subject in self.item_key_number_index(item):
            normalized_subject = subject or "general"
            signatures.add(f"{metric}:{normalized_subject}")
        return signatures

    def _item_event_keywords(self, item: dict[str, object]) -> set[str]:
        text = " ".join(
            part
            for part in (
                str(item.get("title", "")).strip(),
                str(item.get("summary", "")).strip(),
            )
            if part
        ).lower()
        keywords: set[str] = set()
        for token in _EVENT_KEYWORD_PATTERN.findall(text):
            if len(token) < 4 or token in _EVENT_KEYWORD_STOPWORDS:
                continue
            keywords.add(token)
        return keywords

    def _item_identity_keywords(self, item: dict[str, object]) -> set[str]:
        return {
            keyword
            for keyword in self._item_event_keywords(item)
            if keyword not in _EVENT_IDENTITY_STOPWORDS
        }

    def _item_entity_names(self, item: dict[str, object]) -> set[str]:
        names: set[str] = set()
        for entity in list(item.get("entities", []) or []):
            name = (
                str(dict(entity).get("name", "") if isinstance(entity, dict) else getattr(entity, "name", ""))
                .strip()
                .lower()
            )
            if name and len(name) >= 4:
                names.add(name)
        return names

    def _event_time_is_close(self, item: dict[str, object], other_item: dict[str, object]) -> bool:
        item_time = self._event_reference_time(item)
        other_time = self._event_reference_time(other_item)
        if item_time is None or other_time is None:
            return True
        return abs((item_time - other_time).total_seconds()) <= 96 * 3600

    def _event_reference_time(self, item: dict[str, object]) -> datetime | None:
        published_at = self._parse_published_at(
            item.get("published_at"),
            precision=str(item.get("published_at_precision", "")).strip() or "missing",
        )
        if published_at is not None:
            return published_at
        return self._parse_created_at(item.get("created_at"))

    def _latest_published_at(self, members: list[dict[str, object]]) -> str | None:
        best_value: str | None = None
        best_timestamp = float("-inf")
        for item in members:
            published_at = str(item.get("published_at", "")).strip()
            timestamp = -self._source_item_sort_timestamp_for_cluster(published_at)
            if published_at and timestamp > best_timestamp:
                best_timestamp = timestamp
                best_value = published_at
        return best_value

    def _source_item_sort_timestamp_for_cluster(self, value: object) -> float:
        parsed = self._parse_sort_timestamp(value)
        if parsed is None:
            return float("inf")
        return -parsed.timestamp()

    def _slug(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return normalized or "cluster"

    def _unique_preserving_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _numeric_fact_is_compare_ready(self, *, metric: str, subject: str) -> bool:
        normalized_metric = metric.strip()
        normalized_subject = subject.strip()
        if normalized_metric == "tariff_rate":
            return True
        return bool(normalized_subject)

    def _parse_created_at(self, value: object) -> datetime | None:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace(" ", "T").replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _parse_published_at(self, value: object, *, precision: str) -> datetime | None:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        try:
            parsed = parsedate_to_datetime(candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass

        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            if precision == "date":
                try:
                    parsed = datetime.fromisoformat(f"{candidate}T00:00:00")
                except ValueError:
                    return None
            else:
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _parse_sort_timestamp(self, value: object) -> datetime | None:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        parsed = self._parse_published_at(candidate, precision="datetime")
        if parsed is not None:
            return parsed
        return self._parse_published_at(candidate, precision="date")
