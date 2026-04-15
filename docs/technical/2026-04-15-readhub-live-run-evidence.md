# 2026-04-15 Readhub Live Run Evidence

## 目的

把 `Readhub Daily Digest` 的真实采集效果和一条 backend-only 的真实运行结果固定成可复跑、可审计的证据包，不依赖前端。

## 复现命令

```bash
.venv/bin/python -m app.backend_live_run_evidence --analysis-date 2026-04-15
```

默认会：

1. 使用隔离数据库 `data/live-runs/readhub-2026-04-15.db`
2. 使用隔离输出目录 `output/live-runs/readhub-2026-04-15`
3. 跑完整后端流程：
   - source capture
   - market snapshot
   - fixed daily analysis
4. 生成中文优先 evidence doc 和对应 summary / report artifacts

## 本次产物路径

- 证据文档：
  [readhub-backend-live-run-evidence.zh.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/readhub-backend-live-run-evidence.zh.md)
- Pipeline summary JSON：
  [pipeline-summary.json](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/pipeline-summary.json)
- Pipeline summary Markdown：
  [pipeline-summary.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/pipeline-summary.md)
- Free daily report：
  [daily-free.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/daily-free.md)
- Premium daily report：
  [daily-premium.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/daily-premium.md)
- Artifact manifest：
  [artifact-manifest.json](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/artifact-manifest.json)

## 本次真实运行结论

- `Readhub Daily Digest` 成功入库 `2` 条 topic。
- `https://readhub.cn/daily` 可用并作为 canonical endpoint。
- `https://1.readhub.cn/daily` 在本机真实运行中继续 TLS 失败，但被记录为 non-blocking diagnostic，没有中断整条 source refresh。
- Readhub topic enrichment 已保留：
  - `daily.issue_date`
  - `daily.rank`
  - `topic.tags`
  - `topic.tracking`
  - `topic.similar_events`
  - `topic.news_links`
- 本轮完整 capture 共写入 `56` 条 source items，覆盖 `29` 个 source。
- market snapshot 没有整条失败，但只捕获到 `Treasury Yield Curve` 一项，最终 health 仍为 `fail`，原因是 core-board gaps 过多。

## 当前已知限制

- `AP Business` 和 `AP Technology` 在本轮返回 `429`。
- `BLS News Releases` 与 `BLS Release Schedule` 在本轮分别返回 `403`。
- Yahoo fallback 在多数组件行情上继续触发 `429`，导致 market snapshot 只有 `^TNX` 成功。

## 查看重点

优先看这三个文件：

1. [readhub-backend-live-run-evidence.zh.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/readhub-backend-live-run-evidence.zh.md)
2. [pipeline-summary.json](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/pipeline-summary.json)
3. [daily-premium.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/output/live-runs/readhub-2026-04-15/daily-premium.md)
