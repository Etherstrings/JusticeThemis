# 2026-04-11 Source Expansion Wave 2

## 1. 背景

在 wave 1 已经把官方政策、官方数据和主流媒体基线拉起来之后，这一轮继续补两类缺口：

1. 贵金属与能源的 overnight 媒体层信号不足
2. 某些新增媒体源虽然能抓到，但正文摘要和发布时间存在质量问题

这一轮仍然严格遵守当前项目约束：

1. 只维护 `overnight-news-handoff`
2. 不碰 `daily_stock_analysis`
3. `state_spokesperson_releases`
4. `dod_news_releases`

其中第 3 和第 4 项继续保持禁用。

## 2. 本轮完成项

### 2.1 新增 3 个启用信源

新增并启用：

1. `kitco_news`
2. `oilprice_world_news`
3. `farmdoc_daily`

定位：

1. `kitco_news`
   - `coverage_tier = editorial_media`
   - `source_group = commodity_data`
   - `content_mode = precious_metals`
2. `oilprice_world_news`
   - `coverage_tier = editorial_media`
   - `source_group = commodity_data`
   - `content_mode = energy`
3. `farmdoc_daily`
   - `coverage_tier = editorial_media`
   - `source_group = commodity_data`
   - `content_mode = agriculture`

优先级已经调入默认采集池：

1. `kitco_news priority = 80`
2. `oilprice_world_news priority = 77`
3. `farmdoc_daily priority = 73`

在当前 `max_sources = 24` 的默认配置下，这三个源都会进入默认选中集合。

### 2.2 补了 Kitco 的 embedded JSON 摘要提取

问题：

1. Kitco 是 Next.js 页面
2. DOM 直接抽取时，正文开头经常落到作者简介
3. 这样会把新闻摘要错误替换成作者履历

本轮改动：

1. 在 `app/collectors/article.py` 新增 embedded JSON 摘要提取逻辑
2. 只对与当前文章 URL path 匹配的 JSON 对象取值
3. 优先读取 `teaserSnippet`
4. 将 `embedded_json:teaserSnippet` 纳入摘要候选

效果：

1. Kitco 的 live 页面现在能优先使用真正的新闻 teaser
2. 不再默认落入作者简介正文

### 2.3 收紧作者简介降权规则

为了让 Kitco live 页面稳定优先 teaser，本轮补了更贴近真实页面的作者简介识别：

1. `has a diploma in journalism`
2. `more than / over ... of reporting experience`
3. `can be contacted at`

这些模式仅用于降低作者简介类段落的摘要评分，避免其压过真实新闻摘要。

### 2.4 修复时间字段污染

发现的真实问题：

1. 某些文章页只暴露 `14:00` 这类纯时间字符串
2. 旧逻辑会把它当成更高等级的 HTML 发布时间
3. 进而覆盖 section 页已经拿到的完整 `YYYY-MM-DDTHH:MM:SS±HH:MM`

本轮修复：

1. 把纯时间值视为无效发布时间
2. 不允许其覆盖已有完整日期时间

这样避免最终日报时间字段被降级成只剩小时分钟。

### 2.5 修复 HTML 实体残留

发现的真实问题：

1. Kitco teaser 中常见 `&nbsp;`
2. 旧逻辑会把实体原样带入 summary
3. 这会污染前端显示和后续 prompt

本轮修复：

1. 在摘要标准化阶段统一做 `html.unescape`
2. 再进入 HTML 去标签和空白归一化

### 2.6 日报 markdown 新增 `Key News`

问题：

1. 旧版日报只有方向结论
2. 即使已经抓到了很多新闻，最终读物里也不够直观看到“新闻本身 + 来源”
3. 旧版直接复用高分 `supporting_items`，会被官方源完全占满

本轮改动：

1. 在 `RuleBasedDailyAnalysisProvider` 中新增独立 `headline_news`
2. `headline_news` 与 `supporting_items` 分离
3. 对 `headline_news` 加入轻度官方/媒体配额和 source 去重上限
4. `render_daily_report_markdown` 优先渲染 `headline_news`

效果：

1. 晨报正文现在会直接显示重点新闻与来源
2. 不再只剩“方向结论”
3. 新增媒体源如 `CNBC World`、`Kitco News` 能进入最终日报展示层

## 3. 涉及文件

代码：

1. `app/collectors/article.py`
2. `app/sources/registry.py`

测试：

1. `tests/test_collectors.py`
2. `tests/test_pipeline_blueprint.py`

## 4. 测试覆盖

这一轮新增或补强了以下行为验证：

1. Kitco 匹配 URL 的 embedded JSON `teaserSnippet` 应优先于作者简介
2. 新增信源必须出现在默认 registry 中，并带有跨市场元数据
3. pipeline blueprint 中的 editorial lane 必须包含这 3 个新增源
4. 纯时间值不能覆盖已有完整发布时间
5. embedded JSON 摘要中的 HTML 实体必须被清洗
6. Kitco live 风格作者简介必须被 teaser 压过
7. farmdoc 标题后作者/机构 `li` 元数据必须被跳过
8. 日报 markdown 必须展示带来源的重点新闻

