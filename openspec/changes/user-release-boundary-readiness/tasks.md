## 1. Release Boundary Audit

- [x] 1.1 Audit the current project against the supported-user and unsupported-user cohorts, using existing tests, smoke paths, auth boundaries, and deployment surfaces as evidence.
- [x] 1.2 Produce a release-verdict document that explicitly states which user cohort is currently supported, which cohort is not supported, and the blocking gaps that prevent broader release claims.
- [x] 1.3 Ensure the audit and verdict reference the concrete verification path rather than opinion-only language.

## 2. First-Run Readiness Guidance

- [x] 2.1 Update bootstrap guidance so a new technical self-hosted user can follow one fresh-checkout path through dependency install, env setup, service startup, and smoke verification.
- [x] 2.2 Document degraded-but-acceptable first-run states when optional provider credentials are absent, including what remains usable and what becomes partial.
- [x] 2.3 Document the primary first-run failure modes and the next troubleshooting step for each failure class.

## 3. Release Boundary Enforcement

- [x] 3.1 Update operator bootstrap and readiness docs so they include the current release verdict, supported audience, unsupported audience, and blocking reasons for broader release.
- [x] 3.2 Add or update tests that verify the bootstrap and technical docs keep the release boundary, first-run gate, and degraded-mode explanations intact.
- [x] 3.3 Run the deterministic regression suite and the documented first-run smoke path to confirm the published verdict still matches observed project behavior.
