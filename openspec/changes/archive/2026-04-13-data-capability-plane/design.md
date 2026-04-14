## Context

The current project already has a strong product direction:

- official-first overnight document capture
- cross-asset U.S. close snapshot for China-morning use
- fixed free/premium daily reports
- prompt/MMU exports for downstream model reasoning

It also already contains several important building blocks:

- a stable document source registry and search-discovery path
- an initial market instrument registry embedded in `market_snapshot.py`
- provider-specific symbol overrides for iFinD and Treasury
- a cross-asset asset board with China futures mapping
- downstream consumers that depend on assembled `market_snapshot`, `mainlines`, and fixed report artifacts

The problem is therefore not that the project lacks data ingestion completely. The problem is that market data is still represented mainly as one assembled snapshot product rather than as a reusable fact layer. This makes it difficult to:

- verify provider fallback behavior
- inspect freshness and completeness by symbol or bucket
- ground analysis in deterministic market regimes
- attach theme-driven ticker enrichments without polluting the core board path
- ensure the top overnight mainlines come from confirmed market moves first and news explanation second

## Goals / Non-Goals

**Goals**

- Introduce a reusable normalized market-fact layer beneath the assembled market snapshot
- Make provider routing explicit and bucket-aware
- Add deterministic regime grounding so analysis starts from actual overnight market outcomes
- Add non-blocking ticker enrichment for mainline explanation and premium context
- Upgrade health/readiness/validation so operators can distinguish core-board failure from optional enrichment degradation

**Non-Goals**

- A universal "one registry for all sources" abstraction that forces document and numeric sources into the same model
- A broad frontend redesign
- Inline LLM execution inside report generation
- Social-media-first market intelligence

## Decisions

### 1. Keep document sources and market sources as separate modeling layers

`SourceDefinition` remains the correct model for document/news capture because it is centered on URLs, publication times, excerpts, and article normalization. Market data should not be forced into that same abstraction. Instead, market data should use a dedicated instrument/provider model centered on symbols, provider symbols, market timestamps, normalized prices, and bucket-level completeness.

This preserves clarity:

- document plane: official pages, RSS, search discovery, article facts
- market plane: cross-asset observations and market snapshots

### 2. Introduce a market observation layer beneath assembled market snapshots

The assembled market snapshot remains useful and should stay as the product-facing board contract. However, the system needs a reusable observation layer below it.

This new layer should standardize at least:

- symbol identity
- provider identity
- bucket identity
- market timestamp/date
- close, previous close, change, and change percentage
- capture/freshness state
- primary-vs-fallback provenance

This lets the system assemble the board from stable facts, validate missing symbols correctly, and support downstream enrichment without re-parsing provider payloads.

### 3. Provider routing must be bucket-aware, not globally ordered

Provider priority should vary by data type:

- rates and Treasury yield data should prefer official Treasury data where available
- broad U.S. indexes, sectors, and commodities should prefer iFinD when configured, then Yahoo, with other fallbacks added deliberately
- ticker-level enrichment should use Finnhub, Alpha Vantage, and search-backed context separately from the core board path
- A/H-share enrichment should use Tushare, AKShare, and iFinD according to the target market and feature scope

This avoids the false simplicity of one global provider ranking while still keeping routing explicit and testable.

### 4. Add deterministic market regime grounding before narrative analysis

The product thesis is that China-morning users should first see what the overnight market already did and only then read the explanation. That means the system should derive a small set of deterministic regime states from normalized observations before daily narrative generation.

Examples include:

- technology risk-on
- rates pressure
- safe-haven flow
- energy inflation impulse
- USD strengthening
- China proxy strength

Those regimes then become analysis inputs for `daily_analysis`, `handoff`, and MMU export, rather than leaving all mainline interpretation to ad hoc narrative inference.

### 5. Mainline assembly must be regime-led, not event-led

The current project direction says the user should first understand what the overnight market actually did. That requirement is still not fully satisfied if the system takes `topic_tags -> bucket`, then merely checks whether matching assets moved.

The stronger target model is:

```text
market observations
    -> market board metrics
    -> market regimes
    -> event groups
    -> mainline narratives
    -> daily report / handoff / MMU bundle
```

This means:

- regimes are derived first from normalized observations
- event groups explain or challenge those regimes
- mainlines are assembled from `market_regimes + event_groups`, not promoted directly from topic-tagged documents
- events without market confirmation may remain visible as secondary context, but they should not dominate confirmed top mainlines

Recommended internal contracts:

`MarketRegime`

