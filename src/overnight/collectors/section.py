# -*- coding: utf-8 -*-
"""Section page collector for article cards and topic listings."""

from __future__ import annotations

from datetime import datetime
import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from src.overnight.types import SourceCandidate, SourceDefinition


logger = logging.getLogger(__name__)


_GENERIC_ANCHOR_SELECTORS = (
    ".field-content a[href]",
    ".news-title a[href]",
    ".featured-stories__headline a[href]",
    ".view-content a[href]",
    "h5 a[href]",
    "h4 a[href]",
    "h3 a[href]",
    "h2 a[href]",
)
_ARTICLE_PATH_PATTERNS = (
    re.compile(r"/20\d{2}/"),
    re.compile(r"/news/20\d{2}/"),
    re.compile(r"/article/"),
    re.compile(r"/press-releases?/"),
    re.compile(r"/pressroom/releases?/"),
    re.compile(r"/briefing-room/"),
    re.compile(r"/presidential-actions?/"),
    re.compile(r"/briefings-statements?/"),
    re.compile(r"/releases?/"),
)
_HUB_PATH_PATTERNS = (
    re.compile(r"^/$"),
    re.compile(r"^/news/?$"),
    re.compile(r"^/news/current-releases/?$"),
    re.compile(r"^/news/press-releases/?$"),
    re.compile(r"^/world/?$"),
    re.compile(r"^/markets/?$"),
    re.compile(r"^/business/?$"),
    re.compile(r"^/politics/?$"),
    re.compile(r"^/topic/?(?:[^/]+/?)?$"),
    re.compile(r"^/united-kingdom/?$"),
    re.compile(r"^/todayinenergy/?$"),
    re.compile(r"^/stocks/?$"),
    re.compile(r"^/us-market-movers/?$"),
)
_VIDEO_PATH_PATTERN = re.compile(r"/video/")
_TREASURY_RELEASE_PATTERN = re.compile(r"/news/press-releases?/sb\d+$")


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


