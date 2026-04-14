# Frontend V1 Integration

> **Status:** This document describes the current implemented frontend-facing API for the cross-market morning overview. The dashboard already exposes `market_board` and ranked `mainlines` directly, so frontend should consume those backend objects instead of rebuilding the logic client-side. See [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes the current frontend-facing read API implemented in `JusticeThemis`.

It is intentionally limited to the new presentation layer:

- `GET /api/v1/dashboard`
- `GET /api/v1/news`
- `GET /api/v1/news/{item_id}`
- `GET /api/v1/sources`

The older endpoints remain available and unchanged:

- `GET /items`
- `POST /refresh`
- `GET /handoff`
- `GET /healthz`
- `GET /readyz`

Auth note for the older operator surfaces:

- `POST /refresh` requires `X-Admin-Access-Key` unless `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`
- `GET /readyz` requires `X-Admin-Access-Key` unless `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`
- the built-in `/ui` operator page stores the admin key locally in the browser and sends it only for refresh actions

Related machine-facing market endpoints:

- `POST /api/v1/market/us/refresh`
- `GET /api/v1/market/us/daily`

## Integration Summary

| Endpoint | Purpose | Notes |
| --- | --- | --- |
| `GET /api/v1/dashboard` | Home/dashboard payload for the morning overview | Splits items into `lead_signals`, `watchlist`, `background`, adds `market_board` + ranked `mainlines`, and applies light source-diversity caps in the dashboard buckets |
| `GET /api/v1/news` | Full list view with filters, search, pool-mode switching, and pagination | Default sort is `ready` first, then `review`, then `background`; supports `pool_mode=current|full` |
| `GET /api/v1/news/{item_id}` | Full detail for one item | Returns `404` if the item id does not exist |
| `GET /api/v1/sources` | Source registry + recent activity summary | Includes sources with zero recent items |

## Base Assumptions

- Public read routes remain unauthenticated.
- Premium read routes require `X-Premium-Access-Key`.
- Admin mutation and readiness-detail routes require `X-Admin-Access-Key`, unless the server is explicitly running with `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`.
- All responses are JSON.
- `generated_at` is the API render time, not the last refresh time.
- Empty datasets are valid and return `200` with empty arrays and zero counts.
- Frontend should treat `item_id` and `source_id` as the stable identifiers.

## Handoff Compatibility Notes

- `GET /handoff` remains available for downstream-model use and now emits `event_groups` built from the wider recent pool before top-level `items` truncation.
- This means a handoff `event_group.items` array can contain valid cluster members that are not present in the truncated top-level `items` list for the same response.
- `trade_policy` topic tags are intentionally reserved for policy-action coverage such as tariffs, sanctions, export controls, procurement actions, or USTR-linked updates. Bare macro trade-data stories should not be interpreted as policy actions from the word `trade` alone.

## Shared News Item Shape

The same `NewsItem` object is reused in:

- `dashboard.lead_signals`
- `dashboard.watchlist`
- `dashboard.background`
- `news.items`
- `detail.item`

| Field | Type | Meaning |
| --- | --- | --- |
| `item_id` | integer | Stable database id for the captured item |
| `source_id` | string | Stable machine id for the source |
| `source_name` | string | Human-readable source name |
| `canonical_url` | string | Canonical article/document URL |
| `title` | string | Normalized title |
| `summary` | string | Normalized summary/excerpt text |
| `excerpt_source` | string | Provenance of the summary extraction, for example `body_selector:main` |
| `excerpt_char_count` | integer | Character count of `summary` |
| `capture_path` | string | Capture route: `direct` or `search_discovery` |
| `capture_provider` | string or null | Search provider name when the item came from search fallback, otherwise `null` |
| `article_fetch_status` | string | Article-body expansion status: `not_attempted`, `expanded`, or `expand_failed` |
| `capture_provenance` | object | Compact capture provenance block for UI badges and downstream-model audit |
| `document_type` | string | Normalized document category such as `press_release`, `fact_sheet`, `news_article`, `calendar_release` |
| `source_class` | string | Source family such as `policy`, `macro`, `market`, `calendar` |
| `coverage_tier` | string | `official_policy`, `official_data`, or `editorial_media` |
| `organization_type` | string | Registry-level organization bucket such as `official_policy`, `official_data`, `editorial_media`, `wire_media` |
| `priority` | integer | Registry priority used in sorting |
| `is_mission_critical` | boolean | Whether the source is marked as mission-critical in the registry |
| `region_focus` | string | Short region label from the source registry |
| `coverage_focus` | string | Human-readable description of why the source is tracked |
| `published_at` | string or null | Published time from the source when available |
| `published_at_source` | string | Provenance of `published_at`, for example `rss:published` or `section:time` |
| `published_at_precision` | string | `datetime`, `date`, or `missing` |
| `published_at_display` | string or null | Frontend/model-friendly time display. Datetime values are normalized to China time when timezone info exists |
| `source_authority` | string | Deterministic source weight label such as `primary_official` or `editorial_context` |
| `entities` | array | Extracted entity mentions |
| `numeric_facts` | array | Extracted numeric facts. Current deterministic coverage includes percentages, basis points, USD amounts, and job counts. Decimal values keep subject inference intact when the nearby clause contains the subject label. |
| `content_metrics` | object | Lightweight content counters for completeness checks |
| `content_completeness` | string | Deterministic completeness label: `high`, `medium`, `low` |
| `body_detail_level` | string | `detailed`, `summary`, or `brief` based on excerpt basis and summary richness |
| `source_time_reliability` | string | Deterministic time-trust label: `high`, `medium`, `low` |
| `source_integrity` | object | Registry-domain validation block for the canonical URL |
| `timeliness` | object | Deterministic freshness block based on published time versus capture time |
| `data_quality_flags` | array of strings | Deterministic quality warnings such as source-domain mismatch or missing published time |
| `source_capture_confidence` | object | Deterministic capture-confidence block combining source authority, time quality, content completeness, corroboration, and penalties |
| `summary_quality` | string | `high`, `medium`, or `low` based on excerpt basis and summary length |
| `a_share_relevance` | string | Deterministic relevance label: `high`, `medium`, `low` |
| `a_share_relevance_reason` | string | Human-readable explanation for the relevance label |
| `evidence_points` | array of strings | Fact-like evidence snippets extracted from the normalized summary. Duplicate USD evidence is suppressed when the summary already contains shorthand values such as `$57.3B` or `$1.2T`. |
| `impact_summary` | string | Deterministic summary of why the item matters |
| `why_it_matters_cn` | string | Chinese explanation of why the item matters right now |
| `key_numbers` | array | Flattened numeric-fact view for direct UI/model use |
| `fact_table` | array | Ordered fact list that mixes sentence facts and numeric facts for direct model consumption |
| `cross_source_confirmation` | object | Deterministic corroboration block built from the recent comparison pool |
| `fact_conflicts` | array | Structured cross-source conflict rows, currently numeric mismatches and direction mismatches |
| `event_cluster` | object | Deterministic event-level grouping block that ties same-event coverage across multiple sources into one cluster |
| `policy_actions` | array of strings | Deterministic policy-action summary labels |
| `market_implications` | array | Structured implication rows derived from beneficiary/pressured/price-up mappings |
| `uncertainties` | array of strings | Structured uncertainty/watch rows, usually aligned with `follow_up_checks` |
| `llm_ready_brief` | string | Compact one-line expert/model handoff summary for the item |
| `beneficiary_directions` | array of strings | Potential A-share beneficiary directions |
| `pressured_directions` | array of strings | Potential pressured directions |
| `price_up_signals` | array of strings | Potential price-up/cost-push directions |
| `follow_up_checks` | array of strings | Things that still need confirmation before turning into stronger judgments |
| `analysis_status` | string | `ready`, `review`, or `background` |
| `analysis_confidence` | string | `high`, `medium`, or `low` |
| `analysis_blockers` | array of strings | Deterministic blocker flags such as `editorial_context_only` |
| `created_at` | string or null | Capture/persistence time from the local database |
| `family_id` | integer or null | Document family id when assigned |
| `family_key` | string or null | Document family key when assigned |
| `family_type` | string or null | Document family type when assigned |
| `version_id` | integer or null | Document version id when assigned |

### `entities` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Canonical entity name |
| `entity_type` | string | Entity type, currently deterministic |
| `matched_text` | string | Exact text match from the source text |

### `numeric_facts` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `metric` | string | Deterministic metric name |
| `value` | number | Parsed numeric value |
| `unit` | string | Unit such as `percent`, `basis_points`, `usd`, or `jobs` |
| `context` | string | Extracted context snippet |
| `subject` | string or null | Optional subject inference, for example tariff subject |

### `content_metrics` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `summary_sentence_count` | integer | Simple sentence-count estimate for the normalized summary |
| `evidence_point_count` | integer | Number of derived `evidence_points` |
| `numeric_fact_count` | integer | Number of extracted numeric facts |
| `entity_count` | integer | Number of extracted entities |

### `key_numbers` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `metric` | string | Deterministic metric name |
| `value` | number | Raw numeric value |
| `value_text` | string | Display-ready numeric value such as `25.0%`, `25 bp`, `$57.3B`, or `271,000` |
| `unit` | string | Unit such as `percent`, `basis_points`, `usd`, or `jobs` |
| `subject` | string or null | Optional inferred subject |

### `fact_table` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `fact_type` | string | `sentence` or `numeric` |
| `text` | string | Display/model-ready fact string |
| `metric` | string or null | Present for `numeric` rows |
| `value` | number or null | Present for `numeric` rows |
| `value_text` | string or null | Present for `numeric` rows |
| `unit` | string or null | Present for `numeric` rows |
| `subject` | string or null | Present for `numeric` rows |

### `source_capture_confidence` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `level` | string | `high`, `medium`, or `low` |
| `score` | integer | Deterministic `0..100` capture-confidence score |
| `reasons` | array of strings | Main positive reasons, for example official-source status or reliable time metadata |
| `penalties` | array of strings | Main negative factors such as blockers or cross-source conflicts |

### `capture_provenance` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `capture_path` | string | `direct` or `search_discovery` |
| `is_search_fallback` | boolean | `true` when the item entered through the search-discovery supplement path |
| `search_provider` | string or null | Normalized provider id such as `tavily`; `null` for direct captures |
| `article_fetch_status` | string | `not_attempted`, `expanded`, or `expand_failed` |

### `source_integrity` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `hostname` | string | Parsed hostname from `canonical_url` |
| `domain_status` | string | `verified`, `mismatch`, `missing`, or `unknown` |
| `matched_domain` | string or null | Matched registry domain when verified |
| `allowed_domains` | array of strings | Registry domains considered valid for the source |
| `is_https` | boolean | Whether the canonical URL uses HTTPS |
| `https_required` | boolean | Registry policy for HTTPS enforcement |
| `url_valid` | boolean | Final deterministic URL-integrity result used by the capture layer |

### `timeliness` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `anchor_time` | string or null | Capture-anchor time used for freshness calculations |
| `age_hours` | number or null | Hours between publish time and capture anchor |
| `publication_lag_minutes` | integer or null | Capture delay in minutes when precise publish time exists |
| `freshness_bucket` | string | `breaking`, `overnight`, `recent`, `stale`, or `undated` |
| `is_timely` | boolean | Whether the item is still considered timely by the current rules |
| `timeliness_flags` | array of strings | Timeliness warnings such as `stale_publication` or `delayed_capture` |

### `cross_source_confirmation` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `level` | string | `strong`, `moderate`, or `single_source` |
| `supporting_source_count` | integer | Number of distinct corroborating sources |
| `confirmed_by_item_ids` | array of integers | Supporting item ids from the comparison pool |
| `confirmed_by_sources` | array | Structured corroborating-source rows |
| `shared_topics` | array of strings | Shared deterministic topic tags such as `trade_policy`. `trade_policy` is policy-action oriented and should not be treated as a generic macro-trade label. |
| `shared_directions` | array of strings | Shared derived A-share direction labels |

### `confirmed_by_sources` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `item_id` | integer | Supporting item id |
| `source_id` | string | Supporting source id |
| `source_name` | string | Supporting source display name |
| `match_basis` | array of strings | Deterministic corroboration reasons such as `topic:trade_policy` or `numeric:tariff_rate:steel` |

### `market_implications` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `implication_type` | string | `beneficiary`, `pressured`, or `price_up` |
| `direction` | string | Derived A-share direction label |
| `stance` | string | `positive`, `negative`, or `inflationary` |

### `fact_conflicts` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `conflict_type` | string | `numeric_mismatch` or `direction_mismatch` |
| `metric` | string | Conflict dimension such as `tariff_rate` or `market_direction` |
| `subject` | string or null | Optional metric subject or conflicted direction |
| `current_value_text` | string | Current item's display-ready value |
| `other_value_text` | string | Other item's conflicting display-ready value |
| `other_item_id` | integer | Conflicting supporting item id |
| `other_source_id` | string | Conflicting source id |
| `other_source_name` | string | Conflicting source display name |

### `event_cluster` Object

| Field | Type | Meaning |
| --- | --- | --- |
| `cluster_id` | string | Deterministic event-cluster id, suitable for UI grouping or downstream model dedup |
| `cluster_status` | string | `single_source`, `confirmed`, or `conflicted` |
| `primary_item_id` | integer | Preferred lead item inside the cluster, usually the most authoritative member |
| `item_count` | integer | Total item count inside this event cluster |
| `source_count` | integer | Distinct source count inside this event cluster |
| `official_source_count` | integer | Distinct official-source count inside this event cluster |
| `member_item_ids` | array of integers | Ordered cluster member item ids |
| `member_source_ids` | array of strings | Ordered cluster member source ids |
| `latest_published_at` | string or null | Latest source publish time across the cluster |
| `topic_tags` | array of strings | Deterministic topic tags summarizing the cluster. `trade_policy` is reserved for trade-policy actions rather than generic trade-data headlines. |
| `fact_signatures` | array of strings | Deterministic metric signatures such as `tariff_rate:steel` |

## `GET /api/v1/dashboard`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `bucket_limit` | integer | `5` | Max items returned in each dashboard section. Values below `1` are coerced to `1`. |

### Response Shape

```json
{
  "generated_at": "2026-04-07T18:31:12",
  "hero": {
    "total_items": 5,
    "ready_count": 2,
    "review_count": 2,
    "background_count": 1,
    "official_count": 3,
    "editorial_count": 2
  },
  "lead_signals": [],
  "watchlist": [],
  "background": [],
  "source_health": {
    "total_sources": 18,
    "active_sources": 5,
    "inactive_sources": 13,
    "sources": []
  },
  "market_board": {},
  "mainlines": []
}
```

### Semantics

- `lead_signals` contains items where `analysis_status == "ready"`.
- `watchlist` contains items where `analysis_status == "review"`.
- `background` contains items where `analysis_status == "background"`.
- `lead_signals` applies a per-source cap of `1`, so one outlet cannot flood the primary signal rail.
- `watchlist` and `background` apply a softer per-source cap of `2`, preserving variety while still keeping stronger sources near the top.
- `source_health` is recent activity coverage, not a polling heartbeat.
- `source_health.sources` contains only the top `bucket_limit` source summary rows.
- `market_board` reuses the persisted `asset_board` object from `GET /api/v1/market/us/daily` when a market snapshot exists; otherwise it is `{}`.
- `mainlines` comes from the latest cached `free` daily report for the same `analysis_date` as the attached market snapshot; otherwise it is `[]`.

### Rendering Guidance

- Use `hero` for top-line counters.
- Use `lead_signals` as the primary actionable morning list.
- Use `watchlist` as the “needs review / cannot fully trust yet” column.
- Use `background` for contextual or lower-confidence overnight flow.
- Use `source_health` for a compact source coverage panel, not as a detailed grid.
- Use `market_board` as the first screenful summary of overnight cross-asset results.
- Use `mainlines` as the ranked theme rail beneath the market board instead of inferring themes from raw headlines in the browser.
- Use `source_integrity`, `data_quality_flags`, `source_capture_confidence`, `cross_source_confirmation`, and `fact_conflicts` together for trust badges instead of relying on `analysis_status` alone.
- Use `event_cluster.cluster_id` to collapse duplicate same-event coverage in dense list views, while keeping the individual source rows available for audit.
- Only subject-bearing numeric facts currently participate in cross-source numeric confirmation/conflict. Generic amounts without a stable subject stay display-only by design.

## `GET /api/v1/news`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `tab` | string | `all` | Supported values with behavior: `all`, `signals`, `watchlist`, `other` |
| `analysis_status` | string or null | `null` | Exact filter: `ready`, `review`, `background` |
| `coverage_tier` | string or null | `null` | Exact filter: `official_policy`, `official_data`, `editorial_media` |
| `source_id` | string or null | `null` | Exact source filter |
| `q` | string or null | `null` | Case-insensitive substring search across `title`, `summary`, `source_name`, `impact_summary` |
| `pool_mode` | string | `current` | `current` uses only the current actionable window; `full` exposes the broader recent pool including stale recaptures |
| `limit` | integer | `20` | Clamped to `1..50` |
| `cursor` | integer | `0` | Offset-based cursor. Negative values are coerced to `0`. |

### `tab` Behavior

| `tab` | Included Items |
| --- | --- |
| `all` | No extra tab filter |
| `signals` | `analysis_status == "ready"` |
| `watchlist` | `analysis_status == "review"` |
| `other` | `analysis_status == "background"` or `coverage_tier == "editorial_media"` |

Unsupported tab values are currently treated the same as `all`. Frontend should still send only supported values.

### Response Shape

```json
{
  "generated_at": "2026-04-07T18:31:12",
  "pool_mode": "current",
  "current_window_total": 5,
  "full_pool_total": 7,
  "total": 5,
  "returned": 3,
  "limit": 3,
  "next_cursor": "3",
  "filters": {
    "tab": "all",
    "analysis_status": null,
    "coverage_tier": null,
    "source_id": null,
    "q": null,
    "pool_mode": "current"
  },
  "items": []
}
```

### Sorting

Default ordering is:

1. `analysis_status`: `ready` before `review` before `background`
2. `coverage_tier`: `official_policy` before `official_data` before `editorial_media`
3. `a_share_relevance`: `high` before `medium` before `low`
4. `published_at`: newer first
5. `priority`: higher first
6. `created_at`: newer first
7. `item_id`: higher first

### Pool Mode Guidance

- `pool_mode=current` is the default UI mode for China-morning reading.
- `pool_mode=full` is the better choice for a “see everything we captured” screen, audit view, or analyst drill-down page.
- `current_window_total` and `full_pool_total` are returned together so frontend can show how much content is currently actionable versus how much was captured overall.

### Pagination Notes

- `cursor` is an offset, not an opaque token.
- `next_cursor` is returned as a string for the next offset or `null` when there is no next page.
- Because new rows can arrive between requests, cursor pagination is not snapshot-stable.

### Rendering Guidance

- Use `/api/v1/news` for the full-page stream or table view.
- Use `tab=other` to expose “other news” without hiding editorial items that are still `review`.
- Use `analysis_status` and `analysis_blockers` together for trust badges and warning states.
- Use `llm_ready_brief` as the compact export line when sending selected items to an external model.
- Use `event_cluster` when the UI needs an “event view” above the raw article view.

## `GET /api/v1/news/{item_id}`

### Path Param

| Param | Type | Meaning |
| --- | --- | --- |
| `item_id` | integer | Captured item id |

### Success Response

```json
{
  "generated_at": "2026-04-07T18:31:12",
  "item": {}
}
```

### Not Found

```json
{
  "detail": "News item not found"
}
```

### Usage Guidance

- Detail payload returns the full shared `NewsItem` object.
- Frontend does not need to re-fetch source metadata separately.
- Use this route for side panels, drawers, or full detail pages.
- Use `confirmed_by_sources` and `fact_conflicts` when the product needs a source-audit drawer or expert reconciliation panel.
- Use `event_cluster.member_item_ids` to render a same-event drawer or “related coverage” module without a second clustering pass in the frontend.

## `GET /api/v1/sources`

### Query Params

This route currently has no query params.

### Response Shape

```json
{
  "generated_at": "2026-04-07T18:31:12",
  "total_sources": 13,
  "active_sources": 5,
  "inactive_sources": 8,
  "sources": []
}
```

### Source Summary Row

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | Stable source id |
| `source_name` | string | Human-readable source name |
| `coverage_tier` | string | `official_policy`, `official_data`, `editorial_media` |
| `source_group` | string | Content grouping such as `official_policy`, `commodity_data`, or `market_media` |
| `source_tier` | string | Registry source tier such as `P0`, `P1`, `P2` |
| `content_mode` | string | Main content mode such as `policy`, `rates`, `energy`, `market` |
| `asset_tags` | array of strings | Asset buckets this source commonly informs |
| `mainline_tags` | array of strings | Mainline buckets this source commonly feeds |
| `organization_type` | string | Registry organization bucket |
| `source_class` | string | `policy`, `macro`, `market`, `calendar` |
| `entry_type` | string | Collector type such as `rss`, `section_page`, `calendar_page` |
| `priority` | integer | Registry priority |
| `poll_interval_seconds` | integer | Registry poll hint |
| `is_mission_critical` | boolean | Registry criticality flag |
| `search_discovery_enabled` | boolean | Whether this source is allowed to use search supplementation when direct capture is empty/thin |
| `search_query_count` | integer | Count of configured fallback queries for this source |
| `region_focus` | string | Registry region label |
| `coverage_focus` | string | Registry coverage description |
| `item_count` | integer | Recent item count in the current bounded pool |
| `ready_count` | integer | Recent `ready` count |
| `review_count` | integer | Recent `review` count |
| `background_count` | integer | Recent `background` count |
| `latest_item_id` | integer or null | Most recent item id for the source |
| `latest_title` | string or null | Most recent item title |
| `latest_published_at` | string or null | Most recent source publish time |
| `latest_analysis_status` | string or null | Most recent item status |
| `latest_a_share_relevance` | string or null | Most recent relevance label |
| `latest_freshness_bucket` | string or null | Latest item's freshness bucket |
| `latest_is_timely` | boolean or null | Latest item's timeliness boolean |
| `latest_publication_lag_minutes` | integer or null | Latest item's capture delay in minutes |
| `freshness_status` | string | Source-level freshness summary: `fresh`, `watch`, `delayed`, `stale`, or `inactive` |

### Semantics

- All configured sources are returned, including sources with `item_count == 0`.
- `active_sources` means “has at least one item in the recent pool”.
- `search_discovery_enabled` is registry metadata, not a claim that fallback was used recently.
- `search_query_count` lets frontend show which official sources have explicit fallback search coverage configured.
- This is the correct route for building a source coverage page or registry sidebar.

## Empty-State Contract

When the local SQLite database has zero captured rows, the real current implementation returns:

- `dashboard.hero` counts all `0`
- `dashboard.lead_signals`, `dashboard.watchlist`, `dashboard.background` as empty arrays
- `dashboard.market_board == {}`
- `dashboard.mainlines == []`
- `news.total == 0`, `news.returned == 0`, `news.items == []`
- `sources.total_sources == 18`, `sources.active_sources == 0`, and every source row has zero counts with `latest_* == null`

Frontend should explicitly handle this state instead of assuming refresh has already run.

## Recommended Frontend Composition

- Dashboard page:
  - `/api/v1/dashboard`
- Full stream page:
  - `/api/v1/news`
- “Other news” drawer or tab:
  - `/api/v1/news?tab=other`
- Item drill-down:
  - `/api/v1/news/{item_id}`
- Source coverage page:
  - `/api/v1/sources`
