# -*- coding: utf-8 -*-
"""Env-backed live validation helpers for search discovery providers."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterator, Sequence
from urllib.parse import urlsplit

from app.collectors.article import ArticleCollector
from app.collectors.readhub import ReadhubDailyCollector
from app.collectors.section import SectionCollector
from app.db import Database
from app.repository import OvernightRepository
from app.runtime_config import (
    DEFAULT_ENV_FILE_PATHS,
    MARKET_PROVIDER_ENV_NAMES,
    SEARCH_PROVIDER_ENV_NAMES,
    load_env_values_from_files,
)
from app.services.market_snapshot import UsMarketSnapshotService
from app.services.search_discovery import SearchDiscoveryService
from app.services.source_excerpt import RequestsHttpClient
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate, SourceDefinition


DEFAULT_SOURCE_IDS: tuple[str, ...] = (
    "whitehouse_news",
    "ustr_press_releases",
    "treasury_press_releases",
    "ofac_recent_actions",
    "bis_news_updates",
    "doe_articles",
)
READHUB_SOURCE_ID = "readhub_daily_digest"


def summarize_search_candidates(
    *,
    source: SourceDefinition,
    candidates: Sequence[SourceCandidate],
) -> dict[str, object]:
    provider_counts = Counter(
        (candidate.capture_provider or "unknown").strip().lower() or "unknown"
        for candidate in candidates
    )
    sample_urls = [candidate.candidate_url for candidate in candidates[:5] if candidate.candidate_url]
    same_domain_candidates = sum(
        1
        for candidate in candidates
        if _url_matches_allowed_domains(candidate.candidate_url, source.allowed_domains)
    )
    return {
        "source_id": source.source_id,
        "display_name": source.display_name,
        "allowed_domains": list(source.allowed_domains),
        "search_discovery_enabled": bool(source.search_discovery_enabled),
        "query_count": len([query for query in source.search_queries if query.strip()]),
        "total_candidates": len(candidates),
        "same_domain_candidates": same_domain_candidates,
        "provider_counts": dict(provider_counts),
        "sample_urls": sample_urls,
    }


def collect_search_validation_report(
    *,
    service: SearchDiscoveryService | object,
    sources: Sequence[SourceDefinition],
    max_results: int = 4,
    days: int = 7,
) -> dict[str, object]:
    provider_names = [
        str(getattr(provider, "name", "")).strip()
        for provider in getattr(service, "providers", ())
        if str(getattr(provider, "name", "")).strip()
    ]
    report_sources: list[dict[str, object]] = []

    for source in sources:
        if not source.search_discovery_enabled:
            report_sources.append(
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "allowed_domains": list(source.allowed_domains),
                    "search_discovery_enabled": False,
                    "query_count": len([query for query in source.search_queries if query.strip()]),
                    "status": "disabled",
                    "total_candidates": 0,
                    "same_domain_candidates": 0,
                    "provider_counts": {},
                    "sample_urls": [],
                }
            )
            continue
        if not provider_names:
            report_sources.append(
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "allowed_domains": list(source.allowed_domains),
                    "search_discovery_enabled": True,
                    "query_count": len([query for query in source.search_queries if query.strip()]),
                    "status": "unconfigured",
                    "error": "No search discovery providers configured",
                    "total_candidates": 0,
                    "same_domain_candidates": 0,
                    "provider_counts": {},
                    "sample_urls": [],
                }
            )
            continue
        try:
            candidates = service.discover(source=source, max_results=max_results, days=days)
            summary = summarize_search_candidates(source=source, candidates=candidates)
            summary["status"] = "ok"
        except Exception as exc:
            summary = {
                "source_id": source.source_id,
                "display_name": source.display_name,
                "allowed_domains": list(source.allowed_domains),
                "search_discovery_enabled": bool(source.search_discovery_enabled),
                "query_count": len([query for query in source.search_queries if query.strip()]),
                "status": "error",
                "error": str(exc),
                "total_candidates": 0,
                "same_domain_candidates": 0,
                "provider_counts": {},
                "sample_urls": [],
            }
        report_sources.append(summary)

    return {
        "provider_names": provider_names,
        "source_ids": [source.source_id for source in sources],
        "sources": report_sources,
    }


def collect_section_capture_validation_report(
    *,
    collector: SectionCollector | object,
    article_collector: ArticleCollector | object | None,
    sources: Sequence[SourceDefinition],
    article_sample_limit: int = 1,
) -> dict[str, object]:
    report_sources: list[dict[str, object]] = []

    for source in sources:
        if source.entry_type != "section_page":
            report_sources.append(
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "entry_type": source.entry_type,
                    "entry_urls": list(source.entry_urls),
                    "status": "skipped",
                    "total_candidates": 0,
                    "sample_urls": [],
                    "article_samples": [],
                }
            )
            continue

        try:
            candidates = collector.collect(source)
        except Exception as exc:
            report_sources.append(
                {
                    "source_id": source.source_id,
                    "display_name": source.display_name,
                    "entry_type": source.entry_type,
                    "entry_urls": list(source.entry_urls),
                    "status": "error",
                    "error": str(exc),
                    "total_candidates": 0,
                    "sample_urls": [],
                    "article_samples": [],
                }
            )
            continue

        article_samples: list[dict[str, object]] = []
        if article_collector is not None:
            for candidate in candidates[: max(0, article_sample_limit)]:
                try:
                    expanded = article_collector.expand(candidate)
                    article_samples.append(
                        {
                            "url": expanded.candidate_url,
                            "title": expanded.candidate_title,
                            "published_at": expanded.candidate_published_at,
                            "summary": (expanded.candidate_summary or "")[:240],
                            "excerpt_source": expanded.candidate_excerpt_source,
                        }
                    )
                except Exception as exc:
                    article_samples.append(
                        {
                            "url": candidate.candidate_url,
                            "title": candidate.candidate_title,
                            "error": str(exc),
                        }
                    )

        report_sources.append(
            {
                "source_id": source.source_id,
                "display_name": source.display_name,
                "entry_type": source.entry_type,
                "entry_urls": list(source.entry_urls),
                "status": "ok",
                "total_candidates": len(candidates),
                "sample_urls": [candidate.candidate_url for candidate in candidates[:5] if candidate.candidate_url],
                "article_samples": article_samples,
            }
        )

    return {
        "source_ids": [source.source_id for source in sources],
        "sources": report_sources,
    }


def collect_readhub_capture_validation_report(
    *,
    collector: ReadhubDailyCollector | object,
    source: SourceDefinition,
) -> dict[str, object]:
    try:
        candidates = collector.collect(source)
    except Exception as exc:
        return {
            "source_id": source.source_id,
            "display_name": source.display_name,
            "status": "error",
            "error": str(exc),
            "daily_issue_date": "",
            "daily_item_count": 0,
            "sample_topic_urls": [],
            "enrichment_populated_count": 0,
            "enrichment_visibility": {
                "tag_count": 0,
                "tracking_count": 0,
                "similar_event_count": 0,
                "news_link_count": 0,
            },
            "legacy_alias_probe_errors": [],
        }

    issue_dates = []
    enrichment_populated_count = 0
    tag_count = 0
    tracking_count = 0
    similar_event_count = 0
    news_link_count = 0
    for candidate in candidates:
        source_context = dict(candidate.source_context or {})
        daily_context = dict(source_context.get("daily", {}) or {})
        issue_date = str(daily_context.get("issue_date", "")).strip()
        if issue_date and issue_date not in issue_dates:
            issue_dates.append(issue_date)
        topic_context = dict(source_context.get("topic", {}) or {})
        tags = list(topic_context.get("tags", []) or [])
        tracking = list(topic_context.get("tracking", []) or [])
        similar_events = list(topic_context.get("similar_events", []) or [])
        news_links = list(topic_context.get("news_links", []) or [])
        if tags or tracking or similar_events or news_links:
            enrichment_populated_count += 1
        tag_count += len(tags)
        tracking_count += len(tracking)
        similar_event_count += len(similar_events)
        news_link_count += len(news_links)

    return {
        "source_id": source.source_id,
        "display_name": source.display_name,
        "status": "ok",
        "daily_issue_date": issue_dates[0] if issue_dates else "",
        "daily_item_count": len(candidates),
        "sample_topic_urls": [
            candidate.candidate_url
            for candidate in candidates[:5]
            if candidate.candidate_url
        ],
        "enrichment_populated_count": enrichment_populated_count,
        "enrichment_visibility": {
            "tag_count": tag_count,
            "tracking_count": tracking_count,
            "similar_event_count": similar_event_count,
            "news_link_count": news_link_count,
        },
        "legacy_alias_probe_errors": list(getattr(collector, "last_errors", []) or []),
    }


def build_env_backed_search_validation_report(
    *,
    env_file_paths: Sequence[Path | str] = DEFAULT_ENV_FILE_PATHS,
    source_ids: Sequence[str] = DEFAULT_SOURCE_IDS,
    max_results: int = 4,
    days: int = 7,
) -> dict[str, object]:
    loaded_env = load_env_values_from_files(
        env_file_paths=env_file_paths,
        env_names=SEARCH_PROVIDER_ENV_NAMES,
    )
    sources = _resolve_sources(source_ids)
    with _temporary_environ(loaded_env):
        service = SearchDiscoveryService.from_environment()
        report = collect_search_validation_report(
            service=service,
            sources=sources,
            max_results=max_results,
            days=days,
        )
    report["env_files"] = [
        str(Path(candidate_path).expanduser())
        for candidate_path in env_file_paths
        if Path(candidate_path).expanduser().is_file()
    ]
    report["loaded_env_names"] = sorted(loaded_env)
    report["loaded_key_counts"] = {
        env_name: _count_env_keys(value)
        for env_name, value in loaded_env.items()
    }
    return report


def collect_market_snapshot_validation_report(
    *,
    service: UsMarketSnapshotService | object,
) -> dict[str, object]:
    try:
        snapshot = service.refresh_us_close_snapshot()
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "bucket_counts": {},
            "missing_symbols": [],
            "failed_instruments": [],
        }

    capture_summary = dict(snapshot.get("capture_summary", {}) or {})
    return {
        "status": "ok",
        "analysis_date": snapshot.get("analysis_date"),
        "market_date": snapshot.get("market_date"),
        "source_name": snapshot.get("source_name"),
        "headline": snapshot.get("headline"),
        "capture_status": capture_summary.get("capture_status"),
        "captured_instrument_count": capture_summary.get("captured_instrument_count"),
        "missing_symbols": list(capture_summary.get("missing_symbols", []) or []),
        "core_missing_symbols": list(capture_summary.get("core_missing_symbols", []) or []),
        "supporting_missing_symbols": list(capture_summary.get("supporting_missing_symbols", []) or []),
        "optional_missing_symbols": list(capture_summary.get("optional_missing_symbols", []) or []),
        "provider_hits": dict(capture_summary.get("provider_hits", {}) or {}),
        "freshness_status_counts": dict(capture_summary.get("freshness_status_counts", {}) or {}),
        "failed_instruments": list(capture_summary.get("failed_instruments", []) or []),
        "bucket_counts": {
            "indexes": len(list(snapshot.get("indexes", []) or [])),
            "sectors": len(list(snapshot.get("sectors", []) or [])),
            "sentiment": len(list(snapshot.get("sentiment", []) or [])),
            "rates_fx": len(list(snapshot.get("rates_fx", []) or [])),
            "precious_metals": len(list(snapshot.get("precious_metals", []) or [])),
            "energy": len(list(snapshot.get("energy", []) or [])),
            "industrial_metals": len(list(snapshot.get("industrial_metals", []) or [])),
        },
    }


def build_market_snapshot_validation_report(
    *,
    env_file_paths: Sequence[Path | str] = DEFAULT_ENV_FILE_PATHS,
    service_factory: Callable[[OvernightRepository], object] | None = None,
) -> dict[str, object]:
    loaded_env = load_env_values_from_files(
        env_file_paths=env_file_paths,
        env_names=MARKET_PROVIDER_ENV_NAMES,
    )
    with tempfile.TemporaryDirectory(prefix="overnight-live-validation-") as temp_dir:
        db_path = Path(temp_dir) / "validation.db"
        repo = OvernightRepository(Database(path=db_path))
        factory = service_factory or (lambda current_repo: UsMarketSnapshotService(repo=current_repo))
        with _temporary_environ(loaded_env):
            service = factory(repo)
            report = collect_market_snapshot_validation_report(service=service)
    report["env_files"] = [
        str(Path(candidate_path).expanduser())
        for candidate_path in env_file_paths
        if Path(candidate_path).expanduser().is_file()
    ]
    report["loaded_env_names"] = sorted(loaded_env)
    return report


def build_section_capture_validation_report(
    *,
    source_ids: Sequence[str] = DEFAULT_SOURCE_IDS,
    article_sample_limit: int = 1,
    http_client: object | None = None,
) -> dict[str, object]:
    sources = _resolve_sources(source_ids)
    client = http_client or RequestsHttpClient()
    collector = SectionCollector(client)
    article_collector = ArticleCollector(client)
    return collect_section_capture_validation_report(
        collector=collector,
        article_collector=article_collector,
        sources=sources,
        article_sample_limit=article_sample_limit,
    )


def build_readhub_capture_validation_report(*, http_client: object | None = None) -> dict[str, object]:
    source = _resolve_sources((READHUB_SOURCE_ID,))
    if not source:
        return {
            "source_id": READHUB_SOURCE_ID,
            "status": "error",
            "error": "Readhub source is not registered",
        }
    collector = ReadhubDailyCollector(http_client=http_client or RequestsHttpClient())
    return collect_readhub_capture_validation_report(
        collector=collector,
        source=source[0],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.live_validation")
    parser.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Optional dotenv file path. Repeat to pass multiple files.",
    )
    parser.add_argument(
        "--source-id",
        action="append",
        default=[],
        help="Optional source_id to probe. Repeat to pass multiple sources.",
    )
    parser.add_argument("--max-results", type=int, default=4)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--include-section-capture",
        action="store_true",
        help="Also validate primary section-page capture and one article expansion sample per source.",
    )
    parser.add_argument(
        "--include-market-snapshot",
        action="store_true",
        help="Also run the live U.S. market snapshot validation.",
    )
    parser.add_argument(
        "--include-readhub-capture",
        action="store_true",
        help="Also validate the dedicated Readhub daily/topic capture path.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    env_file_paths = tuple(args.env_file) or DEFAULT_ENV_FILE_PATHS
    source_ids = tuple(args.source_id) or DEFAULT_SOURCE_IDS
    report = {
        "search_discovery": build_env_backed_search_validation_report(
            env_file_paths=env_file_paths,
            source_ids=source_ids,
            max_results=args.max_results,
            days=args.days,
        )
    }
    if args.include_section_capture:
        report["section_capture"] = build_section_capture_validation_report(
            source_ids=source_ids,
            article_sample_limit=1,
        )
    if args.include_market_snapshot:
        report["market_snapshot"] = build_market_snapshot_validation_report(env_file_paths=env_file_paths)
    if args.include_readhub_capture:
        report["readhub_capture"] = build_readhub_capture_validation_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _resolve_sources(source_ids: Sequence[str]) -> tuple[SourceDefinition, ...]:
    registry = {source.source_id: source for source in build_default_source_registry()}
    resolved: list[SourceDefinition] = []
    for source_id in source_ids:
        source = registry.get(str(source_id).strip())
        if source is None:
            continue
        resolved.append(source)
    return tuple(resolved)

def _url_matches_allowed_domains(url: str, allowed_domains: Sequence[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    for domain in allowed_domains:
        candidate = str(domain).strip().lower()
        if not candidate:
            continue
        if host == candidate or host.endswith(f".{candidate}"):
            return True
    return False


def _count_env_keys(raw_value: str) -> int:
    return len(
        [
            item
            for item in str(raw_value).replace("\n", ",").replace(";", ",").split(",")
            if item.strip()
        ]
    )


@contextmanager
def _temporary_environ(overrides: dict[str, str]) -> Iterator[None]:
    original: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, previous_value in original.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value


if __name__ == "__main__":
    raise SystemExit(main())
