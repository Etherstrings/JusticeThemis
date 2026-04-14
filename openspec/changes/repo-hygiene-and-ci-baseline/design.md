## Context

`JusticeThemis` 现在已经具备较完整的产品面和稳定的测试面：当前本地回归可以稳定通过 `uv run pytest -q`。但项目目录本身仍然暴露出明显的仓库治理缺口：

- 没有仓库级 `.gitignore`
- 没有 `.dockerignore`
- 没有 CI 工作流
- 工作区内存在 `.venv`、`.pytest_cache`、`__pycache__`
- 根目录同时存在 `justice_themis.egg-info` 和 `overnight_news_handoff.egg-info`
- `data/` 和 `output/` 下存在实际运行产物与导出文件
- 当前目录本身还不是一个受版本控制约束的源码工作区

这意味着项目虽然“能跑、能测、能解释”，但还没有一条清晰的工程边界来回答：

- 哪些文件是仓库应拥有的？
- 哪些文件只是本地运行产物？
- 哪条命令代表可验证通过？
- 什么自动化系统负责在后续变更中持续执行这条验证命令？

在当前阶段，继续扩功能会把这些问题放大；因此最应优先补的是 repo hygiene 和 CI baseline。

## Goals / Non-Goals

**Goals:**

- 定义 source-owned 文件与本地生成产物的边界
- 通过 `.gitignore` / `.dockerignore` 固化 ignore 策略
- 定义一个仓库内的 canonical verification command
- 建立最小可用的 CI workflow，自动执行该验证命令
- 在 README 或等价 bootstrap 文档中写清仓库维护与生成产物边界

**Non-Goals:**

- 引入新的市场、分析或 API 产品能力
- 运行 live provider smoke 或依赖 secrets 的 CI
- 自动删除当前用户本地已有的运行产物
- 迁移 `OVERNIGHT_*` 运行时前缀或数据库 schema
- 把所有历史 `output/` 示例都重构成新的文档资产体系

## Decisions

### Decision: 采用“源码拥有内容 / 本地生成内容”双层边界

本次变更将仓库内容分成两类：

- source-owned：`app/`, `tests/`, `docs/`, `openspec/`, 根配置文件
- generated/local：`.venv`, `.pytest_cache`, `__pycache__`, `*.egg-info`, SQLite 数据库、导出产物、日志等

后者将被明确视为本地产物，不再作为仓库应拥有内容。

Alternatives considered:

- 保持当前目录快照式管理：会让后续版本控制和审查持续混入低价值噪声。
- 立即移动所有历史样例产物：改动面过大，不适合当作第一步基线变更。

### Decision: CI 只跑 deterministic baseline

CI 首阶段只运行与 secrets、外部 provider、live market access 无关的 deterministic verification：

- `uv sync --dev`
- `uv run pytest -q`

这样可以确保 CI 稳定、可复现，不把 provider 波动误当成代码回归。

Alternatives considered:

- 同时跑 live smoke：高噪声、需要 secrets，容易让第一版 CI 不稳定。
- 只写文档不加 CI：无法形成自动守门效果。

### Decision: `.dockerignore` 与 `.gitignore` 协同治理

这次不仅增加 `.gitignore`，也同步加 `.dockerignore`，确保容器构建上下文不把虚拟环境、数据库、导出文件和缓存带入镜像构建过程。

Alternatives considered:

- 只加 `.gitignore`：无法解决 Docker build context 膨胀和无关产物进镜像的问题。

### Decision: 文档中明确 canonical verification command

README 将新增一条明确的仓库验证入口，而不是让维护者从历史命令中自己猜：

- canonical local verification command
- 生成产物与源码边界
- 清理/重建本地产物的基本原则

Alternatives considered:

- 把验证约定只放在 CI 文件里：人看不到，维护门槛仍高。

## Risks / Trade-offs

- [忽略规则写得过宽，可能误伤有价值的样例文件] → 优先按目录和生成类型收口，并保留 `tests/fixtures` / 文档源码等 source-owned 路径。
- [CI 只跑 pytest，覆盖不到未来需要的 lint/type checks] → 先建立稳定 baseline，后续可单独扩展 verification matrix。
- [当前目录还不是 git repo，ignore 规则短期内不直接生效] → 仍然值得先把规则写入仓库，为进入版本控制前提供明确边界。
- [已有 `output/` / `data/` 文件仍会留在本地] → 文档明确它们属于本地产物，不在这次 change 中自动删除。

## Migration Plan

1. 添加仓库级 ignore 文件，定义 generated/local 内容边界。
2. 添加 CI workflow，使用既有 deterministic test suite 作为 baseline gate。
3. 更新 README/bootstrap 文档，明确 source-owned 与 generated 内容的差异，以及 canonical verification command。
4. 在实现完成后通过全文检查和测试验证，确认仓库主路径不再把运行产物当作源码的一部分。

## Open Questions

- 是否要在后续 change 中把部分有展示价值的 `output/` 样例迁移到单独的 `docs/examples/` 或 `tests/fixtures/` 路径？
- 是否要在下一轮把 `ruff` 或类型检查纳入 CI，形成更强的 verification matrix？
- 是否要为“首次把该目录纳入 git”单独写一份 repository bootstrap 文档，而不是只放在 README 中？
