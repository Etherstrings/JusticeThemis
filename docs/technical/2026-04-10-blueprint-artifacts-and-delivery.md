# 2026-04-10 Blueprint, Artifacts, and Delivery

> **日期：** 2026-04-10  
> **项目：** `overnight-news-handoff`  
> **目的：** 把“抓取什么、抓多少、怎么处理、如何给下游”从隐含逻辑固化成明确的后端能力。

## 1. 这次更新解决了什么

这次不是继续往抓取层乱堆代码，而是把整条链路补成一个更像产品的生产流程。

本次新增三层能力：

1. `Pipeline Blueprint`
   - 把固定晨间流程、信源分层、默认预算、API/CLI 入口显式化
2. `Artifact Export`
   - 把 `daily_free_prompt / daily_premium_prompt / mmu_handoff` 变成正式导出产物
3. `Webhook Delivery`
   - 把摘要、蓝图和导出产物打包推给外部系统

## 2. 现在的固定流程是什么

### 2.1 入口

当前有两类正式入口。

CLI：

```bash
uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --max-sources 6 \
  --limit-per-source 2 \
  --recent-limit 20 \
  --output-path output/pipeline-summary-2026-04-10.json
```

API：

1. `/api/v1/pipeline/blueprint`
2. `/api/v1/dashboard`
3. `/api/v1/market/us/daily`
4. `/api/v1/analysis/daily`
5. `/api/v1/analysis/daily/prompt`
6. `/api/v1/mmu/handoff`

### 2.2 默认抓取层

当前抓取层按 `coverage_tier` 分三条主线：

1. `official_policy`
   - 白宫、联储、USTR、Treasury、OFAC、DOE 等
2. `official_data`
   - Census、BLS、BEA、EIA 等
3. `editorial_media`
   - Reuters、AP、CNBC 等

这些不是平铺处理，而是按优先级与可信度分层处理。

### 2.3 默认配额

由 pipeline 参数控制：

1. `max_sources`
   - 单次运行最多刷新多少个信源
2. `limit_per_source`
   - 每个信源最多保留多少条
3. `recent_limit`
   - 最近窗口保留多少条用于 handoff / dashboard / daily analysis

因此“默认会拉多少”的答案不是一个死数，而是：

```text
理论条目上限 = min(启用信源数, max_sources) * limit_per_source
最近窗口上限 = recent_limit
```

同时：

1. `market_snapshot` 会额外拉固定 23 个跨资产观察对象
2. 这些对象已经覆盖
   - 美股指数
   - 板块 ETF
   - 美债收益率与汇率
   - 黄金白银
   - 原油天然气
   - 工业金属
   - 中国映射期货

## 3. 中间怎么处理

### 3.1 Capture Refresh

按 registry 抓：

1. `rss`
2. `section_page`
3. `calendar_page`
4. 必要时 `search_discovery`

### 3.2 Normalization and Guardrails

每条新闻进入统一标准化层，至少处理：

1. 时间字段
2. 规范 URL
3. 摘录来源与摘录质量
4. 数字事实
5. 来源完整性与可信度
6. 与 A 股相关性、潜在受益/承压/涨价方向

另外，这一层现在还包含两道“固定日报稳定性”守卫：

1. 同一 `canonical_url + content_hash` 的完全相同新闻不会重复入库
2. 即使旧数据库里已经有历史重复项，`recent_items` 与 daily analysis 输入也会去重

### 3.3 Event Clustering

多来源报道同一事件时不会直接重复送到分析层，而是先聚成 `event_group`。

这一步的意义是：

1. 防止一个 headline 在媒体间转载后被重复计权
2. 允许官方源与媒体源交叉确认
3. 为后续 `mainline` 和 `MMU handoff` 提供更稳的输入

### 3.4 Market Snapshot

在中国早晨场景里，最重要的逻辑是：

1. 先接受昨夜美股结果已经走完
2. 再用新闻解释为什么

也就是：

1. 不是先靠新闻猜盘
2. 而是先看昨夜市场已经怎么定价
3. 再把新闻主线映射回 A 股方向

### 3.5 Fixed Daily Analysis

日报层仍然分两档：

1. `free`
   - 方向、主线、风险点
2. `premium`
   - 在同一事实底座上输出更细的映射和股票池

当前 provider 仍以 `rule_based` 为主，但其角色已经更明确：

1. 先给固定缓存结论
2. 再为下游 AI 判断提供约束好的输入

## 4. 现在能导出什么

### 4.1 Markdown

已支持：

