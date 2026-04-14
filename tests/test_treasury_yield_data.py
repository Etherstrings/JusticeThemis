# -*- coding: utf-8 -*-
"""Tests for official Treasury 10Y yield adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from app.services.treasury_yield_data import TreasuryYieldClient


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None


class _StaticSession:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    def get(self, url: str, *, timeout: float, headers: dict[str, str]) -> _FakeResponse:
        del timeout, headers
        self.urls.append(url)
        return _FakeResponse(self.html)


def test_treasury_yield_client_builds_chart_payload_from_latest_two_rows() -> None:
    html = """
    <html>
      <body>
        <table>
          <tbody>
            <tr>
              <td class="views-field views-field-field-tdr-date"><time datetime="2026-04-08T12:00:00Z">04/08/2026</time></td>
              <td class="views-field views-field-field-bc-10year">4.26</td>
            </tr>
            <tr>
              <td class="views-field views-field-field-tdr-date"><time datetime="2026-04-07T12:00:00Z">04/07/2026</time></td>
              <td class="views-field views-field-field-bc-10year">4.32</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    session = _StaticSession(html)
    client = TreasuryYieldClient(
        session=session,
        now_fn=lambda: datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(client.fetch_chart("^TNX"))
    result = payload["chart"]["result"][0]

    assert session.urls
    assert "field_tdr_date_value=2026" in session.urls[0]
    assert result["meta"]["symbol"] == "^TNX"
    assert result["meta"]["regularMarketPrice"] == 4.26
    assert result["meta"]["chartPreviousClose"] == 4.32
    assert result["indicators"]["quote"][0]["close"] == [4.32, 4.26]
    assert result["timestamp"][0] < result["timestamp"][1]


def test_treasury_yield_client_uses_latest_two_rows_even_if_table_is_oldest_first() -> None:
    html = """
    <html>
      <body>
        <table>
          <tbody>
            <tr>
              <td class="views-field views-field-field-tdr-date"><time datetime="2026-04-06T12:00:00Z">04/06/2026</time></td>
              <td class="views-field views-field-field-bc-10year">4.32</td>
            </tr>
            <tr>
              <td class="views-field views-field-field-tdr-date"><time datetime="2026-04-07T12:00:00Z">04/07/2026</time></td>
              <td class="views-field views-field-field-bc-10year">4.26</td>
            </tr>
            <tr>
              <td class="views-field views-field-field-tdr-date"><time datetime="2026-04-08T12:00:00Z">04/08/2026</time></td>
              <td class="views-field views-field-field-bc-10year">4.20</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    session = _StaticSession(html)
    client = TreasuryYieldClient(
        session=session,
        now_fn=lambda: datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(client.fetch_chart("^TNX"))
    result = payload["chart"]["result"][0]

    assert result["meta"]["regularMarketPrice"] == 4.20
    assert result["meta"]["chartPreviousClose"] == 4.26
    assert result["indicators"]["quote"][0]["close"] == [4.26, 4.20]
    assert result["timestamp"][0] < result["timestamp"][1]


def test_treasury_yield_client_rejects_unsupported_symbols() -> None:
    client = TreasuryYieldClient(
        session=_StaticSession("<html></html>"),
        now_fn=lambda: datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
    )

    try:
        client.fetch_chart("ALI=F")
    except RuntimeError as exc:
        assert "does not support" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected unsupported-symbol error")
