# 2026-04-14 Remote Repository Convergence Audit

## Objective

Reconcile the current local `JusticeThemis` standalone project with the remote GitHub repository `Etherstrings/JusticeThemis` without losing remote Git history, breaking active automation, or regressing the current standalone runtime and verification contract.

## Remote Baseline

- Canonical repository: `https://github.com/Etherstrings/JusticeThemis`
- Default branch: `main`
- Repository description: `A-share overnight decision workspace translating overseas news into pre-open actions.`
- Latest observed push timestamp: `2026-04-06T16:36:45Z`
- Latest observed `main` commit: `f3362f92984c3035d79240b546f2780a64801e14`
- Latest observed commit message: `feat: broaden default overnight source coverage`

Remote top-level structure still reflects a broader workspace / monorepo shape:

- root files: `.dockerignore`, `.env.example`, `.gitignore`, `AGENTS.md`, `LICENSE`, `README.md`, `main.py`, `server.py`, `webui.py`, `requirements.txt`, `setup.cfg`
- root directories: `api/`, `apps/`, `bot/`, `data_provider/`, `docker/`, `docs/`, `patch/`, `scripts/`, `sources/`, `src/`, `strategies/`, `tests/`

Active remote workflows currently present under `.github/workflows/`:

- `auto-tag.yml`
- `ci.yml`
- `daily_analysis.yml`
- `desktop-release.yml`
- `docker-publish.yml`
- `ghcr-dockerhub.yml`
- `network-smoke.yml`
- `pr-review.yml`
- `stale.yml`

Remote operator-facing entrypoints that require an explicit convergence decision:

- `main.py`
- `server.py`
- `webui.py`
- scheduled automation in `daily_analysis.yml`
- Docker publishing and desktop release workflows

## Local Baseline

Current local repository shape reflects a standalone backend/runtime project:

- source-owned roots: `app/`, `tests/`, `docs/`, `openspec/`, `.github/`
- root files: `README.md`, `pyproject.toml`, `Dockerfile`, `compose.yml`, `.env.example`, `.gitignore`, `.dockerignore`, `uv.lock`
- canonical runtime entrypoint: `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- canonical deterministic verification command: `uv run pytest -q`
- canonical one-shot pipeline command: `uv run justice-themis-pipeline --analysis-date 2026-04-10`

This directory is not currently under Git control. Direct `git status` returns:

```text
fatal: not a git repository (or any of the parent directories): .git
```

That fact blocks any safe direct `pull`, `merge`, or branch-based sync inside the current working directory.

## Structure Mapping

| Surface | Remote state | Local state | Convergence action |
| --- | --- | --- | --- |
| Version-control history | remote `main` branch exists and is active | no local `.git` metadata | preserve remote history |
| Runtime application code | `src/`, `api/`, `apps/`, `server.py`, `main.py` | `app/` package with FastAPI entrypoint | replace old runtime layout with local standalone runtime, keep explicit migration notes |
| Frontend/operator surface | `webui.py` and older workspace UI paths | bundled static UI under `app/ui/` served by FastAPI | migrate to `app/ui/`, retire `webui.py` with documented successor |
| Tests | remote `tests/` target old workspace shape | local `tests/` cover standalone runtime and APIs | replace with local deterministic suite, preserve CI gate |
| Workflow baseline | multiple remote workflows including scheduled jobs and release flows | minimal deterministic `.github/workflows/ci.yml` | preserve standalone CI, retire remote scheduled/release workflows in the convergence branch with explicit migration notes |
| Docker/build | remote `docker/` plus publish workflows | local `Dockerfile`, `compose.yml`, `.dockerignore` | migrate to local container contract, review publish workflow compatibility |
| Docs/bootstrap | remote README for older workspace shape | local `README.md` plus root `README.zh.md` companion for standalone `JusticeThemis` | replace bootstrap docs with the local bilingual README package, preserve canonical runtime contract plus sync notes, and publish both root README files together |
| Secrets/runtime env contract | remote shape unknown from local code | local `OVERNIGHT_*` compatibility contract | preserve current runtime env contract during first sync |

## Active Surface Decisions

- Preserve remote Git history, `AGENTS.md`, and `LICENSE`.
- Replace legacy top-level entrypoints `main.py`, `server.py`, and `webui.py` with compatibility shims that start the current FastAPI app and keep `/ui` reachable through the standalone service.
- Preserve `.github/workflows/ci.yml` as the canonical deterministic baseline workflow.
- Retire remote workflows `auto-tag.yml`, `daily_analysis.yml`, `desktop-release.yml`, `docker-publish.yml`, `ghcr-dockerhub.yml`, `network-smoke.yml`, `pr-review.yml`, and `stale.yml` in the convergence branch until standalone-specific successors are defined.
- Retire workspace-only directories such as `api/`, `apps/`, `bot/`, `data_provider/`, `src/`, and `strategies/` from the first convergence branch because their runtime roles are replaced by the standalone `app/` package and current bootstrap docs.

## Blocking Risks

- Remote scheduled workflows may still assume legacy paths, commands, or artifacts that the standalone runtime no longer provides.
- `webui.py`, `server.py`, and `main.py` may still be referenced by operators or automation and cannot be deleted without a documented successor.
- Docker and desktop-release workflows may fail after import if they assume the old workspace layout.
- Local source import must exclude generated artifacts such as `.venv/`, `.pytest_cache/`, `__pycache__/`, `data/`, and `output/`.
- The local deterministic suite is green in this standalone directory, but it still must be re-run in the convergence workspace before the branch is reviewable.

## Readiness Gates

Synchronization is allowed only when all of the following are true:

1. The canonical target is declared as remote `Etherstrings/JusticeThemis` history plus imported local standalone content.
2. Work happens in an isolated Git-backed convergence workspace cloned from the remote repository.
3. A dedicated sync branch is created off remote `main`.
4. Every divergent path is classified as preserve, replace, migrate, bridge, or retire.
5. A rollback path exists: discard the convergence branch and keep remote `main` untouched.
6. Bootstrap, health/readiness, and deterministic regression checks are defined and executable in the convergence workspace.

## Recommended Sync Procedure

1. Clone `Etherstrings/JusticeThemis` into an isolated workspace outside this non-Git directory.
2. Create a branch such as `codex/remote-repo-convergence` from remote `main`.
3. Copy local source-owned content into that workspace while excluding generated artifacts and local-only control folders.
4. Import the root README package as a unit so `README.md` and `README.zh.md` both exist in the convergence workspace before review.
5. Reconcile operator-facing entrypoints and high-risk workflows before removing legacy files.
6. Run bootstrap and smoke checks, then run `uv run pytest -q`.
7. Review the resulting diff and only then propose merging the convergence branch.

## Rollback Path

- If convergence validation fails, discard the isolated workspace or reset the convergence branch to remote `main`.
- Do not force-push over remote `main`.
- Do not mutate this non-Git source directory in ways that assume remote history has already been imported.
