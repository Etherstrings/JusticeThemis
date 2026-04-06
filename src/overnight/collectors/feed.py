# -*- coding: utf-8 -*-
"""RSS/Atom feed collector for overnight sources."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
import logging
from urllib.parse import urljoin

import feedparser

from src.overnight.types import SourceCandidate, SourceDefinition


logger = logging.getLogger(__name__)


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def _normalize_feed_datetime(raw_value: str) -> str | None:
    raw = raw_value.strip()
    if not raw:
        return None

    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        pass

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        return raw


class FeedCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        if not source.entry_urls:
            return []

        candidates: list[SourceCandidate] = []
        seen_urls: set[str] = set()
        for entry_url in source.entry_urls:
            try:
                feed_text = _fetch_payload(self._http_client, entry_url)
                parsed_feed = feedparser.parse(feed_text)
            except Exception as exc:
                logger.warning("Failed to fetch feed entry url %s for %s: %s", entry_url, source.source_id, exc)
                continue

            for entry in parsed_feed.entries:
                link = str(entry.get("link", "")).strip()
                title = str(entry.get("title", "")).strip()
                if not link or not title:
                    continue

                candidate_url = urljoin(entry_url, link)
                if candidate_url in seen_urls:
                    continue

                seen_urls.add(candidate_url)
                summary = str(entry.get("summary", "")).strip()
                raw_published = str(entry.get("published", "") or entry.get("updated", "")).strip()
                published_at = _normalize_feed_datetime(raw_published) if raw_published else None
                candidates.append(
                    SourceCandidate(
                        candidate_type="feed_item",
                        candidate_url=candidate_url,
                        candidate_title=title,
                        candidate_summary=summary,
                        candidate_published_at=published_at,
                        candidate_section=source.display_name,
                        candidate_tags=(source.source_id,),
                        needs_article_fetch=True,
                        needs_attachment_fetch=False,
                    )
                )
        return candidates
