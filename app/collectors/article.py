# -*- coding: utf-8 -*-
"""Article expansion and canonicalization helpers."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from email.utils import parsedate_to_datetime
import html
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.sources.types import SourceCandidate

_SITE_BODY_SELECTORS: dict[str, tuple[str, ...]] = {
    "whitehouse.gov": (
        ".entry-content.wp-block-post-content",
        ".wp-block-post-content",
        "main article",
        "main",
    ),
    "federalreserve.gov": (
        "#article .col-xs-12.col-sm-8.col-md-8",
        "#article",
        "#content",
        "main",
    ),
    "home.treasury.gov": (
        ".field--name-field-news-body",
        "#block-hamilton-content .field--name-field-news-body",
        "article.entity--type-node",
        "main",
    ),
    "ustr.gov": (
        ".field--name-body",
        "main article",
        "main",
    ),
    "apnews.com": (
        ".RichTextStoryBody",
        ".Page-storyBody .RichTextStoryBody",
        "[data-key='article-body']",
        "main article",
        "main",
    ),
    "cnbc.com": (
        ".ArticleBody-articleBody",
        "article",
        "main",
    ),
    "eia.gov": (
        ".pagecontent.mr_temp4",
        ".pagecontent .main_col",
        ".pagecontent",
    ),
}
_SITE_PUBLISHED_AT_SELECTORS: dict[str, tuple[tuple[str, str], ...]] = {
    "ofac.treasury.gov": (
        (".field--name-field-release-date .field__item", "html:field_release_date"),
    ),
}
_GENERIC_BODY_SELECTORS = (
    "article",
    "main",
    "[role='main']",
    "#content",
    "#main-content",
    "#content-area",
)
_IGNORED_ANCESTOR_KEYWORDS = (
    "breadcrumb",
    "share",
    "social",
    "footer",
    "sidebar",
    "related",
    "newsletter",
    "subscribe",
    "promo",
    "menu",
    "nav",
)
_BLOCK_TAGS = ("p", "li", "h2", "h3", "h4", "blockquote")
_SPACE_PATTERN = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_PATTERN = re.compile(r"\s+([,.;:!?])")
_SPACE_AFTER_OPEN_BRACKET_PATTERN = re.compile(r"([\(\[\{])\s+")
_SPACE_BEFORE_CLOSE_BRACKET_PATTERN = re.compile(r"\s+([\)\]\}])")
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?](?:['\")\]]+)?$")
_TIME_ONLY_PATTERN = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APMapm]{2})?$")
_EXHIBIT_HEADING_PATTERN = re.compile(r".*\(exhibit(?:s)? [^)]+\)$", re.IGNORECASE)
_INLINE_EVENT_FIELD_PATTERN = re.compile(r"\s+(?:Time|Location):\s*.+?(?=(?:\s+(?:Time|Location):)|$)", re.IGNORECASE)
_LIKELY_LABEL_WITH_BODY_PATTERN = re.compile(r"^([^.!?]{3,80})\.\s+(.+)$")
_LIKELY_SENTENCE_VERB_PATTERN = re.compile(
    r"\b(?:is|are|was|were|be|been|being|have|has|had|will|would|could|should|may|might|must|"
    r"do|does|did|increase|increases|increased|decrease|decreases|decreased|"
    r"rise|rises|rose|fall|falls|fell|add|adds|added|remain|remains|remained|"
    r"said|says|say|include|includes|included)\b",
    re.IGNORECASE,
)
_ITINERARY_DATE_HEADING_PATTERN = re.compile(
    r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}$",
    re.IGNORECASE,
)
_FED_ACCESSIBLE_VERSION_PATTERN = re.compile(
    r"^(?:[A-Z][a-z]+ \d{1,2}, \d{4}:\s+)?[^.]*\baccessible version\b:?$",
    re.IGNORECASE,
)
_FED_TABLE_OR_FIGURE_HEADING_PATTERN = re.compile(r"^(?:table|figure)\s+\d+[A-Z]?(?:\.\d+)?\b", re.IGNORECASE)
_SKIP_TEXT_PATTERNS = (
    re.compile(r"^#{3,}$"),
    re.compile(r"^skip to main content$", re.IGNORECASE),
    re.compile(r"^press releases?$", re.IGNORECASE),
    re.compile(r"^statements?\s*&\s*remarks?$", re.IGNORECASE),
    re.compile(r"^view all", re.IGNORECASE),
    re.compile(r"^read more$", re.IGNORECASE),
    re.compile(r"^key takeaways .* are below\.?$", re.IGNORECASE),
    re.compile(r"^privacy policy$", re.IGNORECASE),
    re.compile(r"^site policies", re.IGNORECASE),
    re.compile(r"^careers$", re.IGNORECASE),
    re.compile(r"^additional enforcement actions can be searched for here\b.*$", re.IGNORECASE),
    re.compile(r"^for media inquiries(?:,)?\s+(?:please\s+)?", re.IGNORECASE),
    re.compile(r"^next release:", re.IGNORECASE),
    re.compile(r"^source:", re.IGNORECASE),
    re.compile(r"^time:\s*", re.IGNORECASE),
    re.compile(r"^location:\s*", re.IGNORECASE),
    re.compile(r"^federal open market committee:?$", re.IGNORECASE),
    _FED_ACCESSIBLE_VERSION_PATTERN,
    re.compile(r"^for release at\b.*$", re.IGNORECASE),
    re.compile(r"^this event is open to registered media\b.*$", re.IGNORECASE),
    re.compile(r"^please rsvp to\b.*$", re.IGNORECASE),
    re.compile(r"^attachment\s*\(pdf\)\.?$", re.IGNORECASE),
    re.compile(r"^eia (?:program|press) contact:", re.IGNORECASE),
    re.compile(
        r"^the product described in this press release was prepared by the u\.s\. energy information administration\b.*$",
        re.IGNORECASE,
    ),
    re.compile(r"^_{3,}$"),
    re.compile(r"^(?:\([^)]{1,4}\)\s*)?statistical significance is not applicable\b.*$", re.IGNORECASE),
    re.compile(r"^associated press .*\bcontributed to this report\.?$", re.IGNORECASE),
    re.compile(r"^.+\bis on threads:.*$", re.IGNORECASE),
    re.compile(
        r"^[A-Za-z0-9 ,/&:-]{1,100}\((?:PDF|CSV|XLSX?|ZIP)\)(?:\s*\|\s*[A-Za-z0-9 ,/&:-]{1,80})+$",
        re.IGNORECASE,
    ),
    re.compile(r".*\(AP Photo\/[^)]+\).*$"),
    re.compile(r"^file\s*-\s.*\(AP Photo\/[^)]+\).*$", re.IGNORECASE),
)
_MAX_EXCERPT_CHARS = 1600
_MAX_EXCERPT_BLOCKS = 14
_GENERIC_SUMMARY_PATTERNS = (
    re.compile(r"\bofficial source for\b", re.IGNORECASE),
    re.compile(r"\bprovides information on\b", re.IGNORECASE),
    re.compile(r"\bresponsible for issuing regulations\b", re.IGNORECASE),
    re.compile(r"\bdedicated to factual reporting\b", re.IGNORECASE),
    re.compile(r"\bmore than half the world'?s population sees\b", re.IGNORECASE),
)
_DETAIL_SIGNAL_PATTERNS = (
    re.compile(r"\$\d"),
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE),
    re.compile(r"\b(?:increased|decreased|rose|fell|deficit|surplus|imports|exports|tariff|sanctions|inflation|rate)\b", re.IGNORECASE),
)
_ACCESSIBLE_LINK_TEXT_PATTERNS = (
    re.compile(r"\baccessible materials\b", re.IGNORECASE),
    re.compile(r"\baccessible version\b", re.IGNORECASE),
)
_ATTACHED_MATERIAL_SUMMARY_PATTERN = re.compile(r"\battached tables? and charts?\b", re.IGNORECASE)
_FED_LEADING_PREAMBLE_PATTERNS = (
    re.compile(r"^federal open market committee$", re.IGNORECASE),
    re.compile(r"^accessible version$", re.IGNORECASE),
    re.compile(r"^.+accessible version$", re.IGNORECASE),
    re.compile(r"^for release at\b", re.IGNORECASE),
)
_PUBLISHED_META_CANDIDATES: tuple[tuple[dict[str, str], str], ...] = (
    ({"property": "article:published_time"}, "html:meta_article_published_time"),
    ({"name": "article:published_time"}, "html:meta_article_published_time"),
    ({"property": "og:published_time"}, "html:meta_og_published_time"),
    ({"name": "publish-date"}, "html:meta_publish_date"),
    ({"name": "pubdate"}, "html:meta_pubdate"),
    ({"name": "date"}, "html:meta_date"),
    ({"itemprop": "datePublished"}, "html:meta_itemprop_date_published"),
)
_EMBEDDED_JSON_PUBLISHED_AT_KEYS: tuple[tuple[str, str], ...] = (
    ("publishedon", "html:embedded_json_published_on"),
    ("publishedat", "html:embedded_json_published_at"),
    ("publishdate", "html:embedded_json_publish_date"),
    ("datepublished", "html:embedded_json_date_published"),
)
_JSONLD_SUMMARY_FIELDS: tuple[tuple[str, str], ...] = (
    ("articleBody", "jsonld:articleBody"),
    ("description", "jsonld:description"),
)
_EMBEDDED_JSON_SUMMARY_FIELDS: tuple[tuple[str, str], ...] = (
    ("teaserSnippet", "embedded_json:teaserSnippet"),
    ("summary", "embedded_json:summary"),
    ("description", "embedded_json:description"),
    ("articleBody", "embedded_json:articleBody"),
    ("body", "embedded_json:body"),
)
_EMBEDDED_JSON_URL_KEYS = {
    "canonicalurl",
    "href",
    "link",
    "path",
    "pathname",
    "url",
    "urlalias",
}
_AUTHOR_BIO_PATTERNS = (
    re.compile(
        r"\b(?:is|was)\s+(?:an?|the)\s+[^.]{0,120}\b(?:reporter|editor|journalist|producer|broadcaster)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bover\s+\d+\s+years of experience as (?:a|an)\s+writer, editor\b", re.IGNORECASE),
    re.compile(r"\bhas a diploma in journalism\b", re.IGNORECASE),
    re.compile(r"\b(?:more than|over)\s+(?:a\s+decade|\d+\s+years?)\s+of reporting experience\b", re.IGNORECASE),
    re.compile(r"\bcan be contacted at\b", re.IGNORECASE),
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


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _matching_body_selectors(url: str) -> tuple[str, ...]:
    hostname = urlsplit(url).netloc.lower()
    selectors: list[str] = []
    for domain, domain_selectors in _SITE_BODY_SELECTORS.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            selectors.extend(domain_selectors)
    selectors.extend(_GENERIC_BODY_SELECTORS)
    seen: set[str] = set()
    ordered: list[str] = []
    for selector in selectors:
        if selector in seen:
            continue
        seen.add(selector)
        ordered.append(selector)
    return tuple(ordered)


def _normalize_block_text(value: str) -> str:
    normalized = _SPACE_PATTERN.sub(" ", value.replace("\xa0", " ")).strip()
    normalized = _SPACE_AFTER_OPEN_BRACKET_PATTERN.sub(r"\1", normalized)
    normalized = _SPACE_BEFORE_CLOSE_BRACKET_PATTERN.sub(r"\1", normalized)
    return _SPACE_BEFORE_PUNCT_PATTERN.sub(r"\1", normalized)


def _matching_published_at_selectors(url: str) -> tuple[tuple[str, str], ...]:
    hostname = urlsplit(url).netloc.lower()
    selectors: list[tuple[str, str]] = []
    for domain, domain_selectors in _SITE_PUBLISHED_AT_SELECTORS.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            selectors.extend(domain_selectors)
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for selector in selectors:
        if selector in seen:
            continue
        seen.add(selector)
        ordered.append(selector)
    return tuple(ordered)


def _clean_extracted_block_text(text: str) -> str:
    cleaned = _INLINE_EVENT_FIELD_PATTERN.sub("", text)
    return _normalize_block_text(cleaned)


def _truncate_excerpt(value: str, *, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    normalized = _normalize_block_text(value)
    if len(normalized) <= max_chars:
        return normalized

    candidate = normalized[:max_chars].rstrip()
    sentence_cut = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_cut >= max_chars // 2:
        return candidate[: sentence_cut + 1].strip()

    word_cut = candidate.rfind(" ")
    if word_cut >= max_chars // 2:
        return candidate[:word_cut].strip()
    return candidate


def _looks_like_boilerplate(text: str) -> bool:
    normalized = _normalize_block_text(text)
    if len(normalized) < 3:
        return True
    return any(pattern.match(normalized) for pattern in _SKIP_TEXT_PATTERNS)


def _normalize_summary_value(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    candidate = html.unescape(candidate)
    if "<" in candidate and ">" in candidate:
        candidate = BeautifulSoup(candidate, "lxml").get_text(" ", strip=True)
    return _normalize_block_text(candidate)


def _normalize_published_at_value(value: str) -> str | None:
    candidate = _normalize_summary_value(value)
    if not candidate:
        return None
    if _TIME_ONLY_PATTERN.match(candidate):
        return None

    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        if "T" not in candidate and " " not in candidate:
            return parsed.date().isoformat()
        return parsed.isoformat()
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(candidate).isoformat()
    except (TypeError, ValueError):
        pass

    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(candidate, pattern).date().isoformat()
        except ValueError:
            continue

    return candidate


def _iter_json_ld_objects(soup: BeautifulSoup) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_payload = node.string or node.get_text(" ", strip=True)
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue

        stack: list[object] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, list):
                stack.extend(current)
                continue
            if not isinstance(current, dict):
                continue
            objects.append(current)
            graph = current.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)

    return objects


def _iter_embedded_json_objects(soup: BeautifulSoup) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    for node in soup.find_all("script"):
        script_id = str(node.get("id") or "").strip()
        script_type = str(node.get("type") or "").strip().lower()
        if script_id != "__NEXT_DATA__" and script_type != "application/json":
            continue
        raw_payload = node.string or node.get_text(" ", strip=True)
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue

        stack: list[object] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, list):
                stack.extend(current)
                continue
            if not isinstance(current, dict):
                continue
            objects.append(current)
            stack.extend(current.values())

    return objects


def _normalize_embedded_json_published_at_value(value: object) -> str | None:
    if isinstance(value, str):
        return _normalize_published_at_value(value)
    if isinstance(value, dict):
        for nested_key in ("time", "iso", "datetime", "date", "value"):
            nested_value = value.get(nested_key)
            if isinstance(nested_value, str):
                normalized = _normalize_published_at_value(nested_value)
                if normalized:
                    return normalized
    if isinstance(value, list):
        for item in value:
            normalized = _normalize_embedded_json_published_at_value(item)
            if normalized:
                return normalized
    return None


def _extract_html_published_at(soup: BeautifulSoup, *, article_url: str = "") -> tuple[str | None, str]:
    for attrs, source in _PUBLISHED_META_CANDIDATES:
        meta_node = soup.find("meta", attrs=attrs)
        if meta_node is None or not meta_node.get("content"):
            continue
        normalized = _normalize_published_at_value(str(meta_node["content"]))
        if normalized:
            return normalized, source

    for payload in _iter_json_ld_objects(soup):
        raw_date = payload.get("datePublished")
        if not isinstance(raw_date, str):
            continue
        normalized = _normalize_published_at_value(raw_date)
        if normalized:
            return normalized, "html:jsonld_datePublished"

    for payload in _iter_embedded_json_objects(soup):
        for raw_key, raw_value in payload.items():
            key = str(raw_key).strip().lower()
            for candidate_key, source in _EMBEDDED_JSON_PUBLISHED_AT_KEYS:
                if key != candidate_key:
                    continue
                normalized = _normalize_embedded_json_published_at_value(raw_value)
                if normalized:
                    return normalized, source

    time_node = soup.find("time")
    if time_node is not None:
        raw_time = str(time_node.get("datetime") or time_node.get_text(" ", strip=True)).strip()
        normalized = _normalize_published_at_value(raw_time)
        if normalized:
            return normalized, "html:time_datetime" if time_node.get("datetime") else "html:time_text"

    for selector, source in _matching_published_at_selectors(article_url):
        for node in soup.select(selector):
            raw_value = str(node.get("datetime") or node.get("content") or node.get_text(" ", strip=True)).strip()
            normalized = _normalize_published_at_value(raw_value)
            if normalized:
                return normalized, source

    return None, ""


def _normalize_for_comparison(value: str) -> str:
    normalized = _normalize_summary_value(value)
    return (
        normalized.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
    )


def _normalize_url_match_parts(value: str, *, fallback_url: str) -> tuple[str, str]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return "", ""

    resolved = urljoin(fallback_url, raw_value) if fallback_url else raw_value
    parts = urlsplit(resolved)
    host = parts.netloc.lower()
    path = re.sub(r"/{2,}", "/", (parts.path or "/").strip())
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return host, path or "/"


def _summary_quality_score(text: str) -> int:
    normalized = _normalize_summary_value(text)
    if not normalized:
        return -10

    score = min(len(normalized), 1200) // 16
    if any(pattern.search(normalized) for pattern in _GENERIC_SUMMARY_PATTERNS):
        score -= 35
    if any(pattern.search(normalized) for pattern in _DETAIL_SIGNAL_PATTERNS):
        score += 18
    if "(AP Photo/" in normalized:
        score -= 30
    if any(pattern.search(normalized) for pattern in _AUTHOR_BIO_PATTERNS):
        score -= 90
    if normalized.count(":") >= 2:
        score += 4
    return score


def _pick_better_summary(existing_summary: str, extracted_summary: str) -> tuple[str, str]:
    normalized_existing = _normalize_summary_value(existing_summary)
    normalized_extracted = _normalize_summary_value(extracted_summary)

    if not normalized_existing:
        return normalized_extracted, ""
    if not normalized_extracted:
        return normalized_existing, "candidate_summary:preferred"

    existing_score = _summary_quality_score(normalized_existing)
    extracted_score = _summary_quality_score(normalized_extracted)
    if existing_score >= extracted_score + 8:
        return normalized_existing, "candidate_summary:preferred"
    return normalized_extracted, ""


def _strip_repeated_title_prefix(summary: str, title: str) -> str:
    normalized_summary = _normalize_summary_value(summary)
    normalized_title = _normalize_summary_value(title)
    if not normalized_summary or not normalized_title:
        return normalized_summary

    lowered_summary = _normalize_for_comparison(normalized_summary).lower()
    lowered_title = _normalize_for_comparison(normalized_title).lower()
    if not lowered_summary.startswith(lowered_title):
        return normalized_summary

    remainder = normalized_summary[len(normalized_title):].lstrip(" :;-—–")
    if len(remainder) < 40:
        return normalized_summary
    return remainder


def _has_ignored_ancestor(node: Tag, *, root: Tag) -> bool:
    current = node.parent
    while isinstance(current, Tag):
        if current is root:
            return False
        if current.name in {"header", "nav", "footer", "aside", "form", "script", "style", "noscript"}:
            return True
        joined_classes = " ".join(current.get("class", []))
        joined_id = str(current.get("id", ""))
        joined = f"{joined_classes} {joined_id}".lower()
        if any(keyword in joined for keyword in _IGNORED_ANCESTOR_KEYWORDS):
            return True
        current = current.parent
    return False


def _extract_block_excerpt(container: Tag, *, fallback_url: str) -> tuple[str, int]:
    blocks: list[str] = []
    seen: set[str] = set()
    first_heading = container.find("h1")

    if isinstance(first_heading, Tag):
        elements = (
            element
            for element in first_heading.find_all_next(_BLOCK_TAGS)
            if container in element.parents
        )
    else:
        elements = container.find_all(_BLOCK_TAGS)

    for element in elements:
        if _has_ignored_ancestor(element, root=container):
            continue

        text = _clean_extracted_block_text(element.get_text(" ", strip=True))
        text = _format_list_item_label_with_body(element, text=text)
        if not text or text in seen or _looks_like_boilerplate(text):
            continue
        if _should_skip_site_specific_leading_metadata_block(
            element=element,
            text=text,
            block_count=len(blocks),
            fallback_url=fallback_url,
        ):
            continue
        if _should_skip_leading_block(text=text, block_count=len(blocks), fallback_url=fallback_url):
            continue
        if _should_stop_excerpt_before_block(text=text, block_count=len(blocks), fallback_url=fallback_url):
            break
        if _is_section_heading_block(element, text=text) and not text.endswith((".", "!", "?", ":", ";")):
            text = f"{text}:"
        seen.add(text)
        blocks.append(text)
        combined = " ".join(blocks)
        if len(combined) >= _MAX_EXCERPT_CHARS or len(blocks) >= _MAX_EXCERPT_BLOCKS:
            return _truncate_excerpt(combined), len(blocks)

    return _truncate_excerpt(" ".join(blocks)), len(blocks)


def _format_list_item_label_with_body(element: Tag, *, text: str) -> str:
    if element.name != "li":
        return text

    match = _LIKELY_LABEL_WITH_BODY_PATTERN.match(text)
    if match is None:
        return text

    label, remainder = match.groups()
    label = label.strip()
    remainder = remainder.strip()
    if not label or not remainder:
        return text
    if len(label.split()) > 7:
        return text
    if any(character.isdigit() for character in label):
        return text
    if _LIKELY_SENTENCE_VERB_PATTERN.search(label):
        return text
    return f"{label}: {remainder}"


def _should_skip_site_specific_leading_metadata_block(
    *,
    element: Tag,
    text: str,
    block_count: int,
    fallback_url: str,
) -> bool:
    if block_count > 0:
        return False

    hostname = urlsplit(fallback_url).netloc.lower()
    if hostname == "farmdocdaily.illinois.edu":
        if element.name != "li":
            return False
        if len(text) > 180:
            return False
        if _SENTENCE_BOUNDARY_PATTERN.search(text):
            return False
        if _LIKELY_SENTENCE_VERB_PATTERN.search(text):
            return False
        return True

    return False


def _should_stop_excerpt_before_block(*, text: str, block_count: int, fallback_url: str) -> bool:
    hostname = urlsplit(fallback_url).netloc.lower()
    if (hostname == "ustr.gov" or hostname.endswith(".ustr.gov")) and block_count >= 1:
        if _ITINERARY_DATE_HEADING_PATTERN.match(text):
            return True
    if (hostname == "federalreserve.gov" or hostname.endswith(".federalreserve.gov")) and block_count >= 1:
        if _FED_TABLE_OR_FIGURE_HEADING_PATTERN.match(text):
            return True
    return False


def _should_skip_leading_block(*, text: str, block_count: int, fallback_url: str) -> bool:
    if block_count > 0:
        return False

    hostname = urlsplit(fallback_url).netloc.lower()
    if hostname == "federalreserve.gov" or hostname.endswith(".federalreserve.gov"):
        return any(pattern.match(text) for pattern in _FED_LEADING_PREAMBLE_PATTERNS)
    return False


def _is_section_heading_block(element: Tag, *, text: str) -> bool:
    if element.name in {"h2", "h3", "h4"}:
        return True
    if element.name != "p":
        return False

    joined_classes = " ".join(element.get("class", [])).lower()
    if "has-heading-" in joined_classes:
        return True
    if "text-align-center" in joined_classes or "text-center" in joined_classes:
        return True
    if _EXHIBIT_HEADING_PATTERN.match(text):
        return True
    return text.lower() in {"executive summary", "summary", "key findings"}


def _extract_body_excerpt(soup: BeautifulSoup, *, fallback_url: str) -> tuple[str, str]:
    for selector in _matching_body_selectors(fallback_url):
        best_excerpt = ""
        best_block_count = 0

        for node in soup.select(selector):
            if not isinstance(node, Tag):
                continue
            excerpt, block_count = _extract_block_excerpt(node, fallback_url=fallback_url)
            if not excerpt:
                continue
            if len(excerpt) > len(best_excerpt):
                best_excerpt = excerpt
                best_block_count = block_count

        if best_excerpt and (len(best_excerpt) >= 40 or best_block_count >= 1):
            return best_excerpt, f"body_selector:{selector}"

    return "", ""


def _extract_meta_summary(soup: BeautifulSoup) -> str:
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ):
        meta_node = soup.find("meta", attrs=attrs)
        if meta_node and meta_node.get("content"):
            text = _normalize_block_text(str(meta_node["content"]))
            if text:
                return text
    return ""


def _extract_accessible_material_url(soup: BeautifulSoup, *, fallback_url: str) -> str:
    current_host = urlsplit(fallback_url).netloc.lower()
    current_canonical = canonicalize_url(fallback_url)

    for link in soup.find_all("a", href=True):
        text = _normalize_block_text(link.get_text(" ", strip=True))
        if not text or not any(pattern.search(text) for pattern in _ACCESSIBLE_LINK_TEXT_PATTERNS):
            continue

        resolved_url = canonicalize_url(urljoin(fallback_url, str(link["href"]).strip()))
        target_host = urlsplit(resolved_url).netloc.lower()
        if current_host and target_host and target_host != current_host:
            continue
        if resolved_url == current_canonical:
            continue
        return resolved_url

    return ""


def _normalize_json_ld_summary_value(value: object) -> str:
    if isinstance(value, str):
        return _truncate_excerpt(_normalize_summary_value(value))
    if isinstance(value, list):
        parts = [
            _normalize_summary_value(item)
            for item in value
            if isinstance(item, str) and _normalize_summary_value(item)
        ]
        if parts:
            return _truncate_excerpt(" ".join(parts))
    if isinstance(value, dict):
        for key in ("text", "@value", "value"):
            nested = value.get(key)
            if isinstance(nested, str):
                normalized = _normalize_summary_value(nested)
                if normalized:
                    return _truncate_excerpt(normalized)
    return ""


def _extract_json_ld_summary(soup: BeautifulSoup) -> tuple[str, str]:
    best_summary = ""
    best_source = ""
    best_score = -10_000

    for payload in _iter_json_ld_objects(soup):
        for field, source in _JSONLD_SUMMARY_FIELDS:
            summary = _normalize_json_ld_summary_value(payload.get(field))
            if not summary or _looks_like_boilerplate(summary):
                continue
            score = _summary_quality_score(summary)
            if score > best_score:
                best_summary = summary
                best_source = source
                best_score = score

    return best_summary, best_source


def _embedded_json_object_matches_article(payload: dict[str, object], *, fallback_url: str) -> bool:
    fallback_host, fallback_path = _normalize_url_match_parts(fallback_url, fallback_url=fallback_url)
    if not fallback_path:
        return False

    for raw_key, raw_value in payload.items():
        key = str(raw_key).strip().lower()
        if key not in _EMBEDDED_JSON_URL_KEYS or not isinstance(raw_value, str):
            continue
        candidate_host, candidate_path = _normalize_url_match_parts(raw_value, fallback_url=fallback_url)
        if candidate_path != fallback_path:
            continue
        if not candidate_host or not fallback_host or candidate_host == fallback_host:
            return True
    return False


def _extract_embedded_json_summary(soup: BeautifulSoup, *, fallback_url: str) -> tuple[str, str]:
    best_summary = ""
    best_source = ""
    best_score = -10_000

    for payload in _iter_embedded_json_objects(soup):
        if not _embedded_json_object_matches_article(payload, fallback_url=fallback_url):
            continue
        for field, source in _EMBEDDED_JSON_SUMMARY_FIELDS:
            summary = _normalize_json_ld_summary_value(payload.get(field))
            if not summary or _looks_like_boilerplate(summary):
                continue
            score = _summary_quality_score(summary)
            if field == "teaserSnippet":
                score += 20
            if score > best_score:
                best_summary = summary
                best_source = source
                best_score = score

    return best_summary, best_source


def _pick_more_detailed_excerpt(
    primary_summary: str,
    primary_source: str,
    alternate_summary: str,
    alternate_source: str,
) -> tuple[str, str]:
    normalized_primary = _normalize_summary_value(primary_summary)
    normalized_alternate = _normalize_summary_value(alternate_summary)

    if not normalized_primary:
        return normalized_alternate, alternate_source
    if not normalized_alternate:
        return normalized_primary, primary_source

    primary_score = _summary_quality_score(normalized_primary)
    alternate_score = _summary_quality_score(normalized_alternate)
    if alternate_score >= primary_score + 8:
        return normalized_alternate, alternate_source
    return normalized_primary, primary_source


def _extract_summary_from_content(soup: BeautifulSoup, *, fallback_url: str) -> tuple[str, str]:
    body_excerpt, body_source = _extract_body_excerpt(soup, fallback_url=fallback_url)
    embedded_excerpt, embedded_source = _extract_embedded_json_summary(soup, fallback_url=fallback_url)
    json_ld_excerpt, json_ld_source = _extract_json_ld_summary(soup)
    preferred_excerpt = body_excerpt
    preferred_source = body_source
    preferred_excerpt, preferred_source = _pick_more_detailed_excerpt(
        preferred_excerpt,
        preferred_source,
        embedded_excerpt,
        embedded_source,
    )
    preferred_excerpt, preferred_source = _pick_more_detailed_excerpt(
        preferred_excerpt,
        preferred_source,
        json_ld_excerpt,
        json_ld_source,
    )
    if preferred_excerpt:
        return preferred_excerpt, preferred_source

    headline = soup.find("h1")
    if headline is not None:
        paragraph = headline.find_next("p")
        if paragraph is not None:
            text = _normalize_block_text(paragraph.get_text(" ", strip=True))
            if text and not _looks_like_boilerplate(text):
                return text, "headline_paragraph"

    meta_summary = _extract_meta_summary(soup)
    if meta_summary:
        return meta_summary, "meta:description"

    body = soup.find("body")
    if body is None:
        return "", ""
    excerpt, _ = _extract_block_excerpt(body, fallback_url=fallback_url)
    if excerpt:
        return excerpt, "body_fallback"
    return "", ""


def _extract_body_title(soup: BeautifulSoup, *, fallback_url: str) -> str:
    for selector in _matching_body_selectors(fallback_url):
        for node in soup.select(selector):
            if not isinstance(node, Tag):
                continue
            headline = node.find("h1")
            if headline is None:
                continue
            title = _normalize_block_text(headline.get_text(" ", strip=True))
            if title and not _looks_like_boilerplate(title):
                return title
    return ""


def extract_article_shell(html: str, fallback_url: str) -> tuple[str, str, str, str]:
    soup = BeautifulSoup(html, "lxml")

    canonical_node = soup.find("link", rel="canonical", href=True)
    canonical_href = canonical_node["href"] if canonical_node else fallback_url
    canonical_url = canonicalize_url(urljoin(fallback_url, str(canonical_href).strip()))

    og_title = soup.find("meta", attrs={"property": "og:title"})
    body_title = _extract_body_title(soup, fallback_url=fallback_url)
    h1 = soup.find("h1")
    title_node = soup.find("title")
    title = ""
    if body_title:
        title = body_title
    elif og_title and og_title.get("content"):
        title = str(og_title["content"]).strip()
    elif h1:
        title = h1.get_text(" ", strip=True)
    elif title_node:
        title = title_node.get_text(" ", strip=True)

    summary, excerpt_source = _extract_summary_from_content(soup, fallback_url=fallback_url)

    return canonical_url, title, summary, excerpt_source


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


def _published_precision(value: str | None) -> int:
    candidate = str(value or "").strip()
    if not candidate:
        return 0
    if "T" in candidate or re.search(r"\b\d{2}:\d{2}", candidate):
        return 2
    return 1


def _published_source_rank(source: str) -> int:
    normalized = source.strip()
    if normalized.startswith("html:"):
        return 3
    if normalized.startswith("feed:"):
        return 2
    if normalized.startswith("section:"):
        return 1
    return 0


def _pick_better_published_at(
    existing_value: str | None,
    existing_source: str,
    extracted_value: str | None,
    extracted_source: str,
) -> tuple[str | None, str]:
    current_value = str(existing_value or "").strip() or None
    new_value = str(extracted_value or "").strip() or None
    current_source = existing_source.strip()
    new_source = extracted_source.strip()

    if current_value is None:
        return new_value, new_source
    if new_value is None:
        return current_value, current_source

    current_precision = _published_precision(current_value)
    new_precision = _published_precision(new_value)
    current_rank = _published_source_rank(current_source)
    new_rank = _published_source_rank(new_source)

    if new_precision > current_precision and new_rank >= current_rank:
        return new_value, new_source
    if new_rank > current_rank and new_precision == current_precision and new_value != current_value:
        return new_value, new_source
    return current_value, current_source


class ArticleCollector:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def _extract_linked_accessible_material_excerpt(
        self,
        *,
        soup: BeautifulSoup,
        article_url: str,
        current_summary: str,
    ) -> tuple[str, str]:
        normalized_summary = _normalize_summary_value(current_summary)
        if not normalized_summary or not _ATTACHED_MATERIAL_SUMMARY_PATTERN.search(normalized_summary):
            return "", ""

        accessible_url = _extract_accessible_material_url(soup, fallback_url=article_url)
        if not accessible_url:
            return "", ""

        linked_html = _fetch_payload(self._http_client, accessible_url)
        _, _, linked_summary, linked_source = extract_article_shell(linked_html, fallback_url=accessible_url)
        if not linked_summary:
            return "", ""
        return linked_summary, f"linked_page:accessible_materials->{linked_source or 'unknown'}"

    def expand(self, candidate: SourceCandidate) -> SourceCandidate:
        html = _fetch_payload(self._http_client, candidate.candidate_url)
        soup = BeautifulSoup(html, "lxml")
        canonical_url, canonical_title, canonical_summary, excerpt_source = extract_article_shell(
            html,
            fallback_url=candidate.candidate_url,
        )
        linked_summary, linked_excerpt_source = self._extract_linked_accessible_material_excerpt(
            soup=soup,
            article_url=candidate.candidate_url,
            current_summary=canonical_summary,
        )
        if linked_summary:
            canonical_summary = linked_summary
            excerpt_source = linked_excerpt_source or excerpt_source
        published_at, published_at_source = _extract_html_published_at(
            soup,
            article_url=candidate.candidate_url,
        )
        selected_published_at, selected_published_at_source = _pick_better_published_at(
            candidate.candidate_published_at,
            candidate.candidate_published_at_source,
            published_at,
            published_at_source,
        )
        selected_summary, selected_source = _pick_better_summary(candidate.candidate_summary, canonical_summary)
        selected_title = _pick_better_title(candidate.candidate_title, canonical_title)
        return replace(
            candidate,
            candidate_url=canonical_url,
            candidate_title=selected_title,
            candidate_summary=_strip_repeated_title_prefix(
                selected_summary or candidate.candidate_summary,
                selected_title,
            ),
            candidate_excerpt_source=selected_source or excerpt_source or candidate.candidate_excerpt_source,
            candidate_published_at=selected_published_at,
            candidate_published_at_source=selected_published_at_source,
            needs_article_fetch=False,
        )
