# 2026-04-10 Fixed Daily Pipeline

> **日期：** 2026-04-10  
> **项目：** `overnight-news-handoff`  
> **目的：** 把当前已经分散存在的抓取、市场快照、固定日报生成能力收敛成一个可重复执行的一键流水线入口。

> **同日更新：** 流程蓝图、prompt/MMU artifact 导出、webhook delivery 已补齐。详见
> `docs/technical/2026-04-10-blueprint-artifacts-and-delivery.md`

## 1. 新增入口

当前项目内已新增正式 CLI 入口：

```bash
uv run python -m app.pipeline --analysis-date 2026-04-10 --max-sources 6 --limit-per-source 2 --recent-limit 20 --output-path output/pipeline-summary-2026-04-10.json
```

同时 `pyproject.toml` 已注册 script：

```bash
uv run overnight-news-pipeline --analysis-date 2026-04-10
```

## 2. 这条流水线会做什么

固定顺序如下：

1. 读取本机 env 文件
   - `~/Projects/JusticePlutus/.env`
   - `~/Projects/JusticePlutus/.env.local`
2. 注入运行时所需密钥
   - 搜索发现 provider key
   - `IFIND_REFRESH_TOKEN`
   - `OVERNIGHT_PREMIUM_API_KEY`
3. 运行新闻抓取刷新
4. 运行 U.S. market snapshot 刷新
5. 生成 fixed daily analysis
6. 输出 JSON 摘要到 stdout
7. 如指定 `--output-path`，则落盘执行摘要文件

## 3. 2026-04-10 实跑结果

实跑命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --max-sources 6 \
  --limit-per-source 2 \
  --recent-limit 20 \
  --output-path output/pipeline-summary-2026-04-10.json
```

本轮结果：

1. `status=ok`
2. `analysis_date=2026-04-10`
3. `capture`
   - `collected_sources=6`
   - `collected_items=12`
   - `recent_total=20`
4. `market_snapshot`
   - `source_name=iFinD History, Treasury Yield Curve`
   - `capture_status=complete`
   - `captured_instrument_count=23`
   - `missing_symbols=[]`
5. `daily_analysis`
   - `report_count=2`
   - `report_tiers=["free", "premium"]`

## 4. 为什么这一步重要

这一步解决的不是“有没有能力”，而是“有没有固定执行入口”。

在这次更新前：

1. 新闻抓取、市场快照、日报生成是三段分开的后端能力
2. `live_validation` 会自动读取 env 文件，但正式 pipeline 不会
3. 导致全流程命令一开始退化成只剩 `Treasury Yield Curve`，把 `analysis_date` 错打成了 `1991-03-15`

在这次更新后：

1. pipeline 入口已复用 dotenv 注入能力
2. `market_snapshot` 能正确走到 `iFinD + Treasury`
3. `analysis_date` 与 `market_date` 已恢复到正确的 `2026-04-10 / 2026-04-09`
4. 同一篇新闻重复刷新不会再持续累加到 fixed daily analysis 输入里

## 5. 当前仍未完成的部分

这条流水线虽然已经能跑通，但仍有几类能力没有完成。

### 5.1 调度与自动运行

当前已经完成：

1. `launchd plist` 生成
2. `launchd install/unload/status/tail` 运维计划导出

但还没有完成：

1. 真正安装并加载 `launchd`
2. 固定 `06:15 Asia/Shanghai` 冻结窗口的自动执行策略落地
3. 每日 smoke 与失败告警

### 5.2 信源层

1. `BIS` 的 search fallback 仍保持 disabled
2. `DOE` search discovery 仍是可用但低覆盖
3. `Tavily` 在官方站点 query 上仍不稳定
4. `X` 接入尚未开始

### 5.3 分析层

1. 当前 fixed daily analysis 仍是 rule-based provider
2. MMU handoff payload 已具备，但还没有真正接外部模型执行
3. premium 推荐仍是方向到股票池的映射，不是实盘级投研引擎

### 5.4 输出层

1. `summary / daily report / blueprint` 的 Markdown 导出已完成
2. `daily_free_prompt / daily_premium_prompt / mmu_handoff` JSON 导出已完成
3. `webhook` 分发已完成
4. 还没有 `Telegram / Feishu / WeChat / Email`
5. 还没有 `PDF` 导出

## 6. 现在最值钱的下一步

如果按产品推进顺序排优先级，最值得继续做的是：

1. 把这条 CLI 流水线挂到定时调度
2. 增加每日 smoke 与失败告警
3. 接一个真正的外部 LLM 消费 `/api/v1/mmu/handoff` 或 `/api/v1/analysis/daily/prompt`
4. 再继续补 DOE query，不急着硬开 BIS fallback
5. 补多通道分发与 PDF 导出
