# 2026-04-11 Frontend Full Pool And Diversity

> 项目：`overnight-news-handoff`

这轮不是继续加信源，而是把上一轮扩出来的新闻量更专业地暴露给前端。

## 1. 背景

上一轮扩源后，默认 capture-only 实测已经能拿到：

1. `143` 条入库新闻
2. `59` 条当前窗口有效新闻

但前端层仍有两个明显缺口：

1. `/api/v1/news` 默认只有当前窗口视角，没有正式的 `full news pool` 模式
2. dashboard 的 `lead_signals` 纯按排序截断，容易被同一来源连续占满

这会带来两个问题：

1. 用户看不到“我们其实还抓到了什么”
2. 首页看起来不够专业，容易变成单源刷屏

## 2. 本轮实现

### 2.1 `/api/v1/news` 新增 `pool_mode`

新增 query param：

- `pool_mode=current|full`

语义：

1. `current`
   - 默认值
   - 只返回当前 actionable overnight window
2. `full`
   - 返回更完整的 recent pool
   - 包含 stale recaptures 和非当前窗口条目

新增返回字段：

1. `pool_mode`
2. `current_window_total`
3. `full_pool_total`

这样前端可以同时展示：

1. 当前可读的隔夜新闻量
2. 系统总共抓到的新闻量

## 2.2 dashboard bucket 增加轻量来源多样性

新增 bucket 级来源上限：

1. `lead_signals`
   - 每个 `source_id` 最多 `1` 条
2. `watchlist`
   - 每个 `source_id` 最多 `2` 条
3. `background`
   - 每个 `source_id` 最多 `2` 条

规则是：

1. 先按原有排序走
2. 超过来源上限的项目先暂存
3. 如果还没凑满 bucket，再回填暂存项目

所以它不是硬去重，而是“先保多样性，再保填满”。

## 3. 影响

### 对前端

前端现在可以做两种视图：

1. `China-morning current view`
   - `/api/v1/news?pool_mode=current`
2. `Research / audit / full archive view`
   - `/api/v1/news?pool_mode=full`

同时 dashboard 的首屏主信号不会轻易被单一源刷满。

### 对后端

没有改 capture 层，没有改 handoff 层，也没有改日报分析引擎。

本轮只改：

1. `FrontendApiService`
2. `/api/v1/news` route 参数透传
3. 文档

## 4. 验证

新增行为测试：

1. `test_news_endpoint_can_switch_to_full_pool_mode_and_include_stale_items`
2. `test_dashboard_endpoint_diversifies_lead_signals_across_sources`

全量验证：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

本轮最终结果应保持全绿。
