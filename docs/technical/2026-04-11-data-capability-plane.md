# 2026-04-11 Data Capability Plane

## Scope

This document captures the first complete implementation pass of the `data-capability-plane` change inside `overnight-news-handoff`.

The goal of this pass was to stop treating the overnight market snapshot as one opaque payload and instead make the stack auditable from:

1. normalized market observations
2. deterministic market regimes
3. regime-backed mainlines
4. optional premium enrichment
5. operator diagnostics

## What Is Implemented

### 1. Market observation and routing layer

- Core market observations are persisted in:
  - `overnight_market_capture_runs`
  - `overnight_market_observations`
- Provider routing is bucket-aware:
  - `rates_fx`: Treasury -> iFinD -> Yahoo
  - `index/sector/sentiment/commodities/china_proxy`: iFinD -> Yahoo
- `KWEB` and `FXI` are first-pass `china_proxy` support instruments on the main board.

### 2. Regime-grounded overnight interpretation

- The snapshot now emits additive:
  - `market_regimes`
  - `market_regime_evaluations`
- First-pass deterministic regimes:
  - `technology_risk_on`
  - `rates_pressure`
  - `safe_haven_flow`
  - `energy_inflation_impulse`
  - `usd_strengthening`
  - `china_proxy_strength`
- `mainlines` are now assembled from `market_regimes + event_groups`, not from topic tags alone.
- important but unconfirmed news clusters are preserved in `secondary_event_groups`.

### 3. Consumer compatibility layer

- `daily_analysis` keeps the previous free/premium shape and now adds:
  - `market_regimes`
  - `secondary_event_groups`
  - `ticker_enrichments`
  - `enrichment_summary`
- `MMU handoff` now carries additive:
  - `market_regimes`
  - `secondary_event_groups`
  - premium `ticker_enrichments`
- `frontend dashboard` now exposes:
  - `mainlines`
  - `market_regimes`
  - `secondary_event_groups`

### 4. Optional premium enrichment plane

- First-pass enrichment provider:
  - `Alpha Vantage`
- Enrichment is optional and non-blocking.
- Trigger rules:
  - premium report generation
  - explicit symbol request
  - regime/mainline-driven context requests
- First-pass symbol collection sources:
  - `mainlines[].affected_assets`
  - `market_regimes[].driving_symbols`
  - downstream `stock_calls[].ticker` when the provider can support them
- Persistence:
  - `overnight_ticker_enrichment_records`
- Failure mode:
  - record `status=error`
  - return `enrichment_summary.status=degraded`
  - do not block free report generation, premium report generation, handoff, or MMU export

## Diagnostics Surfaces

### Market snapshot diagnostics

`market_snapshot.capture_summary` now includes:

- `provider_hits`
- `core_missing_symbols`
- `supporting_missing_symbols`
- `optional_missing_symbols`
- `freshness_status_counts`

Operational meaning:

- `core_missing_symbols`: fail-grade gaps for the overnight board
- `supporting_missing_symbols`: warn-grade degradation
- `optional_missing_symbols`: additive/operator-only degradation

### Readiness

`GET /readyz` now reports provider availability for:

- market snapshot
- search discovery
- ticker enrichment

### Live validation

`app.live_validation.collect_market_snapshot_validation_report()` now surfaces:

- `provider_hits`
- tiered missing symbol groups
- freshness counts

### Pipeline health

`PipelineHealthService` now distinguishes:

- core-board failure -> `fail`
- optional market degradation -> `warn`
- ticker enrichment degradation -> `warn`

## Environment Contract

Project-local environment variables used by this plane:

- `IFIND_REFRESH_TOKEN`
- `ALPHA_VANTAGE_API_KEY`
- `ALPHAVANTAGE_API_KEY`

Search-provider variables remain unchanged and are still handled separately.

## Current Limits

This pass is intentionally conservative.

- Alpha Vantage is enrichment-only; it is not part of core board routing.
- First-pass premium enrichment is strongest for U.S. ETFs / U.S.-style symbols already linked to regimes or mainlines.
- China stock enrichment providers such as Tushare / AKShare / iFinD security-level context are not yet wired into this enrichment plane.
- No separate premium enrichment read API has been added yet; enrichment is exposed through report/MMU payloads first.

## Verified State

- Full local test suite passes after this change set:
  - `264 passed`

## Next Iteration Candidates

1. Add dedicated China equity enrichment providers behind the same non-blocking service contract.
2. Add explicit premium read APIs for persisted `ticker_enrichment_records` if downstream consumers need direct browsing.
3. Expand regime-to-direction mappings beyond the first-pass buckets now that the grounding layer is stable.
