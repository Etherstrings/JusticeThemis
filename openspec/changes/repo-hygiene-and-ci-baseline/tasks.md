## 1. Repository Hygiene Baseline

- [x] 1.1 Add repository-level ignore files that exclude generated local artifacts such as virtualenvs, caches, `__pycache__`, egg-info directories, runtime databases, logs, and exported pipeline outputs.
- [x] 1.2 Review current source-owned versus generated paths and update the repository layout or ignore exceptions so committed fixtures/docs remain source-owned while local runtime artifacts are treated as reproducible outputs.

## 2. Continuous Verification Baseline

- [x] 2.1 Add a minimal CI workflow that installs dependencies in a clean environment and runs the canonical deterministic regression command for this repository.
- [x] 2.2 Ensure the CI baseline and local verification path do not depend on live provider credentials, premium keys, or external runtime state.

## 3. Bootstrap And Maintenance Guidance

- [x] 3.1 Update `README.md` and related bootstrap docs to document source-owned paths, generated-artifact boundaries, the canonical verification command, and how local runtime artifacts should be treated.
- [x] 3.2 Add or update container-build hygiene guidance so Docker build context excludes generated local artifacts in the same way as the repository working set.

## 4. Verification

- [x] 4.1 Run repository-focused checks to confirm ignored/generated artifacts are no longer part of the intended tracked working set.
- [x] 4.2 Run the canonical local regression command and verify the project still passes after the hygiene and CI baseline changes.
