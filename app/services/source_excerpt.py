# -*- coding: utf-8 -*-
"""Resolve source-page excerpts with DB-backed caching."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import logging
import time
from typing import Callable, Protocol

import requests

from app.collectors.article import ArticleCollector, canonicalize_url
from app.ledger import StoredSourceItem
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.sources.types import SourceCandidate


logger = logging.getLogger(__name__)


class FetchingClient(Protocol):
    def fetch(self, url: str) -> str | bytes:
        """Fetch one source page and return its body."""


class RequestsHttpClient:
    """Small requests wrapper for article-shell enrichment."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
    _WEAK_ENCODINGS = frozenset({"iso-8859-1", "latin-1", "latin1", "ascii"})

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        retry_attempts: int = 3,
        backoff_seconds: float = 0.6,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.retry_attempts = max(1, int(retry_attempts))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.sleep_fn = sleep_fn or time.sleep

    def fetch(self, url: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=12,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                response.raise_for_status()
                response.encoding = self._preferred_encoding(response)
                return response.text
            except requests.HTTPError as exc:
                last_error = exc
                status_code = getattr(exc.response, "status_code", None)
                if status_code not in self.RETRYABLE_STATUS_CODES or attempt >= self.retry_attempts:
                    raise
            except (requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    raise

            if self.backoff_seconds > 0:
                self.sleep_fn(self.backoff_seconds * attempt)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to fetch source page: {url}")

    def _preferred_encoding(self, response: requests.Response) -> str:
        declared = str(getattr(response, "encoding", "") or "").strip()
        apparent = str(getattr(response, "apparent_encoding", "") or "").strip()
        if declared and declared.lower() not in self._WEAK_ENCODINGS:
            return declared
        if apparent:
            return apparent
        if declared:
            return declared
        return "utf-8"


class OvernightSourceExcerptService:
    """Hydrate source links into cached source-item excerpts."""

    def __init__(
        self,
        *,
        repo: OvernightRepository,
        http_client: FetchingClient | None = None,
    ) -> None:
        self.repo = repo
        self.http_client = http_client or RequestsHttpClient()
        self.article_collector = ArticleCollector(http_client=self.http_client)

    def resolve(
        self,
        *,
        url: str,
        fallback_title: str,
        source_id: str,
    ) -> StoredSourceItem | None:
        raw_url = str(url).strip()
        if not raw_url:
            return None

        canonical_url = canonicalize_url(raw_url)
        cached = self.repo.list_latest_source_items_by_urls([canonical_url]).get(canonical_url)
        if cached is not None and (cached.summary.strip() or cached.title.strip()):
            return cached

        candidate = SourceCandidate(
            candidate_type="article",
            candidate_url=raw_url,
            candidate_title=fallback_title.strip(),
            candidate_summary="",
            candidate_section=source_id,
            needs_article_fetch=True,
        )
        try:
            expanded = self.article_collector.expand(candidate)
            normalized = normalize_candidate(expanded)
        except Exception as exc:
            logger.warning("Failed to enrich source excerpt for %s: %s", raw_url, exc)
            return cached

        raw_id = self.repo.create_raw_record(
            source_id=source_id.strip() or "event_detail_fetch",
            fetch_mode="event_detail_excerpts",
            payload_hash=self._build_payload_hash(normalized.canonical_url, normalized.title, normalized.summary),
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

    def _build_payload_hash(self, canonical_url: str, title: str, summary: str) -> str:
        payload = "\n".join([canonical_url.strip(), title.strip(), summary.strip()])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
