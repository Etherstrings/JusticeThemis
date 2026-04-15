# -*- coding: utf-8 -*-
"""Collect and expose the latest captured overnight source items."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from app.collectors.article import ArticleCollector
from app.collectors.calendar import CalendarCollector
from app.collectors.feed import FeedCollector
from app.collectors.readhub import ReadhubDailyCollector
from app.collectors.section import SectionCollector
from app.normalizer import NumericFact, format_numeric_fact_value, normalize_candidate
from app.repository import OvernightRepository
from app.services.evidence import build_evidence_points
from app.services.event_engine import EventEngine
from app.services.guardrails import assess_analysis_guardrails
from app.services.impact import build_impact_outline
from app.services.relevance import assess_a_share_relevance
from app.services.search_discovery import SearchDiscoveryService
from app.services.source_excerpt import RequestsHttpClient
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate, SourceDefinition
from app.sources.validation import validate_source_url


logger = logging.getLogger(__name__)

_RELEVANCE_PROMOTION_DELTA = 6
_SEARCH_DISCOVERY_DIRECT_CANDIDATE_THRESHOLD = 4
_RICH_FEED_SUMMARY_SKIP_LENGTH = 160
_SOURCE_COOLDOWN_FAILURE_THRESHOLD = 2
_SOURCE_COOLDOWN_HOURS = 6
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?。！？]+\s*")
_TRADE_ACTION_PATTERN = re.compile(
    r"\b(?:tariff|trade action|trade representative|ustr|sanction|export control|import restriction|procurement)\b",
    re.IGNORECASE,
)
_HAWKISH_ACTION_PATTERN = re.compile(r"\b(?:inflation|rate|rates|yield|yields|fomc|restrictive)\b", re.IGNORECASE)
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
_SEARCH_SUMMARY_NEGATIVE_MARKERS = (
    "vendor_count",
    "help us improve",
    "countries &areas",
    "countries & areas",
    "state department home",
    "u.s. department of war",
    "official government organization",
    "skip to content",
)
_SEARCH_SUMMARY_POSITIVE_MARKERS = (
    "washington",
    "released a statement",
    "announced",
    "deployment",
    "sanctions",
    "tariff",
    "trade",
    "forces",
)
_LOW_SIGNAL_TITLE_PATTERN = re.compile(r"\b(?:public schedule|daily schedule|schedule)\b", re.IGNORECASE)
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
        "into",
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


class OvernightSourceCaptureService:
    """Run a lightweight source refresh and expose recent captured items."""

    def __init__(
        self,
        *,
        repo: OvernightRepository,
        registry: list[SourceDefinition] | None = None,
        http_client: object | None = None,
        source_whitelist: set[str] | None = None,
        search_discovery_service: SearchDiscoveryService | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.registry = list(registry or self._build_default_active_registry())
        self.source_whitelist = {item.strip() for item in (source_whitelist or set()) if item.strip()}
        self.http_client = http_client or RequestsHttpClient()
        self._search_discovery_service = search_discovery_service or SearchDiscoveryService.from_environment()
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._section_collector = SectionCollector(http_client=self.http_client)
        self._readhub_collector = ReadhubDailyCollector(http_client=self.http_client)
        self._feed_collector = FeedCollector(http_client=self.http_client)
        self._calendar_collector = CalendarCollector(http_client=self.http_client)
        self._article_collector = ArticleCollector(http_client=self.http_client)
        self._event_engine = EventEngine()
        self._last_collect_diagnostics: dict[str, dict[str, object]] = {}

    def list_recent_items(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, Any]:
        fetch_limit = min(300, max(30, limit * 5))
        if analysis_date:
            source_rows = self.repo.list_source_items_for_analysis_date(
                analysis_date=str(analysis_date).strip(),
                limit=fetch_limit,
            )
        else:
            source_rows = self.repo.list_recent_source_items(limit=fetch_limit)
        rows = self._dedupe_recent_rows(source_rows)[: max(1, limit)]
        comparison_limit = min(300, max(30, limit * 5))
        if analysis_date:
            context_source_rows = self.repo.list_source_items_for_analysis_date(
                analysis_date=str(analysis_date).strip(),
                limit=comparison_limit,
            )
        else:
            context_source_rows = self.repo.list_recent_source_items(limit=comparison_limit)
        context_rows = self._dedupe_recent_rows(context_source_rows)
        items = self._render_recent_items(rows, context_rows=context_rows)
        return {
            "total": len(items),
            "items": items,
        }

    def render_recent_item_row(self, row: dict[str, object]) -> dict[str, object]:
        item_id = int(row.get("item_id", 0) or 0)
        context_rows = [row]
        for context_row in self.repo.list_recent_source_items(limit=30):
            context_item_id = int(context_row.get("item_id", 0) or 0)
            if context_item_id and context_item_id == item_id:
                continue
            context_rows.append(context_row)
        return self._render_recent_items([row], context_rows=context_rows)[0]

    def refresh(
        self,
        *,
        limit_per_source: int = 2,
        max_sources: int = 6,
        recent_limit: int = 12,
    ) -> dict[str, Any]:
        collected_sources = 0
        collected_items = 0
        source_diagnostics: list[dict[str, object]] = []
        selected_sources = self._select_sources(max_sources=max(len(self.registry), max_sources))
        source_states = self.repo.list_source_refresh_states(
            source_ids=[source.source_id for source in selected_sources]
        )

        for source in selected_sources:
            if collected_sources >= max(1, max_sources):
                break
            attempt_started_at = self._now().isoformat()
            existing_state = dict(source_states.get(source.source_id, {}) or {})
            if self._is_source_cooling_down(existing_state, attempt_started_at=attempt_started_at):
                diagnostic = self._record_cooldown_source_attempt(
                    source=source,
                    existing_state=existing_state,
                    attempt_started_at=attempt_started_at,
                )
                source_states[source.source_id] = diagnostic
                source_diagnostics.append(diagnostic)
                continue

            ranked_candidates = self._rank_source_candidates(source, self._collect_source_candidates(source))
            collect_diagnostics = dict(self._last_collect_diagnostics.pop(source.source_id, {}) or {})
            candidates = ranked_candidates[: max(1, limit_per_source)]
            if candidates:
                collected_sources += 1

            persisted_count = 0
            for candidate in candidates:
                stored = self._persist_candidate(source, candidate)
                if stored is None:
                    continue
                collected_items += 1
                persisted_count += 1

            diagnostic = self._record_source_attempt(
                source=source,
                existing_state=existing_state,
                attempt_started_at=attempt_started_at,
                candidate_count=len(ranked_candidates),
                selected_candidate_count=len(candidates),
                persisted_count=persisted_count,
                errors=list(collect_diagnostics.get("errors", []) or []),
                search_discovery_used=bool(collect_diagnostics.get("search_discovery_used", False)),
            )
            source_states[source.source_id] = diagnostic
            source_diagnostics.append(diagnostic)

        recent = self.list_recent_items(limit=recent_limit)
        return {
            "collected_sources": collected_sources,
            "collected_items": collected_items,
            "total": recent["total"],
            "items": recent["items"],
            "source_diagnostics": source_diagnostics,
        }

    def _build_default_active_registry(self) -> list[SourceDefinition]:
        return list(build_default_source_registry())

    def _select_sources(self, *, max_sources: int) -> list[SourceDefinition]:
        selected = [
            source
            for source in self.registry
            if not self.source_whitelist or source.source_id in self.source_whitelist
        ]
        selected.sort(
            key=lambda source: (int(source.priority), 1 if source.is_mission_critical else 0, source.source_id),
            reverse=True,
        )
        return selected[: max(1, max_sources)]

    def _collect_source_candidates(self, source: SourceDefinition) -> list[SourceCandidate]:
        collector = self._collector_for_source(source)
        collected: list[SourceCandidate] = []
        errors: list[str] = []
        search_discovery_used = False
        if collector is not None:
            try:
                collected = list(collector.collect(source))
            except Exception as exc:
                logger.warning("Failed to collect source %s: %s", source.source_id, exc)
                errors.append(self._error_text(exc))
                collected = []
            collector_errors = [
                self._error_text(Exception(str(item)))
                for item in list(getattr(collector, "last_errors", []) or [])
                if str(item).strip()
            ]
            for collector_error in collector_errors:
                if collector_error not in errors:
                    errors.append(collector_error)

        if self._should_use_search_discovery(source, collected):
            search_discovery_used = True
            try:
                supplemental = self._search_discovery_service.discover(
                    source=source,
                    max_results=max(2, 5 - len(collected)),
                )
            except Exception as exc:
                logger.warning("Failed search discovery for source %s: %s", source.source_id, exc)
                errors.append(f"search_discovery: {self._error_text(exc)}")
                supplemental = []
            collected = self._dedupe_candidate_urls([*collected, *supplemental])

        self._last_collect_diagnostics[source.source_id] = {
            "errors": errors[:4],
            "search_discovery_used": search_discovery_used,
        }

        return collected

    def _dedupe_candidate_urls(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        deduped: list[SourceCandidate] = []
        seen_urls: set[str] = set()
        for candidate in candidates:
            normalized_url = self._candidate_url_key(candidate.candidate_url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            deduped.append(candidate)
        return deduped

    def _should_use_search_discovery(self, source: SourceDefinition, candidates: list[SourceCandidate]) -> bool:
        if not source.search_discovery_enabled:
            return False
        if not candidates:
            return True
        if len(candidates) >= _SEARCH_DISCOVERY_DIRECT_CANDIDATE_THRESHOLD:
            return False
        if len(candidates) == 1:
            return self._candidate_is_thin_for_search_discovery(candidates[0])
        return all(self._candidate_is_thin_for_search_discovery(candidate) for candidate in candidates[:2])

    def _candidate_is_thin_for_search_discovery(self, candidate: SourceCandidate) -> bool:
        summary = candidate.candidate_summary.strip()
        if candidate.candidate_excerpt_source.startswith("search:"):
            return False
        if summary and len(summary) >= 160:
            return False
        if summary and len(summary) >= 60 and candidate.candidate_excerpt_source:
            return False
        if summary and len(summary) >= 60 and candidate.candidate_type in {"feed_item", "article"}:
            return False
        return bool(candidate.needs_article_fetch or not summary)

    def _candidate_url_key(self, url: str) -> str:
        parts = urlsplit(str(url).strip())
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))

    def _collector_for_source(self, source: SourceDefinition):
        if source.source_id == "readhub_daily_digest":
            return self._readhub_collector
        if source.entry_type == "rss":
            return self._feed_collector
        if source.entry_type == "section_page":
            return self._section_collector
        if source.entry_type == "calendar_page":
            return self._calendar_collector
        return None

    def _persist_candidate(self, source: SourceDefinition, candidate: SourceCandidate):
        expanded = replace(
            candidate,
            article_fetch_status=(candidate.article_fetch_status or "not_attempted").strip() or "not_attempted",
        )
        if candidate.needs_article_fetch:
            if self._should_skip_article_expansion(candidate):
                expanded = replace(
                    expanded,
                    needs_article_fetch=False,
                    article_fetch_status="skipped_rich_feed_summary",
                )
            else:
                try:
                    expanded = replace(
                        self._article_collector.expand(candidate),
                        article_fetch_status="expanded",
                    )
                except Exception as exc:
                    logger.warning("Failed to expand article shell for %s: %s", candidate.candidate_url, exc)
                    expanded = replace(expanded, article_fetch_status="expand_failed")

        try:
            normalized = normalize_candidate(expanded)
        except Exception as exc:
            logger.warning("Failed to normalize source candidate %s: %s", expanded.candidate_url, exc)
            return None
        source_integrity = validate_source_url(normalized.canonical_url, source)
        if not bool(source_integrity.get("url_valid")):
            logger.warning(
                "Skipping candidate for %s due to invalid source domain: %s",
                source.source_id,
                normalized.canonical_url,
            )
            return None

        existing_by_url = self.repo.list_latest_source_items_by_urls([normalized.canonical_url])
        existing = existing_by_url.get(normalized.canonical_url)
        if existing is not None and self._is_identical_persisted_item(existing=existing, normalized=normalized):
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

    def _should_skip_article_expansion(self, candidate: SourceCandidate) -> bool:
        if candidate.candidate_type != "feed_item":
            return False
        if not candidate.candidate_excerpt_source.startswith("feed:"):
            return False
        return len(candidate.candidate_summary.strip()) >= _RICH_FEED_SUMMARY_SKIP_LENGTH

    def _record_source_attempt(
        self,
        *,
        source: SourceDefinition,
        existing_state: dict[str, object],
        attempt_started_at: str,
        candidate_count: int,
        selected_candidate_count: int,
        persisted_count: int,
        errors: list[str],
        search_discovery_used: bool,
    ) -> dict[str, object]:
        status = self._source_attempt_status(
            candidate_count=candidate_count,
            selected_candidate_count=selected_candidate_count,
            persisted_count=persisted_count,
            errors=errors,
        )
        hard_failure = status == "error" and self._is_hard_failure(errors)
        consecutive_failure_count = int(existing_state.get("consecutive_failure_count", 0) or 0) + 1 if hard_failure else 0
        cooldown_until = None
        if hard_failure and consecutive_failure_count >= _SOURCE_COOLDOWN_FAILURE_THRESHOLD:
            cooldown_until = self._cooldown_until(attempt_started_at)
        last_success_at = attempt_started_at if status == "ok" else existing_state.get("last_success_at")
        stored_state = self.repo.upsert_source_refresh_state(
            source_id=source.source_id,
            last_status=status,
            last_error=errors[0] if errors else "",
            consecutive_failure_count=consecutive_failure_count,
            cooldown_until=cooldown_until,
            last_attempted_at=attempt_started_at,
            last_success_at=str(last_success_at).strip() if last_success_at else None,
            last_candidate_count=candidate_count,
            last_selected_candidate_count=selected_candidate_count,
            last_persisted_count=persisted_count,
            last_elapsed_seconds=0.0,
        )
        return {
            "source_id": source.source_id,
            "source_name": source.display_name,
            "priority": int(source.priority),
            "is_mission_critical": bool(source.is_mission_critical),
            "status": status,
            "skipped_reason": None,
            "candidate_count": candidate_count,
            "selected_candidate_count": selected_candidate_count,
            "persisted_count": persisted_count,
            "search_discovery_used": search_discovery_used,
            "error_count": len(errors),
            "errors": errors[:4],
            "consecutive_failure_count": int(stored_state.get("consecutive_failure_count", 0) or 0),
            "cooldown_until": stored_state.get("cooldown_until"),
            "attempted_at": attempt_started_at,
            "last_success_at": stored_state.get("last_success_at"),
            "elapsed_seconds": 0.0,
        }

    def _record_cooldown_source_attempt(
        self,
        *,
        source: SourceDefinition,
        existing_state: dict[str, object],
        attempt_started_at: str,
    ) -> dict[str, object]:
        stored_state = self.repo.upsert_source_refresh_state(
            source_id=source.source_id,
            last_status="cooldown",
            last_error=str(existing_state.get("last_error") or "").strip(),
            consecutive_failure_count=int(existing_state.get("consecutive_failure_count", 0) or 0),
            cooldown_until=str(existing_state.get("cooldown_until") or "").strip() or None,
            last_attempted_at=attempt_started_at,
            last_success_at=str(existing_state.get("last_success_at") or "").strip() or None,
            last_candidate_count=int(existing_state.get("last_candidate_count", 0) or 0),
            last_selected_candidate_count=int(existing_state.get("last_selected_candidate_count", 0) or 0),
            last_persisted_count=int(existing_state.get("last_persisted_count", 0) or 0),
            last_elapsed_seconds=0.0,
        )
        last_error = str(existing_state.get("last_error") or "").strip()
        return {
            "source_id": source.source_id,
            "source_name": source.display_name,
            "priority": int(source.priority),
            "is_mission_critical": bool(source.is_mission_critical),
            "status": "cooldown",
            "skipped_reason": "hard_failure_cooldown",
            "candidate_count": 0,
            "selected_candidate_count": 0,
            "persisted_count": 0,
            "search_discovery_used": False,
            "error_count": 1 if last_error else 0,
            "errors": [last_error] if last_error else [],
            "consecutive_failure_count": int(stored_state.get("consecutive_failure_count", 0) or 0),
            "cooldown_until": stored_state.get("cooldown_until"),
            "attempted_at": attempt_started_at,
            "last_success_at": stored_state.get("last_success_at"),
            "elapsed_seconds": 0.0,
        }

    def _source_attempt_status(
        self,
        *,
        candidate_count: int,
        selected_candidate_count: int,
        persisted_count: int,
        errors: list[str],
    ) -> str:
        if selected_candidate_count > 0 or candidate_count > 0 or persisted_count > 0:
            return "ok"
        if errors:
            return "error"
        return "empty"

    def _is_source_cooling_down(self, state: dict[str, object], *, attempt_started_at: str) -> bool:
        cooldown_until = str(state.get("cooldown_until") or "").strip()
        if not cooldown_until:
            return False
        try:
            cooldown_at = datetime.fromisoformat(cooldown_until)
            attempt_at = datetime.fromisoformat(attempt_started_at)
        except ValueError:
            return False
        return cooldown_at > attempt_at

    def _cooldown_until(self, attempt_started_at: str) -> str:
        return (
            datetime.fromisoformat(attempt_started_at)
            + timedelta(hours=_SOURCE_COOLDOWN_HOURS)
        ).isoformat()

    def _is_hard_failure(self, errors: list[str]) -> bool:
        for error in errors:
            normalized = str(error or "").strip().lower()
            if not normalized:
                continue
            if "403" in normalized or "forbidden" in normalized or "http_432" in normalized:
                return True
        return False

    def _error_text(self, exc: Exception) -> str:
        return str(exc).strip()[:240] or exc.__class__.__name__

    def _now(self) -> datetime:
        current = self._now_fn()
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _payload_hash(self, candidate: SourceCandidate) -> str:
        payload = "\n".join(
            [
                candidate.candidate_url.strip(),
                candidate.candidate_title.strip(),
                candidate.candidate_summary.strip(),
                (candidate.candidate_published_at or "").strip(),
                candidate.candidate_published_at_source.strip(),
                ",".join(candidate.candidate_entity_names),
                json.dumps(candidate.source_context or {}, ensure_ascii=True, sort_keys=True),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _is_identical_persisted_item(self, *, existing: object, normalized: object) -> bool:
        return (
            str(getattr(existing, "canonical_url", "")).strip() == str(getattr(normalized, "canonical_url", "")).strip()
            and str(getattr(existing, "title_hash", "")).strip() == str(getattr(normalized, "title_hash", "")).strip()
            and str(getattr(existing, "body_hash", "")).strip() == str(getattr(normalized, "body_hash", "")).strip()
            and str(getattr(existing, "content_hash", "")).strip() == str(getattr(normalized, "content_hash", "")).strip()
        )

    def _rank_source_candidates(
        self,
        source: SourceDefinition,
        candidates: list[SourceCandidate],
    ) -> list[SourceCandidate]:
        if len(candidates) < 2:
            return candidates

        scored_candidates = [
            (
                self._candidate_relevance_score(source, candidate),
                len(candidate.candidate_summary.strip()),
                1 if candidate.candidate_published_at else 0,
                candidate,
            )
            for candidate in candidates
        ]
        first_score = scored_candidates[0][0]
        best_score = max(item[0] for item in scored_candidates)
        if first_score >= 0 and best_score - first_score < _RELEVANCE_PROMOTION_DELTA:
            return candidates

        ranked = sorted(
            scored_candidates,
            key=lambda item: (item[0], item[1], item[2]),
            reverse=True,
        )
        return [item[3] for item in ranked]

    def _candidate_relevance_score(self, source: SourceDefinition, candidate: SourceCandidate) -> int:
        assessment = assess_a_share_relevance(
            source_id=source.source_id,
            title=candidate.candidate_title,
            summary=candidate.candidate_summary,
            coverage_tier=source.coverage_tier,
            organization_type=source.organization_type,
            candidate_url=candidate.candidate_url,
        )
        score = assessment.score
        if source.is_mission_critical:
            score += 1
        if candidate.candidate_type == "calendar_event":
            score += 4
        if candidate.candidate_published_at:
            score += 1
        if candidate.candidate_summary.strip():
            score += 1
        if _LOW_SIGNAL_TITLE_PATTERN.search(candidate.candidate_title):
            score -= 4
        if candidate.candidate_excerpt_source.startswith("search:"):
            score += self._search_summary_quality_adjustment(candidate.candidate_summary)
        return score

    def _search_summary_quality_adjustment(self, summary: str) -> int:
        text = summary.strip()
        if not text:
            return -4

        lowered = text.lower()
        adjustment = 0
        adjustment += min(2, len(text) // 240)
        adjustment += sum(2 for marker in _SEARCH_SUMMARY_POSITIVE_MARKERS if marker in lowered)
        adjustment -= sum(3 for marker in _SEARCH_SUMMARY_NEGATIVE_MARKERS if marker in lowered)
        if text.count("*") >= 3:
            adjustment -= 4
        return adjustment

    def _render_recent_items(
        self,
        rows: list[dict[str, object]],
        *,
        context_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        ordered_context_rows = self._dedupe_context_rows([*context_rows, *rows])
        base_items = [self._render_base_item(row) for row in ordered_context_rows]
        event_clusters = self._build_event_clusters(base_items)
        enriched_items = [
            self._enrich_item_relationships(
                item=item,
                context_items=base_items,
                event_clusters=event_clusters,
            )
            for item in base_items
        ]
        enriched_by_id = {int(item.get("item_id", 0) or 0): item for item in enriched_items}

        rendered: list[dict[str, object]] = []
        for row in rows:
            item_id = int(row.get("item_id", 0) or 0)
            rendered.append(
                enriched_by_id.get(
                    item_id,
                    self._enrich_item_relationships(
                        item=self._render_base_item(row),
                        context_items=base_items,
                        event_clusters=event_clusters,
                    ),
                )
            )
        return rendered

    def _dedupe_context_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        seen_item_ids: set[int] = set()
        deduped: list[dict[str, object]] = []
        for row in rows:
            item_id = int(row.get("item_id", 0) or 0)
            if item_id and item_id in seen_item_ids:
                continue
            if item_id:
                seen_item_ids.add(item_id)
            deduped.append(row)
        return deduped

    def _dedupe_recent_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: list[dict[str, object]] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        for row in rows:
            dedupe_key = (
                str(row.get("canonical_url", "")).strip(),
                str(row.get("content_hash", "")).strip(),
                str(row.get("title_hash", "")).strip(),
                str(row.get("body_hash", "")).strip(),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            deduped.append(row)
        return deduped

    def _render_base_item(self, row: dict[str, object]) -> dict[str, object]:
        source_id = str(row.get("source_id", "")).strip()
        matched_source = next((source for source in self.registry if source.source_id == source_id), None)
        title = str(row.get("title", "")).strip()
        summary = str(row.get("summary", "")).strip()
        canonical_url = str(row.get("canonical_url", "")).strip()
        capture_path = str(row.get("capture_path") or "direct").strip() or "direct"
        capture_provider_value = row.get("capture_provider")
        capture_provider = str(capture_provider_value).strip() if capture_provider_value is not None else ""
        capture_provider = capture_provider or None
        article_fetch_status = str(row.get("article_fetch_status") or "not_attempted").strip() or "not_attempted"
        relevance = assess_a_share_relevance(
            source_id=source_id,
            title=title,
            summary=summary,
            coverage_tier=matched_source.coverage_tier if matched_source is not None else "",
            organization_type=matched_source.organization_type if matched_source is not None else "",
            candidate_url=canonical_url,
        )
        numeric_facts = tuple(row.get("numeric_facts", []) or [])
        impact = build_impact_outline(
            source_id=source_id,
            title=title,
            summary=summary,
            relevance_label=relevance.label,
        )
        evidence_points = build_evidence_points(
            summary=summary,
            numeric_facts=tuple(
                NumericFact(**fact) if isinstance(fact, dict) else fact
                for fact in numeric_facts
            ),
        )
        summary_quality = self._summary_quality(
            summary=summary,
            excerpt_source=str(row.get("excerpt_source", "")).strip(),
        )
        guardrails = assess_analysis_guardrails(
            coverage_tier=matched_source.coverage_tier if matched_source is not None else "",
            organization_type=matched_source.organization_type if matched_source is not None else "",
            summary_quality=summary_quality,
            a_share_relevance=relevance.label,
            excerpt_source=str(row.get("excerpt_source", "")).strip(),
            published_at_source=str(row.get("published_at_source", "")).strip(),
            beneficiary_directions=impact.beneficiary_directions,
            pressured_directions=impact.pressured_directions,
            price_up_signals=impact.price_up_signals,
            follow_up_checks=impact.follow_up_checks,
        )
        published_at = row.get("published_at")
        published_at_source = str(row.get("published_at_source", "")).strip()
        published_at_precision = self._published_at_precision(published_at)
        evidence_points_list = list(evidence_points)
        content_metrics = {
            "summary_sentence_count": self._summary_sentence_count(summary),
            "evidence_point_count": len(evidence_points_list),
            "numeric_fact_count": len(numeric_facts),
            "entity_count": len(list(row.get("entities", []) or [])),
        }
        source_time_reliability = self._source_time_reliability(
            published_at_source=published_at_source,
            published_at_precision=published_at_precision,
        )
        source_integrity = self._source_integrity(
            source=matched_source,
            canonical_url=canonical_url,
        )
        timeliness = self._timeliness(
            published_at=published_at,
            published_at_precision=published_at_precision,
            created_at=row.get("created_at"),
        )
        data_quality_flags = self._data_quality_flags(
            source_integrity=source_integrity,
            published_at_precision=published_at_precision,
            source_time_reliability=source_time_reliability,
            timeliness=timeliness,
        )
        key_numbers = self._key_numbers(numeric_facts)
        fact_table = self._fact_table(evidence_points_list=evidence_points_list, key_numbers=key_numbers)
        policy_actions = self._policy_actions(
            source_id=source_id,
            title=title,
            summary=summary,
        )
        market_implications = self._market_implications(impact=impact)
        uncertainties = list(impact.follow_up_checks)
        return {
            "item_id": int(row.get("item_id", 0) or 0),
            "source_id": source_id,
            "source_name": matched_source.display_name if matched_source is not None else source_id or "unknown_source",
            "canonical_url": canonical_url,
            "title": title,
            "summary": summary,
            "excerpt_source": str(row.get("excerpt_source", "")).strip(),
            "excerpt_char_count": len(summary),
            "capture_path": capture_path,
            "capture_provider": capture_provider,
            "article_fetch_status": article_fetch_status,
            "capture_provenance": {
                "capture_path": capture_path,
                "is_search_fallback": capture_path == "search_discovery",
                "search_provider": capture_provider,
                "article_fetch_status": article_fetch_status,
            },
            "document_type": str(row.get("document_type", "")).strip(),
            "source_class": matched_source.source_class if matched_source is not None else "",
            "coverage_tier": matched_source.coverage_tier if matched_source is not None else "",
            "organization_type": matched_source.organization_type if matched_source is not None else "",
            "priority": int(matched_source.priority) if matched_source is not None else 0,
            "is_mission_critical": bool(matched_source.is_mission_critical) if matched_source is not None else False,
            "region_focus": matched_source.region_focus if matched_source is not None else "",
            "coverage_focus": matched_source.coverage_focus if matched_source is not None else "",
            "published_at": published_at,
            "published_at_source": published_at_source,
            "published_at_precision": published_at_precision,
            "published_at_display": self._format_published_at_display(published_at, precision=published_at_precision),
            "source_authority": self._source_authority(
                coverage_tier=matched_source.coverage_tier if matched_source is not None else "",
                organization_type=matched_source.organization_type if matched_source is not None else "",
            ),
            "entities": list(row.get("entities", []) or []),
            "numeric_facts": list(numeric_facts),
            "source_context": dict(row.get("source_context", {}) or {}),
            "content_metrics": content_metrics,
            "content_completeness": self._content_completeness(
                summary_quality=summary_quality,
                published_at_precision=published_at_precision,
                content_metrics=content_metrics,
            ),
            "body_detail_level": self._body_detail_level(
                excerpt_source=str(row.get("excerpt_source", "")).strip(),
                summary_quality=summary_quality,
                content_metrics=content_metrics,
            ),
            "source_time_reliability": source_time_reliability,
            "source_integrity": source_integrity,
            "timeliness": timeliness,
            "data_quality_flags": data_quality_flags,
            "summary_quality": summary_quality,
            "a_share_relevance": relevance.label,
            "a_share_relevance_reason": relevance.reason,
            "evidence_points": evidence_points_list,
            "impact_summary": impact.impact_summary,
            "why_it_matters_cn": impact.impact_summary,
            "key_numbers": key_numbers,
            "fact_table": fact_table,
            "policy_actions": policy_actions,
            "market_implications": market_implications,
            "uncertainties": uncertainties,
            "beneficiary_directions": list(impact.beneficiary_directions),
            "pressured_directions": list(impact.pressured_directions),
            "price_up_signals": list(impact.price_up_signals),
            "follow_up_checks": uncertainties,
            "analysis_status": guardrails.analysis_status,
            "analysis_confidence": guardrails.analysis_confidence,
            "analysis_blockers": list(guardrails.analysis_blockers),
            "created_at": row.get("created_at"),
            "family_id": row.get("family_id"),
            "family_key": row.get("family_key"),
            "family_type": row.get("family_type"),
            "version_id": row.get("version_id"),
        }

    def _enrich_item_relationships(
        self,
        *,
        item: dict[str, object],
        context_items: list[dict[str, object]],
        event_clusters: dict[int, dict[str, object]],
    ) -> dict[str, object]:
        enriched = dict(item)
        item_id = int(enriched.get("item_id", 0) or 0)
        event_cluster = dict(event_clusters.get(item_id, self._fallback_event_cluster(enriched)))
        cluster_id = str(event_cluster.get("cluster_id", "")).strip()
        same_event_context_items = [
            candidate
            for candidate in context_items
            if str(event_clusters.get(int(candidate.get("item_id", 0) or 0), {}).get("cluster_id", "")).strip() == cluster_id
        ]
        if not same_event_context_items:
            same_event_context_items = [enriched]
        fact_conflicts = self._fact_conflicts(item=enriched, context_items=same_event_context_items)
        cross_source_confirmation = self._cross_source_confirmation(
            item=enriched,
            context_items=same_event_context_items,
            fact_conflicts=fact_conflicts,
        )
        source_capture_confidence = self._source_capture_confidence(
            item=enriched,
            cross_source_confirmation=cross_source_confirmation,
            fact_conflicts=fact_conflicts,
        )
        enriched["event_cluster"] = event_cluster
        enriched["source_capture_confidence"] = source_capture_confidence
        enriched["cross_source_confirmation"] = cross_source_confirmation
        enriched["fact_conflicts"] = fact_conflicts
        enriched["llm_ready_brief"] = self._llm_ready_brief(
            item=enriched,
            source_capture_confidence=source_capture_confidence,
            cross_source_confirmation=cross_source_confirmation,
            fact_conflicts=fact_conflicts,
        )
        return enriched

    def _build_event_clusters(self, items: list[dict[str, object]]) -> dict[int, dict[str, object]]:
        return self._event_engine.build_item_event_index(items)

    def _items_belong_to_same_event(
        self,
        item: dict[str, object],
        other_item: dict[str, object],
    ) -> bool:
        if not self._event_time_is_close(item, other_item):
            return False
        shared_topics = self._item_topics(item) & self._item_topics(other_item)
        shared_fact_signatures = self._item_fact_signatures(item) & self._item_fact_signatures(other_item)
        shared_identity_keywords = self._item_identity_keywords(item) & self._item_identity_keywords(other_item)
        shared_entities = self._item_entity_names(item) & self._item_entity_names(other_item)
        shared_directions = self._item_direction_signatures(item) & self._item_direction_signatures(other_item)
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

    def _event_cluster_payload(self, members: list[dict[str, object]]) -> dict[str, object]:
        ordered_members = sorted(members, key=self._event_cluster_member_sort_key)
        primary_item = ordered_members[0]
        member_item_ids = [int(item.get("item_id", 0) or 0) for item in ordered_members]
        member_source_ids = self._unique_preserving_order(
            [str(item.get("source_id", "")).strip() for item in ordered_members]
        )
        topic_tags = self._unique_preserving_order(
            [
                topic
                for item in ordered_members
                for topic in sorted(self._item_topics(item))
            ]
        )
        fact_signatures = self._unique_preserving_order(
            [
                signature
                for item in ordered_members
                for signature in sorted(self._item_fact_signatures(item))
            ]
        )
        latest_published_at = self._latest_published_at(ordered_members)
        source_count = len(member_source_ids)
        official_source_ids = {
            str(item.get("source_id", "")).strip()
            for item in ordered_members
            if str(item.get("coverage_tier", "")).strip() in {"official_policy", "official_data"}
        }
        return {
            "cluster_id": self._event_cluster_id(
                topic_tags=topic_tags,
                fact_signatures=fact_signatures,
                members=ordered_members,
            ),
            "cluster_status": self._event_cluster_status(ordered_members),
            "primary_item_id": int(primary_item.get("item_id", 0) or 0),
            "item_count": len(member_item_ids),
            "source_count": source_count,
            "official_source_count": len(official_source_ids),
            "member_item_ids": member_item_ids,
            "member_source_ids": member_source_ids,
            "latest_published_at": latest_published_at,
            "topic_tags": topic_tags[:4],
            "fact_signatures": fact_signatures[:4],
        }

    def _fallback_event_cluster(self, item: dict[str, object]) -> dict[str, object]:
        return self._event_cluster_payload([item])

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
            for signature, payload in self._item_key_number_index(item).items():
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
            [
                keyword
                for item in members
                for keyword in sorted(self._item_event_keywords(item))
            ]
        )
        if len(keywords) >= 2:
            return f"{self._slug(topic)}__{self._slug(keywords[0])}__{self._slug(keywords[1])}__{primary_item_id}"
        if keywords:
            return f"{self._slug(topic)}__{self._slug(keywords[0])}__{primary_item_id}"
        return f"{self._slug(topic)}__item_{primary_item_id}"

    def _item_fact_signatures(self, item: dict[str, object]) -> set[str]:
        signatures: set[str] = set()
        for signature in self._item_key_number_index(item):
            metric, subject = signature
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
            name = str(dict(entity).get("name", "") if isinstance(entity, dict) else getattr(entity, "name", "")).strip().lower()
            if name and len(name) >= 4:
                names.add(name)
        return names

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
        candidate = str(value or "").strip()
        if not candidate:
            return float("inf")
        try:
            return -datetime.fromisoformat(candidate.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return float("inf")

    def _slug(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return normalized or "cluster"

    def _cross_source_confirmation(
        self,
        *,
        item: dict[str, object],
        context_items: list[dict[str, object]],
        fact_conflicts: list[dict[str, object]],
    ) -> dict[str, object]:
        item_id = int(item.get("item_id", 0) or 0)
        conflicting_item_ids = {
            int(conflict.get("other_item_id", 0) or 0)
            for conflict in fact_conflicts
            if int(conflict.get("other_item_id", 0) or 0)
        }
        current_topics = self._item_topics(item)
        current_directions = self._item_direction_signatures(item)
        current_numbers = self._item_key_number_index(item)
        confirmed_by_sources: list[dict[str, object]] = []
        aggregated_topics: list[str] = []
        aggregated_directions: list[str] = []

        for candidate in context_items:
            other_item_id = int(candidate.get("item_id", 0) or 0)
            if not other_item_id or other_item_id == item_id:
                continue
            if str(candidate.get("source_id", "")).strip() == str(item.get("source_id", "")).strip():
                continue
            if other_item_id in conflicting_item_ids:
                continue

            match_basis = set()
            shared_topics = sorted(current_topics & self._item_topics(candidate))
            shared_directions = sorted(current_directions & self._item_direction_signatures(candidate))
            shared_numbers = sorted(
                signature
                for signature in current_numbers
                if signature in self._item_key_number_index(candidate)
                and current_numbers[signature]["value_text"] == self._item_key_number_index(candidate)[signature]["value_text"]
            )

            for topic in shared_topics:
                match_basis.add(f"topic:{topic}")
                aggregated_topics.append(topic)
            for implication_type, direction in shared_directions:
                match_basis.add(f"direction:{implication_type}:{direction}")
                aggregated_directions.append(direction)
            for metric, subject in shared_numbers:
                normalized_subject = subject or "general"
                match_basis.add(f"numeric:{metric}:{normalized_subject}")

            if not match_basis:
                continue

            confirmed_by_sources.append(
                {
                    "item_id": other_item_id,
                    "source_id": str(candidate.get("source_id", "")).strip(),
                    "source_name": str(candidate.get("source_name", "")).strip(),
                    "match_basis": sorted(match_basis),
                }
            )

        supporting_source_count = len(confirmed_by_sources)
        level = "single_source"
        if supporting_source_count >= 2:
            level = "strong"
        elif supporting_source_count == 1:
            level = "moderate"

        return {
            "level": level,
            "supporting_source_count": supporting_source_count,
            "confirmed_by_item_ids": [int(candidate["item_id"]) for candidate in confirmed_by_sources],
            "confirmed_by_sources": confirmed_by_sources,
            "shared_topics": self._unique_preserving_order(aggregated_topics)[:6],
            "shared_directions": self._unique_preserving_order(aggregated_directions)[:6],
        }

    def _fact_conflicts(
        self,
        *,
        item: dict[str, object],
        context_items: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        item_id = int(item.get("item_id", 0) or 0)
        conflicts: list[dict[str, object]] = []
        seen_signatures: set[tuple[str, str, str, int]] = set()
        current_numbers = self._item_key_number_index(item)
        current_directions = self._item_direction_signatures(item)

        for candidate in context_items:
            other_item_id = int(candidate.get("item_id", 0) or 0)
            if not other_item_id or other_item_id == item_id:
                continue
            if str(candidate.get("source_id", "")).strip() == str(item.get("source_id", "")).strip():
                continue

            other_numbers = self._item_key_number_index(candidate)
            for signature, current_fact in current_numbers.items():
                other_fact = other_numbers.get(signature)
                if other_fact is None:
                    continue
                if current_fact["value_text"] == other_fact["value_text"]:
                    continue
                conflict_key = ("numeric_mismatch", signature[0], signature[1], other_item_id)
                if conflict_key in seen_signatures:
                    continue
                seen_signatures.add(conflict_key)
                conflicts.append(
                    {
                        "conflict_type": "numeric_mismatch",
                        "metric": signature[0],
                        "subject": signature[1] or None,
                        "current_value_text": current_fact["value_text"],
                        "other_value_text": other_fact["value_text"],
                        "other_item_id": other_item_id,
                        "other_source_id": str(candidate.get("source_id", "")).strip(),
                        "other_source_name": str(candidate.get("source_name", "")).strip(),
                    }
                )

            other_directions = self._item_direction_signatures(candidate)
            for direction in self._direction_overlap(current_directions, other_directions):
                current_stances = {signature[0] for signature in current_directions if signature[1] == direction}
                other_stances = {signature[0] for signature in other_directions if signature[1] == direction}
                if current_stances == other_stances:
                    continue
                conflict_key = ("direction_mismatch", direction, "", other_item_id)
                if conflict_key in seen_signatures:
                    continue
                seen_signatures.add(conflict_key)
                conflicts.append(
                    {
                        "conflict_type": "direction_mismatch",
                        "metric": "market_direction",
                        "subject": direction,
                        "current_value_text": "/".join(sorted(current_stances)),
                        "other_value_text": "/".join(sorted(other_stances)),
                        "other_item_id": other_item_id,
                        "other_source_id": str(candidate.get("source_id", "")).strip(),
                        "other_source_name": str(candidate.get("source_name", "")).strip(),
                    }
                )

        conflicts.sort(
            key=lambda conflict: (
                str(conflict.get("conflict_type", "")),
                str(conflict.get("metric", "")),
                str(conflict.get("subject", "")),
                int(conflict.get("other_item_id", 0) or 0),
            )
        )
        return conflicts[:8]

    def _source_capture_confidence(
        self,
        *,
        item: dict[str, object],
        cross_source_confirmation: dict[str, object],
        fact_conflicts: list[dict[str, object]],
    ) -> dict[str, object]:
        score = 0
        reasons: list[str] = []
        penalties: list[str] = []

        source_authority = str(item.get("source_authority", "")).strip()
        if source_authority == "primary_official":
            score += 30
            reasons.append("官方源")
        elif source_authority == "editorial_context":
            score += 18
            reasons.append("媒体辅助源")
        else:
            score += 10
            reasons.append("来源可用")

        source_time_reliability = str(item.get("source_time_reliability", "")).strip()
        if source_time_reliability == "high":
            score += 20
            reasons.append("时间来源可靠")
        elif source_time_reliability == "medium":
            score += 12

        content_completeness = str(item.get("content_completeness", "")).strip()
        if content_completeness == "high":
            score += 18
            reasons.append("内容完整度高")
        elif content_completeness == "medium":
            score += 10

        body_detail_level = str(item.get("body_detail_level", "")).strip()
        if body_detail_level == "detailed":
            score += 10
            reasons.append("正文细节较完整")
        elif body_detail_level == "summary":
            score += 6

        summary_quality = str(item.get("summary_quality", "")).strip()
        if summary_quality == "high":
            score += 8
        elif summary_quality == "medium":
            score += 4

        confirmation_level = str(cross_source_confirmation.get("level", "")).strip()
        if confirmation_level == "strong":
            score += 12
            reasons.append("多源交叉确认")
        elif confirmation_level == "moderate":
            score += 6
            reasons.append("存在交叉确认")

        analysis_status = str(item.get("analysis_status", "")).strip()
        if analysis_status == "ready":
            score += 5
        elif analysis_status == "background":
            score -= 8
            penalties.append("仅作背景参考")

        blocker_count = len(list(item.get("analysis_blockers", []) or []))
        if blocker_count:
            score -= min(12, blocker_count * 3)
            penalties.append("存在分析阻塞项")

        if fact_conflicts:
            score -= 12
            penalties.append("存在跨源事实冲突")

        score = max(0, min(100, score))
        level = "low"
        if score >= 70:
            level = "high"
        elif score >= 50:
            level = "medium"

        return {
            "level": level,
            "score": score,
            "reasons": self._unique_preserving_order(reasons)[:4],
            "penalties": self._unique_preserving_order(penalties)[:4],
        }

    def _llm_ready_brief(
        self,
        *,
        item: dict[str, object],
        source_capture_confidence: dict[str, object],
        cross_source_confirmation: dict[str, object],
        fact_conflicts: list[dict[str, object]],
    ) -> str:
        parts = [
            f"item_id={int(item.get('item_id', 0) or 0)}",
            str(item.get("published_at_display") or item.get("published_at") or "time=unknown"),
            str(item.get("source_name", "")).strip(),
            f"authority={str(item.get('source_authority', '')).strip() or 'unknown'}",
            f"capture={source_capture_confidence['level']}:{int(source_capture_confidence['score'])}",
            f"cross_source={int(cross_source_confirmation.get('supporting_source_count', 0) or 0)}",
            f"conflict_count={len(fact_conflicts)}",
        ]

        key_facts = self._brief_key_facts(item)
        if key_facts:
            parts.append(f"facts={key_facts}")

        directions = self._brief_market_directions(item)
        if directions:
            parts.append(f"a_share={directions}")

        uncertainties = list(item.get("uncertainties", []) or [])
        if uncertainties:
            parts.append(f"watch={uncertainties[0]}")

        return " | ".join(part for part in parts if part)

    def _brief_key_facts(self, item: dict[str, object]) -> str:
        key_numbers = list(item.get("key_numbers", []) or [])
        if key_numbers:
            facts: list[str] = []
            for key_number in key_numbers[:2]:
                metric = str(key_number.get("metric", "")).strip()
                subject = str(key_number.get("subject", "") or "").strip()
                value_text = str(key_number.get("value_text", "")).strip()
                if not metric or not value_text:
                    continue
                fact_text = f"{metric}={value_text}"
                if subject:
                    fact_text += f"({subject})"
                facts.append(fact_text)
            if facts:
                return "; ".join(facts)

        fact_table = list(item.get("fact_table", []) or [])
        first_fact = next((str(fact.get("text", "")).strip() for fact in fact_table if str(fact.get("text", "")).strip()), "")
        return first_fact[:160]

    def _brief_market_directions(self, item: dict[str, object]) -> str:
        parts: list[str] = []
        beneficiaries = list(item.get("beneficiary_directions", []) or [])
        pressured = list(item.get("pressured_directions", []) or [])
        price_up = list(item.get("price_up_signals", []) or [])
        if beneficiaries:
            parts.append(f"beneficiary={'/'.join(beneficiaries[:2])}")
        if pressured:
            parts.append(f"pressured={'/'.join(pressured[:2])}")
        if price_up:
            parts.append(f"price_up={'/'.join(price_up[:2])}")
        return "; ".join(parts)

    def _item_topics(self, item: dict[str, object]) -> set[str]:
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

    def _item_direction_signatures(self, item: dict[str, object]) -> set[tuple[str, str]]:
        signatures: set[tuple[str, str]] = set()
        for implication in list(item.get("market_implications", []) or []):
            implication_type = str(implication.get("implication_type", "")).strip()
            direction = str(implication.get("direction", "")).strip()
            if implication_type and direction:
                signatures.add((implication_type, direction))
        return signatures

    def _item_key_number_index(self, item: dict[str, object]) -> dict[tuple[str, str], dict[str, str]]:
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

    def _direction_overlap(
        self,
        current_directions: set[tuple[str, str]],
        other_directions: set[tuple[str, str]],
    ) -> list[str]:
        current_direction_names = {direction for _implication_type, direction in current_directions}
        other_direction_names = {direction for _implication_type, direction in other_directions}
        return sorted(current_direction_names & other_direction_names)

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

    def _summary_quality(self, *, summary: str, excerpt_source: str) -> str:
        summary_length = len(summary.strip())
        if summary_length < 30:
            return "low"
        if excerpt_source.startswith("body_selector:") and summary_length >= 40:
            return "high"
        if excerpt_source == "candidate_summary:preferred" and summary_length >= 60:
            return "high"
        if excerpt_source in {"headline_paragraph", "body_fallback"} and summary_length >= 80:
            return "medium"
        if excerpt_source.startswith("meta:") and summary_length >= 120:
            return "medium"
        return "medium" if summary_length >= 80 else "low"

    def _published_at_precision(self, value: object) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            return "missing"
        if "T" in candidate or re.search(r"\b\d{2}:\d{2}", candidate):
            return "datetime"
        return "date"

    def _format_published_at_display(self, value: object, *, precision: str) -> str | None:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        if precision == "date":
            return candidate
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return candidate
        if parsed.tzinfo is None:
            return parsed.strftime("%Y-%m-%d %H:%M")
        shanghai_time = parsed.astimezone(_SHANGHAI_TZ)
        return shanghai_time.strftime("%Y-%m-%d %H:%M CST")

    def _source_authority(self, *, coverage_tier: str, organization_type: str) -> str:
        normalized_tier = coverage_tier.strip()
        normalized_org = organization_type.strip()
        if normalized_tier in {"official_policy", "official_data"} or normalized_org in {"official_policy", "official_data"}:
            return "primary_official"
        if normalized_tier == "editorial_media" or normalized_org in {"editorial_media", "wire_media"}:
            return "editorial_context"
        return "other"

    def _summary_sentence_count(self, summary: str) -> int:
        normalized = summary.strip()
        if not normalized:
            return 0
        parts = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(normalized) if part.strip()]
        return len(parts) if parts else 1

    def _content_completeness(
        self,
        *,
        summary_quality: str,
        published_at_precision: str,
        content_metrics: dict[str, int],
    ) -> str:
        if (
            summary_quality == "high"
            and published_at_precision in {"date", "datetime"}
            and content_metrics["evidence_point_count"] >= 1
        ):
            return "high"
        if summary_quality in {"high", "medium"} and published_at_precision != "missing":
            return "medium"
        return "low"

    def _body_detail_level(
        self,
        *,
        excerpt_source: str,
        summary_quality: str,
        content_metrics: dict[str, int],
    ) -> str:
        normalized_source = excerpt_source.strip()
        if normalized_source.startswith("body_selector:") and summary_quality == "high":
            return "detailed"
        if content_metrics["summary_sentence_count"] >= 2 and summary_quality in {"high", "medium"}:
            return "detailed"
        if summary_quality in {"high", "medium"}:
            return "summary"
        return "brief"

    def _source_time_reliability(self, *, published_at_source: str, published_at_precision: str) -> str:
        source = published_at_source.strip()
        if not source or published_at_precision == "missing":
            return "low"
        if source.startswith(("html:", "feed:", "rss:")) and published_at_precision == "datetime":
            return "high"
        if source in {"section:time", "section:nearby_time"} and published_at_precision in {"date", "datetime"}:
            return "medium"
        if published_at_precision in {"date", "datetime"}:
            return "medium"
        return "low"

    def _source_integrity(
        self,
        *,
        source: SourceDefinition | None,
        canonical_url: str,
    ) -> dict[str, object]:
        if source is None:
            return {
                "hostname": "",
                "domain_status": "unknown",
                "matched_domain": None,
                "allowed_domains": [],
                "is_https": canonical_url.startswith("https://"),
                "https_required": True,
                "url_valid": False,
            }
        return validate_source_url(canonical_url, source)

    def _data_quality_flags(
        self,
        *,
        source_integrity: dict[str, object],
        published_at_precision: str,
        source_time_reliability: str,
        timeliness: dict[str, object],
    ) -> list[str]:
        flags: list[str] = []
        if str(source_integrity.get("domain_status", "")).strip() == "mismatch":
            flags.append("source_domain_mismatch")
        if bool(source_integrity.get("https_required")) and not bool(source_integrity.get("is_https")):
            flags.append("non_https_source_url")
        if published_at_precision == "missing" and "missing_published_time" not in list(timeliness.get("timeliness_flags", []) or []):
            flags.append("missing_published_time")
        elif source_time_reliability == "low":
            flags.append("low_time_reliability")
        for flag in list(timeliness.get("timeliness_flags", []) or []):
            candidate = str(flag).strip()
            if candidate and candidate not in flags:
                flags.append(candidate)
        return flags[:6]

    def _timeliness(
        self,
        *,
        published_at: object,
        published_at_precision: str,
        created_at: object,
    ) -> dict[str, object]:
        anchor_dt = self._parse_created_at(created_at)
        anchor_time = anchor_dt.isoformat() if anchor_dt is not None else None
        published_dt = self._parse_published_at(published_at, precision=published_at_precision)
        if published_dt is None:
            return {
                "anchor_time": anchor_time,
                "age_hours": None,
                "publication_lag_minutes": None,
                "freshness_bucket": "undated",
                "is_timely": False,
                "timeliness_flags": ["missing_published_time"],
            }

        age_hours = max(0.0, round((anchor_dt - published_dt).total_seconds() / 3600, 1)) if anchor_dt is not None else None
        publication_lag_minutes = None
        if anchor_dt is not None and published_at_precision == "datetime":
            publication_lag_minutes = max(0, int(round((anchor_dt - published_dt).total_seconds() / 60)))

        freshness_bucket = "stale"
        if age_hours is not None:
            if age_hours <= 12:
                freshness_bucket = "breaking"
            elif age_hours <= 36:
                freshness_bucket = "overnight"
            elif age_hours <= 72:
                freshness_bucket = "recent"

        flags: list[str] = []
        if freshness_bucket == "stale":
            flags.append("stale_publication")
        if publication_lag_minutes is not None and publication_lag_minutes > 720:
            flags.append("delayed_capture")

        return {
            "anchor_time": anchor_time,
            "age_hours": age_hours,
            "publication_lag_minutes": publication_lag_minutes,
            "freshness_bucket": freshness_bucket,
            "is_timely": freshness_bucket != "stale",
            "timeliness_flags": flags,
        }

    def _parse_created_at(self, value: object) -> datetime | None:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
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

    def _key_numbers(self, numeric_facts: tuple[NumericFact, ...]) -> list[dict[str, object]]:
        key_numbers: list[dict[str, object]] = []
        for fact in numeric_facts:
            fact_obj = NumericFact(**fact) if isinstance(fact, dict) else fact
            value_text = self._format_numeric_fact_value(fact_obj)
            key_numbers.append(
                {
                    "metric": fact_obj.metric,
                    "value": fact_obj.value,
                    "value_text": value_text,
                    "unit": fact_obj.unit,
                    "subject": fact_obj.subject,
                }
            )
        return key_numbers[:6]

    def _fact_table(
        self,
        *,
        evidence_points_list: list[str],
        key_numbers: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        fact_table: list[dict[str, object]] = []
        for point in evidence_points_list[:3]:
            fact_table.append(
                {
                    "fact_type": "sentence",
                    "text": point,
                }
            )
        for key_number in key_numbers[:3]:
            subject = f" on {key_number['subject']}" if key_number.get("subject") else ""
            fact_table.append(
                {
                    "fact_type": "numeric",
                    "metric": key_number["metric"],
                    "value": key_number["value"],
                    "value_text": key_number["value_text"],
                    "unit": key_number["unit"],
                    "subject": key_number.get("subject"),
                    "text": f"{key_number['metric']}: {key_number['value_text']}{subject}",
                }
            )
        return fact_table[:6]

    def _policy_actions(self, *, source_id: str, title: str, summary: str) -> list[str]:
        text = " ".join(part for part in (source_id, title, summary) if part).strip()
        actions: list[str] = []
        if _TRADE_ACTION_PATTERN.search(text):
            actions.append("关税/贸易限制仍在执行")
        if _HAWKISH_ACTION_PATTERN.search(text) and "fed" in source_id.lower():
            actions.append("利率路径维持偏紧")
        return actions[:4]

    def _market_implications(self, *, impact: Any) -> list[dict[str, str]]:
        implications: list[dict[str, str]] = []
        for direction in list(impact.beneficiary_directions):
            implications.append(
                {
                    "implication_type": "beneficiary",
                    "direction": str(direction),
                    "stance": "positive",
                }
            )
        for direction in list(impact.pressured_directions):
            implications.append(
                {
                    "implication_type": "pressured",
                    "direction": str(direction),
                    "stance": "negative",
                }
            )
        for direction in list(impact.price_up_signals):
            implications.append(
                {
                    "implication_type": "price_up",
                    "direction": str(direction),
                    "stance": "inflationary",
                }
            )
        return implications[:8]

    def _format_numeric_fact_value(self, fact: NumericFact) -> str:
        return format_numeric_fact_value(fact, style="compact")

    def _numeric_fact_is_compare_ready(self, *, metric: str, subject: str) -> bool:
        normalized_metric = metric.strip()
        normalized_subject = subject.strip()
        if normalized_metric == "tariff_rate":
            return True
        return bool(normalized_subject)
