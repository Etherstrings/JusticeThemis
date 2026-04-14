## 1. Runtime Config Decoupling

- [x] 1.1 Inventory current env loading paths and define the standalone runtime configuration contract, including supported env-file locations and new auth-related variables
- [x] 1.2 Implement a shared config loader for pipeline, API, and validation flows that removes implicit `JusticePlutus` fallback behavior
- [x] 1.3 Add regression tests for config precedence, project-local env loading, and optional-feature degradation when provider keys are missing

## 2. Protected Operation Surfaces

- [x] 2.1 Classify routes into public, premium, and admin surfaces and implement shared auth-guard helpers for those boundaries
- [x] 2.2 Protect refresh/generate/readiness-detail operations with admin authentication plus an explicit unsafe-development override
- [x] 2.3 Add tests covering admin denial, premium denial, free-read success, and readiness disclosure of unsafe-development mode

## 3. Operator Bootstrap And Health

- [x] 3.1 Add repo-root operator assets including `README` and `.env.example` with standalone setup, secrets, and smoke-check guidance
- [x] 3.2 Add container deployment assets such as `Dockerfile` and `compose.yml` wired to the canonical startup command
- [x] 3.3 Add `healthz` and `readyz` routes plus documentation for release verification and rollout expectations

## 4. Premium Analysis Alignment

- [x] 4.1 Update prompt-bundle generation so each bundle is sourced from the matching access-tier report and preserves free/premium content boundaries
- [x] 4.2 Add tier-aware MMU export behavior so premium recommendation context is built from premium report data and requires premium authorization
- [x] 4.3 Add regression tests and API documentation updates for premium prompt and MMU export behavior

## 5. Release Verification

- [x] 5.1 Run the full automated test suite after the hardening changes and record the expected verification commands
- [x] 5.2 Run a full standalone pipeline smoke and a deployment smoke covering startup, health, readiness, and one read route
- [x] 5.3 Update release documentation with rollback notes, disabled-source invariants, and operator acceptance criteria for self-hosted launch
