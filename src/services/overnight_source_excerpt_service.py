# -*- coding: utf-8 -*-
"""Resolve source-page excerpts with DB-backed caching."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import logging
from typing import Protocol

import requests

from src.overnight.collectors.article import ArticleCollector, canonicalize_url
from src.overnight.normalizer import normalize_candidate
from src.overnight.ledger import StoredSourceItem
from src.overnight.types import SourceCandidate
from src.repositories.overnight_repo import OvernightRepository

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

    def fetch(self, url: str) -> str:
        response = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": self.USER_AGENT},
        )
        response.raise_for_status()
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        return response.text


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
        if not all(
            hasattr(self.repo, method_name)
            for method_name in (
                "list_latest_source_items_by_urls",
                "create_raw_record",
                "persist_source_item",
                "assign_document_family",
                "attach_document_version",
            )
        ):
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
