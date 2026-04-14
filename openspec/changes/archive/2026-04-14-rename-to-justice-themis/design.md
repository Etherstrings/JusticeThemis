## Context

项目当前的产品能力已经明显超出 `overnight-news-handoff` 这个名称所表达的范围。根据现有 README、pipeline blueprint、架构文档和 API 入口，这个系统的核心是：

- 先确认隔夜市场结果
- 再用新闻与证据解释结果
- 最后输出晨间固定分析与模型载荷

因此，当前问题不是“项目是否要继续做 handoff”，而是“项目的对外身份是否仍然被旧命名锁死”。现有代码和文档中包含大量 `overnight-news-handoff`、`overnight_news_handoff` 和 `overnight-news-pipeline` 标识；这些标识分布在包元数据、API title、健康检查、蓝图产物、launchd 模板、默认输出文件名和 operator 文档中。

这次变更的约束是兼容优先：

- 不改 API 路径
- 不改 Python 包结构
- 不改 `OVERNIGHT_*` 环境变量前缀
- 不做数据库 schema 或表名迁移
- 不把一次身份层调整升级成全面的内部重命名工程

## Goals / Non-Goals

**Goals:**

- 为项目建立统一的对外产品身份 `JusticeThemis`
- 让 README、FastAPI title、健康标识、blueprint 顶层身份字段和 operator 产物默认名称都反映新身份
- 明确记录旧标识在软改名阶段的兼容角色，避免 operator 误判为一次全量迁移
- 为后续可能的“硬改名”保留清晰边界和迁移路径

**Non-Goals:**

- 迁移 `OVERNIGHT_*` 环境变量到新前缀
- 迁移 `app` 包名或内部模块名
- 调整现有 API route path，如 `/handoff`
- 变更数据库默认 schema、表名或既有数据文件布局
- 在本次变更中引入新的业务能力或分析逻辑

## Decisions

### Decision: 采用双层身份模型

本次变更将“产品身份”和“兼容运行标识”明确分层：

- 产品身份：`JusticeThemis`
- 兼容运行标识：`overnight-news-handoff`、`overnight-news-pipeline`、`OVERNIGHT_*`

这样可以先修正外部语义，再把高风险的内部迁移留给后续单独 change。

Alternatives considered:

- 直接全量重命名所有 env、模块、路径和数据文件：风险过高，改动面大，容易把品牌调整变成破坏性升级。
- 完全不改名，只在文档里解释：不能解决 API title、health/service 标识和产物标签继续误导 operator 的问题。

### Decision: 只改 operator-facing 和 generated surfaces

本次实现只覆盖以下对外或生成型 surface：

- 根 README 和相关 operator 文档
- `pyproject` 中的项目名/描述和必要脚本命名
- FastAPI title
- `/healthz` 与 `/readyz` 返回中的 `service` 身份
- pipeline blueprint 顶层 `pipeline_name` 或等价身份字段
- launchd label、生成文件默认名、导出产物默认命名

内部实现标识保持不动，以减少兼容风险。

Alternatives considered:

- 同时重命名内部常量、路径和数据库默认文件：会放大影响面，也会让 rollback 更复杂。

### Decision: 保持运行契约稳定

`OVERNIGHT_*` 仍然是本阶段唯一受支持的环境变量前缀；默认数据库路径继续保持当前兼容值。这样 operator 在升级到新身份层后，不需要同时修改部署配置。

Alternatives considered:

- 并行支持新的 `JUSTICE_THEMIS_*` 前缀：会增加运行解析复杂度，也会引入“双前缀谁优先”的治理问题。

### Decision: 增加显式名称映射说明

软改名需要在 README 或等价 operator 文档中提供一份明确映射：

- `JusticeThemis` = 规范产品名
- `overnight-news-handoff` = 旧项目/兼容标识
- `OVERNIGHT_*` = 当前运行时兼容环境变量前缀

这样可以减少 operator 在看到新品牌与旧 env 名混用时的困惑。

## Risks / Trade-offs

- [外部身份与内部标识并存会造成短期混乱] → 在 README 和变更文档中明确“软改名”边界，并给出映射表。
- [修改健康检查 `service` 字段可能影响依赖旧值的外部脚本] → 在实现阶段同步更新测试与 smoke 文档，并把旧值变更列入 migration notes。
- [脚本名或 launchd label 变更可能影响已有本地自动化] → 仅更新新生成默认值，不自动迁移已安装 artifact；文档中提示已有 operator 可按需保留旧 label。
- [一次性替换过多名称会引入漏改] → 以明确的 surface inventory 执行，并通过全文检索与测试回归校验。

## Migration Plan

1. 先更新 proposal 覆盖的规范 surface：README、包元数据、API title、health/readyz、pipeline blueprint、launchd/output 默认命名。
2. 补充一份 operator-facing 名称映射说明，解释为何保留 `OVERNIGHT_*`。
3. 运行测试与 smoke 验证，确认对外身份改名没有破坏现有运行契约。
4. 如果上线后发现外部依赖仍绑定旧 `service` 字段或旧 launchd label，则回滚这些对外标识修改，不需要数据回滚。

## Open Questions

- `project.scripts` 是否在软改名阶段同步改成 `justice-themis-pipeline`，还是保留旧命令名以最大化兼容性？
- pipeline blueprint 是否保留历史 `pipeline_name` 作为附加字段，还是直接切到新值？
- 输出目录内的历史文件是否需要保留旧命名示例，还是只更新新生成默认值？
