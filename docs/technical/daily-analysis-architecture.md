# Daily Analysis Architecture

> **Status:** This document explains the current fixed daily-analysis implementation. It will be refactored to consume Market Board, explicit event records, and ranked mainlines as described in [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes how the fixed daily analysis layer works today.

It covers:

- report generation
- report versioning
- free/premium split
- persisted U.S. market snapshot context
- provider abstraction
- provider-agnostic prompt bundling
- simple premium gating
- current deterministic scoring logic

## Purpose

The project now has three distinct layers:

1. capture and normalization
2. item-level deterministic interpretation
3. day-level fixed conclusions

The new daily layer exists because the user requirement is not “show raw news only”. It is:

- generate a stable morning conclusion
- keep that conclusion fixed for the day
- separate free directional conclusions from premium stock-level conclusions
- preserve enough fact provenance that the final conclusion can be audited

## What Is Fixed Per Day

For each `analysis_date`, the system can create:

- one `free` report version
- one `premium` report version

Regeneration does not overwrite the existing report. It creates:

- `version = 1`
- `version = 2`
- `version = 3`

and so on, per `analysis_date + access_tier`.

Read requests always return the latest version for that date and tier.
Specific historical versions can also be addressed explicitly.

This is the mechanism that keeps the daily conclusion stable while still allowing manual re-runs.

## Storage Model

Implemented in [app/db.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/db.py) and [app/repository.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/repository.py).

### Table

`overnight_daily_analysis_reports`

Columns:

- `analysis_date`
- `access_tier`
- `version`
- `provider_name`
- `provider_model`
- `input_item_ids`
- `report_json`
- `created_at`

Key properties:

- `(analysis_date, access_tier, version)` is unique
- latest lookup is indexed by `(analysis_date, access_tier, version DESC)`
- report payloads expose:
  - `input_fingerprint`
  - `report_fingerprint`

Related context table:

- `overnight_market_snapshots`

This is a separate persisted layer that stores one `us_close` market snapshot for each `analysis_date`.

## Service Boundaries

### Item Rendering

[app/services/source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/source_capture.py)

Still owns item-level deterministic interpretation:

- `published_at_precision`
- `published_at_display`
- `source_authority`
- `content_metrics`
- `content_completeness`
- `body_detail_level`
- `source_time_reliability`
- `source_capture_confidence`
- `summary_quality`
- `a_share_relevance`
- `evidence_points`
- `impact_summary`
- `key_numbers`
- `fact_table`
- `cross_source_confirmation`
- `fact_conflicts`
- `event_cluster`
- `policy_actions`
- `market_implications`
- `uncertainties`
- `llm_ready_brief`
- `beneficiary_directions`
- `pressured_directions`
- `price_up_signals`
- `follow_up_checks`
- `analysis_status`
- `analysis_confidence`
- `analysis_blockers`

### Daily Analysis Provider

[app/services/daily_analysis_provider.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/daily_analysis_provider.py)

Defines the provider interface and the current default provider:

- `RuleBasedDailyAnalysisProvider`

This abstraction is important because the project goal is to support future model-backed generation, but the current implementation must remain usable and deterministic before any external model is configured.

### Daily Analysis Orchestration

[app/services/daily_analysis.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/daily_analysis.py)

Responsibilities:

- choose the report date
- select the date-matching input items
- read the persisted U.S. market snapshot for the same `analysis_date` when available
- call the provider once for `free`
- call the provider once for `premium`
- persist both reports as new versions
- retrieve the latest cached report
- retrieve a specific cached version
- list cached versions for `analysis_date + access_tier`
- build provider-agnostic prompt bundles from the latest cached report

### Delivery Layer

[app/main.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/main.py)

Routes:

- `POST /api/v1/analysis/daily/generate`
- `GET /api/v1/analysis/daily`
- `GET /api/v1/analysis/daily/versions`
- `GET /api/v1/analysis/daily/prompt`

It also enforces the simple premium access key check.

## Input Selection

The daily report currently uses rendered recent items from the presentation capture service.

An item is included for `analysis_date` if either field starts with that date:

- `created_at`
- `published_at`

This is intentionally simple and stable for the first version.

Implication:

- the system behaves more like a dated capture/report bucket than a dedicated market-session engine
- if later you need a true “overnight session window”, that should become a separate explicit session model

## Current Scoring Formula

Implemented in [app/services/daily_analysis_provider.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/daily_analysis_provider.py).

### Item Signal Score

Current formula:

`signal_score = analysis_status + coverage_tier + a_share_relevance + analysis_confidence + priority_bonus + source_capture_confidence_bonus + cross_source_confirmation_bonus + timeliness_bonus - blocker_penalty - fact_conflict_penalty - staleness_penalty`

Current component values:

- `analysis_status`
  - `ready = 6`
  - `review = 3`
  - `background = 1`
- `coverage_tier`
  - `official_policy = 4`
  - `official_data = 3`
  - `editorial_media = 1`
- `a_share_relevance`
  - `high = 4`
  - `medium = 2`
  - `low = 0`
- `analysis_confidence`
  - `high = 2`
  - `medium = 1`
  - `low = 0`
- `priority_bonus`
  - `min(4, priority // 25)`
- `source_capture_confidence_bonus`
  - `high` or score `>= 80` gives `+3`
  - `medium` or score `>= 60` gives `+2`
  - score `>= 45` gives `+1`
- `cross_source_confirmation_bonus`
  - `strong` or 2+ corroborating sources gives `+2`
  - `moderate` or 1 corroborating source gives `+1`
- `timeliness_bonus`
  - `breaking = +3`
  - `overnight = +2`
  - `recent = +1`
- `blocker_penalty`
  - `min(3, len(analysis_blockers))`
- `fact_conflict_penalty`
  - `min(2, len(fact_conflicts))`
- `staleness_penalty`
  - `stale` gives `+1` penalty
  - `delayed_capture` adds another `+1` penalty

Score floor:

- final item score is clamped to at least `1`

The item score is also exposed in the API as:

- `supporting_items[].signal_score`
- `supporting_items[].signal_score_breakdown`

This means the report is auditable at the single-item level, not only at the final headline level.

## Direction Aggregation

The provider aggregates three classes of directional output from item-level fields:

- `beneficiary_directions`
- `pressured_directions`
- `price_up_signals`

For each unique direction:

- direction score = sum of the strongest contributing item signal score inside each `event_cluster`
- supporting item ids are collected
- source ids are collected
- official/editorial source mix is counted by distinct source id
- contributing `event_cluster` ids are tracked
- confirmed/conflicted contributing item counts are tracked
- rationale is synthesized from the top contributing item titles
- evidence snippets are aggregated from supporting item `evidence_points`
- follow-up checks are aggregated from supporting item `follow_up_checks`

Confidence rules:

- `high`
  - direction score `>= 18`
  - and at least one official supporting item
  - and at least one corroborated supporting item
  - and zero conflicted supporting items
- `medium`
  - score `>= 8`
- `low`
  - lower than that

This logic is visible in the API so downstream consumers can audit the formula instead of trusting a black box.

## Narrative Layer

The provider now emits a prose-oriented `narratives` block on top of the structured fields.

Current sections:

- `market_view`
- `policy_view`
- `sector_view`
- `risk_view`
- `execution_view`

Purpose:

- make the cached report readable by humans without losing structured detail
- give future external model calls a cleaner summary scaffold
- preserve the free/premium execution boundary in prose form
- surface actual U.S. close behavior beside the overnight news flow when captured

## Free vs Premium

### Free Report

Contains:

- summary
- narratives
- scoring method
- input snapshot
- direction calls
- risk watchpoints
- supporting items

Does not expose:

- stock-level calls

### Premium Report

Contains everything in the free report, plus:

- `stock_calls`

Current premium stock calls are generated from a curated direction-to-stock map. This is implemented as deterministic proxy mapping, not as full security research.

That is why the API explicitly includes:

- `mapping_basis = direction_proxy`

so the consumer can distinguish it from a future model-backed security-level thesis.

## Prompt Bundle Layer

Implemented in [app/services/daily_analysis.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/daily_analysis.py).

Purpose:

- package the latest cached report into provider-agnostic `messages`
- keep external model calls reproducible from the fixed report version
- separate prompt-building from provider execution

Current prompt bundle fields:

- `analysis_date`
- `access_tier`
- `report_version`
- `provider_target = external_llm_ready`
- `input_item_ids`
- `source_audit_pack`
- `market_snapshot` inside the user message content
- `messages`

Important note:

- the fixed report prompt bundle is report-centric
- it now also carries a compact `source_audit_pack` derived from the fixed report's `supporting_items`
- `source_audit_pack` groups supporting items by `event_cluster` so downstream models can deduplicate same-event evidence without making a second request
- the full recent-pool view still lives in `/handoff`, but prompt consumers no longer need `/handoff` for basic source-audit depth

Current message policy:

- `free`
  - explicitly forbids stock-specific buy/sell advice
- `premium`
  - allows stock mappings
  - still requires evidence and risk disclosure

The prompt bundle route can target:

- the latest cached report version
- a specific historical version via `version`

`source_audit_pack` currently contains:

- `supporting_items`
- grouped `event_groups`
- official supporting item ids
- prompt-side field-priority hints
- inclusion counters so the consumer can see how much of the report input was embedded directly

## Premium Gating

Implemented in [app/main.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/main.py).

Current rule:

- `tier=free` needs no key
- `tier=premium` requires header `X-Premium-Access-Key`
- header value must equal `OVERNIGHT_PREMIUM_API_KEY`

If the key is missing or mismatched:

- `403 Premium access key required`

This is intentionally minimal and does not try to model users, plans, or quota.

## Accuracy Improvements Added In This Iteration

### 1. Numeric Fact Deduplication

Implemented in [app/normalizer.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/normalizer.py).

Previously, the same repeated numeric fact could appear multiple times if it was matched in overlapping contexts.

Current behavior:

- dedupe signature = `(metric, value, unit, subject)`
- when duplicates exist, keep the richer/longer context

This reduces noisy repeated facts in downstream analysis.

### 2. Energy Shock False Positive Reduction

Implemented in [app/services/impact.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/impact.py).

Previously, generic wording such as `shipping activity` in trade-data summaries could incorrectly trigger energy/cost-shock logic.

Current behavior:

- generic `shipping` wording alone no longer triggers the energy shock branch
- the energy branch now requires actual energy/oil/gas/Hormuz-style signals

This keeps trade-demand reports from being misread as oil shock reports.

## Provider Evolution Path

The provider abstraction is already in place.

To add a future model-backed provider cleanly, the intended next step is:

1. implement a new provider that satisfies the `DailyAnalysisProvider` interface
2. feed it the same item-level rendered facts
3. persist its output through the same versioned report table
4. keep `free` and `premium` tier semantics unchanged

That means the storage, routing, and version model do not need to be redesigned when external AI is introduced.

## Current Limitations

### 1. No External AI Provider Yet

- current generation is fully deterministic
- provider metadata will show `rule_based`

### 2. Stock Calls Are Proxy Mappings

- premium stock outputs are representative mappings from direction labels to a curated ticker list
- they are not yet issuer-level model-generated theses

### 3. Date Matching Is Simple

- the daily bucket uses `created_at` / `published_at` prefix matching
- there is no explicit overnight-session window or exchange calendar logic yet

### 4. Historical Storage Exists, But No Compare View Yet

- latest read remains the default
- version listing is exposed through `/api/v1/analysis/daily/versions`
- specific historical report/prompt reads are supported via `version`
- there is still no dedicated version diff/compare route

### 5. Prompt Bundle Is Derived, Not Persisted

- the prompt bundle is generated from the requested cached report when requested
- prompt messages are not currently stored as a separate versioned artifact
- `source_audit_pack` is likewise derived at read time from the stored report payload rather than stored as a separate artifact

### 6. Market Snapshot Is Daily-Upserted, Not Versioned

- the U.S. market snapshot is stored in its own table
- current behavior is one row per `analysis_date + session_name`
- it is meant to be stable for the daily close, but it is not yet tracked as a multi-version history
