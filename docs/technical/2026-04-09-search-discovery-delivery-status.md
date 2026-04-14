# Search Discovery Delivery Status

> **Document date:** 2026-04-09  
> **Project:** `overnight-news-handoff`  
> **Scope:** Search-based official-source supplementation for blocked or low-yield overnight news capture

## 1. Purpose of This Document

This document is a detailed technical handoff for the search discovery enhancement completed on **2026-04-09**.

It exists to answer four questions clearly:

1. what has already been implemented
2. what has been verified with tests and live runs
3. what is still incomplete or externally blocked
4. what should be done next

This is a **status document**, not a target-state architecture contract.

For the stable architecture description, see:

- [search-discovery-supplement-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/search-discovery-supplement-architecture.md)
- [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md)

## 2. Scope Boundary

This enhancement was implemented **only** in:

- `overnight-news-handoff`

It was **not** implemented in:

- `daily_stock_analysis`
- `JusticeHermes`
- `JusticePlutus`
- any other sibling project

`JusticePlutus` was used only as a reference for provider patterns and as a source of locally stored API keys during command-time smoke testing. The runtime code in this repo does **not** depend on `JusticePlutus` files.

## 3. Problem This Work Solves

The project already had direct collectors for official sources such as White House, Treasury, USTR, State, DOD, BLS, and others.

The real issue was:

- some official section pages returned `403` or `407` from the current network path
- some section pages were structurally unstable or low-yield
- this caused capture coverage gaps on exactly the sources that matter for overnight cross-market interpretation

The enhancement therefore adds a bounded fallback:

- direct official collection remains first
- search discovery is used only for explicitly enabled sources
- search results must still be same-domain official URLs
- the rest of the pipeline remains deterministic

## 4. High-Level Status

### 4.1 Completed

- env-backed multi-provider search discovery layer
- source-level opt-in metadata
- integration into source capture fallback flow
- explicit persistence of capture provenance in SQLite
- API exposure of capture provenance for news detail / refresh payloads
- API exposure of source-level search-discovery registry metadata
- same-domain validation for search results
- entry-page and binary-asset filtering
- noisy search-snippet cleaning
- search-result ranking improvements
- event-engine mixed-timezone parsing fix
- test coverage for the new behavior
- live smoke using local provider keys
- architecture and delivery documentation

### 4.2 Partially Completed

- State / DOD / BLS search supplementation works at the URL and persistence level, but content quality still varies when article fetch is blocked by the source website
- search-summary cleaning is materially better than before, but still not source-perfect for every government site
- fallback-captured items now explicitly expose `expand_failed`, but the system still does not have source-specific remediation logic to automatically improve those bodies

### 4.3 Not Completed

- source-specific deep cleaners for `state.gov`, `defense.gov`, `bls.gov`
- persistent provider health / quota tracking
- provider-result audit table in the database
- scheduler / job orchestration dedicated to search supplementation
- dedicated frontend display for “captured via search fallback”
- premium AI analysis strategy changes specifically tuned to fallback-captured official news

## 5. Delivered Architecture and Code

### 5.1 New Runtime Component

New file:

- [app/services/search_discovery.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/search_discovery.py)

This file now owns:

- provider key parsing from environment
- lightweight provider clients
- normalization from provider result to `SourceCandidate`
- result filtering
- snippet cleaning
- stale-result filtering
- provider-error sanitization

### 5.2 Updated Type System

Updated file:

- [app/sources/types.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/sources/types.py)

Added fields to `SourceDefinition`:

- `search_discovery_enabled: bool`
- `search_queries: tuple[str, ...]`

This is the contract that keeps search fallback explicit and source-scoped.

### 5.3 Updated Registry

Updated file:

- [app/sources/registry.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/sources/registry.py)

Search discovery is currently enabled for:

- `ustr_press_releases`
- `treasury_press_releases`
- `bls_news_releases`
- `state_spokesperson_releases`
- `dod_news_releases`

These were chosen because they are either:

- mission-critical official sources
- repeatedly blocked in live fetches
- or structurally low-yield enough that bounded same-domain search fallback is justified

### 5.4 Updated Capture Service

Updated file:

- [app/services/source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/source_capture.py)

New behavior:

1. run the original collector first
2. decide whether the collected set is empty or thin
3. if thin and source is enabled, run search discovery
4. merge and dedupe direct + search candidates
5. rank candidates
6. persist through the existing normalization pipeline
7. expose explicit capture provenance through the normal API payloads

Important helper methods added or changed:

- `_should_use_search_discovery(...)`
- `_candidate_is_thin_for_search_discovery(...)`
- `_dedupe_candidate_urls(...)`
- `_candidate_relevance_score(...)` search-quality adjustments

### 5.4.1 Provenance Persistence Now Implemented

Updated files:

