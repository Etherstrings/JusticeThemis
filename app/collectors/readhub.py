# -*- coding: utf-8 -*-
"""Dedicated collector for Readhub daily digest and topic enrichment."""

from __future__ import annotations

from datetime import datetime
import json
import re
from urllib.parse import urljoin

from app.sources.types import SourceCandidate, SourceDefinition


_ISSUE_DATE_PATTERN = re.compile(r">(20\d{2}\.\d{2}\.\d{2})<")


def _fetch_payload(http_client: object, url: str) -> str:
    fetch = getattr(http_client, "fetch", None)
    if callable(fetch):
        payload = fetch(url)
    elif callable(http_client):
        payload = http_client(url)
    else:
        raise TypeError("http_client must be callable or expose fetch(url)")
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


class ReadhubDailyCollector:
    def __init__(self, http_client: object) -> None:
        self._http_client = http_client
        self.last_errors: list[str] = []

    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        self.last_errors = []
        if not source.entry_urls:
            return []

        canonical_daily_url = str(source.entry_urls[0]).strip()
        daily_html = _fetch_payload(self._http_client, canonical_daily_url)
        issue_date = _extract_issue_date(daily_html)
        daily_articles = _extract_daily_articles(daily_html)
        candidates: list[SourceCandidate] = []

        for rank, article in enumerate(daily_articles, start=1):
            topic_id = str(article.get("id", "")).strip()
            title = str(article.get("title", "")).strip()
            summary = str(article.get("summary", "")).strip()
            if not topic_id or not title:
                continue

            topic_url = urljoin(canonical_daily_url, f"/topic/{topic_id}")
            entity_names = tuple(
                str(item.get("name", "")).strip()
                for item in list(article.get("entityList", []) or [])
                if str(item.get("name", "")).strip()
            )
            source_context = {
                "source_family": "readhub_daily",
                "daily": {
                    "canonical_url": canonical_daily_url,
                    "issue_date": issue_date,
                    "rank": rank,
                },
                "topic": {
                    "id": topic_id,
                    "tags": [],
                    "tracking": [],
                    "similar_events": [],
                    "news_links": [],
                    "enrichment_status": "not_attempted",
                },
            }
            published_at = None
            excerpt_source = "readhub:daily_articles"

            try:
                topic_html = _fetch_payload(self._http_client, topic_url)
                topic_state = _extract_topic_initial_state(topic_html)
                topic_summary = str(topic_state.get("summary", "")).strip()
                if topic_summary:
                    summary = topic_summary
                relative_date = str(topic_state.get("relativeDate", "")).strip()
                topic_entity_names = tuple(
                    str(item.get("name", "")).strip()
                    for item in list(topic_state.get("entityList", []) or [])
                    if str(item.get("name", "")).strip()
                )
                if topic_entity_names:
                    entity_names = topic_entity_names
                source_context["topic"] = {
                    "id": topic_id,
                    "relative_date": relative_date,
                    "tags": _topic_tag_names(topic_state),
                    "tracking": _topic_tracking_rows(topic_state),
                    "similar_events": _topic_similar_events(topic_state),
                    "news_links": _topic_news_links(topic_state),
                    "enrichment_status": "ok",
                }
                published_at = _tracking_publish_date(topic_state)
                excerpt_source = "readhub:topic_initial_state"
            except Exception as exc:
                self.last_errors.append(f"topic_enrichment_failed: {topic_url} | {str(exc).strip()}")
                source_context["topic"]["enrichment_status"] = "fetch_failed"

            candidates.append(
                SourceCandidate(
                    candidate_type="readhub_topic",
                    candidate_url=topic_url,
                    candidate_title=title,
                    candidate_summary=summary,
                    candidate_excerpt_source=excerpt_source,
                    candidate_published_at=published_at,
                    candidate_published_at_source="readhub:tracking_publish_date" if published_at else "",
                    candidate_section=source.display_name,
                    candidate_tags=("readhub",),
                    candidate_entity_names=entity_names,
                    source_context=source_context,
                    needs_article_fetch=False,
                    needs_attachment_fetch=False,
                    capture_path="direct",
                )
            )

        for legacy_alias_url in tuple(source.entry_urls[1:]):
            probe_url = str(legacy_alias_url).strip()
            if not probe_url:
                continue
            try:
                _fetch_payload(self._http_client, probe_url)
            except Exception as exc:
                self.last_errors.append(
                    f"legacy_alias_probe_failed: {probe_url} | {str(exc).strip()}"
                )

        return candidates


