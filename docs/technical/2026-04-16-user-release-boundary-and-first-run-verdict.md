# 2026-04-16 User Release Boundary And First-Run Verdict

## Release Verdict

Date of verdict: 2026-04-16

Current evidence-backed release verdict:

- Supported user cohort: technical self-hosted user / internal operator
- Unsupported user cohort: general end user / low-touch external user
- Current status: backend beta that can generate real reports and real evidence packs, but still stops short of a polished general-user product

## Why This Is The Current Verdict

The current supported cohort is the technical self-hosted user because that user can:

- install dependencies with `uv sync --dev`
- start the API locally with `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- authenticate admin and premium routes with shared keys
- run deterministic tests and inspect real backend outputs without needing a separate frontend

The current unsupported cohort is the general end user because the project still lacks:

- an end-user account and session system
- a low-touch hosted onboarding flow
- non-technical error handling and recovery guidance
- a fully stable live-source plane across all official upstreams

## Verification Path

The current verdict is tied to concrete verification, not opinion-only wording.

Deterministic regression command:

```bash
uv run pytest tests/test_market_snapshot.py tests/test_daily_analysis.py tests/test_pipeline_ops.py tests/test_pipeline_runner.py tests/test_backend_live_run_evidence.py tests/test_report_preview.py
```

Observed result on 2026-04-16:

- `62 passed`

Real backend evidence command:

```bash
.venv/bin/python -m app.backend_live_run_evidence --analysis-date 2026-04-16
```

Observed result on 2026-04-16:

- `analysis_date=2026-04-16`
- `collected_sources=29`
- `collected_items=2`
- `recent_total=20`
- `market_snapshot.status=ok`
- `daily_analysis.status=ok`
- generated artifacts include `daily-free.md`, `daily-premium.md`, `daily-premium.html`, and `readhub-backend-live-run-evidence.zh.md`

Real user-visible backend outputs generated from that run:

- `output/live-runs/readhub-2026-04-16/daily-premium.md`
- `output/live-runs/readhub-2026-04-16/daily-premium.html`
- `output/live-runs/readhub-2026-04-16/readhub-backend-live-run-evidence.zh.md`

## First-Run Gate

One supported first-run path for a new technical self-hosted user is:

1. Run `uv sync --dev`.
2. Put `OVERNIGHT_ADMIN_API_KEY` and `OVERNIGHT_PREMIUM_API_KEY` into `.env.local` or process env.
3. Start the service with `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Verify:
   - `curl -s http://127.0.0.1:8000/healthz`
   - `curl -s -H "X-Admin-Access-Key: $OVERNIGHT_ADMIN_API_KEY" http://127.0.0.1:8000/readyz`
   - `curl -s http://127.0.0.1:8000/api/v1/news?limit=3`
5. Run one live backend evidence pass for `2026-04-16`.

First-run success for the supported cohort means:

- API startup succeeds from this repository alone
- public read routes respond without premium/admin headers
- premium and admin gates behave as documented
- a backend live run emits real markdown/html evidence outputs

## Degraded-but-acceptable first-run states

- Without `IFIND_REFRESH_TOKEN`, market snapshot can still complete through Treasury and Stooq fallback, but coverage can be thinner than a credentialed run.
- Without `ALPHA_VANTAGE_API_KEY`, ticker enrichment can remain skipped while the fixed daily report still renders.
- If repeated runs reuse the same recent window, `collected_items` can stay small even when the recent visible output remains healthy.
- If BLS official pages currently return 403 from this environment, the run can still complete, but official macro-source completeness is not fully product-grade.

## Primary failure modes

- Admin auth failure:
  Next step: verify `OVERNIGHT_ADMIN_API_KEY` and retry `readyz`.
- Premium auth failure:
  Next step: verify `OVERNIGHT_PREMIUM_API_KEY` and retry a premium route.
- Local runtime/bootstrap failure:
  Next step: fix the local `uv` / Python environment before judging the product.
- Live-source warning state:
  Next step: inspect source diagnostics for rate limits, cooldowns, and blocked upstreams.

## Blocking Reasons For Broader Release Claims

- Shared-key auth is still operator-oriented and not an end-user identity surface.
- The built-in `/ui` remains an operator panel, not a complete consumer-facing product front-end.
- BLS official pages currently return 403 from this runtime environment, so macro official-source coverage still has a real live-run stability gap.
- The project can generate real backend outputs, but the operational envelope is still best suited to hands-on technical users.
