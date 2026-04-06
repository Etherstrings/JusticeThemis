# JusticeThemis

## Positioning

This release turns the overnight brief from a news digest into an A-share pre-market decision workspace.
The product is aimed at a China-based user waking up in the morning and needing fast answers to four questions:

1. What happened overseas overnight?
2. Which A-share directions may benefit?
3. Which chains may face price pressure?
4. What should be watched before the open instead of after the market has already moved?

## What Shipped

### 1. Multi-screen overnight workspace

- Main brief at `/overnight`
- Pre-open action board at `/overnight/opening`
- Delta comparison at `/overnight/changes`
- Playbook at `/overnight/playbook`
- Event history workspace at `/overnight/history`
- Topic pages at `/overnight/topics/:topicKey`
- Review queue at `/overnight/review`
- Single-event execution desk at `/overnight/events/:eventId`

### 2. A-share translation layer

The frontend now translates each overnight event into:

- evidence strength
- A-share focus areas
- avoid areas
- likely price-pressure chains
- pre-market action lanes

Action lanes:

- `act-now`
- `watch-open`
- `wait-confirm`
- `de-risk`

### 3. Playbook and change detection

- latest-vs-previous brief delta detection
- intensified / steady / cooling / dropped event classification
- 09:00-09:30 playbook steps
- risk gates before the opening auction

### 4. Single-event trading page

The event page now shows:

- current handling
- previous-day shift
- freshness vs repeated fermentation
- event history trail
- same-brief related chain links
- raw source links

This makes a single event readable as an execution object instead of a static detail page.

### 5. Editorial feedback loop

- event/brief feedback submission
- review queue for manual correction
- priority and conclusion challenge flow

## Current Demo Flow

Recommended local pages:

- `/overnight`
- `/overnight/opening`
- `/overnight/changes`
- `/overnight/playbook`
- `/overnight/events/event_now_tariff?briefId=81c1515a-6bf7-41df-8b87-94bbbbc9b118`

The tariff event demo currently shows:

- `P1 -> P0`
- `+12pt`
- `连续发酵 2 次`
- `同晨报联动`

## Key Product Improvements In This Iteration

- Added pre-market action desk on the brief and opening pages
- Added event evidence labels and A-share mapping
- Added opening playbook page
- Upgraded event detail into a single-event execution desk
- Added event-history freshness and previous-day shift context
- Added same-brief related-chain analysis
- Fixed misleading commodity fallback mapping so commodity events now map to domain defaults such as `能源 / 资源 / 有色`

## Verification

Verified during development with:

- `uv run pytest tests/test_overnight_api.py tests/test_overnight_brief_builder.py tests/test_overnight_storage.py`
- `npm --prefix apps/dsa-web run build`
- `npx tsx --test apps/dsa-web/tests/overnightEventContext.test.ts`
- `npx tsx --test apps/dsa-web/tests/overnightLinkage.test.ts`
- `npx tsx --test apps/dsa-web/tests/overnightDecision.test.ts`
- live DOM checks against the local runtime at `http://127.0.0.1:8770`

## Codename

`JusticeThemis`

Themis is the Greek figure associated with order, law, and judgment, which fits a product focused on turning overnight noise into a disciplined decision surface.