- `regime_id`: stable per `(analysis_date, regime_key)`
- `regime_key`: such as `technology_risk_on`, `rates_pressure`, `safe_haven_flow`, `energy_inflation_impulse`
- `direction`: `bullish`, `bearish`, `mixed`, or `neutral`
- `strength`: normalized strength score derived from configured observation rules
- `confidence`: deterministic confidence tier based on completeness and signal agreement
- `driving_symbols`: symbols or rates that triggered the regime
- `supporting_observations`: normalized facts used to justify the regime

`MainlineNarrative`

- `mainline_id`: stable per `(analysis_date, bucket)`
- `mainline_bucket`: product-facing theme bucket
- `regime_ids`: one or more grounding regimes
- `supporting_event_group_ids`: event groups used as explanation
- `affected_assets`: surfaced assets or China mappings
- `market_effect`: user-facing summary of what moved
- `narrative_status`: `confirmed` or `secondary`
- `confidence`: final narrative confidence after combining regime and event evidence

This keeps the system honest: when the market already closed strongly higher in technology, the mainline should start from that result and then ask which documents explain it, not the other way around.

### 6. Market regimes must be rule-auditable and completeness-aware

If regimes become the grounding layer, operators and downstream models need to know why a regime was or was not emitted. A regime cannot just be a heuristic label attached to a board headline.

Recommended internal contract:

`MarketRegimeRule`

- `regime_key`: stable identifier such as `technology_risk_on`
- `required_observation_keys`: observations that must be present and fresh enough for evaluation
- `supporting_observation_keys`: optional observations that strengthen the regime
- `disqualifying_observation_keys`: observations that suppress or weaken the regime
- `minimum_completeness_ratio`: minimum usable coverage before the rule may emit a confirmed regime
- `minimum_strength_score`: threshold for regime emission
- `conflict_policy`: how conflicting signals downgrade direction or confidence
- `freshness_policy`: how stale observations suppress or demote a regime

Recommended evaluation flow:

```text
normalized observations
    -> board metrics
    -> rule evaluation
        -> triggered regimes
        -> suppressed regimes with reasons
    -> regime-backed mainlines
```

Recommended emitted fields per evaluated regime:

- `regime_id`
- `regime_key`
- `triggered`
- `direction`
- `strength`
- `confidence`
- `completeness_ratio`
- `driving_symbols`
- `supporting_observations`
- `suppressed_by`
- `evaluation_notes`

This matters operationally. If `SOXX` is missing or stale, the system should not quietly emit a strong technology regime from editorial explanation alone. It should either suppress the regime or downgrade it with explicit reasons.

### 7. Unconfirmed event groups must surface separately from confirmed mainlines

The project still needs to show important overnight developments that may not yet have strong market confirmation. Those items should remain available to the user, but they should not occupy the same semantic layer as regime-backed mainlines.

Recommended separation:

- `mainlines`: confirmed, regime-backed, top-of-report narratives
- `secondary_event_groups`: notable event clusters without sufficient market confirmation
- `watch_context`: optional operator-facing summary of why those groups were not promoted

Typical downgrade reasons:

- `no_regime_match`
- `insufficient_market_strength`
- `missing_required_observations`
- `stale_market_inputs`
- `competing_regime_dominates`

This gives the product an honest hierarchy:

- first: what the market already proved overnight
- second: what the news likely explains
- third: what is important but not yet market-confirmed

### 8. Ticker enrichment is optional and non-blocking

Ticker enrichment should only run when triggered by:

- a detected market regime
- a high-priority mainline
- premium-tier export needs

It should not be required to produce the core market board or free daily report. This keeps the core overnight pipeline stable and fast while still allowing premium or theme-level outputs to become more concrete and professional.

### 9. Health and readiness should distinguish core-board failure from optional degradation

The current `partial market snapshot` status is too coarse for a richer data layer. The system should classify instruments and outputs by operational importance:

- core board (`P0`)
- important supporting board (`P1`)
- optional enrichment/proxy (`P2`)

This allows health and readiness to fail only when the overnight board loses truly core coverage, while tolerating optional enrichment degradation.

## Data Model Direction

The existing persistence contracts remain valid but need supporting tables.

Recommended additions:

- `overnight_market_observations`
- `overnight_market_capture_runs`
- `overnight_ticker_enrichment_records`

The existing `overnight_market_snapshots` table remains and continues to store the assembled board payload used by the API and downstream consumers.

This yields a layered model:

- observations: normalized raw market facts
- capture runs: operational audit and completeness
- regimes: deterministic overnight market state
- snapshot: assembled product-facing board
- enrichments: optional symbol-level context for premium or theme follow-up

First-pass persistence defaults:

