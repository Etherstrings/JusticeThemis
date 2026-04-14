## Why

`overnight-news-handoff` 已经不再只是一个 handoff 工具，而是一个以结果为先、用证据约束叙事、面向中国早晨阅读场景的隔夜市场判读系统。当前名称把项目缩窄成“导出给下游模型的转运层”，已经不能准确表达其产品定位，也会让运维、文档和对外标识继续围绕过时语义展开。

现在进行一次兼容优先的软改名，可以先统一产品身份层，把对外可见的名称、标题、健康标识、运行产物标签与文档叙事收敛到更准确的 `JusticeThemis`，同时保留现有 `OVERNIGHT_*` 运行契约，避免把一次品牌调整升级成高风险破坏性迁移。

## What Changes

- 将项目的规范产品名从 `overnight-news-handoff` 调整为 `JusticeThemis`，并将其定位表述为“隔夜市场判读引擎 / 晨间裁决台”，不再以 handoff 作为主语。
- 统一 operator-facing 文档、README、FastAPI 标题、`/healthz` 与 `/readyz` 的服务标识，以及 pipeline blueprint 中的顶层身份字段，使其输出 `JusticeThemis` 对应名称。
- 调整调度模板、默认输出文件名、launchd label 等运行产物命名，使新生成的 operator 产物默认以 `JusticeThemis` 语义命名。
- 明确保留现有 `OVERNIGHT_*` 环境变量、数据库默认路径和内部 Python 包结构，作为软改名阶段的兼容边界。
- 补充一份名称映射和迁移说明，让现有 operator 能区分“外部身份已切换”与“内部兼容标识暂未迁移”。

## Capabilities

### New Capabilities
- `product-identity-surface`: 定义项目对外产品身份、可见名称、生成产物命名和兼容映射规则。

### Modified Capabilities
- `operator-bootstrap-and-health`: 调整 operator 文档和健康检查契约中的规范服务身份，使其反映 `JusticeThemis` 而不是旧项目名。
- `standalone-runtime-config`: 明确软改名阶段继续兼容现有 `OVERNIGHT_*` 运行配置与默认数据库路径，不要求 operator 立即迁移环境变量前缀。

## Impact

- Affected code: `README.md`, `pyproject.toml`, `app/main.py`, `app/api_access.py`, `app/services/pipeline_blueprint.py`, `app/db.py`, `app/schedule_template.py`, `app/services/launchd_template.py`, and operator-facing docs under `docs/`.
- Affected runtime artifacts: default health/readiness service marker, generated pipeline blueprint identity, launchd labels, default output filenames, and bootstrap instructions.
- Compatibility: no required change to `OVERNIGHT_*` env vars, API route paths, or Python module layout in this soft-rename phase.
