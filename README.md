# JusticeThemis

[中文](README.zh.md)

<div align="center">

**Turn overnight global signal flow into a China-morning market read your operator can actually act on.**

![FastAPI](https://img.shields.io/badge/FastAPI-Service-059669?style=flat-square&logo=fastapi&logoColor=white)
![Overnight Intel](https://img.shields.io/badge/Overnight-Intel-1F2937?style=flat-square)
![Self Hosted](https://img.shields.io/badge/Mode-Self_Hosted-0F766E?style=flat-square)
![API](https://img.shields.io/badge/Surface-API-1D4ED8?style=flat-square)
![Daily Analysis](https://img.shields.io/badge/Output-Daily_Analysis-7C3AED?style=flat-square)

Overnight sources · U.S. close snapshot · fixed daily reports · MMU handoff

[Local Startup](#local-startup) · [Smoke Check](#smoke-check) · [Support](#support)

</div>

This is the default bootstrap entrypoint for the standalone `JusticeThemis` repository. For the Chinese bootstrap companion, see [README.zh.md](README.zh.md).

JusticeThemis is a standalone overnight international-news capture, U.S. market-close snapshot, fixed China-morning analysis cache, and downstream LLM/MMU export service.

It is positioned as a result-first overnight market interpretation engine for the China-morning workflow, not just a downstream handoff tool.

## <a id="support"></a>Support

If JusticeThemis helps your research or China-morning workflow, you can support ongoing maintenance via GitHub Sponsors:

- GitHub Sponsors: https://github.com/sponsors/Etherstrings

<!-- readme-parity:what-it-does -->
## What It Does

- Captures a curated overnight source pool into SQLite
- Builds one U.S. market-close snapshot for the analysis date
- Generates fixed `free` and `premium` daily analysis reports
- Exports prompt bundles and MMU handoff payloads for downstream model use
- Exposes read APIs plus protected mutation and readiness routes

<!-- readme-parity:runtime-contract -->
## Runtime Contract

Configuration precedence is:

1. process environment
2. explicit env-file path when a CLI supports `--env-file`
3. project-local `.env.local`
4. project-local `.env`

The app no longer reads env files from other repositories by default.

<!-- readme-parity:legacy-compatibility-mapping -->
## Legacy compatibility mapping

- `JusticeThemis`: canonical product identity for docs, API metadata, health surfaces, and newly generated operator artifacts
- `overnight-news-handoff`: legacy project identifier that may still appear in historical docs or compatibility surfaces
- `OVERNIGHT_*`: current supported runtime environment-variable contract in this soft-rename phase
- `overnight-news-pipeline` / `overnight-news-launchd-template`: legacy CLI aliases that remain supported for compatibility

<!-- readme-parity:environment-variables -->
## Environment Variables

See [.env.example](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/.env.example).

Important variables:

- `OVERNIGHT_PREMIUM_API_KEY`: required for premium read routes
- `OVERNIGHT_ADMIN_API_KEY`: required for refresh/generate/readyz routes unless unsafe mode is enabled
- `OVERNIGHT_ALLOW_UNSAFE_ADMIN`: local-only escape hatch for development; do not enable in production
- `IFIND_REFRESH_TOKEN`: strongly recommended for complete U.S. market snapshot coverage; without it the service may degrade to Treasury-only partial market snapshots when Yahoo Finance rate-limits
- `ALPHA_VANTAGE_API_KEY`: optional premium ticker-enrichment provider for regime/mainline-linked U.S. symbols and ETFs
- `OVERNIGHT_NEWS_DB_PATH`: optional SQLite path override

The runtime env prefix remains `OVERNIGHT_*` for compatibility in this phase. There is no required env migration to a `JUSTICE_THEMIS_*` prefix yet.

<!-- readme-parity:release-boundary-and-first-run -->
## Release Boundary And First-Run

### Release Verdict

Current evidence-backed verdict on April 16, 2026:

- Supported user cohort: technical self-hosted user / internal operator
- Unsupported user cohort: general end user / low-touch external user
- Current product state: backend beta that is suitable for hands-on technical evaluation, not a finished general-user product

Current blocking reasons for broader release claims:

- premium/admin access still relies on shared header keys instead of end-user accounts
- the first-run path is still an operator workflow, not a low-touch consumer experience
- BLS official pages currently return 403 from this runtime environment, so live runs can finish with warning-level gaps in official macro source coverage

### First-Run Gate

One fresh-checkout success path for the currently supported cohort is:

1. run `uv sync --dev`
2. set `OVERNIGHT_ADMIN_API_KEY` and `OVERNIGHT_PREMIUM_API_KEY` in `.env.local` or process env
3. start `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
4. verify `GET /healthz`, authenticated `GET /readyz`, and `GET /api/v1/news?limit=3`
5. run one real backend evidence pass with `.venv/bin/python -m app.backend_live_run_evidence --analysis-date 2026-04-16`

Degraded-but-acceptable first-run states:

- without `IFIND_REFRESH_TOKEN`, market snapshot can still complete through Treasury/Stooq fallback, but coverage may be thinner
- without `ALPHA_VANTAGE_API_KEY`, ticker enrichment remains skipped while fixed reports still generate
- if BLS official pages return 403, the live run can still finish, but the release verdict remains beta rather than product-complete

Primary failure modes and next step:

- `401` / `403` on `readyz` or mutation routes: check `OVERNIGHT_ADMIN_API_KEY`
- premium read routes rejected: check `OVERNIGHT_PREMIUM_API_KEY`
- `uv sync --dev` or `uvicorn` startup fails: fix the local Python/uv environment before judging product readiness
- live run health stays `warn`: inspect source diagnostics first, especially BLS 403 and rate-limited upstreams

The detailed audit and first-run verdict are recorded in [docs/technical/2026-04-16-user-release-boundary-and-first-run-verdict.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-16-user-release-boundary-and-first-run-verdict.md).

<!-- readme-parity:current-output-layers -->
## Current Output Layers

- `market_snapshot` remains the assembled board contract and now carries additive `capture_summary.provider_hits`, tiered missing-symbol diagnostics, freshness counts, `market_regimes`, and suppressed regime evaluations
- `daily_analysis` keeps the same free/premium top-level shape while adding additive `market_regimes`, `secondary_event_groups`, `ticker_enrichments`, and `enrichment_summary`
- `MMU handoff` now carries confirmed mainlines, additive regime/secondary context, and premium ticker enrichments without breaking current prompt payloads
- `/api/v1/dashboard` exposes confirmed mainlines separately from `market_regimes` and `secondary_event_groups`

<!-- readme-parity:local-startup -->
## Local Startup

Install dependencies:

```bash
uv sync --dev
pnpm install --dir frontend
```

Canonical local verification command:

```bash
uv run pytest -q
```

Run the API server:

```bash
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the standalone frontend preview in a second terminal:

```bash
pnpm --dir frontend dev
```

The frontend preview listens on `http://127.0.0.1:5173` by default and targets the backend through `VITE_API_BASE_URL`.
The default value is `http://127.0.0.1:8000`; override it in `frontend/.env.local` if you want to point the UI at another backend.

The built-in `/ui` operator panel remains a compatibility surface. New product-facing frontend work should go into `frontend/`.

Run the fixed pipeline once:

```bash
uv run justice-themis-pipeline --analysis-date 2026-04-10
```

Legacy compatibility alias still works:

```bash
uv run overnight-news-pipeline --analysis-date 2026-04-10
```

<!-- readme-parity:canonical-upstream-and-sync -->
## Canonical Upstream And Sync

Canonical upstream for version-control history is the remote GitHub repository `Etherstrings/JusticeThemis` on branch `main`.

This local directory is the current standalone implementation source, but it is not itself a Git worktree. Repository convergence therefore MUST happen in an isolated Git-backed convergence workspace cloned from the canonical upstream, not by running `git init` or ad-hoc merge commands inside this directory.

Current convergence prerequisites are documented in [docs/technical/2026-04-14-remote-repository-convergence.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-14-remote-repository-convergence.md). Use that audit before replacing remote paths, adjusting workflows, or proposing a sync branch for review.

The post-sync verification contract is:

- bootstrap dependencies with `uv sync --dev`
- start the service with `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- verify `GET /healthz`, authenticated `GET /readyz`, and `GET /api/v1/news?limit=3`
- run the canonical deterministic regression command `uv run pytest -q`

The current merge-ready branch plan and review notes are recorded in [docs/technical/2026-04-14-convergence-review-summary.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-14-convergence-review-summary.md).

<!-- readme-parity:repository-hygiene -->
## Repository Hygiene

This repository now treats source-owned content and generated local artifacts as two different classes of files.

<!-- readme-parity:source-owned-paths -->
### Source-owned paths

- `app/`
- `tests/`
- `docs/`
- `openspec/`
- `.github/`
- root configuration files such as `pyproject.toml`, `Dockerfile`, `compose.yml`, `.env.example`, and `README.md`

<!-- readme-parity:generated-local-artifacts -->
### Generated local artifacts

- `.venv/`, `.pytest_cache/`, and `__pycache__/`
- `*.egg-info/`
- `data/` runtime databases
- `output/` exported pipeline deliverables
- local logs, coverage outputs, and similar machine-generated files

These generated files are reproducible local artifacts. They are not part of the intended source-owned working set and are excluded by the repository `.gitignore` and `.dockerignore` baselines.

<!-- readme-parity:verification-baseline -->
### Verification baseline

- Bootstrap dependencies with `uv sync --dev`
- Bootstrap frontend dependencies with `pnpm install --dir frontend`
- Run the canonical deterministic regression command with `uv run pytest -q`
- Run `pnpm --dir frontend build` before claiming the standalone frontend preview is shippable
- The repository CI baseline runs the same deterministic test command and does not require live provider credentials or premium/admin secrets

The built-in `/ui` operator panel now stores an admin key in browser local storage only and sends it on `/refresh`. Leave the field blank if you want a read-only view.

<!-- readme-parity:auth-surfaces -->
## Auth Surfaces

Public read routes:

- `GET /healthz`
- `GET /items`
- `GET /handoff`
- `GET /api/v1/dashboard`
- `GET /api/v1/news`
- `GET /api/v1/news/{item_id}`
- `GET /api/v1/sources`
- `GET /api/v1/pipeline/blueprint`
- `GET /api/v1/market/us/daily`
- `GET /api/v1/analysis/daily?tier=free`
- `GET /api/v1/analysis/daily/versions?tier=free`
- `GET /api/v1/analysis/daily/prompt?tier=free`
- `GET /api/v1/mmu/handoff?tier=free`

Premium read routes require `X-Premium-Access-Key`:

- `GET /api/v1/analysis/daily?tier=premium`
- `GET /api/v1/analysis/daily/versions?tier=premium`
- `GET /api/v1/analysis/daily/prompt?tier=premium`
- `GET /api/v1/mmu/handoff?tier=premium`

Admin routes require `X-Admin-Access-Key` unless `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`:

- `POST /refresh`
- `POST /api/v1/market/us/refresh`
- `POST /api/v1/analysis/daily/generate`
- `GET /readyz`

<!-- readme-parity:smoke-check -->
## Smoke Check

Start the API, then run:

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s -H "X-Admin-Access-Key: $OVERNIGHT_ADMIN_API_KEY" http://127.0.0.1:8000/readyz
curl -s http://127.0.0.1:8000/api/v1/news?limit=3
```

For the standalone frontend preview path, also run:

```bash
pnpm --dir frontend dev
pnpm --dir frontend build
```

Expected:

- `healthz` returns `{"status":"ok","service":"JusticeThemis"}`
- `readyz` returns sanitized runtime state, source-registry counts, and provider availability for search, market snapshot, and ticker enrichment
- `/api/v1/news` returns JSON even when the dataset is empty
- `http://127.0.0.1:5173` renders the standalone frontend preview and can load dashboard/news/analysis data against the local backend
- the built-in `/ui` operator panel remains available as a compatibility surface rather than the primary frontend evolution target

For a full CLI smoke, run:

```bash
uv run python -m app.pipeline --analysis-date 2026-04-11 --output-path /tmp/justice-themis-summary.json
```

If `IFIND_REFRESH_TOKEN` is not configured, the pipeline can still complete, but `market_snapshot.capture_status` may remain `partial` because Yahoo Finance chart requests are rate-limited in live runs.

<!-- readme-parity:container-startup -->
## Container Startup

Build and run with Compose:

```bash
docker compose up --build
```

The API will listen on `http://127.0.0.1:8000`.

The Docker build context is filtered by `.dockerignore` so local caches, runtime databases, and exported outputs are excluded from the image build path.

<!-- readme-parity:rollback-notes -->
## Rollback Notes

- If release hardening breaks an existing local workflow, first check whether the instance was previously depending on external repo env files.
- Roll back by redeploying the previous image/build and restoring the previous env contract.
- Do not remove the admin gate in production as a shortcut; use `OVERNIGHT_ADMIN_API_KEY`.

<!-- readme-parity:disabled-source-invariants -->
## Disabled-Source Invariants

The following source ids remain intentionally disabled in this project and should stay disabled during release work:

- `state_spokesperson_releases`
- `dod_news_releases`

<!-- readme-parity:self-hosted-acceptance-criteria -->
## Self-Hosted Acceptance Criteria

- API starts from this repository alone with project-local env files
- `healthz` and authenticated `readyz` both succeed
- public read routes work without premium/admin headers
- premium routes reject unauthenticated requests and succeed with the premium key
- admin mutation routes reject unauthenticated requests and succeed with the admin key
- one end-to-end pipeline run completes successfully
