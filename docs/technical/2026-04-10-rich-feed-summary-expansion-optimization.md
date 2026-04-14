# 2026-04-10 Rich Feed Summary Expansion Optimization

> **项目：** `overnight-news-handoff`  
> **日期：** 2026-04-10  
> **目标：** 在不减少新闻覆盖量的前提下，缩短默认 `refresh`/capture 耗时。

## 1. 背景

上一轮默认抓取已经能把启用信源基本跑满：

1. 默认预算已经提升到生产态
   - `max_sources=16`
   - `limit_per_source=6`
   - `recent_limit=80`
2. 默认 `refresh` 能抓到
   - `collected_sources=15`
   - `collected_items=85`
   - 当前窗口可用新闻约 `35`
3. 但总耗时仍然偏高
   - 优化前实测约 `223.258s`

这说明问题已经不在“抓不到”，而在“抓到以后处理太慢”。

## 2. 根因定位

对 collect / persist 两段分别测量后，瓶颈主要集中在 **persist 阶段的 article expansion**：

1. `eia_pressroom`
   - `collect_s ≈ 15.891`
   - `persist_s ≈ 54.515`
2. `cnbc_world`
   - `persist_s ≈ 9.772`
3. `doe_articles`
   - `persist_s ≈ 8.145`
4. `census_economic_indicators`
   - `persist_s ≈ 6.098`

进一步检查发现，这些慢源里相当一部分 RSS/Feed 候选本身已经带有较长、可读、结构化的摘要，典型长度包括：

1. `eia_pressroom`
   - `513 / 166 / 232 / 411 / 378 / 154`
2. `census_economic_indicators`
   - `206 / 303 / 149 / 243 / 330 / 191`
3. `fed_news`
   - `236 / 64 / 170 / 84 / 248 / 67`
4. `cnbc_world`
   - 多条约 `119-185`

结论很明确：

1. 不少 feed item 已经足够进入后续结构化流程
2. 但旧逻辑仍然会对所有 `needs_article_fetch=True` 的候选一律做正文扩展
3. 这导致大量“可直接用”的 feed 摘要还要再发起一次网页正文抓取

## 3. 本次改动

### 3.1 行为改动

在 `app/services/source_capture.py` 中新增了选择性跳过逻辑：

1. 仅对 `candidate_type == "feed_item"` 生效
2. 仅对 `candidate_excerpt_source` 以 `feed:` 开头的候选生效
3. 当 feed 摘要长度 `>= 160` 字符时，不再进行 article expansion
4. 持久化状态改为：
   - `article_fetch_status = "skipped_rich_feed_summary"`

### 3.2 为什么这样做

这样做的边界比较保守：

1. 不影响 section page / calendar / search fallback 候选
2. 不影响摘要过短的 feed item
3. 只跳过“feed 自带摘要已经明显够用”的候选

也就是说，本次优化不是“少抓”，而是“少做重复工作”。

## 4. 测试补强

新增回归测试：

1. `tests/test_source_capture.py`
   - `test_source_capture_service_skips_article_expansion_for_rich_feed_summaries`

测试策略：

1. 先写失败测试
2. 用会抛错的假 `ArticleCollector` 验证旧逻辑确实还在错误调用 expansion
3. 再实现最小逻辑修复
4. 重新跑绿

## 5. 实测结果

### 5.1 只跑 capture 的正式实测

命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache /usr/bin/time -p uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --db-path /tmp/overnight-capture-check-Rn50b5/perf.db \
  --skip-market-snapshot \
  --skip-daily-analysis \
  --output-path /tmp/overnight-capture-check-Rn50b5/summary.json
```

结果：

1. `duration_seconds = 196.007`
2. `real = 196.27s`
3. `collected_sources = 15`
4. `collected_items = 85`
5. `recent_total = 80`

### 5.2 与上一轮对比

1. 优化前
   - `≈ 223.258s`
2. 优化后
   - `≈ 196.007s`
3. 改善幅度
   - 约 `27.251s`
   - 约 `12.2%`

### 5.3 可用内容是否回退

同库复算结果：

1. `recent_total = 85`
2. `current_window_total = 36`
3. `handoff_total = 36`
4. `event_group_count = 18`
5. `official_item_count = 19`
6. `editorial_item_count = 17`

结论：

1. 入库总量没有回退
2. 当前窗口可用新闻没有明显下降，反而比上一轮的 `35` 略增到 `36`
3. handoff 事件簇数量仍然足够支撑后续模型分析

## 6. 当前仍存在的瓶颈

这次优化之后，默认抓取仍然没有到“足够快”，剩余主要问题如下：

1. `BLS` 仍有明显阻塞
   - direct section `403`
   - Tavily query `http_432`
   - release schedule `403`
2. 一些需要正文扩展的非 feed 候选仍然会占用时间
3. 个别媒体源即使 feed 摘要较长，仍可能保留正文扩展路径

## 7. 下一步建议

优先级建议如下：

1. 对 `BLS` 增加更便宜的失败短路逻辑
   - 避免每轮默认 refresh 都完整走一遍高概率失败链路
2. 继续细化 article expansion 策略
   - 例如区分 `feed:summary` 与 `feed:description`
   - 按来源域名单独设置 richer/poorer 阈值
3. 增加 per-source runtime 观测输出
   - 把每次运行最慢的前 5 个源直接写入 summary artifact

## 8. 结论

这次优化验证了一个关键方向：

1. 当前系统的主要问题不是“新闻不够”
2. 而是“对已经足够详细的候选做了重复正文抓取”
3. 通过只跳过高质量 feed 摘要的重复 expansion，已经在不减量的情况下把默认 capture 时间压缩到了 `196s` 左右
4. 后续继续优化时，应优先清理失败率高、收益低的来源链路，而不是再把默认预算缩回 demo 态
