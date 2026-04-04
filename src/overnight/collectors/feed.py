# -*- coding: utf-8 -*-
"""RSS/Atom feed collector for overnight sources."""

from __future__ import annotations

import feedparser

from src.overnight.types import SourceCandidate, SourceDefinition


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


class FeedCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        if not source.entry_urls:
            return []

        feed_text = _fetch_payload(self._http_client, source.entry_urls[0])
        parsed_feed = feedparser.parse(feed_text)

        candidates: list[SourceCandidate] = []
        for entry in parsed_feed.entries:
            link = str(entry.get("link", "")).strip()
            title = str(entry.get("title", "")).strip()
            if not link or not title:
                continue

            summary = str(entry.get("summary", "")).strip()
            published_at = str(entry.get("published", "") or entry.get("updated", "")).strip() or None
            candidates.append(
                SourceCandidate(
                    candidate_type="feed_item",
                    candidate_url=link,
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