- observations are grouped under `capture_run_id`
- one observation row is unique per `(capture_run_id, symbol, provider_name)`
- assembled `market_snapshot` remains the canonical persisted read model for APIs and reports
- first-pass regime evaluations are persisted inside assembled snapshot/report payloads rather than a standalone `overnight_market_regimes` table
- suppressed regime summaries are persisted in additive evaluation fields so operators can inspect why a regime did not trigger

## First Coding Pass Defaults

These choices are resolved for the first implementation pass and should not block `apply-change`.

- `KWEB` and `FXI` enter the board as `P1` China-proxy support instruments, not premium-only enrichment
- Alpha Vantage remains enrichment-only in the first pass; core board routing stays Treasury -> iFinD -> Yahoo according to bucket
- premium enrichment is exposed through fixed report / MMU outputs first, not through new dedicated premium APIs
- every confirmed top-level `mainline` must reference at least one `regime_id`
- notable event groups without regime support are exposed through `secondary_event_groups`
- suppressed regimes are persisted as summary evaluation records inside snapshot/handoff/report payloads, not as a separate top-level table in the first pass
- first-pass regime set is limited to:
  - `technology_risk_on`
  - `rates_pressure`
  - `safe_haven_flow`
  - `energy_inflation_impulse`
  - `usd_strengthening`
  - `china_proxy_strength`

Recommended first-pass rule anchors:

- `technology_risk_on`: prioritize `SOXX`, `XLK`, `^IXIC`; weaken when `^VIX` spikes or rates pressure dominates
- `rates_pressure`: prioritize `^TNX`, `DX-Y.NYB`, `CNH=X`; strengthen when tech assets are weak
- `safe_haven_flow`: prioritize `GC=F`, `SI=F`, `^VIX`; strengthen when broad indexes weaken
- `energy_inflation_impulse`: prioritize `CL=F`, `BZ=F`, `NG=F`, `XLE`
- `usd_strengthening`: prioritize `DX-Y.NYB` and `CNH=X`
- `china_proxy_strength`: prioritize `KWEB` and `FXI`, with `CNH=X` as supporting context

## Output Compatibility

Downstream surfaces such as:

- dashboard market board
- `/api/v1/market/us/daily`
- fixed daily reports
- prompt bundles
- MMU handoff

should continue to read from assembled snapshot/report contracts. The new data layer should be introduced below those outputs so internal capability grows without breaking consumers unnecessarily.

Compatibility direction:

- `market_snapshot` remains the primary assembled board contract
- `mainlines` remains a top-level output surface, but becomes regime-led internally
- `market_regimes` may be added as an additive structured field to handoff/MMU payloads
- `secondary_event_groups` may be added as an additive structured field to reports, handoff payloads, and professional dashboard APIs
- fixed daily reports may reference regime summaries without requiring a breaking schema rewrite
- additive fields such as `narrative_status` or `regime_ids` are acceptable if current consumers can ignore them safely

## Risks / Trade-offs

- [Risk] The observation layer becomes over-modeled and slows implementation.  
  Mitigation: start with only the fields already needed for the board, health, and enrichment triggers.

- [Risk] Ticker enrichment grows into a second full market pipeline.  
  Mitigation: require explicit trigger reasons and keep enrichment non-blocking.

- [Risk] Provider routing becomes too abstract to debug.  
  Mitigation: persist capture runs and include provider hit/fallback data in validation/readiness outputs.

- [Risk] Regime rules are too rigid.  
  Mitigation: start with a small set of regimes and treat them as grounding aids, not the full narrative layer.

- [Risk] A real policy or corporate shock may matter before broad assets fully confirm it.  
  Mitigation: keep unsupported event clusters visible as secondary context, but avoid promoting them above confirmed regime-backed mainlines.

- [Risk] Regime evaluation becomes opaque and hard to trust.  
  Mitigation: expose completeness, suppress reasons, and rule-level diagnostics rather than only final labels.

## Rollout Plan

1. Introduce the market observation contract and persistence support
2. Refactor the market snapshot path to assemble from normalized observations
3. Add deterministic regime extraction and a regime-led mainline assembly contract
4. Add secondary-context surfacing so important but unconfirmed events remain visible without polluting confirmed mainlines
5. Wire regime outputs into analysis, handoff, MMU, and dashboard-facing payloads with additive compatibility
6. Add ticker enrichment triggers and persistence
7. Extend readiness, health, validation, and documentation

## Remaining Non-Blocking Questions

- Should a later phase promote regime evaluations into a standalone persisted table for analytics and replay?
- Should premium enrichment eventually receive dedicated read APIs after report/MMU contracts stabilize?
