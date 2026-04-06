# -*- coding: utf-8 -*-
"""Collect and expose the latest captured overnight source items."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import logging
from typing import Any

from src.config import get_config
from src.overnight.collectors.article import ArticleCollector
from src.overnight.collectors.calendar import CalendarCollector
from src.overnight.collectors.feed import FeedCollector
from src.overnight.collectors.section import SectionCollector
from src.overnight.normalizer import normalize_candidate
from src.overnight.source_registry import build_default_source_registry
from src.overnight.types import SourceCandidate, SourceDefinition
from src.repositories.overnight_repo import OvernightRepository
from src.services.overnight_source_excerpt_service import RequestsHttpClient

logger = logging.getLogger(__name__)


class OvernightSourceCaptureService:
    """Run a lightweight source refresh and expose recent captured items."""

    def __init__(
        self,
        *,
        repo: OvernightRepository,
        registry: list[SourceDefinition] | None = None,
        http_client: object | None = None,
    ) -> None:
        self.repo = repo
        self.registry = list(registry or build_default_source_registry())
        self.http_client = http_client or RequestsHttpClient()
        self._section_collector = SectionCollector(http_client=self.http_client)
        self._feed_collector = FeedCollector(http_client=self.http_client)
        self._calendar_collector = CalendarCollector(http_client=self.http_client)
        self._article_collector = ArticleCollector(http_client=self.http_client)

    def list_recent_items(self, *, limit: int = 20) -> dict[str, Any]:
        rows = self.repo.list_recent_source_items(limit=limit)
        items = [self._render_recent_item(row) for row in rows]
        return {
            "total": len(items),
            "items": items,
        }

    def refresh(
        self,
        *,
        limit_per_source: int = 2,
        max_sources: int = 6,
        recent_limit: int = 12,
    ) -> dict[str, Any]:
        collected_sources = 0
        collected_items = 0

        for source in self._select_sources(max_sources=max(len(self.registry), max_sources)):
            if collected_sources >= max(1, max_sources):
                break
            candidates = self._collect_source_candidates(source)[:max(1, limit_per_source)]
            if not candidates:
                continue

            collected_sources += 1
            for candidate in candidates:
                stored = self._persist_candidate(source, candidate)
                if stored is None:
                    continue
                collected_items += 1

        recent = self.list_recent_items(limit=recent_limit)
        return {
            "collected_sources": collected_sources,
            "collected_items": collected_items,
            "total": recent["total"],
            "items": recent["items"],
        }

    def _select_sources(self, *, max_sources: int) -> list[SourceDefinition]:
        whitelist = {
            item.strip()
            for item in get_config().overnight_source_whitelist.split(",")
            if item.strip()
        }
        selected = [
            source
            for source in self.registry
            if not whitelist or source.source_id in whitelist
        ]
        selected.sort(
            key=lambda source: (int(source.priority), 1 if source.is_mission_critical else 0, source.source_id),
            reverse=True,
        )
        return selected[: max(1, max_sources)]

    def _collect_source_candidates(self, source: SourceDefinition) -> list[SourceCandidate]:
        collector = self._collector_for_source(source)
        if collector is None:
            return []
        try:
            return collector.collect(source)
        except Exception as exc:
            logger.warning("Failed to collect source %s: %s", source.source_id, exc)
            return []

    def _collector_for_source(self, source: SourceDefinition):
        if source.entry_type == "rss":
            return self._feed_collector
        if source.entry_type == "section_page":
            return self._section_collector
        if source.entry_type == "calendar_page":
            return self._calendar_collector
        return None

    def _persist_candidate(self, source: SourceDefinition, candidate: SourceCandidate):
        expanded = candidate
        if candidate.needs_article_fetch:
            try:
                expanded = self._article_collector.expand(candidate)
            except Exception as exc:
                logger.warning("Failed to expand article shell for %s: %s", candidate.candidate_url, exc)

        try:
            normalized = normalize_candidate(expanded)
        except Exception as exc:
            logger.warning("Failed to normalize source candidate %s: %s", expanded.candidate_url, exc)
            return None

        raw_id = self.repo.create_raw_record(
            source_id=source.source_id,
            fetch_mode="source_capture_refresh",
            payload_hash=self._payload_hash(expanded),
        )
        stored = self.repo.persist_source_item(replace(normalized, raw_id=raw_id))
        self.repo.assign_document_family(
            stored.id,
            family_key=stored.canonical_url,
            family_type="canonical_document",
        )
        self.repo.attach_document_version(
            stored.id,
            body_hash=stored.body_hash,
            title_hash=stored.title_hash,
        )
        return stored

    def _payload_hash(self, candidate: SourceCandidate) -> str:
        payload = "\n".join(
            [
                candidate.candidate_url.strip(),
                candidate.candidate_title.strip(),
                candidate.candidate_summary.strip(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _render_recent_item(self, row: dict[str, object]) -> dict[str, object]:
        source_id = str(row.get("source_id", "")).strip()
        matched_source = next((source for source in self.registry if source.source_id == source_id), None)
        return {
            "item_id": int(row.get("item_id", 0) or 0),
            "source_id": source_id,
            "source_name": matched_source.display_name if matched_source is not None else source_id or "未知来源",
            "canonical_url": str(row.get("canonical_url", "")).strip(),
            "title": str(row.get("title", "")).strip(),
            "summary": str(row.get("summary", "")).strip(),
            "document_type": str(row.get("document_type", "")).strip(),
            "source_class": matched_source.source_class if matched_source is not None else "",
            "coverage_tier": matched_source.coverage_tier if matched_source is not None else "",
            "created_at": row.get("created_at"),
        }
