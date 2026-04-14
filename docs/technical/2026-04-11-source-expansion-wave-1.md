# 2026-04-11 信源扩容第一波

> 项目：`overnight-news-handoff`  
> 目标：在不碰中国政府站点、不过度纠缠失败恢复逻辑的前提下，直接补充更多可稳定抓取的国际/美股/商品相关信源，并把默认抓取预算抬到更接近产品态的水平。

## 1. 这轮改了什么

这轮工作只做两件事：

1. 扩大 `source registry`
2. 扩大当前 `SectionCollector` 能识别的官方新闻页结构

没有做的事情：

1. 没有恢复或重新启用中国政府站点
2. 没有把重点放在失败冷却、重试策略继续打磨上
3. 没有在这一轮里改动 premium 选股结论逻辑

## 2. 新增信源

本轮新增 11 个启用信源。

### 官方/准官方

| Source ID | Entry Type | 分层 | 作用 |
|---|---|---|---|
| `newyorkfed_news` | `section_page` | `official_data` | 补纽约联储的通胀预期、市场操作、金融环境和研究更新 |
| `ecb_press` | `rss` | `official_data` | 补欧洲央行对全球利率、流动性和美元方向的海外政策语境 |
| `worldbank_news` | `section_page` | `official_data` | 补全球增长、贸易融资、能源/粮食安全等跨国机构口径 |
| `iea_news` | `section_page` | `commodity_data` | 补油气、库存释放、能源安全、关键矿物供应链 |
| `cftc_general_press_releases` | `rss` | `commodity_data` | 补商品/期货/预测市场/清算监管更新 |
| `cftc_enforcement_press_releases` | `rss` | `commodity_data` | 补衍生品与加密相关执法事件 |
| `cftc_speeches_testimony` | `rss` | `commodity_data` | 补 CFTC 主席与委员口径变化 |

### 媒体补充层

| Source ID | Entry Type | 分层 | 作用 |
|---|---|---|---|
| `ap_world` | `section_page` | `editorial_media` | 补地缘政治、冲突与航运/黄金/油价相关主线 |
| `ap_technology` | `section_page` | `editorial_media` | 补 AI、芯片、平台监管、科技供应链 |
| `ap_economy` | `section_page` | `editorial_media` | 补增长、就业、通胀、政策外溢 |
| `ap_financial_markets` | `section_page` | `editorial_media` | 补股债汇金油联动和美股收盘归因 |

## 3. 采集器增强

为了让这些源真实出货，而不是只停在注册表里，本轮扩了 `app/collectors/section.py` 的两部分能力。

### 3.1 新增 anchor selector

新增了以下结构命中：

1. `div.paraHeader a[href]`
2. `a.m-news-detailed-listing__link[href]`
3. `td a[href]`
4. `a[href*="/news/"][href]`
5. `a[href*="/press-release/"][href]`
6. `a[href*="/statement/"][href]`
7. `a[href*="/speech/"][href]`
8. `a[href*="PressReleases/"][href]`

这些选择器分别覆盖了：

1. `New York Fed`
2. `IEA`
3. `CFTC`
4. `World Bank` / 其它 path-based 新闻页

### 3.2 新增 URL 识别规则

新增的 detail URL 识别包括：

1. `/newsevents/news/...`
2. `/pressroom/pressreleases/...`
3. `/news/press-release/2026/...`
4. `/news/statement/2026/...`
5. `/news/speech/2026/...`
6. `/press/pr/date/2026/...`
7. 对 `news` 路径下长 slug 的 detail 页放行

同时增加了更多 `hub` 过滤：

1. `/(lang)/news`
2. `/(lang)/news/all`

这样可以减少“抓到栏目页而不是文章页”的误判。

## 4. 预算更新

本轮把默认抓取预算从旧值抬高到更接近产品态的默认值：

| 项目 | 旧值 | 新值 |
|---|---:|---:|
| `DEFAULT_CAPTURE_LIMIT_PER_SOURCE` | `6` | `6` |
| `DEFAULT_CAPTURE_MAX_SOURCES` | `16` | `24` |
| `DEFAULT_CAPTURE_RECENT_LIMIT` | `80` | `120` |

含义：

1. 每源上限不变，避免单一媒体频道淹没结果池
2. 默认刷新源数明显扩大，避免新增信源却默认抓不到
3. 最近窗口扩大，方便 dashboard / handoff / 固定日报保留更多候选

## 5. 实测结果

### 5.1 新增源在线冒烟

2026-04-11 本地 live smoke 结果：

| Source ID | 实际候选数 |
|---|---:|
| `newyorkfed_news` | `40` |
| `ecb_press` | `15` |
| `worldbank_news` | `8` |
| `iea_news` | `18` |
| `cftc_general_press_releases` | `10` |
| `cftc_enforcement_press_releases` | `10` |
| `cftc_speeches_testimony` | `10` |
| `ap_world` | `40` |
| `ap_technology` | `40` |
| `ap_economy` | `34` |
| `ap_financial_markets` | `35` |

这说明新增源不是“注册成功但线上没货”，而是当前网络路径下确实可抓。

### 5.2 capture-only 全量实测

命令：

```bash
uv run python -m app.pipeline \
  --analysis-date 2026-04-10 \
  --db-path /tmp/overnight-news-handoff-live.XXXXXX/live.db \
  --skip-market-snapshot \
  --skip-daily-analysis \
  --output-path /tmp/overnight-news-handoff-live.XXXXXX/summary.json
```

结果：

1. `enabled_source_count = 27`
2. `default_source_budget = 24`
3. `collected_sources = 24`
4. `collected_items = 143`
5. `recent_total = 120`
6. `duration_seconds = 258.602`

补充统计：

1. `current_window_items = 59`
2. `handoff items = 48`
3. `event_groups = 26`

对比此前约 `36` 条 current-window 新闻，这一轮已经把“当前可读的隔夜有效新闻量”拉到了 `59`。

## 6. 本轮完成项

### 已完成

1. 新增 11 个启用信源
2. 扩展 section collector 以兼容更多 path-based 官方新闻页
3. 更新默认抓取预算到 `24 / 6 / 120`
4. 补充回归测试并通过全量测试
5. 跑通新增源在线冒烟
6. 跑通一次真实 capture-only 全量验证

### 明确保持不动

1. `state_spokesperson_releases`
2. `dod_news_releases`

这两个仍保持禁用，符合当前项目约束。

## 7. 还没完成的事

### 高优先级待继续

1. 继续补稳定的官方能源/商品/交易所级信源
2. 继续拆分高产媒体源，提升“有效新闻密度”而不是只加源数
3. 给新增源补更细的 search discovery query，作为 direct capture 之外的补漏层
4. 让 handoff / dashboard 更明确区分“官方事实层”和“媒体解释层”

### 暂未纳入本轮

1. `X` 监听层
2. 更多 `CNBC` 子 RSS
3. 更细的 `Reuters` 分主题拆源
4. `USDA` 这类当前网络路径下超时/低稳定源
5. `SEC` 这类当前网络路径下有强限流或验证码风险的站点
6. 贵金属专门新闻源与交易所级源

## 8. 验证

本轮代码层验证：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

结果：

```text
217 passed in 6.02s
```

## 9. 涉及文件

核心代码：

1. `app/collectors/section.py`
2. `app/sources/registry.py`
3. `app/runtime_defaults.py`

测试：

1. `tests/test_collectors.py`
2. `tests/test_pipeline_blueprint.py`
3. `tests/test_api.py`

文档：

1. `docs/api/pipeline-blueprint-v1.md`
2. `docs/technical/2026-04-11-source-expansion-wave-1.md`
