# -*- coding: utf-8 -*-
"""Tests for overnight source capture and recent-item listing."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import requests

from app.db import Database
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.services.source_capture import OvernightSourceCaptureService
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceCandidate, SourceDefinition


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "overnight"


class RoutingFixtureClient:
    def __init__(self, routes: dict[str, Path]):
        self.routes = routes
        self.fetches: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetches.append(url)
        for fragment, fixture_path in self.routes.items():
            if fragment in url:
                return fixture_path.read_text(encoding="utf-8")
        raise AssertionError(f"No fixture mapped for url: {url}")


class FailingHttpClient:
    def __init__(self, *, status_code: int = 403, message: str = "Forbidden") -> None:
        self.status_code = status_code
        self.message = message
        self.fetches: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetches.append(url)
        response = requests.Response()
        response.status_code = self.status_code
        response.url = url
        raise requests.HTTPError(
            f"{self.status_code} Client Error: {self.message} for url: {url}",
            response=response,
        )


def test_persisted_source_item_keeps_published_time_and_entities() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_overnight_source_items.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://example.com/releases/tariff-update?utm_source=test",
                candidate_title="White House says 25% tariff on steel imports remains in place",
                candidate_summary="Federal Reserve and USTR officials cited the 25% tariff on steel imports in a policy update.",
                candidate_published_at="2026-04-07T01:30:00+00:00",
                candidate_excerpt_source="body_selector:article",
            )
        )

        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="whitehouse_news",
                    fetch_mode="source_capture_refresh",
                    payload_hash="tariff-update",
                ),
            )
        )

        assert stored.published_at == "2026-04-07T01:30:00+00:00"
        assert stored.excerpt_source == "body_selector:article"
        assert [entity.name for entity in stored.entities] == ["USTR", "Federal Reserve", "White House"]
        assert stored.numeric_facts[0].metric == "tariff_rate"
        assert stored.numeric_facts[0].value == 25.0
        assert stored.numeric_facts[0].subject == "steel"


def test_source_capture_service_formats_time_and_content_quality_fields() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_formatting.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://example.com/releases/tariff-update",
                candidate_title="White House says 25% tariff on steel imports remains in place",
                candidate_summary=(
                    "Federal Reserve and USTR officials cited the 25% tariff on steel imports in a policy update. "
                    "The White House said implementation remains in place while agencies monitor supply chains."
                ),
                candidate_published_at="2026-04-07T01:30:00+00:00",
                candidate_published_at_source="html:meta_article_published_time",
                candidate_excerpt_source="body_selector:article",
            )
        )
        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="whitehouse_news",
                    fetch_mode="source_capture_refresh",
                    payload_hash="formatted-item",
                ),
            )
        )
        repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
        repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )

        item = service.list_recent_items(limit=5)["items"][0]

        assert item["published_at_precision"] == "datetime"
        assert item["published_at_display"] == "2026-04-07 09:30 CST"
        assert item["source_authority"] == "primary_official"
        assert item["content_metrics"]["summary_sentence_count"] == 2
        assert item["content_metrics"]["numeric_fact_count"] == 1
        assert item["content_metrics"]["entity_count"] == 3
        assert item["content_metrics"]["evidence_point_count"] >= 1
        assert item["content_completeness"] == "high"
        assert item["body_detail_level"] == "detailed"
        assert item["source_time_reliability"] == "high"
        assert item["why_it_matters_cn"].endswith("。")
        assert "贸易/关税/供应链" in item["why_it_matters_cn"]
        assert item["key_numbers"] == [
            {
                "metric": "tariff_rate",
                "value": 25.0,
                "value_text": "25.0%",
                "unit": "percent",
                "subject": "steel",
            }
        ]
        assert item["fact_table"][0]["fact_type"] == "sentence"
        assert "25% tariff on steel imports" in item["fact_table"][0]["text"]
        assert item["fact_table"][1] == {
            "fact_type": "numeric",
            "metric": "tariff_rate",
            "value": 25.0,
            "value_text": "25.0%",
            "unit": "percent",
            "subject": "steel",
            "text": "tariff_rate: 25.0% on steel",
        }
        assert item["policy_actions"] == [
            "关税/贸易限制仍在执行",
        ]
        assert item["market_implications"] == [
            {
                "implication_type": "beneficiary",
                "direction": "进口替代制造链",
                "stance": "positive",
            },
            {
                "implication_type": "pressured",
                "direction": "对美出口链",
                "stance": "negative",
            },
            {
                "implication_type": "pressured",
                "direction": "依赖进口零部件的装配链",
                "stance": "negative",
            },
        ]
        assert item["uncertainties"] == [
            "确认税率、覆盖商品清单和生效日期。",
            "确认是否配套豁免、补贴或本土采购政策。",
        ]


def test_source_capture_service_formats_extended_numeric_fact_types() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_numeric_formats.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="news_article",
                candidate_url="https://example.com/macro-snapshot",
                candidate_title="Trade deficit widens while payrolls rise and rate path stays in focus",
                candidate_summary=(
                    "The trade deficit widened to $57.3 billion in February while nonfarm payrolls increased "
                    "by 271,000 jobs. Officials said a 25 basis point rate cut remains under discussion."
                ),
                candidate_published_at="2026-04-07T01:30:00+00:00",
                candidate_published_at_source="html:meta_article_published_time",
                candidate_excerpt_source="body_selector:article",
            )
        )
        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="ap_business",
                    fetch_mode="source_capture_refresh",
                    payload_hash="numeric-formats",
                ),
            )
        )
        repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
        repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )

        item = service.list_recent_items(limit=5)["items"][0]

        assert item["key_numbers"] == [
            {
                "metric": "usd_amount",
                "value": 57_300_000_000.0,
                "value_text": "$57.3B",
                "unit": "usd",
                "subject": "deficit",
            },
            {
                "metric": "jobs_count",
                "value": 271_000.0,
                "value_text": "271,000",
                "unit": "jobs",
                "subject": "payrolls",
            },
            {
                "metric": "basis_points",
                "value": 25.0,
                "value_text": "25 bp",
                "unit": "basis_points",
                "subject": "rates",
            },
        ]
        usd_fact = next(
            fact
            for fact in item["fact_table"]
            if fact.get("fact_type") == "numeric" and fact.get("metric") == "usd_amount"
        )
        jobs_fact = next(
            fact
            for fact in item["fact_table"]
            if fact.get("fact_type") == "numeric" and fact.get("metric") == "jobs_count"
        )

        assert usd_fact == {
            "fact_type": "numeric",
            "metric": "usd_amount",
            "value": 57_300_000_000.0,
            "value_text": "$57.3B",
            "unit": "usd",
            "subject": "deficit",
            "text": "usd_amount: $57.3B on deficit",
        }
        assert jobs_fact == {
            "fact_type": "numeric",
            "metric": "jobs_count",
            "value": 271_000.0,
            "value_text": "271,000",
            "unit": "jobs",
            "subject": "payrolls",
            "text": "jobs_count: 271,000 on payrolls",
        }


def test_source_capture_service_adds_confirmation_conflicts_and_llm_brief() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_context.db")
        repo = OvernightRepository(database)

        def persist_item(
            *,
            source_id: str,
            url: str,
            title: str,
            summary: str,
            published_at: str,
        ) -> int:
            normalized = normalize_candidate(
                SourceCandidate(
                    candidate_type="press_release" if source_id != "ap_business" else "news_article",
                    candidate_url=url,
                    candidate_title=title,
                    candidate_summary=summary,
                    candidate_published_at=published_at,
                    candidate_published_at_source="html:meta_article_published_time",
                    candidate_excerpt_source="body_selector:article",
                )
            )
            stored = repo.persist_source_item(
                replace(
                    normalized,
                    raw_id=repo.create_raw_record(
                        source_id=source_id,
                        fetch_mode="source_capture_refresh",
                        payload_hash=f"{source_id}:{published_at}",
                    ),
                )
            )
            repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
            repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
            return stored.id

        whitehouse_id = persist_item(
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/tariff-update",
            title="White House says 25% tariff on steel imports remains in place",
            summary=(
                "The White House and USTR said the 25% tariff on steel imports remains in place while "
                "agencies review supply chains and procurement plans."
            ),
            published_at="2026-04-07T01:30:00+00:00",
        )
        ustr_id = persist_item(
            source_id="ustr_press_releases",
            url="https://example.com/ustr/steel-tariff-confirmation",
            title="USTR confirms 25% tariff on steel imports",
            summary=(
                "USTR confirmed the 25% tariff on steel imports remains in effect while agencies "
                "coordinate implementation and monitor supply chains."
            ),
            published_at="2026-04-07T01:50:00+00:00",
        )
        ap_id = persist_item(
            source_id="ap_business",
            url="https://example.com/ap/steel-tariff-revision",
            title="AP says tariff on steel imports could move to 15%",
            summary=(
                "AP reported discussion around a possible 15% tariff on steel imports, though officials "
                "have not confirmed any change to the current policy."
            ),
            published_at="2026-04-07T02:10:00+00:00",
        )
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )

        item = next(
            rendered
            for rendered in service.list_recent_items(limit=10)["items"]
            if rendered["item_id"] == whitehouse_id
        )

        assert item["source_capture_confidence"]["level"] == "high"
        assert item["source_capture_confidence"]["score"] >= 80
        assert "官方源" in item["source_capture_confidence"]["reasons"]
        assert item["cross_source_confirmation"]["level"] == "moderate"
        assert item["cross_source_confirmation"]["confirmed_by_item_ids"] == [ustr_id]
        assert item["cross_source_confirmation"]["confirmed_by_sources"][0]["item_id"] == ustr_id
        assert item["cross_source_confirmation"]["confirmed_by_sources"][0]["source_id"] == "ustr_press_releases"
        assert item["cross_source_confirmation"]["confirmed_by_sources"][0]["source_name"] == "USTR Press Releases"
        assert "numeric:tariff_rate:steel" in item["cross_source_confirmation"]["confirmed_by_sources"][0]["match_basis"]
        assert "topic:trade_policy" in item["cross_source_confirmation"]["confirmed_by_sources"][0]["match_basis"]
        assert any(
            basis.startswith("direction:")
            for basis in item["cross_source_confirmation"]["confirmed_by_sources"][0]["match_basis"]
        )
        assert item["fact_conflicts"] == [
            {
                "conflict_type": "numeric_mismatch",
                "metric": "tariff_rate",
                "subject": "steel",
                "current_value_text": "25.0%",
                "other_value_text": "15.0%",
                "other_item_id": ap_id,
                "other_source_id": "ap_business",
                "other_source_name": "AP Business",
            }
        ]
        assert f"item_id={whitehouse_id}" in item["llm_ready_brief"]
        assert "White House News" in item["llm_ready_brief"]
        assert "25.0%" in item["llm_ready_brief"]
        assert "cross_source=1" in item["llm_ready_brief"]


def test_source_capture_service_groups_related_items_into_event_cluster() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_event_cluster.db")
        repo = OvernightRepository(database)

        def persist_item(
            *,
            source_id: str,
            url: str,
            title: str,
            summary: str,
            published_at: str,
        ) -> int:
            normalized = normalize_candidate(
                SourceCandidate(
                    candidate_type="press_release" if source_id != "ap_business" else "news_article",
                    candidate_url=url,
                    candidate_title=title,
                    candidate_summary=summary,
                    candidate_published_at=published_at,
                    candidate_published_at_source="html:meta_article_published_time",
                    candidate_excerpt_source="body_selector:article",
                )
            )
            stored = repo.persist_source_item(
                replace(
                    normalized,
                    raw_id=repo.create_raw_record(
                        source_id=source_id,
                        fetch_mode="source_capture_refresh",
                        payload_hash=f"{source_id}:{published_at}",
                    ),
                )
            )
            repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
            repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
            return stored.id

        whitehouse_id = persist_item(
            source_id="whitehouse_news",
            url="https://example.com/whitehouse/tariff-update",
            title="White House says 25% tariff on steel imports remains in place",
            summary=(
                "The White House and USTR said the 25% tariff on steel imports remains in place while "
                "agencies review supply chains and procurement plans."
            ),
            published_at="2026-04-07T01:30:00+00:00",
        )
        ustr_id = persist_item(
            source_id="ustr_press_releases",
            url="https://example.com/ustr/steel-tariff-confirmation",
            title="USTR confirms 25% tariff on steel imports",
            summary=(
                "USTR confirmed the 25% tariff on steel imports remains in effect while agencies "
                "coordinate implementation and monitor supply chains."
            ),
            published_at="2026-04-07T01:50:00+00:00",
        )
        ap_id = persist_item(
            source_id="ap_business",
            url="https://example.com/ap/steel-tariff-revision",
            title="AP says tariff on steel imports could move to 15%",
            summary=(
                "AP reported discussion around a possible 15% tariff on steel imports, though officials "
                "have not confirmed any change to the current policy."
            ),
            published_at="2026-04-07T02:10:00+00:00",
        )
        fed_id = persist_item(
            source_id="fed_news",
            url="https://example.com/fed/rates-statement",
            title="Federal Reserve says rates may stay restrictive",
            summary=(
                "Federal Reserve officials said inflation remains elevated and rates may need "
                "to stay restrictive while markets assess the next FOMC path."
            ),
            published_at="2026-04-07T02:20:00+00:00",
        )
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )

        items = {
            rendered["item_id"]: rendered
            for rendered in service.list_recent_items(limit=10)["items"]
        }

        cluster = items[whitehouse_id]["event_cluster"]
        assert cluster["cluster_id"].startswith("trade_policy")
        assert cluster["cluster_status"] == "conflicted"
        assert cluster["primary_item_id"] == whitehouse_id
        assert cluster["item_count"] == 3
        assert cluster["source_count"] == 3
        assert cluster["official_source_count"] == 2
        assert cluster["member_item_ids"] == [whitehouse_id, ustr_id, ap_id]
        assert cluster["member_source_ids"] == [
            "whitehouse_news",
            "ustr_press_releases",
            "ap_business",
        ]
        assert cluster["latest_published_at"] == "2026-04-07T02:10:00+00:00"
        assert cluster["topic_tags"] == ["trade_policy"]
        assert "tariff_rate:steel" in cluster["fact_signatures"]

        assert items[ustr_id]["event_cluster"]["cluster_id"] == cluster["cluster_id"]
        assert items[ap_id]["event_cluster"]["cluster_id"] == cluster["cluster_id"]
        assert items[fed_id]["event_cluster"]["cluster_status"] == "single_source"
        assert items[fed_id]["event_cluster"]["member_item_ids"] == [fed_id]


def test_source_capture_service_exposes_source_integrity_and_quality_flags() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_integrity.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/07/sample-release/",
                candidate_title="White House says 25% tariff on steel imports remains in place",
                candidate_summary="The White House said the 25% tariff on steel imports remains in place.",
                candidate_published_at="2026-04-07T01:30:00+00:00",
                candidate_published_at_source="html:meta_article_published_time",
                candidate_excerpt_source="body_selector:article",
            )
        )
        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="whitehouse_news",
                    fetch_mode="source_capture_refresh",
                    payload_hash="source-integrity",
                ),
            )
        )
        with repo.db.connect() as connection:
            connection.execute(
                "UPDATE overnight_source_items SET created_at = ? WHERE id = ?",
                ("2026-04-07 02:00:00", stored.id),
            )
        repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
        repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
        service = OvernightSourceCaptureService(repo=repo, registry=build_default_source_registry(), http_client=RoutingFixtureClient({}))

        item = service.list_recent_items(limit=5)["items"][0]

        assert item["source_integrity"] == {
            "hostname": "www.whitehouse.gov",
            "domain_status": "verified",
            "matched_domain": "whitehouse.gov",
            "allowed_domains": ["whitehouse.gov"],
            "blocked_reason": "",
            "is_https": True,
            "https_required": True,
            "url_valid": True,
        }
        assert item["data_quality_flags"] == []


def test_source_capture_service_exposes_timeliness_fields() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_timeliness.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/07/sample-release/",
                candidate_title="White House says 25% tariff on steel imports remains in place",
                candidate_summary="The White House said the 25% tariff on steel imports remains in place.",
                candidate_published_at="2026-04-07T01:30:00+00:00",
                candidate_published_at_source="html:meta_article_published_time",
                candidate_excerpt_source="body_selector:article",
            )
        )
        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="whitehouse_news",
                    fetch_mode="source_capture_refresh",
                    payload_hash="timeliness",
                ),
            )
        )
        with repo.db.connect() as connection:
            connection.execute(
                "UPDATE overnight_source_items SET created_at = ? WHERE id = ?",
                ("2026-04-07 02:00:00", stored.id),
            )
        repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
        repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)
        service = OvernightSourceCaptureService(repo=repo, registry=build_default_source_registry(), http_client=RoutingFixtureClient({}))

        item = service.list_recent_items(limit=5)["items"][0]

        assert item["timeliness"] == {
            "anchor_time": "2026-04-07T02:00:00+00:00",
            "age_hours": 0.5,
            "publication_lag_minutes": 30,
            "freshness_bucket": "breaking",
            "is_timely": True,
            "timeliness_flags": [],
        }


def test_source_capture_service_skips_article_when_canonical_domain_mismatches_source() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_invalid_canonical.db")
        repo = OvernightRepository(database)
        source = next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")
        html = """
        <html>
          <head>
            <title>Statement from the White House</title>
            <link rel="canonical" href="https://mirror.example.com/whitehouse/fake-policy" />
            <meta property="article:published_time" content="2026-04-07T01:30:00+00:00" />
          </head>
          <body>
            <main>
              <article>
                <p>The White House said tariffs remain in place.</p>
              </article>
            </main>
          </body>
        </html>
        """
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=[source],
            http_client=RoutingFixtureClient({"whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html"}),
        )
        service._article_collector = type(
            "StubArticleCollector",
            (),
            {
                "expand": staticmethod(
                    lambda candidate: replace(
                        candidate,
                        candidate_url="https://mirror.example.com/whitehouse/fake-policy",
                        candidate_summary="The White House said tariffs remain in place.",
                        candidate_excerpt_source="body_selector:article",
                        candidate_published_at="2026-04-07T01:30:00+00:00",
                        candidate_published_at_source="html:meta_article_published_time",
                        needs_article_fetch=False,
                    )
                )
            },
        )()

        stored = service._persist_candidate(
            source,
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/07/sample-release/",
                candidate_title="Statement from the White House",
                candidate_summary="",
                needs_article_fetch=True,
            ),
        )

        assert stored is None


def test_source_capture_service_skips_article_expansion_for_rich_feed_summaries() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_rich_feed_summary.db")
        repo = OvernightRepository(database)
        source = SourceDefinition(
            source_id="example_feed",
            display_name="Example Feed",
            organization_type="editorial_media",
            source_class="news",
            entry_type="rss",
            entry_urls=("https://example.com/feed.xml",),
            priority=50,
            poll_interval_seconds=300,
        )
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=[source],
            http_client=RoutingFixtureClient({}),
        )
        expand_calls: list[str] = []

        def fail_expand(candidate: SourceCandidate) -> SourceCandidate:
            expand_calls.append(candidate.candidate_url)
            raise AssertionError("rich feed summaries should not trigger article expansion")

        service._article_collector = type(
            "FailingArticleCollector",
            (),
            {"expand": staticmethod(fail_expand)},
        )()

        rich_summary = (
            "The Energy Information Administration said it is launching a pilot survey on electricity and cooling "
            "demand from data centers, with initial responses due later this quarter. The release said the agency "
            "will use the program to improve visibility into grid pressure, regional load growth, and the capital "
            "spending plans now shaping U.S. power, gas, and industrial equipment markets."
        )

        stored = service._persist_candidate(
            source,
            SourceCandidate(
                candidate_type="feed_item",
                candidate_url="https://example.com/articles/eia-data-center-survey",
                candidate_title="EIA launches pilot survey on data center energy demand",
                candidate_summary=rich_summary,
                candidate_excerpt_source="feed:summary",
                candidate_published_at="2026-04-09T14:30:00+00:00",
                candidate_published_at_source="feed:published",
                needs_article_fetch=True,
            ),
        )

        assert stored is not None
        assert expand_calls == []
        assert stored.summary == rich_summary
        assert stored.excerpt_source == "feed:summary"
        assert stored.article_fetch_status == "skipped_rich_feed_summary"


def test_source_capture_service_cools_down_after_repeated_hard_failures() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_cooldown.db")
        repo = OvernightRepository(database)
        source = SourceDefinition(
            source_id="failing_feed",
            display_name="Failing Feed",
            organization_type="official_data",
            source_class="macro",
            entry_type="rss",
            entry_urls=("https://example.com/failing-feed.xml",),
            priority=90,
            poll_interval_seconds=300,
            is_mission_critical=True,
        )
        http_client = FailingHttpClient()
        now_values = iter(
            [
                datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 10, 1, 0, tzinfo=timezone.utc),
                datetime(2026, 4, 10, 2, 0, tzinfo=timezone.utc),
            ]
        )
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=[source],
            http_client=http_client,
            now_fn=lambda: next(now_values),
        )

        first = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)
        second = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)
        third = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)

        assert first["collected_items"] == 0
        assert first["source_diagnostics"][0]["status"] == "error"
        assert first["source_diagnostics"][0]["consecutive_failure_count"] == 1
        assert first["source_diagnostics"][0]["cooldown_until"] is None
        assert first["source_diagnostics"][0]["errors"][0].startswith("403 Client Error")

        assert second["source_diagnostics"][0]["status"] == "error"
        assert second["source_diagnostics"][0]["consecutive_failure_count"] == 2
        assert second["source_diagnostics"][0]["cooldown_until"] == "2026-04-10T07:00:00+00:00"

        assert third["source_diagnostics"][0]["status"] == "cooldown"
        assert third["source_diagnostics"][0]["skipped_reason"] == "hard_failure_cooldown"
        assert third["source_diagnostics"][0]["consecutive_failure_count"] == 2
        assert third["source_diagnostics"][0]["cooldown_until"] == "2026-04-10T07:00:00+00:00"
        assert len(http_client.fetches) == 2


def test_source_capture_service_collects_and_lists_recent_items() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_overnight_source_capture.db")
        repo = OvernightRepository(database)
        http_client = RoutingFixtureClient(
            {
                "whitehouse.gov/news/": FIXTURE_DIR / "whitehouse_news.html",
                "whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html",
            }
        )
        registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=registry,
            http_client=http_client,
        )

        result = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)

        assert result["collected_sources"] == 1
        assert result["collected_items"] == 1
        assert result["items"][0]["source_id"] == "whitehouse_news"
        assert result["items"][0]["source_name"] == "White House News"
        assert result["items"][0]["title"]
        assert "whitehouse.gov" in result["items"][0]["canonical_url"]
        assert result["items"][0]["summary"]
        assert result["items"][0]["published_at"]
        assert result["items"][0]["published_at_source"]
        assert result["items"][0]["organization_type"] == "official_policy"
        assert result["items"][0]["is_mission_critical"] is True
        assert result["items"][0]["coverage_focus"]
        assert result["items"][0]["excerpt_source"]
        assert result["items"][0]["excerpt_char_count"] == len(result["items"][0]["summary"])
        assert result["items"][0]["summary_quality"] in {"high", "medium"}
        assert result["items"][0]["a_share_relevance"] in {"high", "medium", "low"}
        assert "官方政策源" in result["items"][0]["a_share_relevance_reason"]
        assert result["items"][0]["entities"][0]["name"] == "White House"

        recent_items = service.list_recent_items(limit=5)
        assert recent_items["total"] == 1
        assert recent_items["items"][0]["canonical_url"].startswith("https://www.whitehouse.gov/")


def test_source_capture_service_skips_identical_repeat_refresh_items() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_dedupe.db")
        repo = OvernightRepository(database)
        http_client = RoutingFixtureClient(
            {
                "whitehouse.gov/news/": FIXTURE_DIR / "whitehouse_news.html",
                "whitehouse.gov/briefing-room/": FIXTURE_DIR / "whitehouse_news.html",
            }
        )
        registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=registry,
            http_client=http_client,
        )

        first = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)
        second = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)
        recent_items = service.list_recent_items(limit=5)

        assert first["collected_items"] == 1
        assert second["collected_items"] == 0
        assert recent_items["total"] == 1


def test_source_capture_service_dedupes_identical_legacy_rows_in_recent_items() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_legacy_dedupe.db")
        repo = OvernightRepository(database)
        normalized = normalize_candidate(
            SourceCandidate(
                candidate_type="press_release",
                candidate_url="https://example.com/releases/fixed-story",
                candidate_title="Fixed story",
                candidate_summary="The same article body appears twice in storage.",
                candidate_published_at="2026-04-10T01:30:00+00:00",
                candidate_excerpt_source="body_selector:article",
            )
        )
        for index in range(2):
            stored = repo.persist_source_item(
                replace(
                    normalized,
                    raw_id=repo.create_raw_record(
                        source_id="whitehouse_news",
                        fetch_mode=f"source_capture_refresh_{index}",
                        payload_hash=f"fixed-story-{index}",
                    ),
                )
            )
            repo.assign_document_family(stored.id, family_key=stored.canonical_url, family_type="canonical_document")
            repo.attach_document_version(stored.id, body_hash=stored.body_hash, title_hash=stored.title_hash)

        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )

        recent_items = service.list_recent_items(limit=5)

        assert recent_items["total"] == 1


def test_source_capture_service_selects_highest_priority_sources_first() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_priority.db")
        repo = OvernightRepository(database)
        registry = [
            SourceDefinition(
                source_id="low_priority",
                display_name="Low Priority",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/low.xml",),
                priority=10,
                poll_interval_seconds=300,
            ),
            SourceDefinition(
                source_id="high_priority",
                display_name="High Priority",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/high.xml",),
                priority=100,
                poll_interval_seconds=300,
            ),
            SourceDefinition(
                source_id="medium_priority",
                display_name="Medium Priority",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/medium.xml",),
                priority=60,
                poll_interval_seconds=300,
            ),
        ]
        service = OvernightSourceCaptureService(repo=repo, registry=registry, http_client=RoutingFixtureClient({}))

        selected = service._select_sources(max_sources=2)

        assert [source.source_id for source in selected] == ["high_priority", "medium_priority"]


def test_source_capture_service_keeps_going_until_it_fills_successful_sources() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_fill.db")
        repo = OvernightRepository(database)
        registry = [
            SourceDefinition(
                source_id="first_empty",
                display_name="First Empty",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/first.xml",),
                priority=100,
                poll_interval_seconds=300,
            ),
            SourceDefinition(
                source_id="second_working",
                display_name="Second Working",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/second.xml",),
                priority=90,
                poll_interval_seconds=300,
            ),
            SourceDefinition(
                source_id="third_working",
                display_name="Third Working",
                organization_type="official_policy",
                source_class="policy",
                entry_type="rss",
                entry_urls=("https://example.com/third.xml",),
                priority=80,
                poll_interval_seconds=300,
            ),
        ]
        service = OvernightSourceCaptureService(repo=repo, registry=registry, http_client=RoutingFixtureClient({}))

        candidate = SourceCandidate(
            candidate_type="feed_item",
            candidate_url="https://example.com/item-1",
            candidate_title="Sample title",
            candidate_summary="Sample summary",
            needs_article_fetch=False,
        )

        captured_ids: list[str] = []

        def fake_collect(source: SourceDefinition):
            if source.source_id == "first_empty":
                return []
            return [candidate]

        def fake_persist(source: SourceDefinition, _candidate: SourceCandidate):
            captured_ids.append(source.source_id)
            return object()

        service._collect_source_candidates = fake_collect  # type: ignore[method-assign]
        service._persist_candidate = fake_persist  # type: ignore[method-assign]
        service.list_recent_items = lambda limit=20: {"total": len(captured_ids), "items": []}  # type: ignore[assignment]

        result = service.refresh(limit_per_source=1, max_sources=2, recent_limit=5)

        assert result["collected_sources"] == 2
        assert captured_ids == ["second_working", "third_working"]


def test_source_capture_service_prioritizes_relevant_policy_candidates_within_source() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_relevance.db")
        repo = OvernightRepository(database)
        registry = [next(source for source in build_default_source_registry() if source.source_id == "whitehouse_news")]
        service = OvernightSourceCaptureService(repo=repo, registry=registry, http_client=RoutingFixtureClient({}))

        irrelevant_candidate = SourceCandidate(
            candidate_type="section_card",
            candidate_url="https://www.whitehouse.gov/briefings-statements/2026/04/presidential-message-on-the-ncaa-college-basketball-national-championship-game/",
            candidate_title="Presidential Message on the NCAA College Basketball National Championship Game",
            candidate_summary="The President congratulates the teams competing in the national championship tonight.",
            candidate_published_at="2026-04-06T14:49:56-04:00",
            candidate_published_at_source="section:nearby_time",
            needs_article_fetch=False,
        )
        relevant_candidate = SourceCandidate(
            candidate_type="section_card",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/07/statement-on-trade-and-supply-chain-resilience/",
            candidate_title="Statement on Trade and Supply Chain Resilience",
            candidate_summary=(
                "The White House announced a trade, tariff, and semiconductor supply chain update "
                "targeting critical minerals and industrial resilience."
            ),
            candidate_published_at="2026-04-07T08:00:00-04:00",
            candidate_published_at_source="section:time",
            needs_article_fetch=False,
        )

        service._collect_source_candidates = lambda _source: [irrelevant_candidate, relevant_candidate]  # type: ignore[assignment]

        result = service.refresh(limit_per_source=1, max_sources=1, recent_limit=5)

        assert result["collected_items"] == 1
        assert result["items"][0]["title"] == "Statement on Trade and Supply Chain Resilience"
        assert result["items"][0]["a_share_relevance"] == "high"
        assert "贸易/关税/供应链" in result["items"][0]["a_share_relevance_reason"]


def test_item_topics_does_not_tag_macro_trade_data_as_trade_policy() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_trade_topic_scope.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        item = {
            "item_id": 1,
            "source_id": "census_economic_indicators",
            "title": "U.S. trade deficit widened in February",
            "summary": "Imports increased more than exports in the latest Census release.",
            "impact_summary": "Macro trade data informs export-chain demand but is not itself a policy action.",
        }

        assert "trade_policy" not in service._item_topics(item)


def test_items_belong_to_same_event_requires_more_than_generic_tariff_overlap() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_event_cluster_tariff_specificity.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        steel_item = {
            "item_id": 1,
            "title": "White House keeps 25% tariff on steel imports",
            "summary": (
                "The White House said the 25% tariff on steel imports remains in place while "
                "agencies review supply chains."
            ),
            "impact_summary": "",
            "source_id": "whitehouse_news",
            "published_at": "2026-04-07T01:00:00+00:00",
            "published_at_precision": "datetime",
            "created_at": "2026-04-07T02:00:00+00:00",
            "entities": [],
            "key_numbers": [
                {
                    "metric": "tariff_rate",
                    "subject": "steel",
                    "value_text": "25.0%",
                }
            ],
            "market_implications": [],
        }
        copper_item = {
            "item_id": 2,
            "title": "USTR studies new tariff on copper imports",
            "summary": (
                "USTR said a new tariff on copper imports is under discussion while agencies "
                "review supply chains."
            ),
            "impact_summary": "",
            "source_id": "ustr_press_releases",
            "published_at": "2026-04-07T03:00:00+00:00",
            "published_at_precision": "datetime",
            "created_at": "2026-04-07T03:10:00+00:00",
            "entities": [],
            "key_numbers": [],
            "market_implications": [],
        }

        assert service._items_belong_to_same_event(steel_item, copper_item) is False


def test_item_topics_detect_precious_metals_specific_tags_before_macro_noise() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_precious_metal_topics.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        item = {
            "item_id": 1,
            "source_id": "kitco_news",
            "title": "Wall Street and Main Street retreat after gold remains rangebound ahead of rate decisions",
            "summary": "Gold stays rangebound while traders wait for central bank rate decisions and bullion demand signals.",
            "impact_summary": "Precious-metals pricing is moving, not just macro policy chatter.",
        }

        topics = service._item_topics(item)

        assert "gold_market" in topics
        assert "rates_macro" in topics
        assert "trade_policy" not in topics


def test_item_topics_detect_kitco_metals_market_titles_without_explicit_topic_tags() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_kitco_precious_titles.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        gold_item = {
            "item_id": 2,
            "source_id": "kitco_news",
            "title": "Gold market analysis for April 24 - key intra-day price entry levels for active traders",
            "summary": "Comex gold futures remain active as traders watch the market through the session.",
            "impact_summary": "Gold pricing remains active in the overnight window.",
        }
        silver_item = {
            "item_id": 3,
            "source_id": "kitco_news",
            "title": "China's silver imports surge 78% in March as investors and manufacturers scramble to secure metal",
            "summary": "Silver imports and bullion demand are moving together.",
            "impact_summary": "Silver demand is part of the market move, not generic macro noise.",
        }

        gold_topics = service._item_topics(gold_item)
        silver_topics = service._item_topics(silver_item)

        assert "gold_market" in gold_topics
        assert "silver_market" in silver_topics


def test_item_topics_detect_hong_kong_and_china_internet_tags() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_china_market_topics.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        item = {
            "item_id": 1,
            "source_id": "scmp_markets",
            "title": "Hong Kong stocks fall as Alibaba and JD.com drag China tech lower",
            "summary": "Hong Kong shares slid as China internet ADR names stayed under pressure.",
            "impact_summary": "KWEB and other China internet proxies remained weak overnight.",
        }

        topics = service._item_topics(item)

        assert "hong_kong_market" in topics
        assert "china_internet" in topics


def test_item_topics_detect_copper_market_in_trade_headlines() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_copper_topics.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        item = {
            "item_id": 1,
            "source_id": "ustr_press_releases",
            "title": "USTR studies new tariff on copper imports",
            "summary": "Agencies are reviewing copper imports and refined copper supply exposure.",
            "impact_summary": "Industrial metals should not be collapsed into generic trade-policy noise.",
        }

        topics = service._item_topics(item)

        assert "copper_market" in topics
        assert "trade_policy" in topics


def test_item_topics_detect_industrial_metals_from_mining_supply_chain_language() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_industrial_metals_topics.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        item = {
            "item_id": 1,
            "source_id": "mining_com_markets",
            "title": "War squeezes global mining as diesel and acid supplies tighten",
            "summary": "Sulfuric acid and SX-EW processing pressure are starting to hit copper supply.",
            "impact_summary": "Mining and mineral processing stress should be visible to industrial-metals logic.",
        }

        topics = service._item_topics(item)

        assert "industrial_metals" in topics
        assert "copper_market" in topics


def test_items_belong_to_same_event_does_not_merge_trade_and_budget_deficit() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_event_cluster_deficit_specificity.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(repo=repo)

        trade_item = {
            "item_id": 1,
            "title": "Trade deficit widens in February",
            "summary": "The trade deficit widened to $57.3 billion as imports outpaced exports.",
            "impact_summary": "",
            "source_id": "census_economic_indicators",
            "published_at": "2026-04-07T01:00:00+00:00",
            "published_at_precision": "datetime",
            "created_at": "2026-04-07T01:10:00+00:00",
            "entities": [],
            "key_numbers": [
                {
                    "metric": "usd_amount",
                    "subject": "deficit",
                    "value_text": "$57.3B",
                }
            ],
            "market_implications": [],
        }
        budget_item = {
            "item_id": 2,
            "title": "Budget deficit widens after spending increase",
            "summary": "The budget deficit widened to $1.2T after federal spending increased.",
            "impact_summary": "",
            "source_id": "treasury_press_releases",
            "published_at": "2026-04-07T02:00:00+00:00",
            "published_at_precision": "datetime",
            "created_at": "2026-04-07T02:10:00+00:00",
            "entities": [],
            "key_numbers": [
                {
                    "metric": "usd_amount",
                    "subject": "deficit",
                    "value_text": "$1.2T",
                }
            ],
            "market_implications": [],
        }

        assert service._items_belong_to_same_event(trade_item, budget_item) is False


def test_rank_source_candidates_penalizes_noisy_search_summaries() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_search_quality.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )
        source = next(item for item in build_default_source_registry() if item.source_id == "whitehouse_news")
        noisy = SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/noisy-release/",
            candidate_title="White House sanctions statement",
            candidate_summary=(
                "Preferences- [x] Preferences Manage {vendor_count} vendors Countries &Areas "
                "White House Home official government organization"
            ),
            candidate_excerpt_source="search:tavily",
        )
        clean = SourceCandidate(
            candidate_type="search_result",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/2026/04/clean-release/",
            candidate_title="White House sanctions statement",
            candidate_summary="The White House said new sanctions coordination with allies will take effect immediately.",
            candidate_excerpt_source="search:tavily",
        )

        ranked = service._rank_source_candidates(source, [noisy, clean])

        assert ranked[0].candidate_url == clean.candidate_url


def test_should_use_search_discovery_only_for_empty_or_thin_candidate_sets() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "test_source_capture_search_gate.db")
        repo = OvernightRepository(database)
        service = OvernightSourceCaptureService(
            repo=repo,
            registry=build_default_source_registry(),
            http_client=RoutingFixtureClient({}),
        )
        source = next(item for item in build_default_source_registry() if item.source_id == "whitehouse_news")
        thin = SourceCandidate(
            candidate_type="section_card",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/thin/",
            candidate_title="Thin candidate",
            candidate_summary="",
            needs_article_fetch=True,
        )
        strong = SourceCandidate(
            candidate_type="feed_item",
            candidate_url="https://www.whitehouse.gov/briefing-room/statements-releases/strong/",
            candidate_title="Strong candidate",
            candidate_summary="Detailed official summary with clear policy and sanctions content.",
            candidate_excerpt_source="feed:description",
            needs_article_fetch=True,
        )

        assert service._should_use_search_discovery(source, []) is True
        assert service._should_use_search_discovery(source, [thin]) is True
        assert service._should_use_search_discovery(source, [strong]) is False
        assert service._should_use_search_discovery(source, [strong, strong]) is False
        assert service._should_use_search_discovery(source, [thin, thin]) is True
        assert service._should_use_search_discovery(source, [thin, thin, thin, thin]) is False
