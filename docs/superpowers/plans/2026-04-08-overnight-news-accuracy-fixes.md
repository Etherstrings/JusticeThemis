# Overnight News Accuracy Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate known accuracy regressions in event clustering, numeric subject inference, handoff packaging, and evidence deduplication so the overnight-news handoff remains trustworthy for fixed daily analysis.

**Architecture:** Keep the current standalone project structure and repair behavior at the smallest responsible boundaries. Drive every fix from a failing regression test first, then tighten clustering heuristics, preserve full event-cluster membership in handoff packaging, and improve evidence/number normalization without broad refactors.

**Tech Stack:** Python 3.12, pytest, SQLite-backed repository services, FastAPI-compatible service layer

---

## File Structure

- Modify: `overnight-news-handoff/app/normalizer.py`
- Modify: `overnight-news-handoff/app/services/source_capture.py`
- Modify: `overnight-news-handoff/app/services/handoff.py`
- Modify: `overnight-news-handoff/app/services/evidence.py`
- Modify: `overnight-news-handoff/tests/test_normalizer.py`
- Modify: `overnight-news-handoff/tests/test_source_capture.py`
- Modify: `overnight-news-handoff/tests/test_handoff.py`
- Modify: `overnight-news-handoff/tests/test_evidence.py`
- Modify: `overnight-news-handoff/docs/api/frontend-v1-integration.md`
- Modify: `overnight-news-handoff/docs/technical/frontend-api-architecture.md`

## Task 1: Fix decimal-aware numeric subject inference

**Files:**
- Modify: `overnight-news-handoff/tests/test_normalizer.py`
- Modify: `overnight-news-handoff/app/normalizer.py`

- [ ] **Step 1: Write the failing test**

Add regression tests proving decimal values do not break subject inference:

```python
def test_normalize_candidate_keeps_subject_inference_when_decimal_values_appear() -> None:
    normalized = normalize_candidate(
        SourceCandidate(
            candidate_type="article",
            candidate_url="https://example.com/decimal-subjects",
            candidate_title="Macro snapshot",
            candidate_summary=(
                "The account showed $57.3 billion in exports. "
                "Officials discussed a 12.5 basis point rate move. "
                "The White House kept a 25.0% tariff on steel imports."
            ),
        )
    )

    facts = {(fact.metric, fact.subject): fact.value for fact in normalized.numeric_facts}

    assert facts[("usd_amount", "exports")] == 57_300_000_000.0
    assert facts[("tariff_rate", "steel")] == 25.0
    assert facts[("basis_points", "rates")] == 12.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_normalizer.py -q`
Expected: FAIL because `_CLAUSE_SEPARATOR_PATTERN` splits decimal literals like `57.3` and `25.0`.

- [ ] **Step 3: Write minimal implementation**

Make clause-window splitting decimal-safe in `app/normalizer.py` so sentence segmentation still breaks at real clause boundaries but not inside numeric literals. Keep existing keyword-based subject inference and only change the separator logic needed to preserve subject windows.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_normalizer.py -q`
Expected: PASS

## Task 2: Tighten trade topic tagging and event clustering

**Files:**
- Modify: `overnight-news-handoff/tests/test_source_capture.py`
- Modify: `overnight-news-handoff/app/services/source_capture.py`

- [ ] **Step 1: Write the failing tests**

Add regression coverage for three false-positive paths:

```python
def test_item_topics_does_not_tag_macro_trade_data_as_trade_policy() -> None:
    ...
    assert "trade_policy" not in service._item_topics(item)

def test_items_belong_to_same_event_requires_more_than_generic_tariff_overlap() -> None:
    ...
    assert service._items_belong_to_same_event(steel_item, copper_item) is False

def test_items_belong_to_same_event_does_not_merge_trade_and_budget_deficit() -> None:
    ...
    assert service._items_belong_to_same_event(trade_item, budget_item) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_source_capture.py -q`
Expected: FAIL because bare `trade` currently maps to `trade_policy` and clustering accepts overly generic shared topics/keywords.

- [ ] **Step 3: Write minimal implementation**

Repair clustering in `app/services/source_capture.py` by:
- narrowing trade-policy topic detection so macro trade-data stories are not labeled as policy actions from the bare word `trade`
- requiring more discriminative overlap before two items can share an event cluster
- preventing generic words like `tariff` and `deficit` from acting as sufficient event identity without a matching product/subject/fact signature

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_source_capture.py -q`
Expected: PASS

