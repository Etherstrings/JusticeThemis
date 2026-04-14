# -*- coding: utf-8 -*-
"""Calendar/release schedule collector."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.sources.types import SourceCandidate, SourceDefinition
from app.sources.validation import is_source_url_allowed


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def _parse_schedule_date(raw_date: str) -> str | None:
    for pattern in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw_date, pattern).date().isoformat()
        except ValueError:
            continue
    return None


class CalendarCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client
        self.last_errors: list[str] = []

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        self.last_errors = []
        if not source.entry_urls:
            return []

        page_url = source.entry_urls[0]
        try:
            html = _fetch_payload(self._http_client, page_url)
        except Exception as exc:
            self.last_errors.append(str(exc).strip())
            raise
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("table#schedule-table tbody tr")

        candidates: list[SourceCandidate] = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            published_at = _parse_schedule_date(cells[0].get_text(" ", strip=True))
            release_link = cells[2].find("a", href=True)
            title = cells[2].get_text(" ", strip=True)
            if not title:
                continue

            candidate_url = page_url
            needs_article_fetch = False
            if release_link is not None:
                candidate_url = urljoin(page_url, str(release_link["href"]).strip())
                if not is_source_url_allowed(candidate_url, source):
                    continue
                needs_article_fetch = True

            candidates.append(
                SourceCandidate(
                    candidate_type="calendar_event",
                    candidate_url=candidate_url,
                    candidate_title=title,
                    candidate_summary=cells[1].get_text(" ", strip=True),
                    candidate_published_at=published_at,
                    candidate_published_at_source="calendar:row" if published_at else "",
                    candidate_section=source.display_name,
                    candidate_tags=("calendar",),
                    needs_article_fetch=needs_article_fetch,
                    needs_attachment_fetch=False,
                )
            )
        return candidates
