# Frontend V1 API And Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend-facing `v1` API layer plus accurate integration and technical documentation for a professional news dashboard.

**Architecture:** Keep existing capture and handoff contracts intact, and add a thin presentation service that reshapes already-validated item data into frontend-friendly dashboard, list, detail, and source-summary responses. Write docs only after the new API responses are implemented and sampled from the running app so field descriptions and examples match reality.

**Tech Stack:** FastAPI, existing capture/handoff services, SQLite repository, pytest

---

### Task 1: Freeze The Frontend API Contract In Tests

**Files:**
- Create: `tests/test_frontend_api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for `/api/v1/dashboard`**

Cover:
- hero counts
- `lead_signals`, `watchlist`, `background`
- source health summary presence

- [ ] **Step 2: Run the targeted tests to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_frontend_api.py -v`
Expected: FAIL because endpoints do not exist yet

- [ ] **Step 3: Write failing tests for `/api/v1/news`, `/api/v1/news/{item_id}`, `/api/v1/sources`**

Cover:
- tab/filter/search behavior
- cursor pagination shape
- detail payload for one item
- source summary counts

- [ ] **Step 4: Re-run targeted tests to confirm correct failures**

Run: `./.venv/bin/python -m pytest tests/test_frontend_api.py tests/test_api.py::test_refresh_and_handoff_endpoints_expose_captured_news_with_source_metadata -v`
Expected: FAIL on missing routes or missing fields

### Task 2: Add A Focused Frontend API Service

**Files:**
- Create: `app/services/frontend_api.py`
- Modify: `app/repository.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add the minimal repository helpers required by the new API**

Helpers:
- fetch one item row by `item_id`
- fetch a bounded recent pool for filtering/search

- [ ] **Step 2: Implement the frontend presentation service with minimal logic**

Methods:
- `get_dashboard(...)`
- `list_news(...)`
- `get_news_item(...)`
- `list_sources(...)`

Rules:
- never recompute capture logic
- reuse existing rendered item shape from `OvernightSourceCaptureService`
- preserve `analysis_status`, `analysis_confidence`, `analysis_blockers`, `evidence_points`

- [ ] **Step 3: Wire new `v1` routes in `app/main.py`**

Routes:
- `GET /api/v1/dashboard`
- `GET /api/v1/news`
- `GET /api/v1/news/{item_id}`
- `GET /api/v1/sources`
- keep existing routes unchanged

- [ ] **Step 4: Run targeted tests until green**

Run: `./.venv/bin/python -m pytest tests/test_frontend_api.py tests/test_api.py::test_refresh_and_handoff_endpoints_expose_captured_news_with_source_metadata -v`
Expected: PASS

### Task 3: Write Frontend Integration Documentation

**Files:**
- Create: `docs/api/frontend-v1-integration.md`

- [ ] **Step 1: Capture live JSON samples from the new routes**

Commands:
- `GET /api/v1/dashboard`
- `GET /api/v1/news`
- `GET /api/v1/news/{item_id}`
- `GET /api/v1/sources`

- [ ] **Step 2: Write the integration doc from implemented behavior**

Include:
- endpoint list
- query params
- response shapes
- field semantics
- frontend rendering guidance
- which sections are primary vs secondary news

- [ ] **Step 3: Double-check every field name against code and sample output**

Expected: doc matches actual route behavior exactly

### Task 4: Write Technical Documentation

**Files:**
- Create: `docs/technical/frontend-api-architecture.md`

- [ ] **Step 1: Document service boundaries and data flow**

Cover:
- repository -> capture service -> frontend API service -> FastAPI route
- why `analysis_status` and `evidence_points` exist
- what the frontend can trust vs what still needs review

- [ ] **Step 2: Document sorting, filtering, and guardrail rules**

Cover:
- `ready/review/background`
- official vs editorial ordering
- pagination model
- known limitations

- [ ] **Step 3: Cross-check technical docs against implementation and tests**

Expected: no undocumented behavior, no stale field names

### Task 5: Verify End-To-End

**Files:**
- Modify: none unless verification reveals gaps

- [ ] **Step 1: Run the full test suite**

Run: `./.venv/bin/python -m pytest tests -q`
Expected: all tests pass

- [ ] **Step 2: Hit the real `v1` routes and inspect payload quality**

Check:
- dashboard splits `ready/review/background` correctly
- `news` endpoint can still expose “other news”
- docs reflect real sample payloads

- [ ] **Step 3: Summarize delivered routes, docs, and residual risks**

Residual risks should mention:
- bounded recent pool vs fully indexed search
- editorial `review` items still needing confirmation
