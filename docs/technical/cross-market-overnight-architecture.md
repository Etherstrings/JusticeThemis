# Cross-Market Overnight Architecture

This document describes the target architecture for the repositioned `JusticeThemis` project.

It is a forward-looking technical contract, not just a description of the current implementation.

For the detailed provider research behind `source acquisition` and `cross-market structured data`, see:

- [2026-04-09-source-acquisition-and-cross-market-data-research.md](2026-04-09-source-acquisition-and-cross-market-data-research.md)
- [2026-04-09-live-validation-runbook.md](2026-04-09-live-validation-runbook.md)

## Purpose

The system exists to solve one China-morning workflow:

1. capture what already happened overnight in U.S. and global markets
2. capture the official and market news that best explains those moves
3. consolidate the overnight story into a small number of mainlines
4. map those mainlines into free direction output and premium stock recommendations

The system is therefore:

- result-first
- cross-market
- official-first on facts
- staged in its model-facing logic

It is not:

- a generic news reader
- a pure U.S.-equity dashboard
- a single-prompt summarizer
- a prediction engine for unfinished sessions

## Core Runtime Layers

The architecture should be understood as eight runtime layers.

### 1. Source Registry

Owns the source universe and capture metadata.

Responsibilities:

- identify what to track
- assign priority and polling hints
- define source class and source authority
- bind sources to mainline buckets and asset tags
- define allowed domains and entry types

Typical source groups:

- `official_policy`
- `official_data`
- `market_media`
- `market_data`
- `commodity_data`

### 2. Capture Engine

Owns raw acquisition.

Responsibilities:

- RSS feed ingestion
- section-page discovery
- article-page expansion
- attachment discovery
- market-data fetching
- retries and fallbacks
- payload hashing and raw-capture traceability

Capture must be broad. It should not collapse broad capture into model-facing payloads directly.

### 3. Normalization Layer

Owns deterministic cleanup and structure.

Responsibilities:

- canonical URL resolution
- publication-time normalization
- title and summary normalization
- body extraction and boilerplate filtering
- document typing
- entity extraction
- numeric fact extraction
- evidence extraction
- source-domain validation

This layer should remain deterministic and auditable.

### 4. Asset Engine

Owns overnight market and commodity results.

Responsibilities:

- collect market closes and relevant end-of-session states
- persist cross-asset snapshots
- normalize displays and raw values
- derive simple trend labels
- produce the `Market Board`

This is a first-class subsystem, not a supporting utility.

### 5. Event Engine

Owns event construction from normalized items.

Responsibilities:

- cluster related source items
- choose primary source items
- attach supporting sources
- record event-level facts and conflicts
- bind events to affected assets and mainline buckets

An event is the unit of overnight memory. A single source item is not.

### 6. Mainline Engine

Owns overnight ranking and explanation structure.

Responsibilities:

- rank overnight event clusters
- link event clusters to market results
- produce the `Mainline Set`
- ensure important asset moves have matching mainlines

This layer prevents the product from forgetting the actual overnight story.

### 7. Analysis Engine

Owns free and premium output generation.

Responsibilities:

- build the free result-first morning analysis
- build the premium recommendation package
- keep both outputs grounded in the same facts
- expose recommendation evidence, risks, and trigger conditions

This layer should sit on top of Market Board + Events + Mainlines, not directly on raw news items.

### 8. Delivery Layer

Owns presentation and downstream packaging.

Responsibilities:

- frontend API
- dashboard responses
- search and detail responses
- fixed daily-analysis responses
- staged MMU handoff payloads
- export and inspection surfaces

## Product Objects

The architecture should produce six top-level daily objects.

### Market Board

The first object a user or downstream model should read.

Contains:

- U.S. index results
- sector proxy results
- core technology leaders and laggards
- rates and FX
- precious metals
- energy
- industrial metals
- China-mapped futures directions

Primary question answered:

- what already happened?

### Mainline Set

The ranked set of 8-12 overnight themes.

Primary question answered:

- what explains the overnight move?

### Important News Set

The 30-50 normalized source items worth browsing directly.

Primary question answered:

- what evidence should the user inspect beneath the mainlines?

### Full News Pool

The complete raw-to-normalized evidence pool.

Primary question answered:

- what did we capture, even if it did not make the top of the stack?

### Free Analysis

The free result-first readout.

Primary question answered:

- what matters for China-facing users at a high level?

### Premium Analysis

The evidence-backed recommendation layer.

Primary question answered:

- what deeper supply-chain, commodity, and stock implications follow from the same fact base?

