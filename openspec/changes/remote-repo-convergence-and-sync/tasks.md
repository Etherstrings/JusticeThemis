## 1. Remote And Local Baseline Audit

- [x] 1.1 Capture the remote `Etherstrings/JusticeThemis` baseline, including default branch, latest commit, top-level structure, active workflows, and operator-facing entrypoints.
- [x] 1.2 Capture the current local standalone baseline, including source-owned paths, canonical bootstrap surfaces, startup commands, and deterministic verification commands.
- [x] 1.3 Produce a convergence mapping that classifies each divergent remote/local path or surface as preserve, replace, migrate, bridge, or retire, and mark unresolved high-risk differences as blockers.

## 2. Convergence Workspace Setup

- [x] 2.1 Create an isolated Git-backed convergence workspace from the remote repository rather than operating inside the current non-Git local directory.
- [x] 2.2 Create a dedicated synchronization branch or equivalent reviewable integration surface from the remote default branch.
- [x] 2.3 Import the current local standalone project into the convergence workspace using the approved structure mapping while excluding generated local artifacts.

## 3. Bootstrap, EntryPoint, And Automation Reconciliation

- [x] 3.1 Update bootstrap documentation to state the canonical upstream, convergence prerequisites, supported startup paths, and post-sync verification contract.
- [x] 3.2 Reconcile remote operator-facing entrypoints, scripts, and workflows so each active surface is either preserved, replaced with a documented successor, or explicitly retired with a migration note.
- [x] 3.3 Ensure ignore rules, container build context, and repository-owned boundaries remain correct after the local project is imported into the Git-backed workspace.

## 4. Sync Readiness And Acceptance Verification

- [x] 4.1 Run the documented bootstrap, health/readiness smoke checks, and canonical deterministic regression path inside the convergence workspace.
- [x] 4.2 Confirm the synchronized workspace satisfies the readiness gates: declared canonical target, complete structure mapping, defined rollback path, and no unresolved blocking audit items.
- [x] 4.3 Prepare a merge-ready review summary describing the resulting repository shape, remaining trade-offs, and the proposed path for merging the convergence branch into the remote mainline.
