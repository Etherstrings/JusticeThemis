# Overnight Evidence And Judgment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show richer captured-news evidence and a one-line judgment for each overnight event.

**Architecture:** Extend the event-detail API contract to include derived evidence items and a one-line judgment. Generate evidence from existing source links plus the source catalog, and generate judgment via model-optional logic with a heuristic fallback. Render the same data in both the main brief page and the event detail page.

**Tech Stack:** Python 3.12, FastAPI, React, TypeScript, unittest, pytest, tsx

---

## File Structure

- Modify: `api/v1/schemas/overnight.py`
- Modify: `src/services/overnight_service.py`
- Create: `src/services/overnight_judgment_service.py`
- Modify: `tests/test_overnight_api.py`
- Modify: `apps/dsa-web/src/types/overnight.ts`
- Create: `apps/dsa-web/src/utils/overnightSourceEvidence.ts`
- Modify: `apps/dsa-web/src/pages/OvernightBriefPage.tsx`
- Modify: `apps/dsa-web/src/pages/OvernightEventDetailPage.tsx`
- Create: `apps/dsa-web/tests/overnightSourceEvidence.test.ts`

### Task 1: Lock API Contract

**Files:**
- Modify: `tests/test_overnight_api.py`

- [ ] **Step 1: Write failing API assertions for event evidence and judgment**
- [ ] **Step 2: Run `./.venv/bin/python -m pytest tests/test_overnight_api.py -q` and verify failure**
- [ ] **Step 3: Commit**

### Task 2: Implement Backend Evidence + Judgment

**Files:**
- Modify: `api/v1/schemas/overnight.py`
- Modify: `src/services/overnight_service.py`
- Create: `src/services/overnight_judgment_service.py`

- [ ] **Step 1: Add response schema fields for evidence items and judgment**
- [ ] **Step 2: Build evidence items from event source links**
- [ ] **Step 3: Add model-optional one-line judgment generation**
- [ ] **Step 4: Run `./.venv/bin/python -m pytest tests/test_overnight_api.py -q` and verify pass**
- [ ] **Step 5: Commit**

### Task 3: Render Frontend Evidence + Judgment

**Files:**
- Modify: `apps/dsa-web/src/types/overnight.ts`
- Create: `apps/dsa-web/src/utils/overnightSourceEvidence.ts`
- Modify: `apps/dsa-web/src/pages/OvernightBriefPage.tsx`
- Modify: `apps/dsa-web/src/pages/OvernightEventDetailPage.tsx`
- Create: `apps/dsa-web/tests/overnightSourceEvidence.test.ts`

- [ ] **Step 1: Write failing frontend evidence conversion test**
- [ ] **Step 2: Implement evidence util and page rendering**
- [ ] **Step 3: Add judgment sentence rendering**
- [ ] **Step 4: Run `npx tsx --test apps/dsa-web/tests/overnightSourceEvidence.test.ts`**
- [ ] **Step 5: Run `npm --prefix apps/dsa-web run build`**
- [ ] **Step 6: Commit**

### Task 4: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests**
- [ ] **Step 2: Run frontend tests**
- [ ] **Step 3: Run frontend build**
- [ ] **Step 4: Check live page text contains evidence and judgment**
- [ ] **Step 5: Commit**
