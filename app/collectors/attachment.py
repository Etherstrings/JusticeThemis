# -*- coding: utf-8 -*-
"""Attachment expansion helpers for article-like pages."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.sources.types import SourceCandidate


_ATTACHMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip")


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def _canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _is_attachment_link(href: str) -> bool:
    return href.lower().endswith(_ATTACHMENT_SUFFIXES)


def extract_attachment_candidates(candidate: SourceCandidate, html: str) -> list[SourceCandidate]:
    soup = BeautifulSoup(html, "lxml")
    attachment_candidates: list[SourceCandidate] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"]).strip()
        if not href:
            continue
        resolved_url = _canonicalize_url(urljoin(candidate.candidate_url, href))
        if not _is_attachment_link(resolved_url) or resolved_url in seen_urls:
            continue

        seen_urls.add(resolved_url)
        title = link.get_text(" ", strip=True)
        if not title:
            title = PurePosixPath(urlsplit(resolved_url).path).name

        attachment_candidates.append(
            SourceCandidate(
                candidate_type="attachment",
                candidate_url=resolved_url,
                candidate_title=title,
                candidate_summary="",
                candidate_published_at=candidate.candidate_published_at,
                candidate_published_at_source=candidate.candidate_published_at_source,
                candidate_section=candidate.candidate_section,
                candidate_tags=("attachment",),
                needs_article_fetch=False,
                needs_attachment_fetch=False,
            )
        )
    return attachment_candidates


class AttachmentCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def expand(self, candidate: SourceCandidate) -> list[SourceCandidate]:
        html = _fetch_payload(self._http_client, candidate.candidate_url)
        return extract_attachment_candidates(candidate, html)
