# -*- coding: utf-8 -*-
"""Article expansion and canonicalization helpers."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src.overnight.types import SourceCandidate


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _extract_summary_from_content(soup: BeautifulSoup) -> str:
    description_meta = soup.find("meta", attrs={"name": "description"})
    if description_meta and description_meta.get("content"):
        return str(description_meta["content"]).strip()

    for container_name in ("article", "main"):
        container = soup.find(container_name)
        if container is None:
            continue
        paragraph = container.find("p")
        if paragraph is not None:
            text = paragraph.get_text(" ", strip=True)
            if text:
                return text

    headline = soup.find("h1")
    if headline is not None:
        paragraph = headline.find_next("p")
        if paragraph is not None:
            text = paragraph.get_text(" ", strip=True)
            if text:
                return text

    body = soup.find("body")
    if body is None:
        return ""
    for paragraph in body.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text:
            return text
    return ""


def extract_article_shell(html: str, fallback_url: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")

    canonical_node = soup.find("link", rel="canonical", href=True)
    canonical_href = canonical_node["href"] if canonical_node else fallback_url
    canonical_url = canonicalize_url(urljoin(fallback_url, str(canonical_href).strip()))

    og_title = soup.find("meta", attrs={"property": "og:title"})
    h1 = soup.find("h1")
    title_node = soup.find("title")
    title = ""
    if og_title and og_title.get("content"):
        title = str(og_title["content"]).strip()
    elif h1:
        title = h1.get_text(" ", strip=True)
    elif title_node:
        title = title_node.get_text(" ", strip=True)

    summary = _extract_summary_from_content(soup)

    return canonical_url, title, summary


def _pick_better_title(existing_title: str, extracted_title: str) -> str:
    candidate_title = extracted_title.strip()
    original_title = existing_title.strip()
    if not candidate_title:
        return original_title
    if not original_title:
        return candidate_title

    normalized_candidate = candidate_title.lower()
    if normalized_candidate in {"news release", "press release", "release", "statement"}:
        return original_title
    if (" - " in candidate_title or " | " in candidate_title) and not any(character.isdigit() for character in candidate_title):
        return original_title
    if len(candidate_title) + 8 < len(original_title):
        return original_title
    return candidate_title


class ArticleCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def expand(self, candidate: SourceCandidate) -> SourceCandidate:
        html = _fetch_payload(self._http_client, candidate.candidate_url)
        canonical_url, canonical_title, canonical_summary = extract_article_shell(html, fallback_url=candidate.candidate_url)
        return replace(
            candidate,
            candidate_url=canonical_url,
            candidate_title=_pick_better_title(candidate.candidate_title, canonical_title),
            candidate_summary=canonical_summary or candidate.candidate_summary,
            needs_article_fetch=False,
        )
