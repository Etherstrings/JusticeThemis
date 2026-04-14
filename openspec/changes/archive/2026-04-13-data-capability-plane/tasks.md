## Execution Order

- Apply tasks in numeric order.
- Do not begin premium enrichment until regime-led mainlines and secondary-context outputs are in place.
- Preserve existing API/report contracts unless a task explicitly adds an additive field.

## 1. Persistence And Observation Layer

- [x] 1.1 Add persistence support for `overnight_market_capture_runs`, `overnight_market_observations`, and `overnight_ticker_enrichment_records` in `app/db.py`.
Acceptance: schema creation is idempotent and existing daily-report tables remain untouched.

- [x] 1.2 Add repository read/write helpers in `app/repository.py` for capture runs, normalized observations, and enrichment records.
Acceptance: repository can write one capture run, append observation rows keyed by `(capture_run_id, symbol, provider_name)`, and read them back by analysis date/session.

- [x] 1.3 Add persistence tests in `tests/` covering schema creation and repository round-trips for observations and capture runs.
Acceptance: tests prove multiple providers can store the same symbol in one run without overwriting each other.

## 2. Market Provider Router And Observation Normalization

- [x] 2.1 Extract instrument/provider routing out of `app/services/market_snapshot.py` into explicit router/normalization helpers.
Acceptance: provider priority is bucket-aware, not one global list.

- [x] 2.2 Add `KWEB` and `FXI` as `P1` China-proxy support instruments in the first-pass board definition.
Acceptance: they participate in observation capture and appear in assembled snapshot payloads when data is available.

- [x] 2.3 Preserve and test provider-symbol overrides for Treasury, iFinD, and Yahoo fallback behavior.
Acceptance: `^TNX`, `SOXX`, `XLK`, `DX-Y.NYB`, `GC=F`, and `SI=F` still resolve to the expected provider symbols.

- [x] 2.4 Write normalized observations before board assembly and record capture diagnostics in the same run.
Acceptance: snapshot assembly can be reproduced from persisted observations for a completed capture run.

- [x] 2.5 Add normalization tests for Treasury, iFinD, and Yahoo-backed rows.
Acceptance: normalized rows include symbol, provider, bucket, market timestamp/date, close, previous close, change, change_pct, freshness, and provenance.

## 3. Regime Engine

- [x] 3.1 Add a dedicated regime engine module, for example `app/services/market_regime_engine.py`, that evaluates first-pass rules from normalized observations and board metrics.
Acceptance: first-pass regime set includes `technology_risk_on`, `rates_pressure`, `safe_haven_flow`, `energy_inflation_impulse`, `usd_strengthening`, and `china_proxy_strength`.

- [x] 3.2 Encode `MarketRegimeRule` completeness, freshness, and conflict semantics.
Acceptance: regime outputs contain `triggered`, `direction`, `strength`, `confidence`, `completeness_ratio`, `driving_symbols`, `supporting_observations`, and suppression reasons.

- [x] 3.3 Persist additive regime evaluation payloads into assembled snapshot output.
Acceptance: snapshot payload can expose triggered regimes and suppressed summaries without a breaking schema change.

- [x] 3.4 Add regime-engine regression tests.
Acceptance: tests cover triggered, downgraded, and suppressed paths for at least technology, rates, safe-haven, and energy cases.

## 4. Mainline Assembly And Secondary Context

- [x] 4.1 Refactor `app/services/mainline_engine.py` so confirmed top mainlines are assembled from `market_regimes + event_groups`, not directly from topic-tagged events.
Acceptance: every confirmed mainline references at least one `regime_id`.

- [x] 4.2 Add `secondary_event_groups` output for notable event clusters without sufficient regime support.
Acceptance: downgrade reasons include `no_regime_match`, `insufficient_market_strength`, `missing_required_observations`, `stale_market_inputs`, or `competing_regime_dominates`.

- [x] 4.3 Update `app/services/daily_analysis.py` and `app/services/handoff.py` to pass `market_regimes`, regime-backed `mainlines`, and `secondary_event_groups`.
Acceptance: old call sites still receive `market_snapshot` and `mainlines`; new fields are additive.

- [x] 4.4 Add regression tests proving unsupported event groups do not outrank regime-backed mainlines.
Acceptance: a high-signal document cluster without market confirmation is present in `secondary_event_groups` and absent from confirmed top mainlines.

## 5. Downstream Consumer Compatibility

- [x] 5.1 Update `app/services/daily_analysis_provider.py` so summary, direction calls, and narratives consume regime-backed mainlines without assuming event-first semantics.
Acceptance: free and premium reports still generate with unchanged top-level shape.

- [x] 5.2 Update `app/services/mmu_handoff.py` to expose additive `market_regimes` and `secondary_event_groups`.
Acceptance: existing `market_attribution` and `premium_recommendation` payloads remain usable by current downstream prompts.

- [x] 5.3 Update `app/services/frontend_api.py` and `app/services/pipeline_markdown.py` to expose professional dashboard/operator views of regimes and secondary context.
Acceptance: dashboard and markdown outputs can show confirmed mainlines separately from secondary context without breaking existing keys.

## 6. Premium Enrichment Plane

- [x] 6.1 Keep Alpha Vantage enrichment-only in the first pass and implement trigger rules in enrichment services.
Acceptance: enrichment only runs for premium flows, triggered mainlines, or explicit regime-driven requests.

- [x] 6.2 Add enrichment persistence/service interfaces for symbol-level price/news/fundamental context.
Acceptance: enrichment failure never blocks snapshot, handoff, or free report generation.

- [x] 6.3 Add premium-enrichment tests.
Acceptance: tests prove enrichment is optional, non-blocking, and tied to eligible triggers only.

## 7. Operations, Health, And Docs

- [x] 7.1 Extend readiness, health, and live validation with provider hit rates, missing core symbols, freshness, and optional-enrichment degradation.
Acceptance: core-board failure is distinguishable from optional degradation.

- [x] 7.2 Update `.env.example` and technical docs for router providers, enrichment providers, and regime diagnostics.
Acceptance: operators can configure the first-pass capability plane without reading implementation code.

- [x] 7.3 Add end-to-end regression coverage for one completed overnight run.
Acceptance: one fixture-backed pipeline path produces snapshot, regimes, mainlines, secondary context, reports, and MMU bundle without contract breakage.
