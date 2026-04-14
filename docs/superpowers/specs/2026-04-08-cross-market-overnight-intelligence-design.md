# Cross-Market Overnight Intelligence Design

**Date:** 2026-04-08

**Status:** Supersedes the earlier "overnight news handoff" positioning. This document freezes the product as a cross-market overnight capture, attribution, and recommendation system.

## Goal

Build a standalone product for China-morning use that answers four questions in order:

1. What already happened in U.S. and global markets overnight?
2. Which international policy, macro, geopolitics, technology, and commodity news best explains that result?
3. Which cross-market mainlines matter most right now?
4. How should those mainlines be mapped into China-facing sector, commodity, and paid-stock outputs?

The product is not a generic news app and not a discretionary prediction engine. It is a result-first overnight replay and mapping system.

## Product Positioning

### Core Promise

By the time the user opens the product in China morning hours, the relevant U.S. session has already played out. The product must therefore start with the completed market result, then attribute that result to the most important overnight events, then map the confirmed mainlines into China-facing directions and paid recommendations.

### Free Tier

The free tier must provide enough detail to understand the overnight move without hiding the evidence:

- a market result board
- 8-12 top mainlines
- 30-50 important news items
- simple China-facing direction calls
- commodity and futures watch directions
- source links and exact timestamps

### Premium Tier

The premium tier builds on the same fact base and must not invent a separate logic stack. It adds:

- deeper event attribution
- sector and supply-chain decomposition
- commodity-chain decomposition
- 10-25 stock recommendations
- recommendation evidence, risk points, and trigger conditions

## Operating Principles

### 1. Result First

The system must always begin with already-finished market outcomes:

- indexes
- sectors
- core technology proxies
- rates and FX
- precious metals
- energy
- industrial metals
- China-mapped futures and chemical chains

News exists to explain results. News does not replace results.

### 2. Official First, Market Explanation Second

Primary official sources anchor facts. Major media sources explain market interpretation and fast-moving context. Media sources must not outrank official sources on factual authority.

### 3. Mainlines Over Headlines

The product should remember 8-12 mainlines, not 100 disconnected headlines. Every important news item should map into:

- one event cluster
- one mainline bucket
- one or more affected assets

### 4. Capture Broadly, Send Narrowly

The raw collection layer should be broad. The model-facing handoff layer should be narrow and structured.

- Raw daily pool target: 80-200 items
- Important news target: 30-50 items
- Event cluster target: 20-50 clusters
- Mainline target: 8-12 items

### 5. Shared Facts Across Free and Premium

Free and premium outputs should be different presentations over one shared overnight fact base. Premium adds depth and recommendation resolution, not a different worldview.

## Daily Output Objects

The system should produce six fixed outputs per analysis date.

### 1. Market Board

The first screen. Includes:

- indexes: SPX, NDX, DJI, RUT, VIX
- sectors: XLK, SOXX, XLF, XLE, XLI, and other major proxies
- core technology leaders and laggards
- rates and FX: US2Y, US10Y, DXY, USD/CNH
- precious metals: gold, silver
- energy: WTI, Brent, natural gas
- industrial metals: copper, aluminum
- China-mapped futures directions: methanol, ethylene glycol, PX, PTA, soda ash, glass, lithium carbonate, industrial silicon

The Market Board should answer:

- what led
- what lagged
- what cross-asset linkage was visible

### 2. Mainline Set

The ranked set of 8-12 overnight mainlines. Each mainline should include:

- a short headline
- mainline bucket
- primary sources
- supporting sources
- why it matters now
- linked assets
- market effect summary
- China mapping summary
- confidence

### 3. Important News Set

The 30-50 news items the user may want to inspect directly. Each item should include:

- title
- source
- exact time
- 200-400 word normalized summary
- numeric facts
- event and mainline links
- raw URL

### 4. Full News Pool

The complete captured pool with raw evidence retained for search, review, export, and later model use.

### 5. Free Analysis

Structured result-first analysis that covers:

- market recap
- mainline recap
- China-facing beneficiary directions
- pressured directions
- price-up or cost-push directions
- commodity and futures watch directions
- open confirmation items

### 6. Premium Analysis

The premium product extends the free output with:

- deeper mainline decomposition
- sector and supply-chain mapping
- commodity-chain mapping
- stock recommendation set
- risk and trigger scaffolding

## Coverage Model

### A. International Policy and Strategic Sources

These sources establish first-order policy and geopolitical facts:

- White House
- Federal Reserve
- USTR
- Treasury
- Commerce
- BIS
- OFAC
- State
- DoD
- DOE

### B. Official Data Sources

