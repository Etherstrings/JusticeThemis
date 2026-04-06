# Overnight Source Coverage v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the overnight source catalog into a real coverage map and expose source-coverage health in the backend and frontend.

**Architecture:** Keep collection behavior unchanged for now. Extend `SourceDefinition` metadata, propagate the new fields through the API/service layer, derive lightweight coverage summaries in health responses, and update the React panels to render grouped coverage with clear gap messaging.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, React, TypeScript, Vite, unittest

---

## File Structure

- Modify: `src/overnight/types.py`
  - Add minimal source metadata fields required by coverage UI and health summary.
- Modify: `src/overnight/source_registry.py`
  - Seed the expanded source catalog and its coverage metadata.
- Modify: `src/services/overnight_service.py`
  - Return richer source items and derive coverage-tier / gap summaries.
- Modify: `api/v1/schemas/overnight.py`
  - Expose the new source and source-health fields via the API schema.
- Modify: `tests/test_overnight_registry.py`
  - Cover the new default registry shape and expected source ids.
- Modify: `tests/test_overnight_api.py`
  - Cover the richer `/sources` and `/health` payloads.
- Modify: `apps/dsa-web/src/types/overnight.ts`
  - Type the new source metadata and health fields.
- Modify: `apps/dsa-web/src/pages/OvernightBriefPage.tsx`
  - Group source cards by coverage tier and render coverage gaps.
- Verify: `./.venv/bin/python -m unittest tests.test_overnight_registry tests.test_overnight_api -v`
- Verify: `npm --prefix apps/dsa-web run build`

### Task 1: Lock Backend Contract With Failing Tests

**Files:**
- Modify: `tests/test_overnight_registry.py`
- Modify: `tests/test_overnight_api.py`
- Test: `tests/test_overnight_registry.py`
- Test: `tests/test_overnight_api.py`

- [ ] **Step 1: Write the failing registry tests**

```python
self.assertIn("ustr_press_releases", source_ids)
self.assertEqual(sources["bls_release_schedule"].coverage_tier, "official_data")
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run: `./.venv/bin/python -m unittest tests.test_overnight_registry -v`
Expected: FAIL because the source ids / metadata do not exist yet

- [ ] **Step 3: Write the failing API contract assertions**

```python
assert payload["items"][0]["coverage_tier"]
assert payload["source_health"]["coverage_tier_counts"]["official_policy"] >= 1
assert isinstance(payload["source_health"]["coverage_gaps"], list)
```

- [ ] **Step 4: Run API tests to verify they fail**

Run: `./.venv/bin/python -m unittest tests.test_overnight_api -v`
Expected: FAIL because the API payload does not expose the new fields yet

- [ ] **Step 5: Commit**

```bash
git add tests/test_overnight_registry.py tests/test_overnight_api.py
git commit -m "test: lock overnight source coverage contract"
```

### Task 2: Implement Source Coverage Metadata

**Files:**
- Modify: `src/overnight/types.py`
- Modify: `src/overnight/source_registry.py`

- [ ] **Step 1: Add minimal source metadata fields to `SourceDefinition`**

```python
coverage_tier: str
region_focus: str
coverage_focus: str
```

- [ ] **Step 2: Seed the expanded default source catalog**

Include at minimum:

- `whitehouse_news`
- `fed_news`
- `ustr_press_releases`
- `treasury_press_releases`
- `bls_news_releases`
- `bls_release_schedule`
- `bea_news`
- `eia_pressroom`
- `reuters_topics`
- `ap_politics`
- `ap_business`
- `cnbc_world`

- [ ] **Step 3: Keep the source-class filter behavior intact**

Do not break `build_default_source_registry(source_class=...)`.

- [ ] **Step 4: Run registry tests**

Run: `./.venv/bin/python -m unittest tests.test_overnight_registry -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/overnight/types.py src/overnight/source_registry.py tests/test_overnight_registry.py
git commit -m "feat: expand overnight source registry coverage"
```

### Task 3: Implement Coverage Summary In API / Service Layer

**Files:**
- Modify: `src/services/overnight_service.py`
- Modify: `api/v1/schemas/overnight.py`
- Modify: `tests/test_overnight_api.py`

- [ ] **Step 1: Extend source payload serialization**

Return:

- `coverage_tier`
- `region_focus`
- `coverage_focus`

- [ ] **Step 2: Extend `source_health` summary**

Add:

- `enabled_mission_critical_sources`
- `coverage_tier_counts`
- `source_class_counts`
- `coverage_gaps`

- [ ] **Step 3: Keep the existing health fields stable**

Do not remove:

- `total_sources`
- `mission_critical_sources`
- `whitelisted_sources`

- [ ] **Step 4: Run API tests**

Run: `./.venv/bin/python -m unittest tests.test_overnight_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/overnight_service.py api/v1/schemas/overnight.py tests/test_overnight_api.py
git commit -m "feat: expose overnight source coverage health"
```

### Task 4: Render Coverage Groups In The Frontend

**Files:**
- Modify: `apps/dsa-web/src/types/overnight.ts`
- Modify: `apps/dsa-web/src/pages/OvernightBriefPage.tsx`

- [ ] **Step 1: Extend frontend types for source metadata and health summary**

```ts
coverageTier: string;
regionFocus: string;
coverageFocus: string;
enabledMissionCriticalSources: number;
coverageTierCounts: Record<string, number>;
sourceClassCounts: Record<string, number>;
coverageGaps: string[];
```

- [ ] **Step 2: Group source cards by `coverageTier` in `SourceCatalogPanel`**

Render sections for:

- 官方政策
- 官方数据
- 主流媒体

- [ ] **Step 3: Extend `HealthPanel` with coverage-tier counts and gap messages**

Keep the current cards, add one explicit gap block so the page explains whether coverage is thin.

- [ ] **Step 4: Run frontend build**

Run: `npm --prefix apps/dsa-web run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dsa-web/src/types/overnight.ts apps/dsa-web/src/pages/OvernightBriefPage.tsx
git commit -m "feat: show overnight source coverage in ui"
```

### Task 5: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend verification**

Run: `./.venv/bin/python -m unittest tests.test_overnight_registry tests.test_overnight_api -v`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix apps/dsa-web run build`
Expected: PASS

- [ ] **Step 3: Run live endpoint verification**

Run:

```bash
curl -sS http://127.0.0.1:8000/api/v1/overnight/sources | jq '.total'
curl -sS http://127.0.0.1:8000/api/v1/overnight/health | jq '.source_health'
```

Expected:

- source count greater than the old baseline of `3`
- `coverage_gaps` present in the health payload

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat: ship overnight source coverage v1"
```
