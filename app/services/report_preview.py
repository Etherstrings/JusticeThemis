# -*- coding: utf-8 -*-
"""Standalone HTML preview renderer for fixed daily analysis reports."""

from __future__ import annotations

from datetime import datetime
import html
from typing import Any


def render_daily_report_preview_html(
    report: dict[str, Any],
    *,
    source_markdown_path: str = "",
    generated_at: str | None = None,
) -> str:
    payload = dict(report or {})
    analysis_date = _text(payload.get("analysis_date")) or "Unknown Date"
    access_tier = _text(payload.get("access_tier")) or "free"
    summary = _summary_payload(payload.get("summary"))
    narratives = dict(payload.get("narratives", {}) or {})
    input_snapshot = dict(payload.get("input_snapshot", {}) or {})
    market_snapshot = dict(payload.get("market_snapshot", {}) or {})
    asset_board = dict(market_snapshot.get("asset_board", {}) or {})
    mainlines = [item for item in list(payload.get("mainlines", []) or []) if isinstance(item, dict)]
    market_regimes = [item for item in list(payload.get("market_regimes", []) or []) if isinstance(item, dict)]
    secondary_event_groups = [
        item for item in list(payload.get("secondary_event_groups", []) or []) if isinstance(item, dict)
    ]
    direction_calls = [item for item in list(payload.get("direction_calls", []) or []) if isinstance(item, dict)]
    headline_news = [
        item
        for item in list(payload.get("headline_news", []) or payload.get("supporting_items", []) or [])
        if isinstance(item, dict)
    ][:8]
    stock_calls = [item for item in list(payload.get("stock_calls", []) or []) if isinstance(item, dict)]
    risk_watchpoints = [_text(item) for item in list(payload.get("risk_watchpoints", []) or []) if _text(item)]
    render_generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    page_title = f"JusticeThemis Daily Report Preview | {analysis_date} | {access_tier}"

    hero_metrics = [
        ("Inputs", str(int(input_snapshot.get("item_count", 0) or 0))),
        ("Official", str(int(input_snapshot.get("official_count", 0) or 0))),
        ("Editorial", str(int(input_snapshot.get("editorial_count", 0) or 0))),
        ("Directions", str(len(direction_calls))),
    ]

    narrative_blocks = [
        ("Market View", _text(narratives.get("market_view"))),
        ("Policy View", _text(narratives.get("policy_view"))),
        ("Sector View", _text(narratives.get("sector_view"))),
        ("Risk View", _text(narratives.get("risk_view"))),
    ]
    narrative_blocks = [(label, value) for label, value in narrative_blocks if value]

    market_headline = _text(asset_board.get("headline")) or _text(market_snapshot.get("headline"))
    source_note = ""
    if source_markdown_path:
        source_note = (
            f'<div class="artifact-note"><span>Source Artifact</span>'
            f"<code>{_escape(source_markdown_path)}</code></div>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape(page_title)}</title>
    <style>
      :root {{
        --paper: #f5ecdf;
        --paper-strong: #fffaf2;
        --ink: #162437;
        --ink-soft: rgba(22, 36, 55, 0.74);
        --line: rgba(22, 36, 55, 0.12);
        --shadow: 0 24px 50px rgba(20, 30, 44, 0.12);
        --accent: #b3542b;
        --accent-soft: rgba(179, 84, 43, 0.12);
        --navy: #20354d;
        --positive: #245741;
        --positive-soft: rgba(36, 87, 65, 0.11);
        --negative: #7b2f2f;
        --negative-soft: rgba(123, 47, 47, 0.1);
        --inflationary: #8a641d;
        --inflationary-soft: rgba(138, 100, 29, 0.12);
        --neutral-soft: rgba(32, 53, 77, 0.08);
        --title-font: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
        --body-font: "Avenir Next", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        --mono-font: "SFMono-Regular", "Menlo", "Monaco", monospace;
      }}

      * {{
        box-sizing: border-box;
      }}

      html, body {{
        margin: 0;
        min-height: 100%;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(179, 84, 43, 0.16), transparent 30%),
          radial-gradient(circle at 100% 10%, rgba(32, 53, 77, 0.14), transparent 26%),
          linear-gradient(180deg, #f8f1e6 0%, #f1e6d7 100%);
        font-family: var(--body-font);
      }}

      body {{
        padding: 28px;
      }}

      .page {{
        max-width: 1380px;
        margin: 0 auto;
      }}

      .hero {{
        display: grid;
        grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.85fr);
        gap: 24px;
        margin-bottom: 24px;
      }}

      .hero-card,
      .panel,
      .rail-card,
      .direction-card,
      .news-card,
      .stock-row,
      .artifact-note {{
        border: 1px solid var(--line);
        background: rgba(255, 250, 242, 0.9);
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
      }}

      .hero-card {{
        padding: 32px;
        border-radius: 28px 28px 72px 28px;
      }}

      .hero-card.dark {{
        padding: 24px;
        border-radius: 24px;
        background:
          linear-gradient(160deg, rgba(22, 36, 55, 0.97), rgba(29, 49, 72, 0.94)),
          linear-gradient(160deg, rgba(179, 84, 43, 0.08), transparent);
        color: #f7f1e7;
      }}

      .eyebrow,
      .section-kicker,
      .mini-label {{
        margin: 0;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        font-size: 11px;
      }}

      .eyebrow,
      .section-kicker {{
        color: #b28a43;
      }}

      .mini-label {{
        color: rgba(247, 241, 231, 0.62);
      }}

      h1,
      h2,
      h3,
      h4 {{
        margin: 0;
        font-family: var(--title-font);
        font-weight: 700;
        line-height: 0.98;
      }}

      h1 {{
        margin-top: 14px;
        font-size: clamp(3rem, 6vw, 5.8rem);
        max-width: 10ch;
      }}

      h2 {{
        font-size: clamp(1.8rem, 2.8vw, 2.6rem);
      }}

      h3 {{
        font-size: 1.35rem;
      }}

      p {{
        margin: 0;
      }}

      .hero-headline {{
        margin-top: 18px;
        max-width: 17ch;
      }}

      .hero-summary {{
        margin-top: 18px;
        max-width: 70ch;
        line-height: 1.7;
        color: var(--ink-soft);
      }}

      .hero-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 22px;
      }}

      .pill {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 999px;
        background: rgba(22, 36, 55, 0.06);
        border: 1px solid rgba(22, 36, 55, 0.08);
        font-size: 0.9rem;
      }}

      .tier-pill {{
        background: linear-gradient(135deg, rgba(179, 84, 43, 0.16), rgba(178, 138, 67, 0.18));
      }}

      .hero-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 18px;
      }}

      .metric {{
        padding: 14px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.08);
      }}

      .metric strong {{
        display: block;
        margin-top: 8px;
        font-size: 1.8rem;
        font-family: var(--title-font);
      }}

      .layout {{
        display: grid;
        grid-template-columns: minmax(0, 1.28fr) minmax(300px, 0.72fr);
        gap: 24px;
      }}

      .stack {{
        display: grid;
        gap: 22px;
      }}

      .panel,
      .rail-card {{
        padding: 24px;
        border-radius: 24px;
      }}

      .panel-header {{
        display: flex;
        justify-content: space-between;
        gap: 14px;
        align-items: end;
        margin-bottom: 18px;
      }}

      .panel-note {{
        max-width: 32ch;
        color: var(--ink-soft);
        line-height: 1.6;
        font-size: 0.95rem;
      }}

      .section-nav {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}

      .section-nav a {{
        text-decoration: none;
        color: inherit;
        padding: 9px 12px;
        border-radius: 999px;
        background: rgba(22, 36, 55, 0.05);
        border: 1px solid rgba(22, 36, 55, 0.08);
        font-size: 0.86rem;
      }}

      .summary-copy {{
        display: grid;
        gap: 14px;
        line-height: 1.75;
      }}

      .summary-copy .headline {{
        font-size: 1.2rem;
        font-weight: 700;
      }}

      .summary-copy .confidence {{
        display: inline-flex;
        width: fit-content;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(22, 36, 55, 0.06);
        border: 1px solid rgba(22, 36, 55, 0.08);
        font-size: 0.9rem;
      }}

      .direction-grid,
      .news-grid {{
        display: grid;
        gap: 14px;
      }}

      .direction-grid {{
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      }}

      .direction-card,
      .news-card,
      .stock-row {{
        padding: 18px;
        border-radius: 20px;
      }}

      .direction-card.positive {{
        background: linear-gradient(180deg, rgba(36, 87, 65, 0.12), rgba(255, 250, 242, 0.92));
      }}

      .direction-card.negative {{
        background: linear-gradient(180deg, rgba(123, 47, 47, 0.11), rgba(255, 250, 242, 0.92));
      }}

      .direction-card.inflationary {{
        background: linear-gradient(180deg, rgba(138, 100, 29, 0.13), rgba(255, 250, 242, 0.92));
      }}

      .stance-row,
      .news-meta,
      .stock-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 10px;
      }}

      .chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(22, 36, 55, 0.08);
        font-size: 0.78rem;
        background: rgba(255, 255, 255, 0.72);
      }}

      .direction-card p,
      .news-card p,
      .stock-row p,
      .rail-copy {{
        line-height: 1.66;
        color: var(--ink-soft);
      }}

      .evidence-list,
      .watch-list,
      .rail-list,
      .list-reset {{
        list-style: none;
        padding: 0;
        margin: 0;
      }}

      .evidence-list,
      .watch-list,
      .rail-list {{
        display: grid;
        gap: 10px;
        margin-top: 14px;
      }}

      .evidence-list li,
      .watch-list li,
      .rail-list li {{
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(22, 36, 55, 0.05);
      }}

      .news-grid {{
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }}

      .news-card h3,
      .stock-row h3 {{
        margin-bottom: 10px;
      }}

      .stock-stack,
      .rail-stack {{
        display: grid;
        gap: 14px;
      }}

      .artifact-note {{
        margin-top: 14px;
        padding: 14px 16px;
        border-radius: 18px;
      }}

      .artifact-note span {{
        display: block;
        margin-bottom: 6px;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: var(--ink-soft);
      }}

      code {{
        font-family: var(--mono-font);
        font-size: 0.84rem;
        word-break: break-all;
      }}

      .rail-kv {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}

      .rail-kv div {{
        padding: 12px;
        border-radius: 16px;
        background: rgba(22, 36, 55, 0.05);
      }}

      .rail-kv strong {{
        display: block;
        font-family: var(--title-font);
        font-size: 1.2rem;
      }}

      .footer-note {{
        margin-top: 24px;
        padding: 18px 22px;
        border-radius: 20px;
        background: rgba(22, 36, 55, 0.06);
        color: var(--ink-soft);
        line-height: 1.65;
      }}

      @media (max-width: 1024px) {{
        body {{
          padding: 18px;
        }}

        .hero,
        .layout {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <header class="hero">
        <section class="hero-card">
          <p class="eyebrow">JusticeThemis Report Preview</p>
          <h1 class="hero-headline">Daily Analysis</h1>
          <p class="hero-summary">{_escape(summary["headline"] or "Fixed daily analysis report preview.")}</p>
          <div class="hero-meta">
            <span class="pill">{_escape(analysis_date)}</span>
            <span class="pill tier-pill">{_escape(access_tier.title())} Tier</span>
            <span class="pill">Confidence: {_escape(summary["confidence"] or "n/a")}</span>
          </div>
          <div class="section-nav" style="margin-top: 18px;">
            <a href="#summary">Summary</a>
            <a href="#directions">Direction Calls</a>
            <a href="#news">Key News</a>
            <a href="#stocks">Stock Calls</a>
            <a href="#risk">Risk Watchpoints</a>
          </div>
          {source_note}
        </section>

        <section class="hero-card dark">
          <p class="mini-label">Run Snapshot</p>
          <h2 style="margin-top: 12px;">{_escape(market_headline or "Report overview ready for browser preview.")}</h2>
          <div class="hero-grid">
            {_render_metric_tiles(hero_metrics)}
          </div>
          <p class="panel-note" style="margin-top: 16px; color: rgba(247, 241, 231, 0.74);">
            Generated at { _escape(render_generated_at) } from the persisted daily analysis payload.
          </p>
        </section>
      </header>

      <div class="layout">
        <main class="stack">
          <section class="panel" id="summary">
            <div class="panel-header">
              <div>
                <p class="section-kicker">Overview</p>
                <h2>Summary</h2>
              </div>
              <p class="panel-note">This page renders the structured report directly instead of skinning raw Markdown.</p>
            </div>
            <div class="summary-copy">
              <p class="headline">{_escape(summary["headline"] or "No headline available.")}</p>
              {_paragraph(summary["core_view"])}
              {_paragraph(_text(narratives.get("execution_view")))}
              <span class="confidence">Confidence: {_escape(summary["confidence"] or "n/a")}</span>
            </div>
          </section>

          <section class="panel" id="directions">
            <div class="panel-header">
              <div>
                <p class="section-kicker">Signal Layer</p>
                <h2>Direction Calls</h2>
              </div>
              <p class="panel-note">Positive, inflationary, and pressured directions stay separated so the trade-off is visible.</p>
            </div>
            <div class="direction-grid">
              {_render_direction_cards(direction_calls)}
            </div>
          </section>

          <section class="panel" id="news">
            <div class="panel-header">
              <div>
                <p class="section-kicker">Evidence Layer</p>
                <h2>Key News</h2>
              </div>
              <p class="panel-note">Top supporting items are shown as the human-readable evidence spine for the report.</p>
            </div>
            <div class="news-grid">
              {_render_news_cards(headline_news)}
            </div>
          </section>

          <section class="panel" id="stocks">
            <div class="panel-header">
              <div>
                <p class="section-kicker">China Mapping</p>
                <h2>Stock Calls</h2>
              </div>
              <p class="panel-note">Premium tier exposes the mapped A-share ideas and keeps the reason visible on every row.</p>
            </div>
            <div class="stock-stack">
              {_render_stock_rows(stock_calls)}
            </div>
          </section>
        </main>

        <aside class="stack">
          <section class="rail-card">
            <div class="panel-header" style="margin-bottom: 14px;">
              <div>
                <p class="section-kicker">Narratives</p>
                <h2>Desk Readout</h2>
              </div>
            </div>
            <ul class="rail-list">
              {_render_narrative_blocks(narrative_blocks)}
            </ul>
          </section>

          <section class="rail-card">
            <div class="panel-header" style="margin-bottom: 14px;">
              <div>
                <p class="section-kicker">Structure</p>
                <h2>Input Snapshot</h2>
              </div>
            </div>
            <div class="rail-kv">
              {_render_snapshot_tiles(input_snapshot)}
            </div>
          </section>

          <section class="rail-card">
            <div class="panel-header" style="margin-bottom: 14px;">
              <div>
                <p class="section-kicker">Machine View</p>
                <h2>Mainlines & Regimes</h2>
              </div>
            </div>
            <div class="rail-stack">
              {_render_named_list("Mainlines", mainlines, "headline")}
              {_render_named_list("Market Regimes", market_regimes, "regime_key")}
              {_render_named_list("Secondary Events", secondary_event_groups, "headline")}
            </div>
          </section>

          <section class="rail-card" id="risk">
            <div class="panel-header" style="margin-bottom: 14px;">
              <div>
                <p class="section-kicker">Risk Control</p>
                <h2>Risk Watchpoints</h2>
              </div>
            </div>
            <ul class="watch-list">
              {_render_watchpoints(risk_watchpoints)}
            </ul>
          </section>
        </aside>
      </div>

      <div class="footer-note">
        This preview is meant to answer a simple product question: what does the user actually see when a real backend run finishes.
        It uses the persisted structured report as the single source of truth and keeps the report date, tier, and evidence spine visible.
      </div>
    </div>
  </body>
</html>
"""


def _render_metric_tiles(items: list[tuple[str, str]]) -> str:
    rendered: list[str] = []
    for label, value in items:
        rendered.append(
            "<div class=\"metric\">"
            f"<span class=\"mini-label\">{_escape(label)}</span>"
            f"<strong>{_escape(value)}</strong>"
            "</div>"
        )
    return "".join(rendered)


def _render_direction_cards(direction_calls: list[dict[str, Any]]) -> str:
    if not direction_calls:
        return "<article class=\"direction-card\"><p>No direction calls.</p></article>"

    rendered: list[str] = []
    for item in direction_calls:
        direction = _text(item.get("direction")) or "Unnamed direction"
        stance = _text(item.get("stance")) or "neutral"
        confidence = _text(item.get("confidence")) or "n/a"
        rationale = _text(item.get("rationale"))
        evidence_points = [_text(value) for value in list(item.get("evidence_points", []) or []) if _text(value)]
        evidence_html = "".join(f"<li>{_escape(value)}</li>" for value in evidence_points[:3]) or "<li>No evidence points.</li>"
        rendered.append(
            f"<article class=\"direction-card { _escape(stance.lower()) }\">"
            "<div class=\"stance-row\">"
            f"<span class=\"chip\">{_escape(stance)}</span>"
            f"<span class=\"chip\">Confidence: {_escape(confidence)}</span>"
            "</div>"
            f"<h3>{_escape(direction)}</h3>"
            f"{_paragraph(rationale or 'No rationale available.')}"
            f"<ul class=\"evidence-list\">{evidence_html}</ul>"
            "</article>"
        )
    return "".join(rendered)


def _render_news_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<article class=\"news-card\"><p>No key news.</p></article>"

    rendered: list[str] = []
    for item in items:
        source_name = _text(item.get("source_name")) or _text(item.get("source_id")) or "Unknown source"
        title = _text(item.get("title")) or "Untitled item"
        impact_summary = _text(item.get("llm_ready_brief")) or _text(item.get("impact_summary"))
        evidence_points = [_text(value) for value in list(item.get("evidence_points", []) or []) if _text(value)]
        follow_up_checks = [_text(value) for value in list(item.get("follow_up_checks", []) or []) if _text(value)]
        rendered.append(
            "<article class=\"news-card\">"
            "<div class=\"news-meta\">"
            f"<span class=\"chip\">{_escape(source_name)}</span>"
            f"<span class=\"chip\">item_id={_escape(str(item.get('item_id', '')))}</span>"
            "</div>"
            f"<h3>{_escape(title)}</h3>"
            f"{_paragraph(impact_summary or 'No brief available.')}"
            f"<ul class=\"evidence-list\">{''.join(f'<li>{_escape(value)}</li>' for value in (evidence_points[:2] or follow_up_checks[:2] or ['No evidence excerpt.']))}</ul>"
            "</article>"
        )
    return "".join(rendered)


def _render_stock_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<article class=\"stock-row\"><p>No stock calls.</p></article>"

    rendered: list[str] = []
    for item in items:
        ticker = _text(item.get("ticker")) or "-"
        name = _text(item.get("name")) or "Unnamed"
        action_label = _text(item.get("action_label")) or "Watch"
        reason = _text(item.get("reason")) or "No reason provided."
        rendered.append(
            "<article class=\"stock-row\">"
            "<div class=\"stock-meta\">"
            f"<span class=\"chip\">{_escape(ticker)}</span>"
            f"<span class=\"chip\">{_escape(action_label)}</span>"
            "</div>"
            f"<h3>{_escape(name)}</h3>"
            f"{_paragraph(reason)}"
            "</article>"
        )
    return "".join(rendered)


def _render_narrative_blocks(items: list[tuple[str, str]]) -> str:
    if not items:
        return "<li>No narrative blocks.</li>"
    return "".join(
        "<li>"
        f"<strong>{_escape(label)}</strong>"
        f"<p class=\"rail-copy\" style=\"margin-top: 8px;\">{_escape(value)}</p>"
        "</li>"
        for label, value in items
    )


def _render_snapshot_tiles(snapshot: dict[str, Any]) -> str:
    fields = [
        ("Items", str(int(snapshot.get("item_count", 0) or 0))),
        ("Clusters", str(int(snapshot.get("event_cluster_count", 0) or 0))),
        ("Ready", str(int(dict(snapshot.get("analysis_status_counts", {}) or {}).get("ready", 0) or 0))),
        ("Review", str(int(dict(snapshot.get("analysis_status_counts", {}) or {}).get("review", 0) or 0))),
        ("Background", str(int(dict(snapshot.get("analysis_status_counts", {}) or {}).get("background", 0) or 0))),
        ("Market", "yes" if bool(snapshot.get("market_snapshot_available")) else "no"),
    ]
    return "".join(
        "<div>"
        f"<span>{_escape(label)}</span>"
        f"<strong>{_escape(value)}</strong>"
        "</div>"
        for label, value in fields
    )


def _render_named_list(section_title: str, items: list[dict[str, Any]], primary_field: str) -> str:
    if not items:
        return (
            "<article class=\"stock-row\">"
            f"<div class=\"stock-meta\"><span class=\"chip\">{_escape(section_title)}</span></div>"
            "<p>No entries.</p>"
            "</article>"
        )

    rows: list[str] = []
    for item in items[:3]:
        label = _text(item.get(primary_field)) or _text(item.get("headline")) or _text(item.get("mainline_bucket")) or "Entry"
        rows.append(
            "<li>"
            f"<strong>{_escape(label)}</strong>"
            f"<p class=\"rail-copy\" style=\"margin-top: 6px;\">{_escape(_secondary_descriptor(item))}</p>"
            "</li>"
        )
    return (
        "<article class=\"stock-row\">"
        f"<div class=\"stock-meta\"><span class=\"chip\">{_escape(section_title)}</span></div>"
        f"<ul class=\"rail-list\">{''.join(rows)}</ul>"
        "</article>"
    )


def _render_watchpoints(items: list[str]) -> str:
    if not items:
        return "<li>No risk watchpoints.</li>"
    return "".join(f"<li>{_escape(item)}</li>" for item in items)


def _summary_payload(summary: Any) -> dict[str, str]:
    if isinstance(summary, dict):
        return {
            "headline": _text(summary.get("headline")),
            "core_view": _text(summary.get("core_view")),
            "confidence": _text(summary.get("confidence")),
        }
    return {
        "headline": _text(summary),
        "core_view": "",
        "confidence": "",
    }


def _secondary_descriptor(item: dict[str, Any]) -> str:
    for field in ("downgrade_reason", "mainline_bucket", "confidence", "strength"):
        value = _text(item.get(field))
        if value:
            return value
    return "Structured report entry."


def _paragraph(value: str) -> str:
    if not value:
        return ""
    return f"<p>{_escape(value)}</p>"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
