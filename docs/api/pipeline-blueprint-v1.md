# Pipeline Blueprint API V1

该接口用于把 `JusticeThemis` 的固定生产流程显式化，回答三个问题：

1. 入口是什么
2. 默认会抓多少
3. 中间如何处理、最后如何导出

## Endpoint

`GET /api/v1/pipeline/blueprint`

## Query Parameters

| Name | Type | Default | Meaning |
|---|---|---:|---|
| `max_sources` | integer | `26` | 单次刷新最多刷新多少个信源 |
| `limit_per_source` | integer | `6` | 每个信源最多保留多少条条目 |
| `recent_limit` | integer | `120` | 最近窗口保留多少条供日报/看板使用 |

## Response Shape

```json
{
  "product_name": "JusticeThemis",
  "pipeline_name": "justice_themis",
  "generated_at": "2026-04-10T17:10:00",
  "objective": "在中国早晨输出固定版隔夜国际新闻、美股收盘和结构化分析产物。",
  "run_window": {
    "timezone": "Asia/Shanghai",
    "target_read_time": "06:15",
    "market_reference": "前一交易日美股收盘",
    "analysis_mode": "fixed_daily_conclusion",
    "recent_limit": 120
  },
  "budget": {
    "default_source_budget": 26,
    "default_item_budget": 144,
    "recent_window_limit": 120
  },
  "source_summary": {
    "enabled_source_count": 27,
    "disabled_source_count": 2,
    "mission_critical_source_count": 9,
    "search_discovery_source_count": 9
  },
  "source_lanes": [
    {
      "lane_id": "official_policy",
      "title": "官方政策主线",
      "summary": "优先盯政策动作、行政命令、贸易与制裁更新。",
      "source_ids": ["whitehouse_news", "fed_news", "ustr_press_releases"],
      "capture_methods": ["rss", "search_discovery", "section_page"],
      "default_source_budget": 10,
      "default_item_budget": 60,
      "mission_critical_count": 6
    }
  ],
  "disabled_sources": [
    {
      "source_id": "state_spokesperson_releases",
      "display_name": "State Department Briefings and Statements",
      "disable_reason": "User-directed stop: do not pull State Department sources in this project."
    }
  ],
  "processing_stages": [
    {
      "stage_id": "capture_refresh",
      "title": "新闻抓取刷新",
      "summary": "按 source registry 抓 section/rss/calendar，必要时再走 search discovery 补漏。"
    }
  ],
  "entrypoints": {
    "cli": [
      {
        "command": "uv run python -m app.pipeline --analysis-date YYYY-MM-DD",
        "purpose": "执行固定晨间 pipeline。"
      }
    ],
    "api": [
      {
        "path": "/api/v1/mmu/handoff",
        "purpose": "读取分阶段 MMU handoff 载荷。"
      }
    ]
  }
}
```

## Field Notes

### `budget`

- `default_source_budget` 是本次运行允许刷新的最大信源数
- `default_item_budget` 是理论上限，不代表每次都一定抓满
- `recent_window_limit` 是看板、日报和 handoff 使用的回看窗口
- 当前生产默认值已更新为 `26 / 6 / 120`，对应更大的官方源 + 媒体源覆盖面

### `product_name` / `pipeline_name`

- `product_name` 是对外规范产品身份，固定为 `JusticeThemis`
- `pipeline_name` 是给结构化载荷和生成产物使用的稳定机器标识，当前为 `justice_themis`

### `source_lanes`

该字段把抓取层拆成明确的几层：

1. `official_policy`
2. `official_data`
3. `editorial_media`
4. `market_snapshot`
5. `llm_exports`

其中：

- 前三层负责“新闻与数据抓取”
- `market_snapshot` 负责“昨夜美股与跨资产结果”
- `llm_exports` 负责“下游模型可消费载荷”

### `disabled_sources`

该字段不只是配置说明，也是风控约束说明。  
当前项目会明确展示被禁用的源及原因，避免运行时误以为“没抓到”是技术问题，实际上可能是策略停用。

## Operational Meaning

对你这类中国早晨查看海外隔夜信息的场景，`pipeline blueprint` 的核心价值不是看接口，而是固定每天的判断边界：

1. 先抓权威源
2. 再看媒体补充
3. 再对照昨夜美股已落地结果
4. 最后导出固定日报和 AI 投喂包

这样可以避免把“预测”放在“事实”前面。
