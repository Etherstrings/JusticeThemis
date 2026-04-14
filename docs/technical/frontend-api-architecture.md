# Frontend API Architecture

> **Status:** This document describes the current item-centric frontend API implementation. The target read layer will become result-first and cross-market as described in [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes how the frontend-facing `v1` API is implemented today.

It is strictly about the current code path, not a future-state design.

## Why This Layer Exists

The project already had two working read surfaces:

- `/items`: recent captured items in storage order
- `/handoff`: official-first package for downstream model reasoning
- `/api/v1/market/us/daily`: persisted U.S. market-close snapshot for China-morning analysis

Those routes are useful, but neither is a clean frontend contract:

- `/items` is capture-centric, not dashboard-centric
- `/handoff` is prompt-package-centric, not UI-centric; it now also carries `market_snapshot` and `handoff_outline`
- `/api/v1/market/us/daily` is machine-context-centric, not news-list-centric

The `v1` frontend API adds a thin presentation layer that:

- reshapes the existing rendered item model into dashboard/list/detail/source-summary responses
- keeps capture and handoff behavior unchanged
- gives frontend code explicit sections for `ready`, `review`, `background`, and “other news”

## Runtime Boundaries

### 1. Storage

`app/db.py`

- bootstraps SQLite tables
- stores raw records, normalized items, document families, document versions

`app/repository.py`

- persists normalized items
- lists recent rows
- fetches a single row by `item_id`
- returns row payloads that still need presentation rendering

### 2. Capture/Item Rendering

`app/services/source_capture.py`

- existing capture pipeline
- still owns the deterministic item rendering logic:
  - `published_at_precision`
  - `published_at_display`
  - `source_authority`
  - `content_metrics`
  - `content_completeness`
  - `body_detail_level`
  - `source_time_reliability`
  - `source_integrity`
  - `timeliness`
  - `data_quality_flags`
  - `source_capture_confidence`
  - `key_numbers`
  - `fact_table`
  - `cross_source_confirmation`
  - `fact_conflicts`
  - `event_cluster`
  - `policy_actions`
  - `market_implications`
  - `uncertainties`
  - `llm_ready_brief`
  - `why_it_matters_cn`
  - source metadata lookup
  - `summary_quality`
  - `a_share_relevance`
  - `evidence_points`
  - `impact_summary`
  - `beneficiary_directions`
  - `pressured_directions`
  - `price_up_signals`
  - `follow_up_checks`
  - `analysis_status`
  - `analysis_confidence`
  - `analysis_blockers`

Important detail:

- these analysis-oriented fields are derived at read time, not stored as columns
- if the heuristics in relevance/impact/guardrails/evidence change, historical items will render with the new deterministic logic
- this now includes formatting-oriented fields, not only judgment-oriented fields
- numeric extraction now covers more than `%` values; the current deterministic set includes percentages, basis points, USD amounts, and job counts
- decimal-aware clause splitting preserves subject inference for values such as `$57.3 billion`, `12.5 basis points`, and `25.0%`
- corroboration/conflict fields are derived in a second pass over a recent comparison pool, not from a separate materialized table
- event-level grouping is also derived in that second pass and exposed as `event_cluster`
- source-origin integrity is checked against registry allowlisted domains; refresh-time persistence drops candidates whose canonical URL falls outside the source's allowed domain set

Comparison-pool rules:

- list-style reads compare each requested item against `max(30, limit * 3)` recent items, capped at `100`
- detail reads also load a recent comparison pool so trust/conflict fields stay aligned with list rendering
- event clustering currently uses deterministic shared-topic, shared-fact, and identity-keyword rules
- generic overlap such as bare `trade`, generic `deficit`, or process words like `review` and `widened` is intentionally not enough to define one event
- `trade_policy` tagging is restricted to policy-action coverage; macro trade-data headlines should not inherit that tag from the bare word `trade`
- only compare-ready numeric facts enter cross-source numeric matching; the current rule is conservative and prefers facts with a stable subject label
- corroboration and conflict matching are then constrained to candidates inside the same `event_cluster`
- conflict rows currently capture numeric mismatches and direction mismatches across sources

### Handoff Packaging

`app/services/handoff.py`

- reorders rendered items for downstream model use
- carries `market_snapshot`
- now also emits `handoff_outline`
- now also emits `event_groups`
- `event_groups` are built from the wider sorted pool before top-level `items` truncation, so cluster members may exist only inside `event_groups`

`handoff_outline` exists to reduce prompt drift in downstream models by making the reading order explicit:

- which item ids should be read first
- which event clusters should be read first
- which items are official vs editorial
- which items are watch/background
- which fields should be trusted first inside each item

The current preferred item-field order is:

1. `published_at_display`
2. `published_at_precision`
3. `source_authority`
4. `source_integrity`
5. `content_metrics`
6. `source_time_reliability`
7. `data_quality_flags`
8. `timeliness`
9. `body_detail_level`
10. `source_capture_confidence`
11. `key_numbers`
12. `fact_table`
13. `cross_source_confirmation`
14. `fact_conflicts`
15. `event_cluster`
16. `policy_actions`
17. `market_implications`
18. `uncertainties`
19. `llm_ready_brief`
20. `why_it_matters_cn`
21. `evidence_points`
22. `impact_summary`

Evidence-formatting rule:

- when a summary already contains a USD shorthand such as `$57.3B` or `$1.2T`, `evidence_points` should not add a duplicate numeric line that restates the same fact

### 3. Frontend Presentation Layer

`app/services/frontend_api.py`

- reads already-rendered items from the capture service
- sorts, filters, groups, paginates, and summarizes them
- does not refetch source pages
- does not recompute normalization
- does not mutate stored data

### 4. Delivery Layer

`app/main.py`

- wires the new routes
- keeps `/items`, `/refresh`, and `/handoff` intact

## Why `main.py` Instantiates A Separate Presentation Capture Service

`create_app()` now creates:

- the existing `capture_service` used by `/items`, `/refresh`, and `/handoff`
- a separate `FrontendApiService` that uses a presentation-only `OvernightSourceCaptureService`

The presentation-only capture service is initialized with `build_default_source_registry()` instead of the active-refresh subset.

This is deliberate:

- refresh behavior should remain limited to the hardened active source set
- frontend rendering and `/api/v1/sources` should still know about the full configured registry
- detail views should resolve source metadata even for sources that are configured but not in the active refresh subset

## Data Flow

### `GET /api/v1/dashboard`

1. `FrontendApiService.get_dashboard()`
2. loads a recent pool through `capture_service.list_recent_items(limit=200)`
3. sorts the pool
4. filters to the current actionable window
5. splits items by `analysis_status`
6. applies light source-diversity caps in dashboard buckets
   - `lead_signals`: max `1` item per `source_id`
   - `watchlist`: max `2` items per `source_id`
   - `background`: max `2` items per `source_id`
5. derives top-line counts
6. calls `list_sources()` for recent source coverage
7. returns dashboard sections plus a compact source summary

### `GET /api/v1/news`

1. `FrontendApiService.list_news()`
2. loads both:
   - a bounded `current` pool
   - a bounded `full` pool
3. chooses one pool based on `pool_mode`
4. applies tab/status/tier/source/search filters in memory
5. applies offset pagination
6. returns the filtered page plus `next_cursor`, `pool_mode`, `current_window_total`, and `full_pool_total`

### `GET /api/v1/news/{item_id}`

1. repository fetch by id
2. capture service renders the single row into the shared `NewsItem` shape
3. capture rendering also loads a recent comparison pool so corroboration/conflict fields are available in detail views
4. route returns `404` if no row exists

### `GET /api/v1/sources`

1. `FrontendApiService.list_sources()`
2. loads the recent rendered pool
3. groups items by `source_id`
4. merges group counts into the full configured registry
5. returns every configured source, active or inactive

## Sorting Rules

The default news sort key is:

1. `analysis_status`
   - `ready`
   - `review`
   - `background`
2. `coverage_tier`
   - `official_policy`
   - `official_data`
   - `editorial_media`
3. `a_share_relevance`
   - `high`
   - `medium`
   - `low`
4. `published_at`
   - newer first
5. `priority`
   - higher first
6. `created_at`
   - newer first
7. `item_id`
   - higher first

This is intentionally not identical to `/handoff`.

Why:

- `/handoff` is optimized for downstream model reasoning and official-first packaging
- `/api/v1/news` is optimized for UI scanning and therefore puts `ready` items ahead of `review` items, even if both are official

## Pool Modes

`/api/v1/news` now has two explicit pool modes:

### `current`

- default mode
- filters the rendered recent pool through `filter_current_window_items(...)`
- intended for the China-morning actionable read layer

### `full`

- uses the broader recent rendered pool without current-window filtering
- intended for analyst drill-down, audit views, and “show me everything we captured” pages

Both totals are returned together so frontend can explain the difference between:

1. all captured recent evidence
2. the currently actionable overnight subset

## Filter Rules

### `tab`

- `all`: no extra filter
- `signals`: `analysis_status == "ready"`
- `watchlist`: `analysis_status == "review"`
- `other`: `analysis_status == "background"` or `coverage_tier == "editorial_media"`

`other` intentionally includes editorial items that are still `review`, because “other news” is a source-context concept, not only a low-confidence concept.

### Exact Filters

- `analysis_status`
- `coverage_tier`
- `source_id`

These are simple string equality filters after rendering.

### Search

`q` is a case-insensitive substring match over:

- `title`
- `summary`
- `source_name`
- `impact_summary`

There is no tokenization, stemming, highlighting, or SQL full-text index in the current implementation.

## Source Summary Rules

`/api/v1/sources` returns all configured sources from `build_default_source_registry()`.

For each source, the API computes:

- `item_count`
- `ready_count`
- `review_count`
- `background_count`
- `latest_item_id`
- `latest_title`
- `latest_published_at`
- `latest_analysis_status`
- `latest_a_share_relevance`

“Latest” is chosen by:

1. newest `published_at`
2. fallback to newest `created_at`
3. then highest `item_id`

Source rows are sorted by:

1. `item_count` descending
2. `ready_count` descending
3. `priority` descending
4. `source_id` ascending

## Guardrail Semantics That Frontend Can Trust

`analysis_status`, `analysis_confidence`, and `analysis_blockers` are deterministic outputs from `app/services/guardrails.py`.

Current status rules:

- `ready`
  - high-relevance official policy/data item
  - high summary quality
  - has actionable mapping
  - no weak excerpt basis
  - has published time provenance
- `review`
  - item is potentially important but still missing some confidence conditions
- `background`
  - low relevance, or editorial item without enough reason to elevate beyond background

Important edge case:

- editorial items can still be `review` if they are high-relevance and contain concrete mappings
- this is why `/api/v1/dashboard.watchlist` can contain editorial sources

## Empty-State Behavior

If the SQLite database has zero captured rows:

- dashboard still returns all configured source summaries
- news list returns an empty page, not an error
- source rows keep metadata but all recent counters are `0`
- `latest_*` fields are `null`

This is intentional and should be preserved. It lets frontend render a professional empty state before the first refresh.

## Current Performance Model

The frontend API is intentionally simple:

- no SQL-side search
- no SQL-side grouped source aggregation
- no materialized presentation tables

Instead it works over a bounded recent pool:

- `dashboard`: recent pool of `200`
- `sources`: recent pool of `200`
- `news`: current pool + full pool, each built from `max(200, (cursor + limit) * 4)`, capped at `500`

This is fast enough for the current product scope and keeps the implementation easy to reason about.

## Known Limitations

### 1. Bounded Recent Pool

- counts and filters operate on a bounded recent pool, not the full historical database
- very old rows will not affect `/api/v1/dashboard`, `/api/v1/news`, or `/api/v1/sources`

### 2. Offset Cursor

- `cursor` is an offset, not an opaque stable cursor
- pagination can shift if new items arrive between page requests

### 3. In-Memory Filtering

- all frontend filters are applied after recent items are rendered
- this keeps behavior simple but is not a substitute for full-text indexing

### 4. Deterministic Re-Render On Read

- analysis fields are computed on demand
- changing heuristics changes how older items are presented

### 5. No Refresh Metadata In Read Contract

- `generated_at` is response render time only
- there is currently no dedicated `last_refresh_at` field in the `v1` read endpoints

## Compatibility

The new layer is additive.

Unchanged routes:

- `/items`
- `/refresh`
- `/handoff`

The frontend API should be treated as a BFF-style read contract sitting beside the existing capture and handoff routes, not replacing them.
