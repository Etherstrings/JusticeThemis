# 2026-04-10 Source Refresh Diagnostics And Cooldown

> **项目：** `overnight-news-handoff`  
> **日期：** 2026-04-10  
> **目标：** 把抓取流程从“只返回结果”升级为“返回结果 + 解释结果 + 记住失败”。

## 1. 为什么这一轮要做

前几轮已经把默认抓取规模提到了生产态：

1. 默认 `max_sources=16`
2. 默认 `limit_per_source=6`
3. 默认 `recent_limit=80`

但系统仍有一个明显短板：

1. 某些源会连续多轮 `403`
2. 日志里能看到失败，但 API 和 pipeline 结果里看不到
3. 下一轮 refresh 还是会重复撞同一个坏源
4. 前端源面板只会显示“没有内容”，无法区分“空源”和“故障源”

这对于一个主打“隔夜新闻抓取”的产品是不够专业的。

## 2. 本次迭代做了什么

### 2.1 新增持久化来源状态表

新增 SQLite 表：

1. `overnight_source_refresh_state`

存储字段包括：

1. `source_id`
2. `last_status`
3. `last_error`
4. `consecutive_failure_count`
5. `cooldown_until`
6. `last_attempted_at`
7. `last_success_at`
8. `last_candidate_count`
9. `last_selected_candidate_count`
10. `last_persisted_count`
11. `last_elapsed_seconds`

这意味着来源状态不再是单次内存态，而是可以跨多轮 refresh 保持。

### 2.2 refresh 返回来源级诊断

`OvernightSourceCaptureService.refresh()` 现在除了总条数之外，还会返回：

1. `source_diagnostics`

每个来源诊断项包含：

1. `source_id`
2. `source_name`
3. `status`
4. `candidate_count`
5. `selected_candidate_count`
6. `persisted_count`
7. `search_discovery_used`
8. `error_count`
9. `errors`
10. `consecutive_failure_count`
11. `cooldown_until`
12. `attempted_at`
13. `skipped_reason`

### 2.3 连续硬失败自动冷却

新增硬失败冷却规则：

1. 连续硬失败阈值：`2`
2. 冷却时长：`6` 小时
3. 当前硬失败判定：
   - 包含 `403`
   - 包含 `Forbidden`
   - 包含 `http_432`

行为如下：

1. 第一次硬失败
   - 记录 `status=error`
   - `consecutive_failure_count=1`
2. 第二次连续硬失败
   - 记录 `status=error`
   - `consecutive_failure_count=2`
   - 写入 `cooldown_until`
3. 第三次 refresh 如果仍在冷却窗口内
   - 不再实际抓取
   - 直接返回 `status=cooldown`
   - `skipped_reason=hard_failure_cooldown`

### 2.4 collector 错误会向上透传

此前 `feed` / `section` collector 内部会把 fetch 错误吃掉，只留下空结果。

这次补充了轻量 side-channel：

1. `FeedCollector.last_errors`
2. `SectionCollector.last_errors`
3. `CalendarCollector.last_errors`

因此上层 `source_capture` 终于能区分：

1. 真的没有候选
2. 有候选但被筛掉
3. 实际是抓取时就失败了

### 2.5 前端源面板暴露运行状态

`/api/v1/sources` 现在新增：

1. `last_refresh_status`
2. `operational_status`
3. `consecutive_failure_count`
4. `cooldown_until`
5. `last_error`
6. `last_attempted_at`
7. `last_success_at`
8. `last_candidate_count`
9. `last_selected_candidate_count`
10. `last_persisted_count`
11. `last_elapsed_seconds`

这样一个源是“最近没内容”还是“已经冷却”，前端可以直接区分。

### 2.6 pipeline summary / health 也接上了来源诊断

新增两处联动：

1. `OvernightPipelineService.run()` 会把 `source_diagnostics` 放进 `summary["capture"]`
2. `PipelineHealthService` 会对 mission-critical 且 `status=cooldown/error` 的来源发出 warning
3. pipeline Markdown 摘要增加 `## Source Diagnostics` 区块

## 3. 真实验证

### 3.1 BLS 定向验证命令

使用真实网络，仅针对 `bls_news_releases` 连跑三次：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -c "..."
```

数据库路径：

```text
/tmp/overnight-source-state-check-zd4wLk/bls.db
```

### 3.2 三次结果

第一次：

1. `status = error`
2. `search_discovery_used = true`
3. `errors[0] = 403 Client Error: Forbidden for url: https://www.bls.gov/bls/news-release/home.htm`
4. `consecutive_failure_count = 1`

第二次：

1. `status = error`
2. `consecutive_failure_count = 2`
3. `cooldown_until = 2026-04-10T22:42:10.808181+00:00`

第三次：

1. `status = cooldown`
2. `skipped_reason = hard_failure_cooldown`
3. 不再实际抓取该源

### 3.3 前端源面板读取结果

同库下 `FrontendApiService.list_sources()` 读取到的 BLS 行如下：

1. `last_refresh_status = cooldown`
2. `operational_status = cooldown`
3. `consecutive_failure_count = 2`
4. `cooldown_until = 2026-04-10T22:42:10.808181+00:00`
5. `last_error = 403 Client Error: Forbidden for url: https://www.bls.gov/bls/news-release/home.htm`

这说明来源状态已经不再埋在日志里，而是正式进入 API 数据面。

## 4. 测试覆盖

本轮新增/扩展测试覆盖：

1. `tests/test_source_capture.py`
   - `test_source_capture_service_cools_down_after_repeated_hard_failures`
2. `tests/test_frontend_api.py`
   - `test_sources_endpoint_exposes_refresh_cooldown_state`
3. `tests/test_pipeline_ops.py`
   - `test_pipeline_health_service_warns_when_mission_critical_source_is_cooling_down`
   - `test_render_pipeline_summary_markdown_includes_source_diagnostics`
4. `tests/test_pipeline_runner.py`
   - 断言 pipeline summary 透传 `source_diagnostics`

全量结果：

1. `213 passed in 7.99s`

## 5. 当前收益

这轮迭代带来的直接收益有三类：

1. **可解释性**
   - refresh 终于能回答“哪个源坏了，坏在哪里”
2. **可恢复性**
   - 连续硬失败源会自动冷却，避免每轮都重复撞墙
3. **可产品化**
   - 前端、pipeline summary、health 都能消费同一套来源状态

## 6. 仍未完成的点

这轮还没有做到的部分：

1. search provider 级错误细分
   - 例如 Tavily `http_432` 目前仍主要留在日志里
2. 实际耗时 `last_elapsed_seconds`
   - 当前已留字段，但还没有做更精细的 monotonic timing
3. 冷却后的自动解冻验证
   - 目前依赖下一轮 refresh 去刷新状态

## 7. 下一步建议

按价值排序，建议继续做：

1. 给 `SearchDiscoveryService` 增加 provider 级诊断回传
2. 把 `source_diagnostics` 纳入 `/api/v1/dashboard`
3. 对 mission-critical 且持续冷却的源做单独告警出口
4. 给最慢来源补 `elapsed_seconds` 真正计时，形成 top-slow-sources 面板

## 8. 结论

这次不是“多抓了几个源”，而是把抓取系统做成了更像正式后端的形态：

1. 失败有状态
2. 状态可持久化
3. 连续硬失败会自动避让
4. 前端与 pipeline 能直接读取这份状态

对于后续继续补信源、补搜索补漏、做定时任务和告警，这一层是必须先补上的地基。
