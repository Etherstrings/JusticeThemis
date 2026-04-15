## Why

截至 `2026-04-15`，`https://readhub.cn/daily` 在当前环境下可直接返回 `200`，并且页面本身已经包含服务端渲染的“每日早报”内容和内嵌 `articles` JSON；对应 `https://readhub.cn/topic/<id>` 详情页还能提供 `tagList`、`trackingList`、`newsList` 和 `similarEventList` 等更丰富结构化数据。当前项目还没有把这类中文聚合晨报源纳入采集面，也没有一个可复现的“真实跑一天后端并生成证据文档”的标准输出路径。

## What Changes

- 新增一个面向 `readhub.cn/daily` 的聚合晨报采集能力，允许系统抓取当天 digest 列表，并按需对 `topic/<id>` 页面做二跳增强。
- 将 Readhub source 明确定义为聚合/编辑类信源，而不是官方事实源，确保它只补充发现与上下文，不覆盖现有官方源优先级。
- 为 Readhub topic enrichment 增加结构化上下文持久化能力，使系统不仅保留扁平摘要，还能保留 tags、聚合外链、历史追踪和同类事件比较信息。
- 新增一条“backend-only live run evidence”交付路径：针对一个真实 analysis date 运行后端全链路，输出可审计 Markdown 文档，展示采集、Readhub 命中、日报生成和关键限制/失败点。
- 为 Readhub 可抓取性与真实运行效果增加 deterministic 测试和 live validation / runbook 约束，使“能不能拉到、效果怎么样”不再依赖人工会话复述。

## Capabilities

### New Capabilities
- `readhub-daily-digest-ingestion`: 定义 Readhub daily 页面抓取、topic 二跳增强、聚合上下文持久化以及在现有 source pipeline 中的优先级边界。
- `backend-live-run-evidence-doc`: 定义一条针对指定 analysis date 的真实后端运行与 Markdown 证据文档产出能力，用于展示实际效果而不依赖前端。

### Modified Capabilities

## Impact

- Affected code will likely include `app/sources/registry.py`, one or more new collectors/parsers under `app/collectors/`, normalization and persistence paths under `app/normalizer.py`, `app/ledger.py`, `app/repository.py`, `app/db.py`, and validation/reporting surfaces such as `app/live_validation.py` and pipeline/export helpers.
- Affected artifacts will likely include new or updated tests under `tests/`, new output/report Markdown under `output/`, and technical run documentation under `docs/technical/`.
- The change adds a new Chinese aggregated source and a reproducible backend evidence path, but it does not require any frontend implementation in this phase.
