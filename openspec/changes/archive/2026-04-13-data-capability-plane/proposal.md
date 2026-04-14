## Why

`overnight-news-handoff` already captures overnight official/news sources, builds a persisted U.S. market-close snapshot, generates fixed daily reports, and exports prompt/MMU artifacts. What it does not yet have is a formal data capability plane beneath those outputs.

Today the system has two parallel MVP-style inputs:

- document/news facts captured into `overnight_source_items`
- one assembled `market_snapshot` JSON used by dashboards, reports, and MMU handoff

That structure is enough for the current backend MVP, but it is not enough for the next stage of data expansion. As more providers are introduced, the current design would force provider-specific logic directly into the market snapshot flow or into news capture, making it harder to reason about freshness, missing symbols, fallback behavior, cross-provider verification, and premium ticker-level enrichment.

This change introduces a formal data capability plane so the project can ingest and normalize cross-asset market data, derive deterministic overnight market regimes, and optionally attach ticker-level enrichment for premium or theme-driven reasoning, while keeping the existing product surface largely stable.

## What Changes

- Add a formal `market observation` contract for normalized cross-asset facts below `market_snapshot`
- Add a `market provider router` that manages provider priority, symbol overrides, and fallback behavior by bucket and intent
- Add a deterministic `regime and mainline grounding` layer so the system can explain overnight news starting from the actual market outcome and assemble top mainlines from regime-backed evidence rather than event tags alone
- Add a `ticker enrichment` plane for on-demand symbol-level news, fundamentals, and proxy context used by premium or mainline-triggered flows
- Add explicit freshness and completeness rules so capture health can distinguish between missing core board data and optional enrichment gaps
- Keep the current dashboard, market snapshot, daily report, prompt bundle, and MMU export surfaces intact wherever possible

## Capabilities

### New Capabilities

- `market-observation-contract`: define the normalized cross-asset observation layer beneath assembled market snapshots
- `market-provider-router`: define bucket-aware provider routing, symbol override, and fallback behavior for market data capture
- `regime-and-mainline-grounding`: define deterministic overnight market regime extraction from normalized observations
- `ticker-enrichment-plane`: define non-blocking theme-driven and premium-driven ticker enrichment behavior
- `data-freshness-and-completeness`: define health, completeness, and degradation rules for core market data and optional enrichments

### Modified Capabilities

- None.

## Impact

- Affected services: `app/services/market_snapshot.py`, `app/services/asset_board.py`, `app/services/daily_analysis.py`, `app/services/daily_analysis_provider.py`, `app/services/mainline_engine.py`, `app/services/handoff.py`, `app/services/mmu_handoff.py`, `app/services/frontend_api.py`, `app/services/pipeline_markdown.py`, `app/services/pipeline_health.py`, and `app/live_validation.py`
- Affected persistence: `app/db.py` and `app/repository.py`
- Affected runtime contract: `app/runtime_config.py`, readiness reporting, and `.env.example`
- Affected operator surface: live validation, readiness detail, and health semantics for partial market capture
- Expected API evolution: keep current routes stable, optionally add observation- and enrichment-specific read routes

## Non-Goals

- Adding X or social media ingestion as a primary source
- Re-enabling intentionally disabled China-government source policy boundaries
- Replacing fixed report generation with inline external model execution
- Redesigning the frontend or changing the product thesis away from "first confirm the overnight market result, then explain it"
- Running full-universe daily enrichment on many tickers regardless of market regime or premium need