## Task 3: Preserve complete event groups in handoff output

**Files:**
- Modify: `overnight-news-handoff/tests/test_handoff.py`
- Modify: `overnight-news-handoff/app/services/handoff.py`

- [ ] **Step 1: Write the failing test**

Add a regression test showing `event_groups` preserve all cluster members even when `items` is truncated by `limit`:

```python
def test_get_handoff_event_groups_keep_full_cluster_membership_from_wider_pool() -> None:
    handoff = service.get_handoff(limit=1)

    assert len(handoff["items"]) == 1
    assert handoff["event_groups"][0]["item_ids"] == [21, 22, 23]
    assert [item["item_id"] for item in handoff["event_groups"][0]["items"]] == [21, 22, 23]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_handoff.py -q`
Expected: FAIL because `get_handoff()` currently truncates before building `event_groups`.

- [ ] **Step 3: Write minimal implementation**

Build `event_groups` from the wider sorted pool before `items` truncation while keeping top-level `items`, `groups`, `total`, and outline semantics tied to the requested limit.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_handoff.py -q`
Expected: PASS

## Task 4: Improve evidence dedupe for shorthand USD values

**Files:**
- Modify: `overnight-news-handoff/tests/test_evidence.py`
- Modify: `overnight-news-handoff/app/services/evidence.py`

- [ ] **Step 1: Write the failing test**

Add a regression test proving `$57.3B` and `$1.2T` in summaries suppress duplicate numeric evidence lines:

```python
def test_build_evidence_points_treats_usd_suffix_shorthand_as_existing_fact() -> None:
    points = build_evidence_points(
        summary="The deficit widened to $57.3B in February. Funding reached $1.2T for the program.",
        numeric_facts=(...),
    )

    assert len(points) == 2
    assert not any(point.startswith("usd_amount:") for point in points)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_evidence.py -q`
Expected: FAIL because shorthand USD suffixes are not recognized by `_summary_already_mentions_fact()`.

- [ ] **Step 3: Write minimal implementation**

Extend `app/services/evidence.py` to recognize normalized USD shorthand tokens such as `B`, `BN`, `T`, and `TN`, along with readable billion/million/trillion forms, without overmatching unrelated numbers.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_evidence.py -q`
Expected: PASS

## Task 5: Sync API documentation with repaired semantics

**Files:**
- Modify: `overnight-news-handoff/docs/api/frontend-v1-integration.md`
- Modify: `overnight-news-handoff/docs/technical/frontend-api-architecture.md`

- [ ] **Step 1: Document the repaired semantics**

Update docs so frontend and downstream-model consumers understand:
- `event_groups` are built from the wider recent pool and may contain cluster members outside the truncated top-level `items`
- `trade_policy` topic tags are policy-action oriented rather than generic trade-data tags
- numeric fact/evidence formatting preserves decimal subject accuracy and suppresses redundant shorthand USD evidence

- [ ] **Step 2: Verify docs read consistently with implementation**

Read both docs after code changes and confirm terminology matches the actual response payloads and service behavior.

## Task 6: Run full verification and independent review

**Files:**
- Modify: none

- [ ] **Step 1: Run the full suite**

Run: `./.venv/bin/python -m pytest tests -q`
Expected: PASS

- [ ] **Step 2: Run focused repro probes**

Run the previously reproduced one-off probes for:
- steel tariff vs copper tariff clustering
- trade deficit vs budget deficit clustering
- decimal subject inference for `$57.3 billion`, `12.5 basis points`, and `25.0%`
- evidence dedupe for `$57.3B`

Expected: all repros confirm the bug is gone.

- [ ] **Step 3: Independent review**

Dispatch a fresh review subagent with the changed file set and request confirmation that:
- each confirmed finding is fixed
- no regression was introduced in the repaired logic
- verification evidence is sufficient
