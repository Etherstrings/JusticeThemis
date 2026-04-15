# -*- coding: utf-8 -*-
"""Tests for Readhub validation/report helpers."""

from __future__ import annotations

import requests

from app.collectors.readhub import ReadhubDailyCollector
from app.live_validation import collect_readhub_capture_validation_report
from app.sources.registry import build_default_source_registry
from app.sources.types import SourceDefinition


class RoutingFixtureClient:
    def __init__(self, responses: dict[str, str], failing_urls: set[str] | None = None) -> None:
        self.responses = responses
        self.failing_urls = set(failing_urls or set())

    def fetch(self, url: str) -> str:
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
        <div><span>2026.04.15</span></div>
        <script>
          self.__next_f.push([1,"10:[\\"$\\",\\"$L23\\",null,{\\"articles\\":[
            {\\"id\\":\\"8sReadhubA\\",\\"title\\":\\"OpenAI 内部备忘录曝光\\",\\"summary\\":\\"摘要 A\\",\\"entityList\\":[{\\"name\\":\\"OpenAI\\"}]},
            {\\"id\\":\\"8sReadhubB\\",\\"title\\":\\"苹果折叠 iPhone 量产延后\\",\\"summary\\":\\"摘要 B\\",\\"entityList\\":[{\\"name\\":\\"苹果\\"}]}
          ]}]\\n"]);
        </script>
      </body>
    </html>
    """


def _topic_html(topic_id: str, title: str, tag_name: str, news_origin: str, news_url: str) -> str:
    return f"""
    <html>
      <body>
        <script>
          self.__next_f.push([1,"11:[\\"$\\",\\"$L25\\",null,{{\\"initialState\\":{{\\"id\\":\\"{topic_id}\\",\\"title\\":\\"{title}\\",\\"summary\\":\\"topic summary\\",\\"relativeDate\\":\\"昨天\\",\\"entityList\\":[{{\\"name\\":\\"{title.split(' ')[0]}\\"}}],\\"tagList\\":[{{\\"name\\":\\"{tag_name}\\"}}],\\"trackingList\\":[{{\\"publishDate\\":\\"2026-04-14T03:00:00.000Z\\",\\"title\\":\\"{title}\\",\\"uid\\":\\"{topic_id}\\"}}],\\"similarEventList\\":[{{\\"name\\":\\"相似事件\\",\\"time\\":\\"2024年\\",\\"events\\":[{{\\"title\\":\\"背景\\",\\"content\\":\\"背景说明\\"}}]}}],\\"newsList\\":[{{\\"siteNameDisplay\\":\\"{news_origin}\\",\\"title\\":\\"样例报道\\",\\"url\\":\\"{news_url}\\"}}],\\"stockReleaseList\\":[]}},\\"children\\":\\"$L27\\"}}]\\n"]);
        </script>
      </body>
    </html>
    """


def test_collect_readhub_capture_validation_report_shows_counts_urls_and_enrichment_visibility() -> None:
    source = _source_by_id("readhub_daily_digest")
    collector = ReadhubDailyCollector(
        http_client=RoutingFixtureClient(
            responses={
                "https://readhub.cn/daily": _daily_html(),
                "https://readhub.cn/topic/8sReadhubA": _topic_html(
                    "8sReadhubA",
                    "OpenAI 内部备忘录曝光",
                    "AI",
                    "36Kr",
                    "https://36kr.com/p/10001",
                ),
                "https://readhub.cn/topic/8sReadhubB": _topic_html(
                    "8sReadhubB",
                    "苹果折叠 iPhone 量产延后",
                    "苹果",
                    "新浪科技",
                    "https://finance.sina.com.cn/p/20002",
                ),
            },
            failing_urls={"https://1.readhub.cn/daily"},
        )
    )

    report = collect_readhub_capture_validation_report(collector=collector, source=source)

    assert report["status"] == "ok"
    assert report["source_id"] == "readhub_daily_digest"
    assert report["daily_issue_date"] == "2026-04-15"
    assert report["daily_item_count"] == 2
    assert report["sample_topic_urls"] == [
        "https://readhub.cn/topic/8sReadhubA",
        "https://readhub.cn/topic/8sReadhubB",
    ]
    assert report["enrichment_populated_count"] == 2
    assert report["enrichment_visibility"] == {
        "tag_count": 2,
        "tracking_count": 2,
        "similar_event_count": 2,
        "news_link_count": 2,
    }
    assert report["legacy_alias_probe_errors"] == [
        "legacy_alias_probe_failed: https://1.readhub.cn/daily | SSL connect error for url: https://1.readhub.cn/daily"
    ]
