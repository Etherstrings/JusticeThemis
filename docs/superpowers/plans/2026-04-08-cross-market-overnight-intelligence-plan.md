# Cross-Market Overnight Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reposition the standalone overnight-news-handoff project into a result-first cross-market overnight system covering international news, U.S. market results, commodities, China-facing futures mapping, free analysis, and premium stock recommendations.

**Architecture:** Preserve and extend the current capture, normalization, and persistence layers. Rebuild the top of the stack around a Market Board, event clusters, ranked mainlines, and staged MMU handoff payloads so the product stops over-relying on brittle rule-based direction mapping.

**Tech Stack:** Python 3.12, pytest, SQLite, FastAPI-compatible service layer, requests, feedparser, BeautifulSoup/lxml

---

## File Structure

- Create: `docs/technical/cross-market-overnight-architecture.md`
- Create: `docs/api/mmu-handoff-v1.md`
- Modify: `app/sources/registry.py`
- Modify: `app/sources/types.py`
- Modify: `app/services/source_capture.py`
- Modify: `app/services/market_snapshot.py`
- Create: `app/services/asset_board.py`
- Create: `app/services/event_engine.py`
- Create: `app/services/mainline_engine.py`
- Create: `app/services/mmu_handoff.py`
- Modify: `app/services/handoff.py`
- Modify: `app/services/daily_analysis.py`
- Modify: `app/services/daily_analysis_provider.py`
- Modify: `app/services/frontend_api.py`
- Modify: `app/main.py`
- Modify: `app/repository.py`
- Modify: `app/db.py`
- Modify: `tests/test_collectors.py`
- Modify: `tests/test_market_snapshot.py`
- Create: `tests/test_asset_board.py`
- Create: `tests/test_event_engine.py`
- Create: `tests/test_mainline_engine.py`
- Create: `tests/test_mmu_handoff.py`
- Modify: `tests/test_daily_analysis.py`
- Modify: `tests/test_frontend_api.py`

## Task 1: Freeze the top-down architecture and delivery contracts

**Files:**
- Create: `docs/technical/cross-market-overnight-architecture.md`
- Create: `docs/api/mmu-handoff-v1.md`
- Modify: `docs/api/frontend-v1-integration.md`
- Modify: `docs/api/daily-analysis-v1.md`
- Modify: `docs/api/market-snapshot-v1.md`

- [ ] **Step 1: Write the architecture document**

Document:

- Market Board
- Mainline Set
- Important News Set
- Full News Pool
- Free Analysis
- Premium Analysis
- staged MMU roles
- result-first ordering rules

- [ ] **Step 2: Write the MMU handoff contract**

Define fixed JSON payload shapes for:

- `MMU-1 single_item_understanding`
- `MMU-2 event_consolidation`
- `MMU-3 market_attribution`
- `MMU-4 premium_recommendation`

- [ ] **Step 3: Update public API docs**

Revise the existing docs so they describe:

- cross-market result-first semantics
- expanded asset coverage
- free vs premium boundaries
- event and mainline identifiers

- [ ] **Step 4: Review docs for consistency**

Read all affected docs and make terminology consistent:

- `mainline`
- `event cluster`
- `market board`
- `important news`
- `premium recommendation`

## Task 2: Expand the source registry into a cross-market registry

**Files:**
- Modify: `app/sources/types.py`
- Modify: `app/sources/registry.py`
- Modify: `tests/test_collectors.py`

- [ ] **Step 1: Write failing tests for new registry metadata**

Add tests proving registry entries can express:

- source tier
- source group
- content mode
- asset tags
- mainline tags

- [ ] **Step 2: Run registry-related tests to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_collectors.py -q`
Expected: FAIL because new metadata does not exist yet.

- [ ] **Step 3: Implement minimal registry type extensions**

Extend `SourceDefinition` and registry construction to support:

- new official strategic sources
- new policy/data/commodity grouping
- explicit metadata needed by mainline ranking

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_collectors.py -q`
Expected: PASS

## Task 3: Upgrade market snapshots into a cross-asset Market Board

**Files:**
- Modify: `app/services/market_snapshot.py`
- Create: `app/services/asset_board.py`
- Modify: `app/repository.py`
- Modify: `app/db.py`
- Modify: `tests/test_market_snapshot.py`
- Create: `tests/test_asset_board.py`

- [ ] **Step 1: Write failing tests for expanded asset coverage**

Add tests that require the market layer to carry:

- indexes
- sector proxies
- rates and FX
- precious metals
- energy
- industrial metals
- China-mapped futures directions

- [ ] **Step 2: Run the focused market tests**

Run: `./.venv/bin/python -m pytest tests/test_market_snapshot.py tests/test_asset_board.py -q`
Expected: FAIL because the current snapshot covers only a smaller U.S. equity set and no dedicated asset-board object.

- [ ] **Step 3: Implement minimal Market Board support**

Keep the existing snapshot machinery but:

- expand instruments and buckets
- add provider-fallback seams
- build a reusable `asset_board` object for downstream services