- [app/sources/types.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/sources/types.py)
- [app/normalizer.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/normalizer.py)
- [app/ledger.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/ledger.py)
- [app/db.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/db.py)
- [app/repository.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/repository.py)

Persisted fields:

- `capture_path`
- `capture_provider`
- `article_fetch_status`

Current semantics:

- `capture_path="direct"` means the item came from the ordinary collector path
- `capture_path="search_discovery"` means the item entered through bounded search fallback
- `capture_provider` is empty in storage for direct captures and normalized to `null` in API output
- `article_fetch_status="not_attempted"` applies to direct items that never required article expansion
- `article_fetch_status="expanded"` means article-body expansion succeeded before normalization
- `article_fetch_status="expand_failed"` means the search/direct shell was persisted without a successful body expansion

This removes the previous ambiguity where frontend or downstream consumers had to infer fallback behavior from `excerpt_source`.

### 5.4.2 Frontend / Read API Exposure Now Implemented

Updated files:

- [app/services/source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/source_capture.py)
- [app/services/frontend_api.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/frontend_api.py)

New read-side fields:

- per item:
  - `capture_path`
  - `capture_provider`
  - `article_fetch_status`
  - `capture_provenance`
- per source row:
  - `search_discovery_enabled`
  - `search_query_count`

Practical impact:

- refresh payloads can now show whether a captured item is direct or fallback-derived
- news detail pages can render provenance badges without reverse-engineering `excerpt_source`
- source registry pages can show which important official sources already have explicit fallback coverage configured

### 5.5 Event Engine Fix

Updated file:

- [app/services/event_engine.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/event_engine.py)

Why this changed:

- live smoke introduced persisted items whose `published_at` values were in mixed formats
- some were ISO 8601 with timezone
- some were RFC-style published times from search providers
- event clustering compared offset-aware and offset-naive datetimes and crashed

What was fixed:

- `created_at` parsing normalized to UTC-aware datetime
- `published_at` parsing now supports RFC-style timestamps via `parsedate_to_datetime`
- date-only and ISO values are normalized consistently

## 6. Provider Support

Implemented providers:

- `Bocha`
- `Tavily`
- `SerpAPI`
- `Brave`

### 6.1 Environment Variables

Supported env names:

- `BOCHA_API_KEYS`
- `BOCHA_API_KEY`
- `TAVILY_API_KEYS`
- `TAVILY_API_KEY`
- `SERPAPI_API_KEYS`
- `SERPAPI_API_KEY`
- `BRAVE_API_KEYS`
- `BRAVE_API_KEY`

Supported separators:

- comma
- newline
- semicolon

### 6.2 Provider Priority

The current `from_environment()` order is:

1. `Bocha`
2. `Tavily`
3. `SerpAPI`
4. `Brave`

### 6.3 Current Practical Observation

During the 2026-04-09 smoke runs:

- `Bocha` was configured
- `Tavily` was configured
- `SerpAPI` was configured
- `Brave` was not observed in local env files used for smoke

In practice:

- `Tavily` provided most of the usable same-domain fallback candidates
- `SerpAPI` often hit `429`
- `Bocha` was available but less reliable for the official-source queries tested here

## 7. Filtering and Cleaning Rules

Search results are **not** accepted as-is.

### 7.1 Allowed URL Rules

Search results must satisfy:

- same-domain validation using `allowed_domains`
- HTTPS rules inherited from the source definition

### 7.2 Excluded URL Classes

Filtered out before persistence:

- entry pages
- binary files such as `.pdf`, `.csv`, `.xls`, `.xlsx`, `.zip`, `.doc`, `.docx`, `.ppt`, `.pptx`
- known BLS non-article table/index pages such as `.tNN.htm` and `.toc.htm`

### 7.3 Staleness Rule

If a provider publication time can be parsed, the result is filtered out when older than:

- `max(21, days + 7)`

This is intentionally conservative because:

- provider timestamps are inconsistent
- some providers return weak or missing publication metadata

### 7.4 Snippet Cleaning

The cleaner removes or suppresses:

- cookie banners
- “skip to main content”
- `.gov` trust banners
- privacy-policy text
- menu/search chrome
- navigation trees
- social-link strips
- repeated site-header fragments

If a snippet is cleaned down to pure noise, the current code now returns:

- empty summary

It does **not** fall back to the original raw noisy text anymore.

### 7.5 Provider Error Sanitization

HTTP failures are sanitized before logging.

This was added to avoid leaking:

- request URLs containing query strings
- provider key material embedded in error messages

## 8. Thinness and Ranking Logic

### 8.1 Search Supplement Trigger

Search discovery no longer triggers on a pure `len(collected) < 2` rule alone.

Current trigger:

