# -*- coding: utf-8 -*-
"""Env-backed search discovery supplements for low-yield official sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlsplit, urlunsplit
import logging
import os

import requests

from app.sources.types import SourceCandidate, SourceDefinition
from app.sources.validation import is_source_url_allowed


logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 12
_SKIPPED_FILE_EXTENSIONS = (".pdf", ".csv", ".xls", ".xlsx", ".zip", ".doc", ".docx", ".ppt", ".pptx")
_SKIPPED_PATH_PATTERNS = (
    re.compile(r"\.t\d+\.htm$", re.IGNORECASE),
    re.compile(r"\.toc\.htm$", re.IGNORECASE),
)
_SOURCE_LOW_VALUE_PATH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "whitehouse_news": (
        re.compile(r"^/gallery(?:/|$)", re.IGNORECASE),
        re.compile(r"^/live(?:/|$)", re.IGNORECASE),
        re.compile(r"^/(?:news|releases|briefings-statements|fact-sheets|presidential-actions)/?$", re.IGNORECASE),
        re.compile(r"^/(?:news|releases|briefings-statements|fact-sheets|presidential-actions)/page/\d+/?$", re.IGNORECASE),
        re.compile(r"^/briefing-room/(?:statements-releases|speeches-remarks|press-briefings)/?$", re.IGNORECASE),
        re.compile(r"^/presidential-actions/?$", re.IGNORECASE),
    ),
    "ustr_press_releases": (
        re.compile(r"^/node(?:/\d+)?/?$", re.IGNORECASE),
    ),
    "ofac_recent_actions": (
        re.compile(
            r"^/recent-actions/(?:general-licenses|faqs?|guidance-on-compliance|advisories|settlements-information)/?$",
            re.IGNORECASE,
        ),
    ),
}
_SOURCE_REQUIRED_PATH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "whitehouse_news": (
        re.compile(r"^/(?:fact-sheets|briefings-statements|releases|presidential-actions)/.+", re.IGNORECASE),
        re.compile(r"^/briefing-room/(?:statements-releases|speeches-remarks|press-briefings)/.+", re.IGNORECASE),
    ),
    "ustr_press_releases": (
        re.compile(
            r"^/(?:about|about-us)/policy-offices/press-office/(?:press-releases|speeches-and-remarks)/.+",
            re.IGNORECASE,
        ),
    ),
    "ofac_recent_actions": (
        re.compile(r"^/recent-actions/.+", re.IGNORECASE),
    ),
}
_SEARCH_NOISE_PATTERNS = (
    re.compile(r"^#+\s*"),
    re.compile(r"^cookie settings$", re.IGNORECASE),
    re.compile(r"^skip to main content", re.IGNORECASE),
    re.compile(r"^an official website of the united states government$", re.IGNORECASE),
    re.compile(r"^we use cookies\b", re.IGNORECASE),
    re.compile(r"^functional-?", re.IGNORECASE),
    re.compile(r"^the technical storage or access\b", re.IGNORECASE),
    re.compile(r"^here'?s how you know\b", re.IGNORECASE),
    re.compile(r"official websites use \.gov", re.IGNORECASE),
    re.compile(r"secure \.gov websites use https", re.IGNORECASE),
    re.compile(r"share sensitive information only on official", re.IGNORECASE),
    re.compile(r"privacy policy", re.IGNORECASE),
    re.compile(r"^menu$", re.IGNORECASE),
    re.compile(r"^search:?$", re.IGNORECASE),
    re.compile(r"^contact us telephone", re.IGNORECASE),
    re.compile(r"^country offices", re.IGNORECASE),
    re.compile(r"^u\.s\. ambassadors", re.IGNORECASE),
    re.compile(r"^homeoffice of the spokesperson", re.IGNORECASE),
    re.compile(r"^help us improve", re.IGNORECASE),
    re.compile(r"^close$", re.IGNORECASE),
    re.compile(r"^image \d", re.IGNORECASE),
)
_EMBEDDED_NOISE_PATTERNS = (
    re.compile(r"skip to content", re.IGNORECASE),
    re.compile(r"an official website of the united states government", re.IGNORECASE),
    re.compile(r"here'?s how you know", re.IGNORECASE),
    re.compile(r"a\s*\.gov\s*website belongs to an official government organization in the united states\.?", re.IGNORECASE),
    re.compile(r"americans in the middle east: for consular information or assistance,[^.]+\.", re.IGNORECASE),
)
_NAVIGATION_MARKERS = (
    "facebookxinstagramyoutube",
    "countries & areas",
    "govdelivery",
    "press products",
    "today in dow",
    "feature stories",
    "state department home",
    "u.s. department of war",
)


@dataclass(frozen=True)
class SearchDiscoveryResult:
    title: str
    snippet: str
    url: str
    published_at: str | None = None


class SearchDiscoveryProvider:
    """Small HTTP-backed search provider with multi-key fallback."""

    name = "provider"
    env_names: tuple[str, ...] = ()

    def __init__(self, *, api_keys: tuple[str, ...]) -> None:
        self._api_keys = tuple(key for key in api_keys if key)
        self._next_index = 0

    @property
    def is_available(self) -> bool:
        return bool(self._api_keys)

    def search(self, *, query: str, max_results: int, days: int = 7) -> list[SearchDiscoveryResult]:
        if not self.is_available:
            return []

        for _ in range(len(self._api_keys)):
            api_key = self._next_key()
            if not api_key:
                return []
            try:
                return self._search_once(query=query, api_key=api_key, max_results=max_results, days=days)
            except requests.RequestException as exc:
                logger.warning(
                    "Search discovery provider %s failed for query '%s': %s",
                    self.name,
                    query,
                    _safe_request_error(exc),
                )
            except Exception as exc:
                logger.warning(
                    "Search discovery provider %s failed for query '%s': %s",
                    self.name,
                    query,
                    exc.__class__.__name__,
                )
        return []

    def _next_key(self) -> str | None:
        if not self._api_keys:
            return None
        key = self._api_keys[self._next_index % len(self._api_keys)]
        self._next_index = (self._next_index + 1) % len(self._api_keys)
        return key

    def _search_once(self, *, query: str, api_key: str, max_results: int, days: int) -> list[SearchDiscoveryResult]:
        raise NotImplementedError


class BochaSearchProvider(SearchDiscoveryProvider):
    name = "Bocha"
    env_names = ("BOCHA_API_KEYS", "BOCHA_API_KEY")
    _endpoint = "https://api.bocha.cn/v1/web-search"

    def _search_once(self, *, query: str, api_key: str, max_results: int, days: int) -> list[SearchDiscoveryResult]:
        freshness = "oneWeek"
        if days <= 1:
            freshness = "oneDay"
        elif days > 30:
            freshness = "oneYear"
        elif days > 7:
            freshness = "oneMonth"

        response = requests.post(
            self._endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "freshness": freshness,
                "summary": True,
                "count": min(max_results, 10),
            },
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data", {}).get("webPages", {}).get("value", [])
        return [
            SearchDiscoveryResult(
                title=str(item.get("name", "")).strip(),
                snippet=str(item.get("summary") or item.get("snippet") or "").strip(),
                url=str(item.get("url", "")).strip(),
                published_at=str(item.get("datePublished", "")).strip() or None,
            )
            for item in items[:max_results]
            if str(item.get("url", "")).strip()
        ]


class TavilySearchProvider(SearchDiscoveryProvider):
    name = "Tavily"
    env_names = ("TAVILY_API_KEYS", "TAVILY_API_KEY")
    _endpoint = "https://api.tavily.com/search"

    def _search_once(self, *, query: str, api_key: str, max_results: int, days: int) -> list[SearchDiscoveryResult]:
        response = requests.post(
            self._endpoint,
            json={
                "api_key": api_key,
                "query": query,
                "topic": "news",
                "search_depth": "advanced",
                "max_results": min(max_results, 10),
                "include_answer": False,
                "include_raw_content": True,
                "days": max(1, days),
            },
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            SearchDiscoveryResult(
                title=str(item.get("title", "")).strip(),
                snippet=_select_tavily_snippet(item),
                url=str(item.get("url", "")).strip(),
                published_at=str(item.get("published_date", "")).strip() or None,
            )
            for item in payload.get("results", [])[:max_results]
            if str(item.get("url", "")).strip()
        ]


class SerpAPISearchProvider(SearchDiscoveryProvider):
    name = "SerpAPI"
    env_names = ("SERPAPI_API_KEYS", "SERPAPI_API_KEY")
    _endpoint = "https://serpapi.com/search.json"

    def _search_once(self, *, query: str, api_key: str, max_results: int, days: int) -> list[SearchDiscoveryResult]:
        tbs = "qdr:w"
        if days <= 1:
            tbs = "qdr:d"
        elif days > 30:
            tbs = "qdr:y"
        elif days > 7:
            tbs = "qdr:m"

        response = requests.get(
            self._endpoint,
            params={
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "google_domain": "google.com",
                "hl": "en",
                "gl": "us",
                "tbs": tbs,
                "num": min(max_results, 10),
            },
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            SearchDiscoveryResult(
                title=str(item.get("title", "")).strip(),
                snippet=str(item.get("snippet", "")).strip(),
                url=str(item.get("link", "")).strip(),
                published_at=str(item.get("date", "")).strip() or None,
            )
            for item in payload.get("organic_results", [])[:max_results]
            if str(item.get("link", "")).strip()
        ]


class BraveSearchProvider(SearchDiscoveryProvider):
    name = "Brave"
    env_names = ("BRAVE_API_KEYS", "BRAVE_API_KEY")
    _endpoint = "https://api.search.brave.com/res/v1/web/search"

    def _search_once(self, *, query: str, api_key: str, max_results: int, days: int) -> list[SearchDiscoveryResult]:
        freshness = "pw"
        if days <= 1:
            freshness = "pd"
        elif days > 30:
            freshness = "py"
        elif days > 7:
            freshness = "pm"

        response = requests.get(
            self._endpoint,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": min(max_results, 10),
                "freshness": freshness,
                "search_lang": "en",
                "country": "US",
                "safesearch": "off",
            },
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("web", {}).get("results", [])
        return [
            SearchDiscoveryResult(
                title=str(item.get("title", "")).strip(),
                snippet=str(item.get("description", "")).strip(),
                url=str(item.get("url", "")).strip(),
                published_at=str(item.get("page_age") or item.get("age") or "").strip() or None,
            )
            for item in items[:max_results]
            if str(item.get("url", "")).strip()
        ]


class SearchDiscoveryService:
    """Normalize search-provider results into source candidates."""

    def __init__(self, *, providers: tuple[object, ...] = ()) -> None:
        self.providers = tuple(providers)

    @classmethod
    def from_environment(cls) -> "SearchDiscoveryService":
        providers: list[SearchDiscoveryProvider] = []
        for provider_type in (
            SerpAPISearchProvider,
            BochaSearchProvider,
            TavilySearchProvider,
            BraveSearchProvider,
        ):
            api_keys = _parse_env_keys(provider_type.env_names)
            if api_keys:
                providers.append(provider_type(api_keys=api_keys))
        return cls(providers=tuple(providers))

    def discover(
        self,
        *,
        source: SourceDefinition,
        max_results: int = 5,
        days: int = 7,
    ) -> list[SourceCandidate]:
        if not source.search_discovery_enabled or not self.providers:
            return []

        queries = _effective_queries(source)
        discovered: list[SourceCandidate] = []
        seen_urls: set[str] = set()

        for query in queries:
            if len(discovered) >= max_results:
                break
            for provider in self.providers:
                if not getattr(provider, "is_available", True):
                    continue
                try:
                    provider_results = provider.search(query=query, max_results=max_results, days=days)
                except Exception as exc:
                    logger.warning(
                        "Search discovery provider %s errored for source %s: %s",
                        getattr(provider, "name", "provider"),
                        source.source_id,
                        exc,
                    )
                    continue
                ranked_results = sorted(
                    provider_results,
                    key=lambda item: (
                        1 if str(item.published_at or "").strip() else 0,
                        _snippet_quality_score(item.snippet),
                        len(str(item.title or "").strip()),
                    ),
                    reverse=True,
                )
                for item in ranked_results:
                    candidate = self._to_candidate(source=source, provider=provider, result=item, days=days)
                    if candidate is None:
                        continue
                    normalized_url = _canonical_url_key(candidate.candidate_url)
                    if normalized_url in seen_urls:
                        continue
                    seen_urls.add(normalized_url)
                    discovered.append(candidate)
                    if len(discovered) >= max_results:
                        break
                if len(discovered) >= max_results:
                    break
        return discovered

    def _to_candidate(
        self,
        *,
        source: SourceDefinition,
        provider: object,
        result: SearchDiscoveryResult,
        days: int,
    ) -> SourceCandidate | None:
        url = str(result.url).strip()
        if (
            not url
            or _is_binary_asset_url(url)
            or _is_non_article_path(url)
            or _is_low_value_source_path(url, source)
            or not _matches_source_path_policy(url, source)
            or _matches_entry_url(url, source)
            or _is_stale_search_result(result.published_at, days=days)
            or not is_source_url_allowed(url, source)
        ):
            return None

        provider_name = str(getattr(provider, "name", "provider")).strip().lower() or "provider"
        published_at = str(result.published_at or "").strip() or None
        return SourceCandidate(
            candidate_type="search_result",
            candidate_url=url,
            candidate_title=str(result.title).strip() or url,
            candidate_summary=_clean_search_snippet(result.snippet),
            candidate_excerpt_source=f"search:{provider_name}",
            candidate_published_at=published_at,
            candidate_published_at_source="search:published" if published_at else "",
            candidate_section="search_discovery",
            needs_article_fetch=True,
            capture_path="search_discovery",
            capture_provider=provider_name,
        )


def _parse_env_keys(env_names: tuple[str, ...]) -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()
    for env_name in env_names:
        raw_value = os.environ.get(env_name, "")
        if not raw_value.strip():
            continue
        for part in raw_value.replace("\n", ",").replace(";", ",").split(","):
            candidate = part.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            keys.append(candidate)
    return tuple(keys)


def _effective_queries(source: SourceDefinition) -> tuple[str, ...]:
    configured_queries = tuple(query.strip() for query in source.search_queries if query.strip())
    if configured_queries:
        return configured_queries

    allowed_domains = tuple(domain.strip() for domain in source.allowed_domains if domain.strip())
    if allowed_domains:
        return tuple(f"site:{domain} {source.display_name}" for domain in allowed_domains)
    return (source.display_name,)


def _canonical_url_key(url: str) -> str:
    parts = urlsplit(str(url).strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _is_binary_asset_url(url: str) -> bool:
    lowered = _canonical_url_key(url).lower()
    return lowered.endswith(_SKIPPED_FILE_EXTENSIONS)


def _matches_entry_url(url: str, source: SourceDefinition) -> bool:
    candidate_key = _entry_url_key(url)
    return any(candidate_key == _entry_url_key(entry_url) for entry_url in source.entry_urls)


def _is_non_article_path(url: str) -> bool:
    path = urlsplit(str(url).strip()).path or ""
    return any(pattern.search(path) for pattern in _SKIPPED_PATH_PATTERNS)


def _is_low_value_source_path(url: str, source: SourceDefinition) -> bool:
    patterns = _SOURCE_LOW_VALUE_PATH_PATTERNS.get(source.source_id, ())
    if not patterns:
        return False
    path = urlsplit(str(url).strip()).path or ""
    return any(pattern.search(path) for pattern in patterns)


def _matches_source_path_policy(url: str, source: SourceDefinition) -> bool:
    patterns = _SOURCE_REQUIRED_PATH_PATTERNS.get(source.source_id, ())
    if not patterns:
        return True
    path = urlsplit(str(url).strip()).path or ""
    return any(pattern.search(path) for pattern in patterns)


def _is_stale_search_result(published_at: str | None, *, days: int) -> bool:
    parsed = _parse_published_at(published_at)
    if parsed is None:
        return False
    age_days = (datetime.now(timezone.utc) - parsed).days
    return age_days > max(21, days + 7)


def _parse_published_at(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = parsedate_to_datetime(raw)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    for pattern in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _safe_request_error(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return f"http_{status_code}"
    return exc.__class__.__name__


def _select_tavily_snippet(item: dict[str, object]) -> str:
    content = str(item.get("content") or "").strip()
    raw_content = str(item.get("raw_content") or "").strip()
    candidates = [content, raw_content]
    scored = sorted(
        ((_snippet_quality_score(candidate), candidate) for candidate in candidates if candidate),
        key=lambda entry: entry[0],
        reverse=True,
    )
    return scored[0][1][:2400] if scored else ""


def _snippet_quality_score(value: str) -> int:
    cleaned = _clean_search_snippet(value)
    if not cleaned:
        return 0

    lowered = cleaned.lower()
    score = min(len(cleaned), 900)
    positive_markers = (
        "washington",
        "statement",
        "announced",
        "release",
        "sanctions",
        "deployment",
        "forces",
        "tariff",
        "trade",
        "treasury",
        "state department",
    )
    negative_markers = (
        "cookie",
        "preferences",
        "vendor_count",
        "official websites use .gov",
        "share sensitive information only",
        "contact us telephone",
    )
    score += sum(40 for marker in positive_markers if marker in lowered)
    score -= sum(120 for marker in negative_markers if marker in lowered)
    return score


def _clean_search_snippet(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", raw)
    normalized = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", normalized)
    normalized = normalized.replace("**", " ")

    lines: list[str] = []
    for chunk in normalized.splitlines():
        candidate = chunk.strip()
        candidate = re.sub(r"\s+", " ", candidate)
        if not candidate:
            continue
        lowered = candidate.lower()
        if candidate.count("*") >= 3 or any(marker in lowered for marker in _NAVIGATION_MARKERS):
            continue
        if any(pattern.search(candidate) for pattern in _SEARCH_NOISE_PATTERNS):
            continue
        if candidate.startswith("#"):
            candidate = candidate.lstrip("#").strip()
            if not candidate:
                continue
        lines.append(candidate)

    if not lines:
        return ""

    cleaned = " ".join(lines)
    for pattern in _EMBEDDED_NOISE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    lowered = cleaned.lower()
    if cleaned.count("*") >= 3 and any(marker in lowered for marker in _NAVIGATION_MARKERS):
        return ""
    if "vendor_count" in lowered or lowered.startswith("preferences-"):
        return ""
    return cleaned[:1200]


def _entry_url_key(url: str) -> str:
    parts = urlsplit(str(url).strip())
    path = (parts.path.rstrip("/") or "/").lower()
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
