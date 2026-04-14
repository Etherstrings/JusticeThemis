## Why

`overnight-news-handoff` has reached the point where the core overnight pipeline works, but the project is not yet release-ready as a standalone service. It still relies on hidden cross-project environment defaults, exposes privileged API operations too broadly, lacks a standard operator bootstrap package, and does not fully align premium downstream exports with premium report context.

This change hardens the project for standalone self-hosting and controlled release without changing the product thesis. The goal is to turn a working backend MVP into a deployment-ready service boundary with explicit configuration, access control, operator documentation, and premium-tier contract integrity.

## What Changes

- **BREAKING** Remove implicit runtime dependence on env files from unrelated repositories and replace it with a standalone project-local runtime configuration contract.
- **BREAKING** Protect privileged mutation endpoints with explicit admin access rules instead of leaving refresh/generate operations broadly callable.
- Add operator bootstrap and release assets: repo-root setup documentation, environment variable example, container/deployment artifacts, and health/readiness contracts.
- Align premium prompt/MMU export paths with premium analysis context so premium downstream consumers do not inherit free-tier limitations by accident.
- Preserve current source policy boundaries, including keeping disabled sources disabled and avoiding source-expansion scope creep in this hardening change.

## Capabilities

### New Capabilities
- `standalone-runtime-config`: define standalone runtime configuration loading, precedence, and feature-scoped availability rules without hidden cross-project coupling.
- `protected-operations-api`: define public, premium, and admin API access boundaries for read and mutation routes.
- `operator-bootstrap-and-health`: define the operator bootstrap package, deployment entrypoints, and health/readiness verification surfaces required for release.
- `premium-analysis-alignment`: define tier-correct prompt/MMU export behavior and premium recommendation handoff integrity.

### Modified Capabilities
- None.

## Impact

- Affected code: `app/pipeline.py`, `app/live_validation.py`, `app/main.py`, `app/services/daily_analysis.py`, `app/services/pipeline_artifacts.py`, `app/services/mmu_handoff.py`, and related tests.
- Affected APIs: refresh/generate routes, premium analysis read routes, MMU export route, and new health/readiness routes.
- Affected operator surface: env loading, startup contract, deployment instructions, and release smoke flow.
- New repo assets likely required: root `README`, `.env.example`, `Dockerfile`, `compose.yml` or equivalent deployment file, and updated runbooks.
