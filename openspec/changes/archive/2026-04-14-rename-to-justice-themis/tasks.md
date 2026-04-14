## 1. Product Identity Surfaces

- [x] 1.1 Update `README.md`, package metadata, and operator-facing bootstrap docs to present `JusticeThemis` as the canonical product identity and include a legacy-name compatibility mapping.
- [x] 1.2 Update `app/main.py`, `app/api_access.py`, and `app/services/pipeline_blueprint.py` so API metadata, liveness/readiness identity, and blueprint-facing identity surfaces report `JusticeThemis`.

## 2. Generated Artifact Naming And Compatibility Boundary

- [x] 2.1 Update `app/schedule_template.py`, `app/services/launchd_template.py`, and related generated-output defaults so new operator artifacts use `JusticeThemis`-aligned labels and filenames.
- [x] 2.2 Preserve the existing `OVERNIGHT_*` runtime contract and default database-path compatibility in code and docs, without introducing a second env-prefix scheme in this phase.

## 3. Verification And Migration Notes

- [x] 3.1 Update tests, smoke expectations, and any identity-specific documentation that currently asserts `overnight-news-handoff` as the canonical external service name.
- [x] 3.2 Run rename-focused string checks and the automated test suite to verify that legacy names remain only on approved compatibility surfaces after the soft rename.
