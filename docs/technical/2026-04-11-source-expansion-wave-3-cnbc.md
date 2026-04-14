# 2026-04-11 Source Expansion Wave 3 CNBC

## 1. 目标

在 wave 2 已经补上商品媒体层之后，这一轮继续补强两个用户最关心的层面：

1. 美股盘后与宏观 headline
2. 科技股与 AI / 芯片主线

本轮仍然只维护 `overnight-news-handoff`，不触碰其它项目。

## 2. 候选源调研

本轮实际验证了以下候选源：

### 2.1 可用且质量较好

1. `CNBC Markets RSS`
2. `CNBC Technology RSS`
3. `CNBC Business RSS`
4. `CNBC U.S. News RSS`
5. `Yahoo Finance RSS`

### 2.2 可用但当前不建议接生产

1. `Yahoo Finance RSS`
   - 可抓
   - 正文扩展也能工作
   - 但混入较多合作内容、门户分发内容和非核心市场内容
2. `MarketWatch RSS`
   - feed 可抓
   - 但文章页当前环境下返回 `401/Forbidden`
   - 不适合当前 direct article expansion 链路
3. `Investing.com RSS`
   - feed 可抓
   - 但实际返回内容明显陈旧，不适合作为当前生产层信源

### 2.3 当前不值得继续投入

1. `FXStreet RSS`
   - `403`
2. `AgWeb RSS`
   - `403`
3. `Mining Weekly RSS`
   - `403`

结论：

1. 当前最合适的新生产源是 `CNBC Markets`
2. 第二个是 `CNBC Technology`

## 3. 本轮新增信源

新增：

1. `cnbc_markets`
2. `cnbc_technology`

分类：

1. `coverage_tier = editorial_media`
2. `source_group = market_media`
3. `source_tier = P2`

内容模式：

1. `cnbc_markets -> content_mode = market`
2. `cnbc_technology -> content_mode = technology`

## 4. 默认预算更新

为了让新增源不是“接入但默认跑不到”，本轮把运行时默认预算从：

1. `24 / 6 / 120`

更新为：

1. `26 / 6 / 120`

对应变化：

1. `DEFAULT_CAPTURE_MAX_SOURCES = 26`

这样 `CNBC Markets` 和 `CNBC Technology` 可以在不挤掉 wave 2 关键源的前提下直接进入默认采集池。

## 5. 默认选中结果

按当前默认排序后的前 `26` 个 source 中，已确认包含：

1. `cnbc_markets`
2. `cnbc_technology`
3. `kitco_news`
4. `oilprice_world_news`
5. `farmdoc_daily`

这意味着：

1. 美股市场层增强已经进入默认生产路径
2. 不是只有手工 smoke 可用

## 6. 在线冒烟结果

### 6.1 `cnbc_markets`

结果：

1. `candidate_count = 30`
2. `persisted_count = 6`
3. `excerpt_source = body_selector:.ArticleBody-articleBody`
4. 发布时间提取正常

样例：

1. `Here's the inflation breakdown for March 2026 — in one chart`
2. `Trump praises Palantir as stock has worst week in over a year and Iran conflict drags on`
3. `Where fixed income investors are finding yield as geopolitical risk rattles markets`

### 6.2 `cnbc_technology`

结果：

1. `candidate_count = 30`
2. `persisted_count = 6`
3. `excerpt_source = body_selector:.ArticleBody-articleBody`
4. 发布时间提取正常

样例：

1. `Vance, Bessent questioned tech giants on AI security before Anthropic's Mythos release`
2. `TSMC posts 35% jump in revenue to new record high as AI chip demand stays strong`
3. `Google expands partnership with Intel for AI chips`

## 7. Capture-only 实测

命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --db-path /tmp/overnight-news-handoff-cnbc-wave.db \
  --skip-market-snapshot \
  --skip-daily-analysis \
  --output-path /tmp/overnight-news-handoff-cnbc-wave-summary.json
```

结果：

1. `status = ok`
2. `duration_seconds = 263.983`
3. `collected_sources = 26`
4. `collected_items = 151`
5. `recent_total = 120`

和上一轮 `26` 源之前的 `141` 条相比，这一轮默认实抓条数提升到：

1. `151`

净增：

1. `+10` 条

而且新增量主要来自：

1. `cnbc_markets persisted_count = 6`
2. `cnbc_technology persisted_count = 6`

## 8. 日报展示层变化

由于前一轮已经把 `headline_news` 和 `Key News` 接进日报 markdown，本轮新增的 `CNBC` 结果也能自然进入最终展示层。

当前最新日报导出里，已经能看到：

1. 官方新闻
2. 商品媒体层
3. `CNBC` 市场/科技层

共同出现在同一份日报中。

## 9. 测试

本轮新增和更新了以下验证：

1. registry 必须包含 `cnbc_markets`
2. registry 必须包含 `cnbc_technology`
3. blueprint 的 editorial lane 必须包含这两个新源
4. `/refresh` 默认预算必须更新为 `26 / 6 / 120`

全量测试结果：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

结果：

```text
226 passed in 6.73s
```

## 10. 当前状态

现在默认生产链路已经覆盖：

1. 官方政策层
2. 官方数据层
3. 美股市场 headline
4. 科技与芯片 headline
5. 贵金属
6. 能源
7. 农业

## 11. 后续仍值得继续做的事

1. 继续找能稳定直抓的美股市场层源，优先替代 `MarketWatch` 这类 feed 可抓但正文受限的站点
2. 继续补贵金属 / 农业 / 化工链的高质量源
3. 让 `Key News` 进一步按主线聚类，而不是单条平铺
4. 让 API 直接暴露 `headline_news`，方便前端单独展示