- enabled source + zero candidates -> supplement
- enabled source + one thin candidate -> supplement
- enabled source + first two candidates both thin -> supplement
- otherwise do not supplement

Current “thin” heuristics treat candidates as non-thin when they already have:

- sufficiently detailed summary text
- or explicit excerpt source indicating a strong direct capture
- or feed/article style candidates with meaningful summary length

### 8.2 Ranking Adjustments

Candidate ranking now includes extra heuristics for search-derived summaries:

- content-like text gets promoted
- cookie/navigation-heavy text gets penalized
- low-signal titles like `public schedule` get penalized

This was added because live smoke showed that same-domain official URLs are not enough; some official URLs still produce useless navigation text and should not win ranking.

## 9. Verification Evidence

### 9.1 Test Status

As of **2026-04-09**, the full local suite passed:

- `149 passed in 0.75s`

Verification command:

```bash
./.venv/bin/python -m pytest -q
```

### 9.2 New or Updated Test Coverage

Relevant files:

- [tests/test_search_discovery.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_search_discovery.py)
- [tests/test_api.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_api.py)
- [tests/test_collectors.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_collectors.py)
- [tests/test_event_engine.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_event_engine.py)
- [tests/test_source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_source_capture.py)

Covered behavior now includes:

- env parsing for provider keys
- provider-order creation from environment
- same-domain search-result normalization
- off-domain filtering
- search fallback through `/refresh`
- registry metadata assertions
- mixed datetime parsing in event clustering
- search-noise cleaning
- pure-noise snippet behavior
- entry-page filtering even under path-casing differences
- ranking penalties for noisy search summaries
- thin/empty gating for search supplementation

### 9.3 Independent Review

A separate sub-agent code review was run after implementation.

Its key findings were:

- pure-noise cleaned snippets were still falling back to raw noise
- canonical URL handling was inconsistent between discovery and capture
- supplementation trigger was too count-based

All three were subsequently addressed in code and locked with tests.

## 10. Live Smoke Results on 2026-04-09

The live smoke used local environment keys injected at command time from the machine.

### 10.1 Provider Detection

Detected providers during smoke:

- `Bocha`
- `Tavily`
- `SerpAPI`

### 10.2 Captured Sources in Smoke

A live `refresh` run against the enabled official sources produced persisted results for:

- `bls_news_releases`
- `dod_news_releases`
- `state_spokesperson_releases`
- `treasury_press_releases`
- `ustr_press_releases`

### 10.3 Example Smoke Output

Observed persisted items included:

- `BLS`: `State Employment and Unemployment Summary`
- `DOD`: `Statement From Secretary of Defense Lloyd J. Austin III on Steps to ...`
- `State`: `U.S. Assistance to Ensure the Safety of American Citizens Overseas`
- `Treasury`: `New Guidance Unlocks Economic Opportunity for Overlooked Communities`
- `USTR`: `Op-Ed by Ambassador Jamieson Greer: Another Fish Story From the WTO`

### 10.4 What Smoke Proved

Confirmed:

- search discovery can run with locally configured keys
- same-domain official URLs are being discovered and persisted
- the existing persistence and rendering stack accepts those results
- fallback capture still works even when direct official section pages fail

Not confirmed:

- that the final summary quality is sufficient for all blocked sites
- that search providers will consistently return recent, article-like State/DOD results every day
- that provider quotas will be adequate for production-scale polling

## 11. What Is Fully Completed

The following should be considered implemented and usable:

### 11.1 Search Discovery Runtime

- provider instantiation from env
- multi-key parsing
- provider fallback behavior
- same-domain result normalization

### 11.2 Source-Level Search Enablement

- registry metadata
- source-scoped query definitions
- opt-in only behavior

### 11.3 Capture Integration

- fallback invocation after direct capture
- candidate deduplication
- ranking integration
- normal persistence path

### 11.4 Regression Hardening

- mixed-time parsing fix in event engine
- sanitized provider error logging
- test coverage for review-discovered risks

### 11.5 Documentation

- architecture summary
- plan-status update
- this detailed delivery-status document

## 12. What Is Not Yet Finished

This section is intentionally explicit. These items are not done yet.

### 12.1 Source-Specific Extraction Quality for Blocked Sites

Not completed:

- State-specific fallback summarizer that reliably strips site chrome
- DOD-specific fallback summarizer that consistently extracts the real body
- BLS-specific fallback summarizer that removes release-metadata clutter and surfaces actual macro content

Impact:

- fallback-captured URLs may be correct
- persisted summaries may still be weaker than desired for model handoff

### 12.2 Persistent Operational Monitoring

Not completed:

- provider success-rate metrics
- per-source fallback-hit metrics
- stored provider-origin audit rows
- quota/latency dashboards

Impact:

- current verification is manual and smoke-test driven
- no historical reliability telemetry is persisted yet