1. pipeline summary markdown
2. free daily report markdown
3. premium daily report markdown
4. pipeline blueprint markdown

### 4.2 JSON

已支持：

1. pipeline summary json
2. pipeline blueprint json
3. `daily_free_prompt`
4. `daily_premium_prompt`
5. `mmu_handoff`

### 4.3 新增 CLI 参数

这次新增：

1. `--blueprint-json-path`
2. `--blueprint-markdown-path`
3. `--daily-free-prompt-path`
4. `--daily-premium-prompt-path`
5. `--mmu-handoff-path`
6. `--delivery-webhook-url`
7. `--delivery-timeout-seconds`

## 5. Webhook Delivery 现在怎么工作

如果传入：

```bash
--delivery-webhook-url https://example.com/hook
```

pipeline 会把以下内容打成一个 JSON 包：

1. `summary`
2. `health`
3. `blueprint`
4. `artifacts`
5. `artifact_payloads`

这意味着下游系统可以直接消费：

1. 固定日报 prompt
2. staged MMU handoff
3. 当前 pipeline 健康状态
4. 当前抓取预算与禁用源策略

当前还补上了两条运行约束：

1. 本地 artifact 会先写盘，再触发 webhook
2. webhook 若失败，只会把 `delivery.status` 标成 `fail`，不会吞掉已经完成的本地输出

## 6. 已完成项

截至本次迭代，下面这些已经完成：

1. 独立项目边界已稳定，只维护 `overnight-news-handoff`
2. 默认信源 registry 已明确禁用 `State / DoD`
3. 搜索发现补漏已有 provider 注入与权威站点过滤
4. 美股与跨资产快照已稳定到 23/23
5. 固定 daily pipeline CLI 已跑通
6. pipeline health 评估已上线
7. summary/free/premium markdown 导出已上线
8. `pipeline blueprint` API 与 markdown/json 导出已上线
9. `daily_free_prompt / daily_premium_prompt / mmu_handoff` 导出已上线
10. `webhook delivery` 已上线
11. 相同新闻重复刷新不再重复入库
12. 历史重复条目不会再污染 fixed daily analysis 输入
13. 同日复跑若无新增条目，health 改为 `warn` 而不是误判 `fail`
14. `analysis_date` 现在会真正贯穿到 MMU handoff 生成链路
15. `skip-market-snapshot / skip-daily-analysis` 不会再错误导出依赖这些阶段的 artifact
16. webhook 失败不会再阻断本地 summary/markdown/json 写盘

## 7. 还没完成的

仍未完成的部分需要明确区分：

### 7.1 已有接口，但未真正自动化

1. `launchd` 运维计划已经能导出，但还没有真正安装到主机
2. 还没有固定失败重试与告警升级
3. 还没有每日自动 smoke 执行记录

### 7.2 已有 handoff，但未真正接外部模型执行

1. `MMU handoff` 已经能导出
2. `daily prompt bundle` 已经能导出
3. 但还没有内置的 OpenAI / Gemini / Anthropic 实际调用执行器

### 7.3 信源层仍有扩展空间

1. `BIS` search fallback 仍然保持停用
2. `DOE` 可继续补 query
3. `X` 仍未接入
4. 更多财经媒体或付费源尚未接入

### 7.4 分发层仍然偏基础

1. 当前只有 `webhook`
2. 还没有 `Telegram / Feishu / Email / WeChat`
3. 还没有 `PDF` 导出

## 8. 下一步最值得做什么

如果继续按产品价值排序，建议顺序是：

1. 真正安装 `launchd`，把每天 `06:15 Asia/Shanghai` 固化
2. 接一个外部模型执行器，消费 `daily prompt` 与 `MMU handoff`
3. 增加失败通知通道
4. 继续扩充高质量国际财经与市场信源

## 9. 这一轮之后，回答你的核心问题

### 9.1 入口有哪些

1. 固定 pipeline CLI
2. dashboard API
3. daily analysis API
4. daily prompt API
5. MMU handoff API
6. pipeline blueprint API

### 9.2 大约拉多少

由 `max_sources * limit_per_source` 决定新闻理论上限；  
由 `recent_limit` 决定分析窗口；  
由固定 23 个观察对象决定市场快照规模。

### 9.3 中间怎么处理

抓取 -> 标准化 -> 可信度约束 -> 事件聚类 -> 市场快照 -> 固定日报 -> prompt/MMU 导出 -> webhook 分发。

### 9.4 最后怎么给你

现在至少有三种形式：

1. API 读取
2. 本地 markdown/json 文件
3. webhook 推给你的下游服务
