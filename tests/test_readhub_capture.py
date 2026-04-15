# -*- coding: utf-8 -*-
"""Tests for Readhub daily/topic capture and persistence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

import requests

from app.collectors.readhub import ReadhubDailyCollector
from app.db import Database
from app.normalizer import normalize_candidate
from app.repository import OvernightRepository
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceDefinition


class RoutingFixtureClient:
    def __init__(self, responses: dict[str, str], failing_urls: set[str] | None = None) -> None:
        self.responses = responses
        self.failing_urls = set(failing_urls or set())
        self.fetches: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetches.append(url)
        if url in self.failing_urls:
            response = requests.Response()
            response.status_code = 525
            response.url = url
            raise requests.exceptions.SSLError(f"SSL connect error for url: {url}", response=response)
        if url not in self.responses:
            raise AssertionError(f"Unexpected fixture url: {url}")
        return self.responses[url]


def _source_by_id(source_id: str) -> SourceDefinition:
    return next(source for source in build_default_source_registry() if source.source_id == source_id)


def _daily_html() -> str:
    return """
    <html>
      <body>
        <div class="style-module-scss-module__ZdPb2G__date"><span>2026.04.15</span></div>
        <script>
          self.__next_f.push([1,"10:[\\"$\\",\\"$L23\\",null,{\\"ts\\":1776,\\"articles\\":[
            {\\"id\\":\\"8sReadhubA\\",\\"title\\":\\"OpenAI 内部备忘录曝光\\",\\"summary\\":\\"Readhub 每日早报中的话题摘要 A\\",\\"entityList\\":[{\\"name\\":\\"OpenAI\\"},{\\"name\\":\\"Anthropic\\"}]},
            {\\"id\\":\\"8sReadhubB\\",\\"title\\":\\"苹果折叠 iPhone 量产延后\\",\\"summary\\":\\"Readhub 每日早报中的话题摘要 B\\",\\"entityList\\":[{\\"name\\":\\"苹果\\"}]}
          ]}]\\n"]);
        </script>
      </body>
    </html>
    """


def _topic_html(
    *,
    topic_id: str,
    title: str,
    summary: str,
    entity_names: list[str],
    tags: list[str],
    news_title: str,
    news_url: str,
    news_origin: str,
) -> str:
    entity_entries = ",".join(f'{{\\"name\\":\\"{name}\\"}}' for name in entity_names)
    tag_entries = ",".join(f'{{\\"name\\":\\"{name}\\"}}' for name in tags)
    return f"""
    <html>
      <body>
        <script>
          self.__next_f.push([1,"11:[\\"$\\",\\"$L25\\",null,{{\\"initialState\\":{{\\"id\\":\\"{topic_id}\\",\\"title\\":\\"{title}\\",\\"summary\\":\\"{summary}\\",\\"relativeDate\\":\\"昨天\\",\\"entityList\\":[{entity_entries}],\\"tagList\\":[{tag_entries}],\\"trackingList\\":[{{\\"publishDate\\":\\"2026-04-14T03:00:00.000Z\\",\\"title\\":\\"{title}\\",\\"uid\\":\\"{topic_id}\\"}}],\\"similarEventList\\":[{{\\"name\\":\\"历史对比事件\\",\\"time\\":\\"2024年4月\\",\\"events\\":[{{\\"title\\":\\"资产情况\\",\\"content\\":\\"可用于对比的历史上下文\\"}}]}}],\\"newsList\\":[{{\\"siteNameDisplay\\":\\"{news_origin}\\",\\"title\\":\\"{news_title}\\",\\"url\\":\\"{news_url}\\"}}],\\"stockReleaseList\\":[]}},\\"children\\":\\"$L27\\"}}]\\n"]);
        </script>
      </body>
    </html>
    """


def test_readhub_source_is_registered_as_low_priority_aggregated_editorial_source() -> None:
    source = _source_by_id("readhub_daily_digest")
    whitehouse = _source_by_id("whitehouse_news")
    bea = _source_by_id("bea_news")

    assert source.entry_urls[0] == "https://readhub.cn/daily"
    assert source.entry_urls[1] == "https://1.readhub.cn/daily"
    assert source.organization_type == "editorial_media"
    assert source.coverage_tier == "editorial_media"
    assert source.is_mission_critical is False
    assert source.priority < whitehouse.priority
    assert source.priority < bea.priority


def test_readhub_collector_uses_canonical_daily_endpoint_and_tolerates_legacy_alias_failure() -> None:
    source = _source_by_id("readhub_daily_digest")
    client = RoutingFixtureClient(
        responses={
            "https://readhub.cn/daily": _daily_html(),
            "https://readhub.cn/topic/8sReadhubA": _topic_html(
                topic_id="8sReadhubA",
                title="OpenAI 内部备忘录曝光",
                summary="Readhub topic 页面摘要 A",
                entity_names=["OpenAI", "Anthropic"],
                tags=["AI", "大模型"],
                news_title="OpenAI 相关媒体报道",
                news_url="https://36kr.com/p/10001",
                news_origin="36Kr",
            ),
            "https://readhub.cn/topic/8sReadhubB": _topic_html(
                topic_id="8sReadhubB",
                title="苹果折叠 iPhone 量产延后",
                summary="Readhub topic 页面摘要 B",
                entity_names=["苹果"],
                tags=["苹果", "硬件"],
                news_title="苹果折叠机进展",
                news_url="https://finance.sina.com.cn/p/20002",
                news_origin="新浪科技",
            ),
        },
        failing_urls={"https://1.readhub.cn/daily"},
    )
    collector = ReadhubDailyCollector(http_client=client)

    candidates = collector.collect(source)

    assert client.fetches[0] == "https://readhub.cn/daily"
    assert "https://1.readhub.cn/daily" in client.fetches
    assert len(candidates) == 2
    assert [candidate.candidate_url for candidate in candidates] == [
        "https://readhub.cn/topic/8sReadhubA",
        "https://readhub.cn/topic/8sReadhubB",
    ]
    assert candidates[0].candidate_type == "readhub_topic"
    assert candidates[0].candidate_title == "OpenAI 内部备忘录曝光"
    assert candidates[0].candidate_summary == "Readhub topic 页面摘要 A"
    assert candidates[0].candidate_published_at == "2026-04-14T03:00:00+00:00"
    assert candidates[0].candidate_entity_names == ("OpenAI", "Anthropic")
    assert candidates[0].needs_article_fetch is False
    assert candidates[0].source_context == {
        "source_family": "readhub_daily",
        "daily": {
            "canonical_url": "https://readhub.cn/daily",
            "issue_date": "2026-04-15",
            "rank": 1,
        },
        "topic": {
            "id": "8sReadhubA",
            "relative_date": "昨天",
            "tags": ["AI", "大模型"],
            "tracking": [
                {
                    "publish_date": "2026-04-14T03:00:00.000Z",
                    "title": "OpenAI 内部备忘录曝光",
                    "uid": "8sReadhubA",
                }
            ],
            "similar_events": [
                {
                    "name": "历史对比事件",
                    "time": "2024年4月",
                    "events": [
                        {
                            "title": "资产情况",
                            "content": "可用于对比的历史上下文",
                        }
                    ],
                }
            ],
            "news_links": [
                {
                    "site_name": "36Kr",
                    "title": "OpenAI 相关媒体报道",
                    "url": "https://36kr.com/p/10001",
                }
            ],
            "enrichment_status": "ok",
        },
    }
    assert len(collector.last_errors) == 1
    assert "https://1.readhub.cn/daily" in collector.last_errors[0]


def test_readhub_source_context_persists_through_normalizer_and_repository() -> None:
    source = _source_by_id("readhub_daily_digest")
    client = RoutingFixtureClient(
        responses={
            "https://readhub.cn/daily": _daily_html(),
            "https://readhub.cn/topic/8sReadhubA": _topic_html(
                topic_id="8sReadhubA",
                title="OpenAI 内部备忘录曝光",
                summary="Readhub topic 页面摘要 A",
                entity_names=["OpenAI", "Anthropic"],
                tags=["AI", "大模型"],
                news_title="OpenAI 相关媒体报道",
                news_url="https://36kr.com/p/10001",
                news_origin="36Kr",
            ),
            "https://readhub.cn/topic/8sReadhubB": _topic_html(
                topic_id="8sReadhubB",
                title="苹果折叠 iPhone 量产延后",
                summary="Readhub topic 页面摘要 B",
                entity_names=["苹果"],
                tags=["苹果", "硬件"],
                news_title="苹果折叠机进展",
                news_url="https://finance.sina.com.cn/p/20002",
                news_origin="新浪科技",
            ),
        },
    )
    collector = ReadhubDailyCollector(http_client=client)
    candidate = collector.collect(source)[0]

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = OvernightRepository(Database(Path(temp_dir) / "readhub.db"))
        normalized = normalize_candidate(candidate)
        stored = repo.persist_source_item(
            replace(
                normalized,
                raw_id=repo.create_raw_record(
                    source_id="readhub_daily_digest",
                    fetch_mode="source_capture_refresh",
                    payload_hash="readhub-topic-a",
                ),
            )
        )
        payload = repo.get_source_item_by_id(stored.id)

    assert stored.source_context["daily"]["issue_date"] == "2026-04-15"
    assert stored.source_context["daily"]["rank"] == 1
    assert stored.source_context["topic"]["tags"] == ["AI", "大模型"]
    assert [entity.name for entity in stored.entities] == ["OpenAI", "Anthropic"]
    assert payload is not None
    assert payload["source_context"]["topic"]["news_links"] == [
        {
            "site_name": "36Kr",
            "title": "OpenAI 相关媒体报道",
            "url": "https://36kr.com/p/10001",
        }
    ]