These sources anchor macro and commodity facts:

- BLS
- BEA
- Census
- EIA
- Treasury financing and refunding material when relevant

### C. Market Explanation Sources

These sources explain how markets interpreted the overnight move:

- Reuters
- AP
- CNBC

### D. Market and Asset Data Sources

These sources provide deterministic overnight results:

- U.S. indexes and sector ETFs
- core large-cap technology names
- Treasury yields and dollar index
- gold and silver
- crude oil, Brent, natural gas
- copper and aluminum
- China-mapped futures proxies and direction tables

## Mainline Buckets

Every event and important news item should map to at least one of the following buckets:

- `rates_liquidity`
- `trade_export_control`
- `geopolitics_energy`
- `macro_data`
- `tech_semiconductor`
- `precious_metals_safe_haven`
- `industrials_chemicals`
- `shipping_logistics`

These buckets are not cosmetic. They define what the product remembers.

## System Architecture

### 1. Source Registry

Owns:

- source identity
- source tier
- source type
- entry URLs
- polling intervals
- asset tags
- mainline tags
- allowed domains

### 2. Capture Engine

Owns:

- RSS capture
- section-page discovery
- article expansion
- attachment discovery
- market data capture
- retry and fallback logic

### 3. Normalization Layer

Owns:

- canonical URL resolution
- title and summary normalization
- published-time normalization
- document typing
- entity extraction
- numeric fact extraction
- source integrity checks

### 4. Asset Engine

Owns the Market Board and all cross-asset snapshots. This must be separate from news collection.

### 5. Event Engine

Owns:

- event clustering
- supporting-source aggregation
- conflict markers
- event-level facts
- event-to-asset linkage

### 6. Mainline Engine

Owns:

- ranking overnight event clusters
- binding them to market results
- selecting the 8-12 top mainlines

### 7. Analysis Engine

Owns:

- free result-first analysis
- premium recommendation output
- stock and commodity mapping layers

### 8. Delivery Layer

Owns:

- APIs
- lightweight inspection UI
- downstream MMU handoff payloads
- export-ready daily payloads

## MMU Strategy

The product should use multiple narrow MMU passes instead of one large undifferentiated prompt.

### MMU-1: Single-Item Understanding

Input:

- one normalized news card
- source metadata
- evidence fields

Output:

- standard summary
- event type
- key facts
- worthiness for event clustering

### MMU-2: Event Consolidation

Input:

- one event cluster candidate
- primary official source
- supporting sources
- market commentary if available

Output:

- canonical event record
- source hierarchy
- conflict notes
- importance hints

### MMU-3: Cross-Market Attribution

Input:

- Market Board
- 10-20 high-value event records

Output:

- overnight mainline ranking
- market attribution summary
- explanation of why technology, energy, metals, or safe havens moved

### MMU-4: Premium Recommendation Layer

Input:

- confirmed mainlines
- China-facing mapping tables
- candidate stock universe

Output:

- premium recommendation set
- evidence-backed stock mapping
- risk conditions and invalidation points

## Input Budget Rules

To keep the system reliable:

- do not send raw full pools to MMUs
- single normalized item summaries should stay compact
- each event cluster should be capped to a small number of sources
- the attribution pass should only see the Market Board plus the top event layer

Capture can be broad. Model input must stay narrow.

## Reuse Strategy

This product should reuse the current standalone codebase aggressively.

### Keep and Extend

- source registry and source type models
- RSS, section, article, calendar, and attachment collectors
- article extraction quality improvements for official sources
- database and repository layers
- normalization and evidence extraction
- market snapshot persistence framework
- lightweight API shell and inspection UI

### Reposition, Do Not Delete

- current event clustering
- current handoff packaging
- current daily-analysis caching and versioning

These are useful skeletons but should be repurposed around result-first mainlines.

### Downgrade

Current hard-coded direction and recommendation logic should become a low-authority hint layer or be replaced by MMU-driven interpretation. The present rule engine is useful for scaffolding but should not remain the final source of judgment.

## Non-Goals

The product should explicitly avoid:

- intraday prediction of unfinished U.S. sessions
- treating every article as equally important
- replacing official facts with media speculation
- using one giant prompt as the primary architecture
- maintaining a separate premium fact base

## Success Criteria

The redesign is successful when:

- the product always starts with completed overnight market results
- international policy, macro, market, and commodity capture all feed one shared overnight fact base
- 8-12 mainlines explain the overnight move without losing access to the broader news pool
- free output is useful on its own
- premium output deepens the same fact base into actionable sector, commodity, and stock recommendations
- existing high-quality capture code is preserved and upgraded rather than discarded
