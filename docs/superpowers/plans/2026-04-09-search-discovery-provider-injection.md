# Search Discovery Provider Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an env-backed search discovery layer so the overnight project can supplement blocked/low-yield official sources with authoritative same-domain search results and use locally configured provider keys when available.

**Architecture:** Keep the existing collector flow as the primary path. Add a separate search discovery service that reads optional provider keys from the environment, normalizes provider results into `SourceCandidate`, and supplements only sources that explicitly opt in through registry metadata. This preserves the current event/mainline/analysis pipeline while widening capture coverage for blocked sites.

**Tech Stack:** Python 3.12, requests, pytest, existing source-capture pipeline

---

### Task 1: Add failing tests for search discovery and source fallback

**Files:**
- Create: `tests/test_search_discovery.py`
- Modify: `tests/test_collectors.py`
- Modify: `tests/test_api.py`

- [x] **Step 1: Write failing tests for environment parsing and provider result normalization**

- [x] **Step 2: Run the focused tests and verify they fail for the missing search discovery layer**

Run: `./.venv/bin/python -m pytest tests/test_search_discovery.py -q`
Expected: FAIL because the search discovery service does not exist yet.

- [x] **Step 3: Write failing tests for source-capture supplementation**

Cover:
- direct collector returns no candidates
- registry source is search-enabled
- search discovery returns allowed-domain candidates
- refresh persists those candidates as normal items

- [x] **Step 4: Run the affected tests**

Run: `./.venv/bin/python -m pytest tests/test_collectors.py tests/test_api.py tests/test_search_discovery.py -q`
Expected: FAIL because source capture does not yet call a search supplement.

### Task 2: Implement the env-backed search discovery service

**Files:**
- Create: `app/services/search_discovery.py`
- Modify: `app/sources/types.py`
- Modify: `app/sources/registry.py`
- Modify: `app/services/source_capture.py`

- [x] **Step 1: Add the minimal source metadata needed for opt-in search supplementation**

Add fields for:
- `search_discovery_enabled`
- `search_queries`

- [x] **Step 2: Implement lightweight provider clients with no new runtime dependency**

Support:
- `Tavily`
- `Bocha`
- `Brave`
- `SerpAPI`

Requirements:
- comma-separated multi-key parsing
- provider priority order
- same-domain filtering against `allowed_domains`
- bounded result count

- [x] **Step 3: Wire the service into `OvernightSourceCaptureService`**

Rules:
- primary collector still runs first
- search discovery only runs for opt-in sources
- search discovery supplements when the primary path is empty or thin
- duplicate URLs are removed before persistence

- [x] **Step 4: Update strategic blocked sources to use search discovery**

Initial registry targets:
- `bls_news_releases`
- `state_spokesperson_releases`
- `dod_news_releases`

Optional supplement targets:
- `treasury_press_releases`
- `ustr_press_releases`

### Task 3: Verify the new behavior end-to-end

**Files:**
- Add: `docs/technical/search-discovery-supplement-architecture.md`

- [x] **Step 1: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_search_discovery.py tests/test_collectors.py tests/test_api.py -q`
Expected: PASS

- [x] **Step 2: Run the full suite**

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS

- [x] **Step 3: Run live smoke with local provider env if available**

Use the local JusticePlutus env files only as command-time environment injection, not as an application dependency.

Verify:
- provider keys are detected without printing secret values
- at least one blocked source now yields same-domain candidates through search discovery

- [x] **Step 4: Update docs to describe the new discovery layer**

Document:
- primary collector vs search supplement
- env var names
- source-level opt-in semantics
