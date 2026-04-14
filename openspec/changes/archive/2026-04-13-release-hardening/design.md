## Context

`overnight-news-handoff` already has a working overnight capture pipeline, a U.S. market-close snapshot path, deterministic free/premium daily reports, and prompt/MMU export surfaces. Fresh validation shows the end-to-end pipeline can run successfully and the current test suite is stable.

The release gaps are concentrated in cross-cutting concerns rather than core data capture. The current runtime still defaults to env files from another repository, several mutation endpoints are effectively unprotected, repo-root deployment artifacts are missing, and premium downstream exports are not fully aligned with premium report data. There are also no existing OpenSpec specs in this repository yet, so this change establishes the first release-oriented capability contracts.

The user constraints for this hardening phase are:

- keep this as a standalone project
- do not broaden scope into major source expansion work
- do not re-enable disabled State Department or DoD sources
- do not treat inline external model execution as part of release hardening

## Goals / Non-Goals

**Goals:**
- Remove hidden cross-project runtime coupling and make configuration resolution explicit.
- Protect privileged mutation surfaces without introducing a full user-account system.
- Add a release-ready operator bootstrap package and runtime health/readiness contract.
- Align premium prompt/MMU exports with premium report context while preserving deterministic fixed report generation.

**Non-Goals:**
- Expanding source coverage, adding X ingestion, or redesigning source ranking logic.
- Building multi-tenant auth, OAuth, billing, or user management.
- Replacing deterministic fixed report generation with inline external LLM execution.
- Frontend redesign or broader product-surface refactoring.
- Re-enabling disabled policy sources that were intentionally turned off for this project.

## Decisions

### 1. Centralize runtime configuration with explicit standalone precedence

The project will move to a shared runtime configuration contract used by CLI, API, and validation flows. Resolution order should be explicit and standalone:

1. process environment
2. explicit env-file path when provided
3. project-local `.env.local`
4. project-local `.env`

The runtime must not silently probe env files from unrelated repositories. Optional providers remain feature-scoped: missing search or market credentials should disable only the dependent feature, not corrupt unrelated pipeline stages.

Alternatives considered:
- Continue falling back to `JusticePlutus` env files: rejected because it breaks standalone release semantics and creates hidden deployment coupling.
- Require process env only: rejected because it weakens operator ergonomics for local/self-hosted deployments.

### 2. Introduce three explicit access surfaces: public, premium, and admin

The API surface should be classified as:

- `public read`: non-premium read routes that can remain open in a private/self-hosted deployment
- `premium read`: read routes that expose premium report data and require the premium access key
- `admin operation`: refresh/generate/readiness-detail routes that mutate state or expose sensitive operational detail

Admin routes will require a dedicated admin credential such as `OVERNIGHT_ADMIN_API_KEY`. For local development only, an explicit unsafe override flag can be supported, but it must be opt-in and visible in readiness output. Safe behavior should be the default.

Alternatives considered:
- Full JWT/OAuth auth layer: rejected as overbuilt for this release-hardening phase.
- Leaving mutation routes open and relying on private-network placement: rejected because accidental exposure is too easy and release hardening needs explicit control.

### 3. Add a first-class operator bootstrap package

This repo should become operable without tribal knowledge. Release hardening therefore includes:

- root `README` with supported startup paths
- `.env.example` documenting required and optional variables
- container/deployment artifacts such as `Dockerfile` and `compose.yml`
- one documented smoke path
- health/readiness routes with sanitized outputs

The minimal public health route should answer liveness without leaking secrets. Detailed readiness should summarize DB availability, runtime mode, source-registry counts, feature availability, and unsafe-mode state, and it should be protected if it exposes more than a simple status.

Alternatives considered:
- Keep only launchd-oriented docs: rejected because that is a host-specific convenience path, not a general release contract.
- Add only docs with no runtime health routes: rejected because operators need machine-checkable readiness, not just prose.

### 4. Keep fixed reports deterministic and align premium downstream exports

The daily fixed report remains deterministic in this change. Prompt bundles and MMU handoff payloads are still exports for downstream model execution, not inline model generation during report creation.

However, the tier boundaries must become correct:

- free prompt export must remain free-only and non-stock-specific
- premium prompt export must be built from the premium cached report
- premium MMU recommendation context must use premium report data rather than inheriting free-only context

This likely implies adding explicit tier selection to MMU export behavior or otherwise making premium recommendation export an authenticated premium surface.

Alternatives considered:
- Keep MMU premium recommendation built from the free report: rejected because it weakens premium integrity and makes downstream premium reasoning inconsistent.
- Call an external model inline to solve the alignment issue: rejected because it changes the product/runtime model rather than hardening the current one.

### 5. Roll out with explicit migration and failure visibility

This change should be treated as release-hardening, not a silent refactor. Hidden defaults are removed intentionally, so migration needs explicit documentation and readiness feedback.

The rollout path should be:

1. introduce shared config loader and new documented env contract
2. wire API auth boundaries and readiness output
3. add repo-root deployment assets and smoke path
4. align premium export flow
5. verify full pipeline, health/readiness, and deployment boot

Rollback should be operationally simple: redeploy the previous build and previous env contract if needed. Route paths should remain stable where possible so rollback is packaging/config focused rather than client-breaking.

## Risks / Trade-offs

- [Risk] Existing local workflows break after external env fallback is removed. → Mitigation: ship `.env.example`, clear startup/readiness diagnostics, and migration docs that name the old assumption explicitly.
- [Risk] Admin-key requirements disrupt existing automation. → Mitigation: document required headers and provide compose/env wiring examples plus a local-only unsafe override.
- [Risk] Health/readiness routes expose too much operational detail. → Mitigation: keep `/healthz` minimal and sanitize or protect detailed readiness output.
- [Risk] Premium export alignment changes downstream consumer expectations. → Mitigation: keep free behavior stable, document tiered MMU behavior, and add regression tests around premium export payloads.
- [Risk] Container/deployment assets add maintenance overhead. → Mitigation: keep the supported deployment path minimal and ensure it uses the same canonical startup command as docs and smoke tests.

## Migration Plan

1. Add standalone runtime configuration loader and remove implicit external repo fallbacks.
2. Introduce admin-route protection and readiness reporting.
3. Add root deployment assets and operator bootstrap docs.
4. Make prompt/MMU exports tier-correct for premium use.
5. Run full tests, full pipeline smoke, and deployment smoke before release.

## Open Questions

- Should premium MMU export use a `tier` query parameter on the existing route or a separate premium route?
- Should detailed readiness be admin-protected by default, or acceptable as an internal-network-only surface?
- Is Docker Compose the primary release path, or should launchd remain the canonical self-hosted path with container support as secondary?