def _extract_issue_date(html: str) -> str:
    match = _ISSUE_DATE_PATTERN.search(html)
    if match is None:
        return ""
    raw_value = match.group(1).strip()
    try:
        return datetime.strptime(raw_value, "%Y.%m.%d").date().isoformat()
    except ValueError:
        return raw_value.replace(".", "-")


def _extract_daily_articles(html: str) -> list[dict[str, object]]:
    normalized_html = _decode_embedded_json(html)
    payload = _extract_json_payload(
        html=normalized_html,
        markers=('"articles":[',),
        opening_char="[",
        closing_char="]",
    )
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _extract_topic_initial_state(html: str) -> dict[str, object]:
    normalized_html = _decode_embedded_json(html)
    payload = _extract_json_payload(
        html=normalized_html,
        markers=('"initialState":{',),
        opening_char="{",
        closing_char="}",
    )
    return payload if isinstance(payload, dict) else {}


def _extract_json_payload(
    *,
    html: str,
    markers: tuple[str, ...],
    opening_char: str,
    closing_char: str,
) -> object:
    for marker in markers:
        marker_index = html.find(marker)
        if marker_index < 0:
            continue
        start_index = marker_index + len(marker) - 1
        fragment = _balanced_fragment(html, start_index, opening_char=opening_char, closing_char=closing_char)
        if not fragment:
            continue
        try:
            return _load_first_json_value(_decode_embedded_json(fragment))
        except json.JSONDecodeError:
            continue

    key_names = list(
        dict.fromkeys(
            key_name
            for marker in markers
            for key_name in re.findall(r"[A-Za-z]+", marker)
        )
    )
    for key_name in key_names:
        search_start = 0
        while True:
            key_index = html.find(key_name, search_start)
            if key_index < 0:
                break
            colon_index = html.find(":", key_index)
            if colon_index < 0:
                break
            start_index = html.find(opening_char, colon_index)
            if start_index < 0:
                break
            fragment = _balanced_fragment(
                html,
                start_index,
                opening_char=opening_char,
                closing_char=closing_char,
            )
            if fragment:
                try:
                    return _load_first_json_value(_decode_embedded_json(fragment))
                except json.JSONDecodeError:
                    pass
            search_start = key_index + len(key_name)
    raise ValueError(f"Readhub payload marker not found for {markers[0]}")


def _balanced_fragment(text: str, start_index: int, *, opening_char: str, closing_char: str) -> str:
    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == opening_char:
            depth += 1
        elif char == closing_char:
            depth -= 1
            if depth == 0:
                return text[start_index:index + 1]
    return ""


def _decode_embedded_json(fragment: str) -> str:
    return (
        fragment.replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\n", " ")
        .replace("\\t", " ")
    )


def _load_first_json_value(payload: str) -> object:
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(payload.lstrip())
    return value


def _tracking_publish_date(topic_state: dict[str, object]) -> str | None:
    tracking_list = list(topic_state.get("trackingList", []) or [])
    if not tracking_list:
        return None
    publish_date = str(dict(tracking_list[0]).get("publishDate", "")).strip()
    if not publish_date:
        return None
    try:
        return datetime.fromisoformat(publish_date.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return publish_date


def _topic_tag_names(topic_state: dict[str, object]) -> list[str]:
    return [
        str(item.get("name", "")).strip()
        for item in list(topic_state.get("tagList", []) or [])[:10]
        if str(item.get("name", "")).strip()
    ]


def _topic_tracking_rows(topic_state: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in list(topic_state.get("trackingList", []) or [])[:10]:
        row = dict(item or {})
        rows.append(
            {
                "publish_date": str(row.get("publishDate", "")).strip(),
                "title": str(row.get("title", "")).strip(),
                "uid": str(row.get("uid", "")).strip(),
            }
        )
    return rows


def _topic_similar_events(topic_state: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in list(topic_state.get("similarEventList", []) or [])[:5]:
        payload = dict(item or {})
        events: list[dict[str, str]] = []
        for event in list(payload.get("events", []) or [])[:5]:
            event_payload = dict(event or {})
            events.append(
                {
                    "title": str(event_payload.get("title", "")).strip(),
                    "content": str(event_payload.get("content", "")).strip(),
                }
            )
        rows.append(
            {
                "name": str(payload.get("name", "")).strip(),
                "time": str(payload.get("time", "")).strip(),
                "events": events,
            }
        )
    return rows


def _topic_news_links(topic_state: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in list(topic_state.get("newsList", []) or [])[:10]:
        payload = dict(item or {})
        rows.append(
            {
                "site_name": str(payload.get("siteNameDisplay", "")).strip(),
                "title": str(payload.get("title", "")).strip(),
                "url": str(payload.get("url", "")).strip(),
            }
        )
    return rows
