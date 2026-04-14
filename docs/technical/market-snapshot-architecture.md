# Market Snapshot Architecture

> **Status:** This document explains the current persisted U.S. market snapshot layer. It should now be read as the base layer for the broader cross-market Market Board described in [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes the current persisted U.S. market snapshot layer.

## Purpose

The news capture pipeline alone is not enough for a China-morning workflow.

The user also needs to know:

- how U.S. equities actually closed
- whether risk appetite broadened or narrowed
- which major sector proxies led or lagged

This layer adds one deterministic market snapshot that can be read directly, packed into `/handoff`, and embedded into the fixed daily analysis prompt bundle.

## Runtime Boundary

Implemented primarily in:

- [market_snapshot.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/market_snapshot.py)
- [repository.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/repository.py)
- [db.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/db.py)

## Storage Model

Table:

- `overnight_market_snapshots`

Columns:

- `analysis_date`
- `market_date`
- `session_name`
- `source_name`
- `source_url`
- `snapshot_json`
- `created_at`
- `updated_at`

Key properties:

- one row per `analysis_date + session_name`
- current behavior is upsert, not multi-version append
- the stored payload is already grouped and ready for downstream consumption

## Time Semantics

The service intentionally tracks two dates:

- `market_date`
  - the original U.S. session date in the exchange timezone
- `analysis_date`
  - the China-morning date after conversion to `Asia/Shanghai`

Example:

- U.S. regular close at `2026-04-06 16:00 America/New_York`
- converted to `2026-04-07 04:00 Asia/Shanghai`
- stored as:
  - `market_date = 2026-04-06`
  - `analysis_date = 2026-04-07`

This is the key bridge that lets a China-morning report include the previous U.S. close without inventing a separate manual mapping step.

## Capture Source

Current provider order:

1. if `IFIND_REFRESH_TOKEN` exists:
   - `iFinD History`
   - `Treasury Yield Curve`
   - `Yahoo Finance Chart`
2. otherwise:
   - `Treasury Yield Curve`
   - `Yahoo Finance Chart`

Current usage:

1. daily-close snapshot only
2. latest valid close
3. previous close for change and change-percent calculation
4. provider-specific symbol override when the canonical product symbol and upstream vendor code differ
5. provider applicability gating for special sources such as `iFinD` and `Treasury Yield Curve`

The implementation is intentionally conservative:

- daily-close snapshot only
- no intraday session logic
- no streaming or premarket/postmarket interpretation
- keep both raw numeric values and formatted display values in the stored payload

Current iFinD path characteristics:

- enabled only when `IFIND_REFRESH_TOKEN` exists in process env
- uses `cmd_history_quotation`
- normalizes iFinD raw history into a Yahoo-like chart payload shape so the downstream snapshot parser stays deterministic
- currently covers the main U.S. broad-market, sector, precious-metals, energy, copper, and `USD/CNH` buckets through validated iFinD codes or ETF proxies

Current Treasury path characteristics:

- currently dedicated to `^TNX`
- reads the official Treasury daily yield-curve page
- normalizes the latest two valid rows into the same downstream chart payload shape
- removes `^TNX` from the Yahoo-only fallback path

## Instrument Buckets

The service groups configured symbols into:

- `index`
- `sector`
- `sentiment`

Current default examples include:

- major indexes such as `^GSPC`, `^IXIC`, `^DJI`, `^RUT`
- volatility proxy `^VIX`
- sector ETFs such as `XLK`, `XLF`, `XLE`, `XLI`, `XLV`, `XLY`, `XLP`
- semiconductor proxy `SOXX`

## Output Formatting

Each captured instrument now carries two layers of fields:

- raw values
  - `close`
  - `previous_close`
  - `change`
  - `change_pct`
  - `volume`
- formatted values
  - `close_text`
  - `previous_close_text`
  - `change_text`
  - `change_pct_text`
  - `volume_text`
  - `change_direction`

This is deliberate:

- downstream code can still compute from raw numbers
- UI and external model prompts can use the formatted strings directly without re-implementing number formatting

The service also emits:

- `market_time`
  - UTC timestamp
- `market_time_local`
  - original exchange-local timestamp
- `analysis_time_shanghai`
  - China-morning aligned timestamp

## Derived Signals

The service emits deterministic `risk_signals` on top of raw prices:

- `risk_mode`
- advancing/declining sector counts
- positive/negative index counts
- strongest and weakest sector
- strongest and weakest index
- volatility proxy

Current rule for `risk_mode` is intentionally simple:

- `risk_on`
  - most captured indexes are positive
  - and volatility proxy is down when available
- `risk_off`
  - most captured indexes are negative
  - and volatility proxy is up when available
- otherwise `mixed`

## Capture Completeness

The top-level snapshot now exposes `capture_summary`.

Purpose:

- show whether the snapshot is complete or partial
- tell downstream consumers exactly which symbols were missing
- avoid silent degradation when one or two vendor responses fail

Current behavior:

- if at least one instrument is captured, the service can still persist a `partial` snapshot
- if zero instruments are captured, the refresh fails
- if the primary provider fails for one instrument, the service keeps trying the next provider in order

Latest live-validated status on `2026-04-10`:

- `capture_status=complete`
- `captured_instrument_count=23`
- `ALI=F` is now satisfied through iFinD proxy symbol `DBB.P`
- `source_name` becomes `iFinD History, Treasury Yield Curve` when both providers contribute to the same snapshot
- live validation now reports `sentiment` and `rates_fx` bucket counts explicitly, so `^TNX` integration is visible in the validation output

## Integration Points

### Direct API

- `POST /api/v1/market/us/refresh`
- `GET /api/v1/market/us/daily`

### Handoff

`/handoff` now includes top-level `market_snapshot` so an external model can see price action and news evidence in one payload.

### Fixed Daily Analysis

`DailyAnalysisService` reads the stored snapshot for `analysis_date` and passes it into the daily provider.

The provider currently uses it to:

- enrich `narratives.market_view`
- expose `market_snapshot` in the stored report JSON
- expose the same block in the prompt bundle for downstream LLM calls

## Current Limitations

- no per-day multi-version market snapshot history yet
- no exchange-calendar engine yet
- no official exchange-direct licensed data source yet
- no intraday or premarket/postmarket modeling yet
- `ALI=F` currently depends on a proxy mapping (`DBB.P`), so future revisions should still verify whether a more direct aluminum/base-metals symbol is available in iFinD
