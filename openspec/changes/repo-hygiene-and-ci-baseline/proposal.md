## Why

`JusticeThemis` 现在的业务层已经比较完整，测试也稳定通过，但仓库外壳仍然缺少最基本的工程约束：项目目录里存在 `.venv`、`.pytest_cache`、`__pycache__`、SQLite 数据文件、导出产物和双份 egg-info，且当前没有仓库级 `.gitignore`、`.dockerignore` 或 CI 工作流来定义“什么是源代码、什么是生成物、什么命令代表可验证通过”。

如果现在不先补这块基线，后续每次继续迭代都会优先撞上工作区污染、产物误提交、镜像上下文膨胀和“本机能跑但没有自动回归”的问题。对这个项目来说，下一步最必须继续迭代的不是再加新产品功能，而是把仓库治理和自动验证补到能支撑持续开发的程度。

## What Changes

- 建立仓库级 hygiene baseline，明确哪些目录/文件属于 source-owned，哪些属于本地运行、缓存或导出产物，并通过 ignore 规则固化下来。
- 建立最小 CI baseline，使用仓库内已经稳定的 `uv` + `pytest` 验证链，定义一个规范的自动回归入口。
- 收敛打包与生成产物边界，避免 `.egg-info`、`data/*.db`、`output/*`、`__pycache__` 这类文件继续混入日常开发面。
- 更新 operator/bootstrap 文档，使贡献者或未来维护者能够区分“仓库应保留的文件”和“本地运行后自然产生的文件”。
- **BREAKING** 将仓库治理语义从“目录快照可直接运行”提升为“受约束的源码工作区”；已有本地产物不会被自动删除，但今后不再视为仓库拥有内容。

## Capabilities

### New Capabilities
- `repository-hygiene-baseline`: 定义源码工作区、生成产物、缓存文件、数据文件和打包产物的边界，以及仓库级 ignore 规则。
- `continuous-verification-baseline`: 定义仓库内的最小自动验证工作流，使项目拥有统一的本地/CI 回归命令和通过标准。

### Modified Capabilities
- `operator-bootstrap-and-health`: 补充仓库 bootstrap 与维护说明，使 operator/maintainer 能明确区分仓库拥有内容、运行时生成内容和标准验证入口。

## Impact

- Affected files likely include `.gitignore`, `.dockerignore`, `.github/workflows/*`, `README.md`, selected docs under `docs/`, and possibly small packaging/bootstrap adjustments in `pyproject.toml`.
- Affected systems: local development workflow, Docker build context, repository cleanliness, contribution bootstrap flow, and automated regression verification.
- Non-goals in this change: no new market-data, analysis, or API product features; no environment-variable prefix migration; no database schema change.