def _normalize_card_date(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    raw = raw_value.strip()
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if "T" not in raw and " " not in raw:
            return parsed.date().isoformat()
        return parsed.isoformat()
    except ValueError:
        pass

    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return raw


class SectionCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        if not source.entry_urls:
            return []

        candidates: list[SourceCandidate] = []
        seen_urls: set[str] = set()
        for page_url in source.entry_urls:
            try:
                html = _fetch_payload(self._http_client, page_url)
                soup = BeautifulSoup(html, "lxml")
            except Exception as exc:
                logger.warning("Failed to fetch section entry url %s for %s: %s", page_url, source.source_id, exc)
                continue

            cards = soup.select("#news-feed article.news-card, #topic-list article.topic-card")
            for card in cards:
                candidate = _build_card_candidate(card=card, page_url=page_url, source=source)
                if candidate is None or candidate.candidate_url in seen_urls:
                    continue
                seen_urls.add(candidate.candidate_url)
                candidates.append(candidate)

            for anchor in _iter_generic_candidate_links(soup):
                candidate = _build_generic_candidate(anchor=anchor, page_url=page_url, source=source)
                if candidate is None or candidate.candidate_url in seen_urls:
                    continue
                seen_urls.add(candidate.candidate_url)
                candidates.append(candidate)

        return candidates


def _build_card_candidate(card: Tag, *, page_url: str, source: SourceDefinition) -> SourceCandidate | None:
    link = card.find("a", href=True)
    if link is None:
        return None

    href = str(link["href"]).strip()
    title = link.get_text(" ", strip=True)
    if not href or not title:
        return None

    summary_node = card.select_one("p.summary") or card.find("p")
    summary = summary_node.get_text(" ", strip=True) if summary_node else ""
    time_node = card.find("time")
    published_at = None
    if time_node is not None:
        raw_datetime = (time_node.get("datetime") or time_node.get_text(" ", strip=True)).strip() or None
        published_at = _normalize_card_date(raw_datetime)

    return SourceCandidate(
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


def _iter_generic_candidate_links(soup: BeautifulSoup) -> list[Tag]:
    seen: set[tuple[str, str]] = set()
    links: list[Tag] = []
    for selector in _GENERIC_ANCHOR_SELECTORS:
        for anchor in soup.select(selector):
            href = str(anchor.get("href", "")).strip()
            text = anchor.get_text(" ", strip=True)
            key = (href, text)
            if not href or not text or key in seen:
                continue
            seen.add(key)
            links.append(anchor)
    return links


def _build_generic_candidate(anchor: Tag, *, page_url: str, source: SourceDefinition) -> SourceCandidate | None:
    href = str(anchor.get("href", "")).strip()
    title = anchor.get_text(" ", strip=True)
    if not href or not title:
        return None

    candidate_url = urljoin(page_url, href)
    if not _looks_like_article_url(candidate_url, page_url=page_url):
        return None

    summary = _extract_nearby_summary(anchor, title=title)
    published_at = _extract_nearby_published_at(anchor)
    return SourceCandidate(
        candidate_type="section_card",
        candidate_url=candidate_url,
        candidate_title=title,
        candidate_summary=summary,
        candidate_published_at=published_at,
        candidate_section=source.display_name,
        candidate_tags=_card_tags(anchor.parent if isinstance(anchor.parent, Tag) else anchor, source),
        needs_article_fetch=True,
        needs_attachment_fetch=False,
    )


def _looks_like_article_url(url: str, *, page_url: str) -> bool:
    parts = urlsplit(url)
    page_parts = urlsplit(page_url)
    if parts.scheme not in {"http", "https"}:
        return False
    if parts.netloc and parts.netloc != page_parts.netloc:
        return False

    path = parts.path.rstrip("/") or "/"
    lowered_path = path.lower()
    if _VIDEO_PATH_PATTERN.search(lowered_path):
        return False
    if any(pattern.match(lowered_path) for pattern in _HUB_PATH_PATTERNS):
        return False
    if any(pattern.search(lowered_path) for pattern in _ARTICLE_PATH_PATTERNS):
        return True
    if _TREASURY_RELEASE_PATTERN.search(lowered_path):
        return True

    segments = [segment for segment in lowered_path.split("/") if segment]
    if not segments:
        return False
    slug = segments[-1]
    if slug.endswith((".html", ".htm", ".php")):
        return True
    if len(segments) >= 3 and "-" in slug and len(slug) >= 18 and any(character.isdigit() for character in slug):
        return True
    return False


def _extract_nearby_summary(anchor: Tag, *, title: str) -> str:
    containers = _nearby_containers(anchor, max_depth=3)
    title_text = title.strip()
    for container in containers:
        for paragraph in container.find_all("p", limit=3):
            text = paragraph.get_text(" ", strip=True)
            if text and text != title_text and len(text) >= 20:
                return text

    current = anchor.parent if isinstance(anchor.parent, Tag) else None
    sibling_hops = 0
    while current is not None and sibling_hops < 2:
        sibling = current.find_next_sibling(["p", "div"])
        if sibling is None:
            break
        if sibling.name == "p":
            text = sibling.get_text(" ", strip=True)
            if text and text != title_text and len(text) >= 20:
                return text
        else:
            paragraph = sibling.find("p")
            if paragraph is not None:
                text = paragraph.get_text(" ", strip=True)
                if text and text != title_text and len(text) >= 20:
                    return text
        current = sibling
        sibling_hops += 1
    return ""


def _extract_nearby_published_at(anchor: Tag) -> str | None:
    for container in _nearby_containers(anchor, max_depth=3):
        time_node = container.find("time")
        if time_node is None:
            continue
        raw_datetime = (time_node.get("datetime") or time_node.get_text(" ", strip=True)).strip() or None
        normalized = _normalize_card_date(raw_datetime)
        if normalized:
            return normalized
    return None


def _nearby_containers(anchor: Tag, *, max_depth: int) -> list[Tag]:
    containers: list[Tag] = []
    current = anchor.parent if isinstance(anchor.parent, Tag) else None
    depth = 0
    while current is not None and depth < max_depth:
        if current.name in {"article", "div", "li", "section", "span"}:
            containers.append(current)
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return containers