全量测试结果：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

结果：

```text
226 passed in 6.04s
```

## 5. 默认采集池验证

使用当前 registry 按默认规则排序后的前 24 个源中，已经确认包含：

1. `kitco_news`
2. `oilprice_world_news`
3. `farmdoc_daily`

对应结论：

1. 这不是“注册成功但默认跑不到”的伪扩源
2. 这 3 个源已经进入默认生产路径

## 6. 在线冒烟结果

本轮针对新增信源做了直接 section + article 扩展验证。

### 6.1 `kitco_news`

结果：

1. `candidates = 17`
2. `excerpt_source = embedded_json:teaserSnippet`
3. `published_at = 2026-04-10T15:18:58-04:00`

摘要样例：

```text
(Kitco News) - The gold market has extended its winning streak to three weeks, and while sentiment has improved, it remains precariously balanced on the edge of a barrel of oil, according to analysts.
```

### 6.2 `oilprice_world_news`

结果：

1. `candidates = 3`
2. `excerpt_source = jsonld:articleBody`
3. `published_at = 2026-04-07T15:00:00-05:00`

说明：

1. 当前可稳定抓到文章级正文与发布时间
2. 候选量不大，但质量和时效明显优于“抓不到”

### 6.3 `farmdoc_daily`

结果：

1. `candidates = 20`
2. `excerpt_source = body_selector:article`
3. `published_at = 2026-04-10T15:13:49+00:00`
4. lead summary 已经切到正文首段，不再默认落到作者与机构列表

说明：

1. 候选量很足
2. 发布时间可用
3. 正文摘要质量已经显著改善

## 7. 完整 Pipeline 实测

命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --db-path /tmp/overnight-news-handoff-wave2-v2.db \
  --output-path /tmp/overnight-news-handoff-wave2-v2-summary.json \
  --summary-markdown-path /tmp/overnight-news-handoff-wave2-v2-summary.md \
  --daily-free-markdown-path /tmp/overnight-news-handoff-wave2-v2-free.md \
  --daily-premium-markdown-path /tmp/overnight-news-handoff-wave2-v2-premium.md \
  --daily-free-prompt-path /tmp/overnight-news-handoff-wave2-v2-free-prompt.json \
  --daily-premium-prompt-path /tmp/overnight-news-handoff-wave2-v2-premium-prompt.json \
  --mmu-handoff-path /tmp/overnight-news-handoff-wave2-v2-mmu.json \
  --blueprint-json-path /tmp/overnight-news-handoff-wave2-v2-blueprint.json \
  --blueprint-markdown-path /tmp/overnight-news-handoff-wave2-v2-blueprint.md
```

结果摘要：

1. `status = ok`
2. `analysis_date = 2026-04-10`
3. `duration_seconds = 266.832`
4. `enabled_source_count = 30`
5. `disabled_source_count = 2`
6. `default_source_budget = 24`
7. `collected_sources = 24`
8. `collected_items = 141`
9. `recent_total = 120`
10. `market_snapshot.status = ok`
11. `market_snapshot.captured_instrument_count = 23`
12. `daily_analysis.report_count = 2`
13. `health.status = ok`

新增源在本轮真实运行中的表现：

1. `kitco_news persisted_count = 6`
2. `oilprice_world_news persisted_count = 3`
3. `farmdoc_daily persisted_count = 6`

这说明新增 commodity/editorial 源已经真正进入固定晨报流水线，而不是停留在单独 collector 的实验状态。

## 8. 当前仍未完成的点

### 高优先级剩余项

1. 继续扩充 commodity / precious metals / agriculture 方向的稳定权威源
2. 让最终日报或 news API 更直接暴露“抓到的新闻 + 来源 + 摘要”，而不只是方向结论
3. 继续提高媒体层与 market snapshot 的联动解释质量

### 本轮明确没有做的事

1. 没有恢复任何中国政府站点
2. 没有恢复 `state_spokesperson_releases`
3. 没有恢复 `dod_news_releases`
4. 没有在这一轮引入 `X` 监听

## 9. 结论

wave 2 的价值不在于“再加几个 source_id”，而在于把新增商品新闻源真正推入默认生产链路，并把 Kitco 这类真实 live 页面中的摘要与时间污染问题修掉。

当前状态已经达到：

1. 默认采集池更广
2. 贵金属 / 能源 / 农业新闻覆盖更完整
3. Kitco 摘要更准确
4. Farmdoc 摘要已切到正文首段
5. 发布时间更稳
6. 晨报会直接展示带来源的重点新闻
7. 完整 pipeline 实跑通过

下一轮最值得做的是继续补高质量 commodity 源，并把“抓到的新闻 + 来源 + 摘要”更直接地暴露到最终日报和 API 输出中。