- [ ] **Step 4: Re-run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_market_snapshot.py tests/test_asset_board.py -q`
Expected: PASS

## Task 4: Separate event clustering from result interpretation

**Files:**
- Create: `app/services/event_engine.py`
- Modify: `app/services/source_capture.py`
- Create: `tests/test_event_engine.py`

- [ ] **Step 1: Write failing tests for explicit event records**

Add tests that require:

- event ids
- event status
- affected assets
- official-source counts
- event-level key facts

- [ ] **Step 2: Run event-engine tests**

Run: `./.venv/bin/python -m pytest tests/test_event_engine.py -q`
Expected: FAIL because event logic is currently embedded inside capture enrichment instead of a standalone engine.

- [ ] **Step 3: Implement the minimal event engine**

Extract event-building into a focused service that consumes normalized items and emits explicit event records.

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_event_engine.py tests/test_source_capture.py -q`
Expected: PASS

## Task 5: Introduce a ranked Mainline Engine

**Files:**
- Create: `app/services/mainline_engine.py`
- Modify: `app/services/handoff.py`
- Create: `tests/test_mainline_engine.py`

- [ ] **Step 1: Write failing tests for result-first mainline ranking**

Add tests proving:

- mainlines require asset linkage
- official sources outrank media on fact authority
- technology, energy, and rates mainlines appear when corresponding assets move materially

- [ ] **Step 2: Run mainline tests to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_mainline_engine.py -q`
Expected: FAIL because the project currently ranks enriched items rather than explicit overnight mainlines.

- [ ] **Step 3: Implement the minimal mainline engine**

Build ranked mainlines from:

- Market Board
- event records
- source authority
- confirmation counts

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_mainline_engine.py tests/test_handoff.py -q`
Expected: PASS

## Task 6: Build staged MMU handoff payloads

**Files:**
- Create: `app/services/mmu_handoff.py`
- Modify: `app/services/handoff.py`
- Create: `tests/test_mmu_handoff.py`

- [ ] **Step 1: Write failing tests for all four MMU payload builders**

Add tests for:

- single-item handoff
- event handoff
- market-attribution handoff
- premium recommendation handoff

- [ ] **Step 2: Run the MMU handoff tests**

Run: `./.venv/bin/python -m pytest tests/test_mmu_handoff.py -q`
Expected: FAIL because no dedicated MMU handoff service exists yet.

- [ ] **Step 3: Implement the minimal handoff builders**

Produce compact structured payloads with explicit length controls and fixed field order.

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_mmu_handoff.py tests/test_handoff.py -q`
Expected: PASS

## Task 7: Rebuild free analysis and premium recommendations on top of Market Board + Mainlines

**Files:**
- Modify: `app/services/daily_analysis.py`
- Modify: `app/services/daily_analysis_provider.py`
- Modify: `tests/test_daily_analysis.py`

- [ ] **Step 1: Write failing tests for result-first analysis semantics**

Add tests proving:

- free output starts from overnight market results
- premium output reuses the same mainlines
- recommendations require event and asset evidence
- commodity and futures directions appear alongside China sector directions

- [ ] **Step 2: Run daily-analysis tests**

Run: `./.venv/bin/python -m pytest tests/test_daily_analysis.py -q`
Expected: FAIL because the current provider still leans on rule-based item direction aggregation.

- [ ] **Step 3: Implement minimal provider changes**

Keep report caching and versioning, but rebuild the content pipeline to consume:

- Market Board
- event records
- ranked mainlines
- staged recommendation mapping

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_daily_analysis.py -q`
Expected: PASS

## Task 8: Update API and frontend delivery for the new product shape

**Files:**
- Modify: `app/services/frontend_api.py`
- Modify: `app/main.py`
- Modify: `tests/test_frontend_api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for result-first delivery**

Add tests proving the read layer exposes:

- Market Board
- mainlines
- important news
- free/premium analysis separation

- [ ] **Step 2: Run API/frontend tests**

Run: `./.venv/bin/python -m pytest tests/test_frontend_api.py tests/test_api.py -q`
Expected: FAIL because the current responses are item-centric and not yet organized around the new product contracts.

- [ ] **Step 3: Implement minimal delivery changes**

Expose new response blocks while preserving backward-compatible fields where reasonable.

- [ ] **Step 4: Re-run tests**

Run: `./.venv/bin/python -m pytest tests/test_frontend_api.py tests/test_api.py -q`
Expected: PASS

## Task 9: Full verification

**Files:**
- Modify: none

- [ ] **Step 1: Run the full suite**

Run: `./.venv/bin/python -m pytest tests -q`
Expected: PASS

- [ ] **Step 2: Run a real overnight dry run in a temporary database**

Run a one-shot script that:

- refreshes news
- refreshes market assets
- builds event records
- builds mainlines
- generates free and premium outputs

Expected:

- the pipeline completes without relying on one giant prompt
- the first screen is the Market Board
- the resulting mainlines explain the overnight move better than the prior item-first flow

- [ ] **Step 3: Review for reuse discipline**

Confirm the implementation reuses:

- collectors
- normalization
- storage
- evidence extraction
- API shell

and does not discard working capture code unnecessarily.
