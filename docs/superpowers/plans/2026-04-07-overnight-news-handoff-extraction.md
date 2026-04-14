# Overnight News Handoff Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the validated overnight news-capture core into a standalone project that captures authoritative sources and emits an official-first LLM handoff package.

**Architecture:** Build a new Python/FastAPI app with isolated source, collector, storage, capture, and handoff modules. Port only the proven capture core and its tests, then add a minimal UI for inspection and JSON export.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/SQLite, requests, feedparser, BeautifulSoup, pytest, Vite/React/TypeScript

---

## File Structure

- Create: `overnight-news-handoff/pyproject.toml`
- Create: `overnight-news-handoff/README.md`
- Create: `overnight-news-handoff/.gitignore`
- Create: `overnight-news-handoff/app/main.py`
- Create: `overnight-news-handoff/app/config.py`
- Create: `overnight-news-handoff/app/db.py`
- Create: `overnight-news-handoff/app/storage.py`
- Create: `overnight-news-handoff/app/sources/types.py`
- Create: `overnight-news-handoff/app/sources/registry.py`
- Create: `overnight-news-handoff/app/collectors/base.py`
- Create: `overnight-news-handoff/app/collectors/feed.py`
- Create: `overnight-news-handoff/app/collectors/section.py`
- Create: `overnight-news-handoff/app/collectors/calendar.py`
- Create: `overnight-news-handoff/app/collectors/article.py`
- Create: `overnight-news-handoff/app/normalizer.py`
- Create: `overnight-news-handoff/app/ledger.py`
- Create: `overnight-news-handoff/app/services/source_excerpt.py`
- Create: `overnight-news-handoff/app/services/source_capture.py`
- Create: `overnight-news-handoff/app/services/handoff.py`
- Create: `overnight-news-handoff/app/api/routes.py`
- Create: `overnight-news-handoff/app/api/schemas.py`
- Create: `overnight-news-handoff/web/src/App.tsx`
- Create: `overnight-news-handoff/web/src/api.ts`
- Create: `overnight-news-handoff/web/src/types.ts`
- Create: `overnight-news-handoff/tests/test_api.py`
- Create: `overnight-news-handoff/tests/test_collectors.py`
- Create: `overnight-news-handoff/tests/test_source_excerpt.py`
- Create: `overnight-news-handoff/tests/test_source_capture.py`
- Create: `overnight-news-handoff/tests/test_handoff.py`

## Task 1: Scaffold the standalone project

**Files:**
- Create: `overnight-news-handoff/tests/test_api.py`
- Create: `overnight-news-handoff/app/main.py`
- Create: `overnight-news-handoff/pyproject.toml`

- [ ] **Step 1: Write the failing test**

Add a smoke test that imports the FastAPI app and expects `/items` to return `200` with an empty payload.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_api.py::test_items_endpoint_returns_empty_payload_initially -v`
Expected: FAIL because the app does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the project root, minimal FastAPI app, and placeholder route returning `{ "total": 0, "items": [] }`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_api.py::test_items_endpoint_returns_empty_payload_initially -v`
Expected: PASS

## Task 2: Port source registry and collectors

**Files:**
- Create: `overnight-news-handoff/app/sources/*`
- Create: `overnight-news-handoff/app/collectors/*`
- Create: `overnight-news-handoff/tests/test_collectors.py`
- Create: `overnight-news-handoff/tests/fixtures/overnight/*`

- [ ] **Step 1: Write the failing tests**

Port collector tests covering RSS parsing, section-page extraction, relative-link resolution, article-shell expansion, and multiple entry URLs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_collectors.py -v`
Expected: FAIL because collectors are not implemented.

- [ ] **Step 3: Write minimal implementation**

Port the collector logic from the old project and rewrite imports to local modules only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_collectors.py -v`
Expected: PASS

## Task 3: Add normalization and standalone storage

**Files:**
- Create: `overnight-news-handoff/app/normalizer.py`
- Create: `overnight-news-handoff/app/ledger.py`
- Create: `overnight-news-handoff/app/db.py`
- Create: `overnight-news-handoff/app/storage.py`
- Create: `overnight-news-handoff/tests/test_source_capture.py`

- [ ] **Step 1: Write the failing test**

Add tests that persist a normalized source item and assert published time, entities, and numeric facts are stored.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_source_capture.py::test_persisted_source_item_keeps_published_time_and_entities -v`
Expected: FAIL because storage and normalization are missing.

- [ ] **Step 3: Write minimal implementation**

Build a standalone SQLite-backed storage layer and port the normalizer logic required by the capture flow.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_source_capture.py::test_persisted_source_item_keeps_published_time_and_entities -v`
Expected: PASS

## Task 4: Add resilient source capture services

**Files:**
- Create: `overnight-news-handoff/app/services/source_excerpt.py`
- Create: `overnight-news-handoff/app/services/source_capture.py`
- Create: `overnight-news-handoff/tests/test_source_excerpt.py`
- Modify: `overnight-news-handoff/tests/test_source_capture.py`

- [ ] **Step 1: Write the failing tests**

Add tests for transient SSL EOF retry, multi-source refresh, and richer recent-item metadata.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_source_excerpt.py tests/test_source_capture.py -v`
Expected: FAIL because services are incomplete.

- [ ] **Step 3: Write minimal implementation**

Port the retrying HTTP client, article excerpt cache, capture refresh logic, and recent-item rendering.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_source_excerpt.py tests/test_source_capture.py -v`
Expected: PASS

## Task 5: Add official-first handoff service and API

**Files:**
- Create: `overnight-news-handoff/app/services/handoff.py`
- Create: `overnight-news-handoff/app/api/schemas.py`
- Create: `overnight-news-handoff/app/api/routes.py`
- Modify: `overnight-news-handoff/app/main.py`
- Create: `overnight-news-handoff/tests/test_handoff.py`
- Modify: `overnight-news-handoff/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert `/handoff` exists, official sources are ordered before editorial media, pool widening happens before truncation, and prompt scaffold is included.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_handoff.py tests/test_api.py -v`
Expected: FAIL because handoff logic and routes do not exist.

- [ ] **Step 3: Write minimal implementation**

Extract and localize the official-first handoff logic, then expose `/refresh`, `/items`, and `/handoff`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_handoff.py tests/test_api.py -v`
Expected: PASS

## Task 6: Build the lightweight inspection UI

**Files:**
- Create: `overnight-news-handoff/web/package.json`
- Create: `overnight-news-handoff/web/src/main.tsx`
- Create: `overnight-news-handoff/web/src/App.tsx`
- Create: `overnight-news-handoff/web/src/api.ts`
- Create: `overnight-news-handoff/web/src/types.ts`

- [ ] **Step 1: Run build to verify failure**

Run: `npm --prefix web run build`
Expected: FAIL because the web app does not exist.

- [ ] **Step 2: Write minimal implementation**

Create a lightweight React page focused only on refresh, captured items, source attribution, and handoff JSON.

- [ ] **Step 3: Run build to verify it passes**

Run: `npm --prefix web run build`
Expected: PASS

## Task 7: Live validation

- [ ] **Step 1: Run the full suite**

Run: `./.venv/bin/python -m pytest tests -q`
Expected: PASS

- [ ] **Step 2: Run live refresh probe**

Run a standalone refresh and confirm official-first handoff output contains official items ahead of editorial items.
