## Why

当前本地 `JusticeThemis` 目录已经演进成一个独立的隔夜后端/管线仓库，具备 OpenSpec、独立 README、稳定测试和独立运行边界；但远端 GitHub 仓库 `Etherstrings/JusticeThemis` 仍停留在 `2026-04-06` 的更大工作区形态，包含 `apps/`, `api/`, `src/`, `bot/`, `webui.py` 等多子系统，并持续运行定时 workflow。与此同时，本地目录本身不是 Git 工作树，没有 `origin`，因此既不能直接 `pull`，也不能用普通 merge 流程把当前本地状态并回远端。

这意味着“检查远端进度并与本地合并同步”不是一个简单的 git 操作，而是一项仓库收敛工程：必须先确认远端仓库对当前产品是否仍是 canonical upstream，明确本地 standalone 项目与远端 monorepo 的结构映射，再定义安全的同步与验收路径。否则贸然同步，很容易把当前可用的本地项目覆盖回旧结构，或者把远端正在运行的自动化链路意外打断。

## What Changes

- 建立一套远端 GitHub 仓库与本地 standalone 项目之间的结构收敛与同步方案，而不是把同步等同于 `git pull`。
- 产出一份远端/本地差异审计：包括仓库形态差异、目录映射、关键运行面、CI/workflow 差异，以及哪些内容应保留、替换、迁移或下线。
- 定义 canonical upstream 与 sync target：明确未来应以哪个仓库形态为准，以及本地当前项目如何安全进入 GitHub 受版本控制状态。
- 定义一次可执行的同步流程：获取远端历史、建立受控同步分支或 worktree、导入本地当前项目、保留必要兼容面、执行验证并完成推送。
- 定义同步后的可用性验收标准，确保项目在远端更新后仍然满足当前本地 README/测试所声明的“可运行、可验证、可维护”状态。

## Capabilities

### New Capabilities
- `remote-repository-convergence`: 定义远端 GitHub 仓库与本地 standalone 项目之间的结构映射、保留/替换规则和目标收敛形态。
- `sync-readiness-audit`: 定义远端/本地同步前必须完成的审计内容、风险判断和同步前置条件。

### Modified Capabilities
- `operator-bootstrap-and-health`: 扩展 bootstrap 语义，使仓库文档不仅说明如何运行项目，也说明 canonical upstream、同步前提和同步后的可用性验收路径。

## Impact

- Affected systems: GitHub remote repository `Etherstrings/JusticeThemis`, local project bootstrap flow, future version-control workflow, CI/workflow layout, and release verification path.
- Likely affected artifacts in implementation: repository bootstrap docs, Git metadata/bootstrap files, GitHub workflow layout, and possibly repository structure under the future synchronized upstream.
- Risk profile: high. This change governs how an already-running remote repository and a newer local standalone project are reconciled without losing functionality or operational continuity.
