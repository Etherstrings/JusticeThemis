# -*- coding: utf-8 -*-
"""Section page collector for article cards and topic listings."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

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


def _card_tags(card: Tag, source: SourceDefinition) -> tuple[str, ...]:
    tags: list[str] = []
    topic = card.get("data-topic")
    if isinstance(topic, str) and topic.strip():
        tags.append(topic.strip().lower())
    if "reuters" in source.source_id:
        tags.append("reuters")
    return tuple(tags)


class SectionCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        if not source.entry_urls:
            return []

        page_url = source.entry_urls[0]
        html = _fetch_payload(self._http_client, page_url)
        soup = BeautifulSoup(html, "lxml")

        cards = soup.select("#news-feed article.news-card, #topic-list article.topic-card")
        candidates: list[SourceCandidate] = []
        for card in cards:
            link = card.find("a", href=True)
            if link is None:
                continue

            href = str(link["href"]).strip()
            title = link.get_text(" ", strip=True)
            if not href or not title:
                continue

            summary_node = card.select_one("p.summary") or card.find("p")
            summary = summary_node.get_text(" ", strip=True) if summary_node else ""
            time_node = card.find("time")
            published_at = None
            if time_node is not None:
                published_at = (time_node.get("datetime") or time_node.get_text(" ", strip=True)).strip() or None

            candidates.append(
                SourceCandidate(
                    candidate_type="section_card",
                    candidate_url=urljoin(page_url, href),
                    candidate_title=title,
                    candidate_summary=summary,
                    candidate_published_at=published_at,
                    candidate_section=source.display_name,
                    candidate_tags=_card_tags(card, source),
                    needs_article_fetch=True,
                    needs_attachment_fetch=False,
                )
            )
        return candidates
