# -*- coding: utf-8 -*-
"""RSS/Atom feed collector for overnight sources."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import feedparser

from app.sources.types import SourceCandidate, SourceDefinition
from app.sources.validation import is_source_url_allowed


logger = logging.getLogger(__name__)

_SPACE_PATTERN = re.compile(r"\s+")
_LINE_SPLIT_PATTERN = re.compile(r"[\r\n]+")
_PERCENT_ARTIFACT_PATTERN = re.compile(r"°\s*%")
_FEED_SKIP_PATTERNS = (
    re.compile(r"^read more$", re.IGNORECASE),
    re.compile(r"^continue reading$", re.IGNORECASE),
)


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


def _normalize_feed_summary(value: object) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    if "<" in candidate and ">" in candidate:
        soup = BeautifulSoup(candidate, "lxml")
        for node in soup.find_all("br"):
            node.replace_with("\n")
        candidate = soup.get_text("\n", strip=True)

    lines: list[str] = []
    for raw_line in _LINE_SPLIT_PATTERN.split(candidate.replace("\xa0", " ")):
        normalized_line = _SPACE_PATTERN.sub(" ", raw_line).strip()
        normalized_line = _PERCENT_ARTIFACT_PATTERN.sub("%", normalized_line)
        if not normalized_line:
            continue
        if any(pattern.match(normalized_line) for pattern in _FEED_SKIP_PATTERNS):
            continue
        lines.append(normalized_line)

    if not lines:
        return ""

    normalized_parts: list[str] = []
    for line in lines:
        if line[-1] not in ".!?":
            line = f"{line}."
        normalized_parts.append(line)
    normalized = " ".join(normalized_parts).strip()
    if any(pattern.match(normalized) for pattern in _FEED_SKIP_PATTERNS):
        return ""
    return normalized


def _extract_feed_summary(entry: feedparser.FeedParserDict) -> str:
    candidates: list[str] = []
    for field in ("summary", "description"):
        normalized = _normalize_feed_summary(entry.get(field, ""))
        if normalized:
            candidates.append(normalized)

    for content_block in list(entry.get("content", []) or []):
        value = content_block.get("value") if isinstance(content_block, dict) else ""
        normalized = _normalize_feed_summary(value)
        if normalized:
            candidates.append(normalized)

    if not candidates:
        return ""

    return max(
        candidates,
        key=lambda candidate: (
            len(candidate),
            candidate.count("."),
        ),
    )


class FeedCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client
        self.last_errors: list[str] = []

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        self.last_errors = []
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
                self.last_errors.append(str(exc).strip())
                continue

            for entry in parsed_feed.entries:
                link = str(entry.get("link", "")).strip()
                title = str(entry.get("title", "")).strip()
                if not link or not title:
                    continue

                candidate_url = urljoin(entry_url, link)
                if candidate_url in seen_urls:
                    continue
                if not is_source_url_allowed(candidate_url, source):
                    continue

                seen_urls.add(candidate_url)
                summary = _extract_feed_summary(entry)
                raw_published = str(entry.get("published", "") or entry.get("updated", "")).strip()
                published_at = _normalize_feed_datetime(raw_published) if raw_published else None
                candidates.append(
                    SourceCandidate(
                        candidate_type="feed_item",
                        candidate_url=candidate_url,
                        candidate_title=title,
                        candidate_summary=summary,
                        candidate_excerpt_source="feed:summary" if summary else "",
                        candidate_published_at=published_at,
                        candidate_published_at_source="feed:published" if published_at else "",
                        candidate_section=source.display_name,
                        candidate_tags=(source.source_id,),
                        needs_article_fetch=True,
                        needs_attachment_fetch=False,
                    )
                )
        return candidates
