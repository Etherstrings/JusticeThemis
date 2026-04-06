# JusticeThemis

A-share overnight decision workspace translating overseas financial and political news into pre-open actions.

`JusticeThemis` is built for a China-based user who wakes up in the morning and wants four answers fast:

1. What happened overseas overnight?
2. Which A-share directions may benefit?
3. Which chains may face price pressure?
4. What should be watched before the opening auction?

## What It Is

This repo packages the overnight product into a standalone workspace instead of treating it as a side feature.

Core product surfaces:

- `/overnight`: main overnight brief
- `/overnight/opening`: pre-open action board
- `/overnight/changes`: latest-vs-previous delta comparison
- `/overnight/playbook`: opening playbook
- `/overnight/history`: event and topic history workspace
- `/overnight/topics/:topicKey`: topic views
- `/overnight/review`: editorial review queue
- `/overnight/events/:eventId`: single-event execution desk

## Product Model

The product is not designed as a generic news feed.
It turns raw overnight inputs into a compact decision surface:

- top events ranked by priority and confidence
- A-share focus areas
- avoid areas
- likely price-pressure chains
- confirmation flags
- pre-market action lanes
- single-event trading context
- historical fermentation and previous-day shift
- same-brief related-chain links

Action lanes:

- `act-now`
- `watch-open`
- `wait-confirm`
- `de-risk`

## Current Shipped State

The current repo includes:

- multi-page overnight frontend workspace
- overnight brief API and storage
- delta detection between consecutive briefs
- event history aggregation
- topic history aggregation
- feedback queue and review workflow
- A-share translation logic
- event freshness and linkage logic

Release summary:

- [JusticeThemis Release Notes](docs/releases/2026-04-06-justice-themis.md)

Design and planning history:

- [Overnight Design Spec](docs/superpowers/specs/2026-04-05-overnight-intelligence-morning-brief-design.md)
- [Overnight Implementation Plan](docs/superpowers/plans/2026-04-05-overnight-intelligence-morning-brief.md)

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Etherstrings/JusticeThemis.git
cd JusticeThemis
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd apps/dsa-web
npm install
cd ../..
```

### 4. Configure environment

Copy and edit your environment file if needed:

```bash
cp .env.example .env
```

Recommended areas to configure for the overnight product:

- upstream model/API keys
- overnight source access
- proxy settings if overseas sources require it
- delivery channels if you want notifications

### 5. Run the app

```bash
python main.py --webui-only
```

Or run with the broader service mode:

```bash
python main.py --webui
```

Frontend-only build:

```bash
npm --prefix apps/dsa-web run build
```

## Key Routes

After startup, the overnight product is centered on:

- `http://127.0.0.1:8000/overnight`
- `http://127.0.0.1:8000/overnight/opening`
- `http://127.0.0.1:8000/overnight/changes`
- `http://127.0.0.1:8000/overnight/playbook`
- `http://127.0.0.1:8000/overnight/history`

Key APIs:

- `/api/v1/overnight/brief/latest`
- `/api/v1/overnight/brief/latest/delta`
- `/api/v1/overnight/history`
- `/api/v1/overnight/history/events`
- `/api/v1/overnight/history/topics`
- `/api/v1/overnight/feedback`

## Local Verification

Frontend verification:

```bash
npm --prefix apps/dsa-web run build
npx tsx --test apps/dsa-web/tests/overnightEventContext.test.ts
npx tsx --test apps/dsa-web/tests/overnightLinkage.test.ts
npx tsx --test apps/dsa-web/tests/overnightDecision.test.ts
```

Backend verification depends on local Python dependencies being installed.
If your environment has the required packages, run:

```bash
python3 -m pytest tests/test_overnight_api.py tests/test_overnight_brief_builder.py tests/test_overnight_storage.py
```

## Repo Structure

Important paths:

- `api/v1/endpoints/overnight.py`
- `src/services/overnight_service.py`
- `src/repositories/overnight_repo.py`
- `src/overnight/brief_builder.py`
- `apps/dsa-web/src/pages/`
- `apps/dsa-web/src/utils/`
- `apps/dsa-web/tests/`

## Notes

- The repo still contains broader stock-analysis infrastructure inherited from the original codebase.
- This forked repo is maintained as a dedicated home for the overnight decision product.
- If overseas sources are unreachable locally, check proxy configuration before assuming the overnight pages are broken.

## License

[MIT License](LICENSE)