### 12.3 Scheduler / Production Orchestration

Not completed in this enhancement:

- scheduled fallback-specific job execution
- backoff policies driven by provider health
- source-specific refresh windows

The current runtime is compatible with manual/API-triggered refresh, but this enhancement did not add production orchestration.

### 12.4 Dedicated UI / API Exposure of Fallback Provenance

Current item output already exposes `excerpt_source`, but not a dedicated flag such as:

- `captured_via_search_fallback`
- `search_provider_name`
- `search_query_used`

This means the frontend can infer some provenance from `excerpt_source`, but there is no first-class presentation model for it yet.

### 12.5 Model-Layer Tuning

Not completed:

- prompt strategy that explicitly distinguishes direct-capture vs search-fallback evidence quality
- per-source confidence weighting tied to fallback-only summaries
- premium recommendation logic tuned for fallback-derived policy text

The current enhancement stops at capture and deterministic rendering.

## 13. Known External Blockers and Risks

These are not local code bugs. They are current operational blockers.

### 13.1 Official Site Access Blocking

Observed on 2026-04-09:

- `https://www.state.gov/briefings-statements/` -> `407`
- `https://www.defense.gov/News/Releases/` -> `403`
- `https://www.bls.gov/bls/news-release/home.htm` -> `403`

Impact:

- direct section discovery is unreliable or unavailable from the current network path
- article fetch for same-domain discovered URLs may also fail

### 13.2 Search Provider Quotas / Rate Limits

Observed:

- `SerpAPI` returned `429` repeatedly during smoke

Impact:

- `SerpAPI` should be treated as opportunistic fallback, not a guaranteed primary provider

### 13.3 Weak Provider Publication Metadata

Current risk:

- some providers may return relative or weak publication times
- unparseable times are not automatically marked stale

Impact:

- older results can still slip through when provider freshness filters are loose

### 13.4 Query Drift Risk

Current registry still includes at least one USTR search query using:

- `site:ustr.gov/about/policy-offices/...`

while the direct entry URLs use:

- `about-us`

This is not fatal, but it can reduce recall consistency.

## 14. Current Readiness Assessment

### 14.1 Ready for Use

Ready now:

- local development
- manual refresh workflows
- evidence capture improvement for blocked official sources
- model handoff preparation where imperfect but same-domain official capture is better than empty capture

### 14.2 Not Yet Ready for “Trust It Blindly” Production Use

Not ready yet if the requirement is:

- every captured official item must have strong clean body text
- provider quality must be stable without manual monitoring
- fallback provenance must be fully observable in ops dashboards

## 15. Recommended Next Steps

Priority order below is deliberate.

### P0

- Add source-specific cleaners for `state.gov`, `defense.gov`, and `bls.gov`
- Add a dedicated fallback provenance field into the rendered item payload
- Add a source-specific quality threshold that can reject obviously weak fallback summaries even when the URL is same-domain

### P1

- Add provider-result audit persistence
- Add refresh metrics by source/provider
- Tune or expand USTR / State / DOD queries based on another week of live sampling

### P2

- Add production scheduler / retry policy
- Add UI surfaces showing “direct” vs “search supplement” capture origin
- Feed fallback provenance directly into daily-analysis and MMU prompt scaffolds

## 16. Exact Files Added or Modified in This Enhancement

### Added

- [app/services/search_discovery.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/search_discovery.py)
- [docs/technical/search-discovery-supplement-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/search-discovery-supplement-architecture.md)
- [docs/technical/2026-04-09-search-discovery-delivery-status.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-09-search-discovery-delivery-status.md)

### Modified

- [app/sources/types.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/sources/types.py)
- [app/sources/registry.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/sources/registry.py)
- [app/services/source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/source_capture.py)
- [app/services/event_engine.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/app/services/event_engine.py)
- [tests/test_search_discovery.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_search_discovery.py)
- [tests/test_api.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_api.py)
- [tests/test_collectors.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_collectors.py)
- [tests/test_event_engine.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_event_engine.py)
- [tests/test_source_capture.py](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/tests/test_source_capture.py)
- [docs/superpowers/plans/2026-04-09-search-discovery-provider-injection.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/superpowers/plans/2026-04-09-search-discovery-provider-injection.md)

## 17. Final Summary

As of **2026-04-09**, the search-discovery enhancement is **functionally implemented and verified** inside `overnight-news-handoff`.

It has already improved official-source coverage under real blocking conditions by:

- finding same-domain official URLs
- persisting them through the normal pipeline
- keeping the rest of the architecture unchanged

However, the enhancement is **not finished at the quality ceiling**.

The biggest remaining gap is no longer “can we find official URLs?”  
The remaining gap is now:

- “can we extract consistently strong body text when the source website blocks direct article fetch?”

That is the next technical frontier.
