## 1. README Pair Construction

- [x] 1.1 Update `README.md` to add language navigation, explicit default-entrypoint wording, and any structure identifiers needed for parity verification.
- [x] 1.2 Create root-level `README.zh.md` with the same bootstrap section structure and equivalent Chinese coverage for identity, runtime contract, startup, smoke checks, hygiene, auth surfaces, and convergence notes.
- [x] 1.3 Ensure both README files preserve the same canonical commands, canonical upstream reference, and non-Git convergence guidance.

## 2. Verification And Publication Contract

- [x] 2.1 Add or update deterministic verification so it checks README language-switch links, ordered structure parity, and critical bootstrap invariants across `README.md` and `README.zh.md`.
- [x] 2.2 Update linked technical/bootstrap guidance so it explicitly states that GitHub publication for the README package must happen through the isolated Git-backed convergence workspace.
- [x] 2.3 Verify that the GitHub-ready convergence workspace includes both root README files together before review or merge.

## 3. Acceptance

- [x] 3.1 Run the documentation parity verification and any affected regression commands after the README package is updated.
- [x] 3.2 Review the English and Chinese bootstrap documents for consistency with current product identity, release-boundary wording, and existing smoke/acceptance claims.