## Result-First Ordering Rule

Every consumer-facing and model-facing flow should obey this order:

1. `Market Board`
2. `Mainline Set`
3. `Important News Set`
4. `Full News Pool`
5. `Free Analysis`
6. `Premium Analysis`

If a page, prompt, or payload starts from raw news instead of results, the architecture has drifted.

## Asset Coverage Model

The architecture should treat these asset groups as first-class.

### U.S. Equity Results

- `SPX`
- `NDX`
- `DJI`
- `RUT`
- `VIX`

### Sector and Style Proxies

- `XLK`
- `SOXX`
- `XLF`
- `XLE`
- `XLI`
- additional major sector/style proxies as needed

### Core Technology Watchlist

Representative names such as:

- `NVDA`
- `AMD`
- `MSFT`
- `AAPL`
- `AVGO`
- `TSM`
- `AMZN`
- `META`

### Rates and FX

- `US2Y`
- `US10Y`
- `DXY`
- `USD/CNH`

### Precious Metals

- gold
- silver

### Energy

- WTI
- Brent
- natural gas

### Industrial Metals

- copper
- aluminum

### China-Mapped Futures

The system should carry China-facing mapping outputs for:

- methanol
- ethylene glycol
- PX
- PTA
- soda ash
- glass
- lithium carbonate
- industrial silicon

These do not need to originate from the same data vendor as U.S. assets, but they must exist as output objects.

## Mainline Buckets

Every event and important news item should map to one or more of these buckets:

- `rates_liquidity`
- `trade_export_control`
- `geopolitics_energy`
- `macro_data`
- `tech_semiconductor`
- `precious_metals_safe_haven`
- `industrials_chemicals`
- `shipping_logistics`

These buckets power ranking, memory, attribution, and display grouping.

## Data Flow

The daily flow should look like this:

1. `Capture Engine` gathers source items and market data.
2. `Normalization Layer` turns raw payloads into normalized items and asset rows.
3. `Asset Engine` builds the Market Board.
4. `Event Engine` clusters normalized items into event records.
5. `Mainline Engine` ranks event records against market outcomes.
6. `Delivery Layer` emits Important News, Full News, and MMU payloads.
7. `Analysis Engine` builds Free Analysis and Premium Analysis.

Nothing downstream should bypass this order.

## Persistence Model

The current SQLite-backed storage remains appropriate and should be extended instead of replaced.

Persisted layers should include:

- raw capture records
- normalized source items
- document families and versions
- market snapshots
- derived daily-analysis reports

The redesign should add or evolve persistence for:

- asset-board-ready cross-asset snapshots
- explicit event records when they become stable enough to store
- mainline records if versioning or auditability requires it

## MMU Integration Boundary

The architecture explicitly avoids one giant prompt.

The MMU boundary should receive compact, typed, staged payloads:

- single-item understanding
- event consolidation
- market attribution
- premium recommendation

The MMU should not be responsible for:

- raw crawling
- HTML cleanup
- canonicalization
- direct storage concerns
- reconstructing the overnight result board from scratch

## Reuse Policy

The redesign should preserve and extend the strongest existing code:

- collectors
- normalization
- source validation
- repository and database layers
- evidence extraction
- existing market snapshot persistence skeleton

The redesign should demote or replace brittle top-layer heuristics:

- overconfident rule-based direction mapping
- item-first ordering that loses overnight mainlines
- recommendation logic that is insufficiently tied to market outcomes

## Failure Model

The architecture should degrade gracefully.

### If market data fails

- keep news capture running
- surface the missing result layer explicitly
- avoid pretending a result-first analysis still exists

### If official sources fail

- keep market results and media context available
- downgrade confidence on factual attribution

### If media sources fail

- keep official sources and asset results
- reduce interpretive depth, not factual core

### If one MMU stage fails

- preserve prior stage outputs
- avoid collapsing the entire morning product

## Engineering Guidance

Implementation should preserve the current standalone boundary:

- no dependency on unrelated projects
- no dependence on the prior daily stock analysis app
- no rewriting of stable capture components without strong reason

The system should evolve top-down:

1. document contracts
2. shape outputs
3. align services
4. then refine heuristics

## Success Conditions

The architecture is working when:

- the first thing the user sees is the overnight result board
- mainlines explain the move instead of merely listing recent news
- official facts, market reactions, and commodity reactions live in one coherent system
- free output is immediately useful
- premium output is deeper but obviously derived from the same facts
- the existing collector and normalization code remains a durable asset rather than discarded effort
