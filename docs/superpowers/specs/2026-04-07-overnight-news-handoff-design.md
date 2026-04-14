# Overnight News Handoff Design

**Date:** 2026-04-07

**Goal**

Build a standalone product focused on one job: capture authoritative overseas financial, policy, and macro news quickly, normalize it, and expose an official-first structured package that can be sent to a downstream large model for judgment.

**Why This Exists**

The earlier capture implementation proved the core logic, but it was embedded inside a broader A-share analysis product. That coupling is now a liability. The user wants a separate information-acquisition product, not a feature hidden inside the old stack.

This new project extracts only the validated core:

- source registry
- source collectors
- capture refresh pipeline
- normalized storage
- LLM handoff export

It must not depend on the old morning-brief shell, A-share analysis workflow, or large operational dashboard.

## Product Boundary

**Included**

- authoritative source registry
- section-page, RSS, article-shell, and calendar capture
- transient-failure retry handling
- normalized source item storage
- recent item listing
- official-first handoff package for downstream model reasoning
- lightweight API
- lightweight inspection UI

**Explicitly Excluded**

- old morning-brief generation
- event clustering and board synthesis tied to the old product
- feedback/history/admin surfaces from the old app
- stock analysis, strategy scoring, or direct A-share judgment inside the product
- any runtime dependency on an external analysis product

## Recommended Initial Source Set

- White House News
- Federal Reserve News
- USTR Press Releases
- Treasury Press Releases
- Census Economic Indicators
- BEA News
- EIA Pressroom
- CNBC World
- AP Business
- AP Politics

Keep weak sources out of the default path until separately hardened:

- BLS
- Reuters

## Architecture

The standalone app is a focused Python application with four runtime layers.

### 1. Source Layer

Owns source metadata and capture rules.

- source identity
- organization type
- coverage tier
- priority
- polling hints
- entry URLs

### 2. Capture Layer

Owns HTTP fetching, retry policy, collector selection, candidate normalization, and persistence.

Responsibilities:

- fetch section pages / feeds / article shells
- recover from transient SSL EOF and timeout failures
- normalize URL, title, summary, document type, entities, numeric facts, published time
- persist recent items in a standalone store

### 3. Handoff Layer

Owns one output shape: official-first structured packages for downstream models.

Responsibilities:

- sort with official policy first, official data second, editorial media last
- widen the candidate pool before truncating so media items do not crowd out official items
- group items by coverage tier
- include prompt scaffold, item ids, sources, freshness, and extracted facts

The product’s own “judgment” responsibility stops here for now.

### 4. Delivery Layer

Owns the minimal product surface.

- `POST /refresh`
- `GET /items`
- `GET /handoff`
- lightweight page for inspection and copy/export

## Migration Rule

The migration is an extraction, not a copy of the whole old product.

**Port directly**

- `src/overnight/source_registry.py`
- `src/overnight/types.py`
- `src/overnight/normalizer.py`
- `src/overnight/collectors/*`
- `src/services/overnight_source_capture_service.py`
- `src/services/overnight_source_excerpt_service.py`
- handoff-related parts of `src/services/overnight_service.py`
- relevant tests and fixtures

**Rebuild cleanly in the new project**

- storage bootstrapping
- API layer
- app config
- lightweight UI

**Do not port**

- brief builder
- runner
- feedback/history
- unrelated stock analysis modules

## Success Criteria

The project is successful when:

- it runs as a standalone project under its own directory
- it has no runtime imports from an external analysis product
- it can refresh and persist authoritative overseas news
- `GET /handoff` returns an official-first package suitable for downstream model use
- the lightweight UI shows captured news plus source attribution
