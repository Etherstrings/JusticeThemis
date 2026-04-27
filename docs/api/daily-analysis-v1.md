# Daily Analysis API V1

> **Status:** This document describes the current implemented cross-market daily-analysis API. The live report shape is already result-first: `market_snapshot / asset_board -> mainlines -> direction_calls -> stock_calls`. See [2026-04-08-cross-market-overnight-intelligence-design.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/superpowers/specs/2026-04-08-cross-market-overnight-intelligence-design.md) and [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes the fixed daily analysis layer currently implemented in `JusticeThemis`.

The current implementation already supports:

- fixed daily report generation
- cached report retrieval
- free and premium tiers
- versioned regeneration
- simple premium access-key gating
- persisted U.S. market-close context with cross-asset `asset_board` when available
- ranked overnight `mainlines` derived from the market board plus clustered events
- prompt-bundle export for external model generation without mutating the fixed cached report

The current implementation does **not** yet call an external model provider inline during report generation. The default provider is the built-in deterministic rule engine: `rule_based`. For downstream model use, pair this document with [mmu-handoff-v1.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/api/mmu-handoff-v1.md).

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/analysis/daily/generate` | Generate and cache the fixed daily reports for one date |
| `GET /api/v1/analysis/daily` | Read the latest cached report for one date and tier |
| `GET /api/v1/analysis/daily/desk-report` | Read the result-first `desk_report` long-form product for one date and tier |
| `GET /api/v1/analysis/daily/group-report` | Read the result-first `group_report` sendable mid-long product for one date and tier |
| `GET /api/v1/analysis/daily/versions` | List cached versions for one date and tier |
| `GET /api/v1/analysis/daily/prompt` | Read a provider-agnostic prompt bundle based on the latest cached report |

## Product Semantics

- A daily report is fixed after generation.
- The system generates two reports for the same date:
  - `free`
  - `premium`
- Each cached daily report now derives two additional result-first products from the same fact base:
  - `desk_report`: a thick internal morning note that keeps all seven buckets and calls out data gaps directly
  - `group_report`: a sendable five-section mid-long note that still starts from market results rather than generic summary prose
- Regeneration creates a new `version` instead of overwriting the previous one.
- Read requests always return the latest version for that date and tier.
- The report is ordered around completed overnight results first, then ranked `mainlines`, then A-share direction/stock mappings.
- `stock_calls` are only allowed in `premium`, and they must inherit evidence from `direction_calls` and linked `mainlines` rather than appearing as standalone guesses.

## `POST /api/v1/analysis/daily/generate`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `analysis_date` | string or null | local server date | Target report date in `YYYY-MM-DD` format |

### Behavior

- The route builds reports from captured items whose `created_at` or `published_at` matches `analysis_date`.
- It always generates both `free` and `premium` reports in one call.
- Current provider metadata is returned in each generated report.
- This route now requires `X-Admin-Access-Key` unless `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`.

### Response Shape

```json
{
  "analysis_date": "2026-04-07",
  "reports": [
    {
      "analysis_date": "2026-04-07",
      "access_tier": "free",
      "version": 1,
      "generated_at": "2026-04-07T12:06:29",
      "provider": {
        "name": "rule_based",
        "model": null
      },
      "input_item_ids": [1, 2, 3],
      "summary": {},
      "market_snapshot": {},
      "mainlines": [],
      "narratives": {},
      "scoring_method": {},
      "input_snapshot": {},
      "direction_calls": [],
      "stock_calls": [],
      "risk_watchpoints": [],
      "supporting_items": []
    }
  ]
}
```

### Notes

- `stock_calls` is empty in the generated `free` report.
- `stock_calls` is populated in the generated `premium` report when a mapped direction exists.
- `mainlines` is present in both `free` and `premium` because both tiers share the same fact base and overnight ranking layer.

## `GET /api/v1/analysis/daily`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `analysis_date` | string or null | local server date | Target report date in `YYYY-MM-DD` format |
| `tier` | string | `free` | `free` or `premium` |
| `version` | integer or null | latest | Optional explicit report version |

### Headers

| Header | Required | Meaning |
| --- | --- | --- |
| `X-Premium-Access-Key` | only for `tier=premium` | Must match `OVERNIGHT_PREMIUM_API_KEY` |

### Success Response

```json
{
  "analysis_date": "2026-04-07",
  "access_tier": "free",
  "version": 2,
  "generated_at": "2026-04-07T12:06:29",
  "provider": {
    "name": "rule_based",
    "model": null
  },
  "input_item_ids": [1, 2, 3],
  "summary": {
    "report_type": "daily_fixed",
    "analysis_date": "2026-04-07",
    "headline": "偏多方向：银行/保险；承压方向：高估值成长链。",
    "core_view": "本日报告基于 3 条输入生成，其中官方源 2 条，媒体源 1 条。同时纳入了美股收盘快照。方向结论按固定公式聚合并缓存。",
    "confidence": "high"
  },
  "market_snapshot": {
    "analysis_date": "2026-04-07",
    "market_date": "2026-04-06",
    "session_name": "us_close",
    "headline": "标普500 +2.00%；纳指综指 +2.00%；VIX -10.00%；板块上 科技板块 领涨，能源板块 偏弱。"
  },
  "narratives": {
    "market_view": "2026-04-07 对应的美股收盘表现为 标普500 +2.00%；纳指综指 +2.00%；VIX -10.00%；新闻主线偏向 银行/保险；当前最明确的承压方向是 高估值成长链。",
    "policy_view": "官方层面的主导输入来自 Federal Reserve says inflation and rates may stay restrictive；U.S. trade data shows exports rose 12% as imports stabilized。",
    "sector_view": "偏多方向优先看 银行/保险；承压方向优先看 高估值成长链；成本/涨价链关注 原油/燃料油。",
    "risk_view": "确认后续 FOMC 路径和下一次通胀/就业数据；确认进口、出口和库存分项是否延续同方向变化；结合美元、运价和后续月度数据验证传导强度。",
    "execution_view": "当前官方输入 2 条，媒体补充 1 条。免费层只输出方向，不输出具体个股建议。"
  },
  "scoring_method": {
    "item_signal_formula": "signal_score = analysis_status + coverage_tier + a_share_relevance + analysis_confidence + priority_bonus + source_capture_confidence_bonus + cross_source_confirmation_bonus + timeliness_bonus - blocker_penalty - fact_conflict_penalty - staleness_penalty",
    "direction_aggregation": "Direction scores sum the strongest contributing item per event cluster, while preserving all supporting evidence item ids."
  },
  "input_snapshot": {
    "item_count": 3,
    "event_cluster_count": 3,
    "official_count": 2,
    "editorial_count": 1,
    "market_snapshot_available": true,
    "analysis_status_counts": {
      "ready": 2,
      "review": 1
    }
  },
  "direction_calls": [],
  "stock_calls": [],
  "risk_watchpoints": [],
  "supporting_items": []
}
```

### Errors

#### Missing Premium Key

```json
{
  "detail": "Premium access key required"
}
```

Status: `403`

#### Missing Cached Report

```json
{
  "detail": "Daily analysis not found"
}
```

Status: `404`

## `GET /api/v1/analysis/daily/group-report`

This endpoint returns the derived `group_report` object for the requested date/tier.

The object is JSON-first, and it also carries a ready-to-export `markdown` field.

Key contract:

- fixed section order:
  - `一句定盘`
  - `结果数据层`
  - `新闻/信息层`
  - `昨晚市场没认的消息`
  - `A股今天怎么打`
- result buckets keep the fixed seven-bucket ordering and omit empty buckets in the group version
- every result row is rendered as `方向词 + 具体数值`
- non-empty result buckets may carry an additive `texture` object; current first-stage coverage is `us_equities` and `china_proxy`
- `ignored_heat` is now matrix-shaped: it keeps backward-compatible `entries`, and also exposes `message_misses` plus `asset_misses`
- news buckets are now layered: they keep backward-compatible `entries`, and also expose `primary_entries` plus `background_entries`

## `GET /api/v1/analysis/daily/desk-report`

This endpoint returns the derived `desk_report` object for the requested date/tier.

The object is JSON-first, and it also carries a ready-to-export `markdown` field.

Key contract:

- keeps the same seven-bucket result ordering as the group product
- retains empty buckets and marks them as `当前没货` or `当前缺口`
- expands the news/explanation layer and adds explicit `归因层` and `数据缺口层`
- non-empty result buckets may carry an additive `texture` object; current first-stage coverage is `us_equities` and `china_proxy`
- `ignored_heat` is now matrix-shaped: it keeps backward-compatible `entries`, and also exposes `message_misses` plus `asset_misses`
- news buckets are now layered: they keep backward-compatible `entries`, and also expose `primary_entries` plus `background_entries`

## Field Semantics

### Top-Level Metadata

| Field | Meaning |
| --- | --- |
| `analysis_date` | The business/report date for the fixed report |
| `access_tier` | `free` or `premium` |
| `version` | Monotonic report version for the same date and tier |
| `generated_at` | Cache creation time for this version |
| `provider.name` | Current generator name. Today this is `rule_based`. |
| `provider.model` | Provider model identifier when available. Currently `null` for the rule engine. |
| `input_item_ids` | Captured item ids used to build this report version |
| `input_fingerprint` | Stable SHA-256 fingerprint of `input_item_ids` |
| `report_fingerprint` | Stable SHA-256 fingerprint of the stored report payload |
| `market_snapshot` | Optional persisted U.S. market-close context for the same `analysis_date`, including cross-asset groups and `asset_board` |
| `mainlines` | Ranked overnight mainlines built from completed market results plus event clusters |

### `summary`

| Field | Meaning |
| --- | --- |
| `report_type` | Current fixed value: `daily_fixed` |
| `headline` | Short report headline summarizing the strongest positive and negative direction |
| `core_view` | One-paragraph explanation of source mix and generation style |
| `confidence` | Daily-report level confidence, not per-direction confidence |

### `narratives`

This is the prose layer built on top of the structured output.

| Field | Meaning |
| --- | --- |
| `market_view` | Market-level daily interpretation |
| `policy_view` | Policy/data-focused summary |
| `sector_view` | Sector and direction summary |
| `risk_view` | Main watchpoints still needing confirmation |
| `execution_view` | How to use the report, including free/premium boundary |

## `GET /api/v1/analysis/daily/versions`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `analysis_date` | string or null | local server date | Target report date in `YYYY-MM-DD` format |
| `tier` | string | `free` | `free` or `premium` |

### Headers

| Header | Required | Meaning |
| --- | --- | --- |
| `X-Premium-Access-Key` | only for `tier=premium` | Must match `OVERNIGHT_PREMIUM_API_KEY` |

### Response Shape

```json
{
  "analysis_date": "2026-04-07",
  "access_tier": "free",
  "versions": [
    {
      "analysis_date": "2026-04-07",
      "access_tier": "free",
      "version": 2,
      "generated_at": "2026-04-07T12:40:00",
      "provider": {
        "name": "rule_based",
        "model": null
      },
      "input_item_ids": [1, 2, 3],
      "input_fingerprint": "sha256...",
      "report_fingerprint": "sha256...",
      "headline": "偏多方向：银行/保险；承压方向：高估值成长链。",
      "confidence": "high"
    }
  ]
}
```

### Semantics

- Versions are returned newest to oldest.
- This route is the audit entry point after manual regeneration.
- Use `version` from this route to fetch an old report or old prompt bundle.

### `scoring_method`

This section exists so the rule output is auditable.

- `item_signal_formula` explains how single-item importance is scored
- `direction_aggregation` explains how direction calls are aggregated from item scores after same-event deduplication

### `input_snapshot`

| Field | Meaning |
| --- | --- |
| `item_count` | Number of input items used for the report |
| `event_cluster_count` | Number of distinct event clusters represented in the input set |
| `official_count` | Items from `official_policy` or `official_data` |
| `editorial_count` | Items from `editorial_media` |
| `analysis_status_counts` | Count by `ready`, `review`, `background` |
| `market_snapshot_available` | Whether a persisted market snapshot was attached to this report |

### `market_snapshot`

When available, this block contains the same structured payload returned by `GET /api/v1/market/us/daily`.

Use it to show:

- previous U.S. session date
- major-index close behavior
- major sector proxy leadership
- volatility context
- rates, FX, precious metals, energy, and industrial-metals context
- China-facing futures watch rows under `china_mapped_futures`
- the normalized cross-asset `asset_board` object for model/UI reuse

### Result-First Bucket Texture

This is an additive field on result buckets inside `desk_report.result_data.buckets[]` and `group_report.result_data.buckets[]`.

Current notes:

- treat `texture` as optional
- first-stage guaranteed coverage only exists for `美股指数与板块` and `国内资产映射`
- markdown exporters may render it as one extra line: `盘面纹理：...`

| Field | Meaning |
| --- | --- |
| `texture.market_shape` | One of `普涨` / `普跌` / `结构分化` / `一般` |
| `texture.leaders` | Top rows that are clearly holding the bucket up |
| `texture.laggards` | Top rows that are clearly dragging the bucket down |
| `texture.texture_line` | One-line straight summary of the bucket's internal structure, suitable for markdown export |

### Desk Continuation Check

This is a desk-only additive block on `desk_report.continuation_check`.

Current notes:

- group report does not expose this block
- it reuses existing `china_mapped_futures` and `external_signal_panel` data
- if there is not enough watch data, it should explicitly say the continuation check has a gap instead of guessing

| Field | Meaning |
| --- | --- |
| `continuation_check.items[]` | Lightweight follow-through check for whether the overnight mainline has a usable post-close continuation signal |

### Ignored Heat Matrix

This is an additive field on `group_report.ignored_heat` and `desk_report.ignored_heat`.

Current notes:

- `entries` is retained for backward compatibility
- new consumers should prefer `message_misses` and `asset_misses`
- markdown exporters may render the same section as two blocks: `消息没认` and `资产没认`

| Field | Meaning |
| --- | --- |
| `ignored_heat.message_misses` | Hot public messages that did not make the strong evidence chain |
| `ignored_heat.asset_misses` | Cross-asset mismatches where the expected linked assets did not move together |
| `ignored_heat.entries` | Backward-compatible flattened list: `message_misses + asset_misses` |

Each `asset_misses[]` row includes the common `source / event / reason / line / related_buckets` fields and also exposes:

| Field | Meaning |
| --- | --- |
| `asset_misses[].strength` | Deterministic mismatch score used for ordering stronger observed dislocations first |
| `asset_misses[].observed_rows` | The concrete result rows used to form the mismatch line, preserving symbols, display names, direction words, and values |
| `asset_misses[].primary_context` | Primary-news context from the related result buckets, when available, so consumers can see which main-cause lines were checked against the price mismatch |
| `asset_misses[].conflict_check` | Deterministic status object explaining whether related primary-news context was available for the mismatch check |
| `asset_misses[].audit_line` | Desk-friendly audit sentence derived from `conflict_check`; desk markdown may render it, group markdown omits it to stay sendable |

### News Bucket Layering

This is an additive field on each bucket inside `group_report.news_layer.buckets[]` and `desk_report.news_layer.buckets[]`.

Current notes:

- `entries` is retained for backward compatibility
- new consumers should prefer `primary_entries` and `background_entries`
- markdown exporters may render the same bucket as two blocks: `主因` and `背景`

| Field | Meaning |
| --- | --- |
| `news_layer.buckets[].primary_entries` | The strongest same-bucket entries that directly explain the price result |
| `news_layer.buckets[].background_entries` | Same-topic but weaker supporting context that should not overwrite the main cause |
| `news_layer.buckets[].entries` | Backward-compatible flattened list: `primary_entries + background_entries` |

Each `background_entries[]` row keeps the normal news-entry fields and may also expose:

| Field | Meaning |
| --- | --- |
| `background_entries[].background_reason` | Deterministic reason explaining why the entry was kept as background instead of primary cause |
| `background_entries[].event_cluster_overlap` | Cluster comparison against the strongest primary entry, including `entry_cluster_id`, `primary_cluster_id`, `same_cluster`, and `shared_topic_tags` |

### `mainlines`

Each mainline is the ranked overnight theme layer above raw items and below A-share direction/stock mappings.

| Field | Meaning |
| --- | --- |
| `mainline_id` | Stable overnight mainline id |
| `mainline_bucket` | Deterministic theme bucket such as `rates_liquidity` or `tech_semiconductor` |
| `headline` | Concise Chinese mainline headline |
| `importance_rank` | Rank within the overnight session, lower is more important |
| `importance_score` | Deterministic score used for ordering |
| `confidence` | `high`, `medium`, or `low` |
| `linked_event_ids` | Event cluster ids supporting this mainline |
| `affected_assets` | Cross-asset instruments or mapped China-facing directions touched by this mainline |
| `evidence_count` | Supporting-event count used to build the mainline |
| `summary` | Short Chinese explanation of the mainline |

### `direction_calls`

Each direction call contains:

| Field | Meaning |
| --- | --- |
| `signal_type` | `beneficiary`, `pressured`, or `price_up` |
| `direction` | Aggregated A-share direction label |
| `stance` | `positive`, `negative`, or `inflationary` |
| `score` | Aggregated direction score |
| `confidence` | `high`, `medium`, or `low` |
| `evidence_item_ids` | Supporting item ids |
| `source_ids` | Supporting source ids |
| `source_mix` | Count of distinct official vs editorial supporting sources |
| `supporting_titles` | Top supporting titles |
| `evidence_points` | Aggregated evidence snippets from supporting items |
| `evidence_mainline_ids` | Ranked mainline ids that this direction inherits from |
| `follow_up_checks` | Aggregated direction-level watchpoints |
| `event_cluster_count` | Number of event clusters contributing to this direction |
| `event_cluster_ids` | Event-cluster ids contributing to this direction |
| `confirmed_item_count` | Contributing items with cross-source corroboration |
| `conflicted_item_count` | Contributing items carrying fact conflicts |
| `rationale` | Human-readable explanation of why this direction exists |

### `stock_calls`

Only meaningful in the `premium` report.

Each stock call contains:

| Field | Meaning |
| --- | --- |
| `ticker` | Mapped A-share ticker |
| `name` | Stock display name |
| `direction` | Source direction that triggered the mapping |
| `stance` | Usually `positive` or `negative` |
| `confidence` | Inherits the direction-call confidence |
| `action` | Current machine label such as `buy_watchlist` or `avoid_or_reduce` |
| `action_label` | Human-readable action label |
| `mapping_basis` | Current fixed value: `direction_proxy` |
| `evidence_item_ids` | Supporting item ids |
| `linked_mainline_ids` | Mainline ids carried through from the source direction call |
| `reason` | Human-readable reason explaining the mapping |

### `risk_watchpoints`

- Flattened and deduplicated follow-up checks from the supporting items
- Use these as “still needs confirmation” bullets in UI

### `supporting_items`

This is the audited fact layer behind the daily conclusion.

Each item keeps:

- source identity
- title
- rule-derived `signal_score`
- `signal_score_breakdown`
- `timeliness`
- `source_capture_confidence`
- `cross_source_confirmation`
- `fact_conflicts`
- `event_cluster`
- `llm_ready_brief`
- impact outline
- direction lists
- follow-up checks
- `evidence_points`

Frontend or downstream AI should prefer this section when showing “why the conclusion was made”.

If a downstream model also needs source-level capture trust or reconciliation context, pair the fixed report with `GET /handoff` or `GET /api/v1/news/{item_id}`. Those routes expose richer item fields such as:

- `source_capture_confidence`
- `cross_source_confirmation`
- `fact_conflicts`
- `event_cluster`
- `llm_ready_brief`

## `GET /api/v1/analysis/daily/prompt`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `analysis_date` | string or null | local server date | Target report date in `YYYY-MM-DD` format |
| `tier` | string | `free` | `free` or `premium` |
| `version` | integer or null | latest | Optional explicit report version |

### Headers

| Header | Required | Meaning |
| --- | --- | --- |
| `X-Premium-Access-Key` | only for `tier=premium` | Must match `OVERNIGHT_PREMIUM_API_KEY` |

### Response Shape

```json
{
  "analysis_date": "2026-04-07",
  "access_tier": "free",
  "report_version": 1,
  "provider_target": "external_llm_ready",
  "input_item_ids": [1, 2, 3],
  "source_audit_pack": {
    "included_item_count": 3,
    "input_item_count": 3,
    "omitted_input_item_count": 0,
    "event_group_count": 2,
    "official_item_ids": [1, 2],
    "supporting_items": [],
    "event_groups": [],
    "field_priority": []
  },
  "messages": [
    {
      "role": "system",
      "content": "..."
    },
    {
      "role": "user",
      "content": "..."
    }
  ]
}
```

### Semantics

- This route does not call an external model.
- It packages the cached fixed report into provider-agnostic messages.
- If `version` is omitted, it uses the latest report version.
- If `version` is provided, it uses that exact cached version.
- `tier=free` forbids stock-specific buy/sell advice in the system prompt.
- `tier=premium` allows stock mappings, but still requires evidence and risk disclosure.
- the user message now also includes `market_snapshot` so downstream models can combine price action with captured news.
- the response now also includes `source_audit_pack`, a compact source-evidence bundle derived from `supporting_items`.
- `source_audit_pack.event_groups` groups those supporting items by `event_cluster`, so an external model can reason at event level before reading individual items.
- `/handoff` is still the richer full-pool route, but the prompt bundle no longer requires a second request just to access supporting source evidence.

### `source_audit_pack`

This is the compact raw-evidence layer packaged alongside the prompt.

| Field | Meaning |
| --- | --- |
| `included_item_count` | Number of supporting items embedded into the prompt bundle |
| `input_item_count` | Full report input size before compacting to the supporting set |
| `omitted_input_item_count` | Input items not embedded into the compact evidence pack |
| `event_group_count` | Number of grouped event clusters represented in the compact pack |
| `official_item_ids` | Embedded supporting item ids from official-policy or official-data sources |
| `supporting_items` | The same audited supporting items included in the fixed report |
| `event_groups` | Compact event-level grouping built from the embedded supporting items |
| `field_priority` | Suggested reading order for source-audit fields inside each supporting item |

## Empty-State Behavior

If no report has been generated for the requested date and tier:

- `GET /api/v1/analysis/daily` returns `404`

If a report is generated from an empty input set:

- the route still returns a valid fixed report
- `summary.headline` explicitly states there was no usable input
- `direction_calls`, `stock_calls`, and `supporting_items` are empty arrays

## Environment Variables

| Variable | Meaning |
| --- | --- |
| `OVERNIGHT_PREMIUM_API_KEY` | Required to read `tier=premium` reports |
| `OVERNIGHT_ADMIN_API_KEY` | Required to call `POST /api/v1/analysis/daily/generate` in safe mode |
| `OVERNIGHT_ALLOW_UNSAFE_ADMIN` | Local-only override that disables admin auth for mutation routes |

## Current Limitations

- The current provider is deterministic and local. It does not yet call an external LLM.
- Premium stock calls are currently proxy mappings from direction labels to a curated stock map.
- The report input set is determined by `created_at`/`published_at` date matching, not by a separate trading-session table.
- The prompt bundle is generated from the latest cached report, and `source_audit_pack` is a compact subset rather than the full recent source pool.
- If no U.S. market snapshot has been captured yet, the report still generates successfully and `market_snapshot` is `{}`.
