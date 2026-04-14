# 2026-04-09 Live Validation Runbook

> **日期：** 2026-04-09  
> **项目：** `overnight-news-handoff`  
> **目的：** 把“本机 env -> 实际联调 -> 权限边界 -> 当前失败点”固定成可复跑、可审计的验证记录。

> **当前人工边界：**
> 1. 不碰中国政府网站  
> 2. 美国官方站点可以抓  
> 3. `State/DoD` 已按用户要求从默认采集与默认 live validation 范围中移除

> **补充说明：**
> 1. `2026-04-10` 又追加了一轮 `BIS / DOE` 定向 query probe
> 2. 详细记录见 [2026-04-10-bis-doe-search-validation.md](./2026-04-10-bis-doe-search-validation.md)
> 3. `2026-04-10` 已新增 fixed daily pipeline 入口，记录见 [2026-04-10-fixed-daily-pipeline.md](./2026-04-10-fixed-daily-pipeline.md)

## 1. 本次新增的项目内验证入口

独立项目内已新增一个本地 live validation 模块：

```bash
uv run python -m app.live_validation --include-section-capture --include-market-snapshot
```

它当前负责三件事：

1. 从本机 dotenv 文件读取 `BOCHA_API_KEYS / TAVILY_API_KEYS / SERPAPI_API_KEYS / BRAVE_API_KEYS`
2. 对 `search discovery` 做真实在线验证，并输出不含密钥的 JSON 报告
3. 对 `section capture + article expansion sample` 与 `U.S. market snapshot` 做真实在线验证

当前 `market snapshot` 验证会额外从同一组 env 文件读取：

1. `IFIND_REFRESH_TOKEN`

默认读取的 env 文件路径为：

1. `~/Projects/JusticePlutus/.env`
2. `~/Projects/JusticePlutus/.env.local`

这一步已经沉淀进独立项目代码，不再需要手工 source shell 变量才可验证。

## 2. 2026-04-10 rerun live 结果总览

本次 rerun live validation 的结论应拆成四层看：

### 2.1 Search Discovery 已验证的部分

1. `Search discovery env 注入`
   - 已从本机 env 文件成功加载 `BOCHA_API_KEYS`、`TAVILY_API_KEYS`、`SERPAPI_API_KEYS`
2. `Search discovery provider 装载`
   - 当前项目内成功装载 `SerpAPI`、`Bocha`、`Tavily`
3. `官方源 same-domain 发现能力`
   - `whitehouse_news` 命中 `4/4`
   - `ustr_press_releases` 命中 `2/2`
   - `treasury_press_releases` 命中 `4/4`
   - `ofac_recent_actions` 命中 `3/3`
4. `doe_articles`
   - 当前 query 在本轮 live run 下返回 `1` 条 same-domain 结果
   - 说明 DOE search query 已恢复可用，但命中规模仍偏小
5. `BIS`
   - 当前 `search_discovery_enabled=false`
   - 这是有意禁用，不是错误；原因是 direct section capture 已验证，但 search fallback 还未单独验证
6. provider 现实表现
   - 本轮官方源 query 里 `SerpAPI` 仍是主命中来源
   - `Bocha` 在 `whitehouse_news` 上拿到了 `3` 条 same-domain 结果，和 `SerpAPI` 共同补足官方页面发现
   - `Tavily` 对这些 query 仍多次返回 `http_432`
7. source-aware 质量过滤
   - `White House` 搜索侧已过滤 `/gallery`、分页页与栏目 listing 页
   - `USTR` 搜索侧已过滤 `ustr.gov/node`
   - `OFAC` 搜索侧已过滤 `recent-actions/general-licenses` 等栏目 listing 页

### 2.2 Section Capture 已验证的部分

1. `whitehouse_news`
   - direct section capture 成功
   - 当前 live run 抓到 `10` 条候选，并成功展开 1 条正文样本
2. `ustr_press_releases`
   - direct section capture 成功
   - 当前 live run 抓到 `450` 条候选，并成功展开 1 条正文样本
3. `treasury_press_releases`
   - direct section capture 成功
   - 当前 live run 抓到 `15` 条候选，并成功展开 1 条正文样本
4. `ofac_recent_actions`
   - direct section capture 成功
   - 当前 live run 抓到 `10` 条候选，并成功展开 1 条正文样本
   - 正文展开后的 `published_at` 已保留为 `2026-04-08`
5. `bis_news_updates`
   - direct section capture 成功
   - 当前 live run 抓到 `29` 条候选，并成功展开 1 条正文样本
   - 正文展开后的 `published_at` 已保留为 `2026-03-27T04:00:00+00:00`
6. `doe_articles`
   - direct section capture 成功
   - 当前 live run 抓到 `13` 条候选，并成功展开 1 条正文样本

### 2.3 Market Snapshot 已验证的部分

1. `market snapshot` rerun live validation 返回 `status=ok`
2. 当前 `analysis_date=2026-04-10`，`market_date=2026-04-09`
3. 当前 `source_name=iFinD History, Treasury Yield Curve`
4. 当前 `capture_status=complete`
5. 已捕获 `23/23` 个默认 instrument
6. `ALI=F` 已不再缺失，当前通过 iFinD 代理代码 `DBB.P` 补齐
7. `^TNX` 已不再缺失，现由官方 `Treasury Yield Curve` provider 提供
8. live validation 的 `bucket_counts` 现已包含 `sentiment` 与 `rates_fx`

### 2.4 已确认的权限边界与仍待验证项

1. 已确认的 iFinD 权限边界
   - `A 股实时` 可用
   - `港股实时` 可用
   - `美股历史` 可用
   - `美股指数历史` 可用
   - `美股个股实时` 当前账号无权限，实测 `AAPL.O -> -4230`
   - `美股指数实时` 当前账号无权限，实测 `IXIC.GI -> -4225`
2. 当前仍待继续验证
   - `iFinD` 更完整的商品、外汇、更多指数代码矩阵
   - `X` 接入后的夜间噪声治理、限频成本与账户白名单
   - `海外驱动 -> 国内期货/化工合约映射` 的字段表与日常回归验证

## 3. Search Discovery 详细结果

2026-04-10 rerun 的 source-aware 结果如下：

| source_id | query_count | 结果数 | 同域结果数 | 主要 provider | 结论 |
| --- | ---: | ---: | ---: | --- | --- |
| `whitehouse_news` | 2 | 4 | 4 | `Bocha + SerpAPI` | 当前可用，且已通过 source-aware 路径过滤清掉 gallery / pagination / listing 噪声 |
| `ustr_press_releases` | 2 | 2 | 2 | `SerpAPI` | 当前可用，`node` 弱路径已被过滤 |
| `treasury_press_releases` | 1 | 4 | 4 | `SerpAPI` | 当前可用，same-domain 精度高 |
| `ofac_recent_actions` | 2 | 3 | 3 | `SerpAPI` | 当前已验证可用 |
| `bis_news_updates` | 0 | 0 | 0 | 无 | 当前有意禁用 search discovery，保留 direct section capture |
| `doe_articles` | 2 | 1 | 1 | `SerpAPI` | direct section 可用，search query 已恢复命中 |

工程解释：

1. `SerpAPI` 是当前这轮官方源 query 的最强命中来源
2. `Bocha` 在 `White House` 这类 query 上体现了明显补位价值
3. `Tavily` 在这些官方站点 query 上仍多次返回 `http_432`
4. `BIS` 当前不是“找不到内容”，而是“search fallback 未验证，所以明确标成 disabled”
5. source-aware path filter 已成为必要层，不能只靠 same-domain 判断官方页面质量

## 4. Section Capture 详细结果

2026-04-10 rerun 的 direct section capture 结果如下：

| source_id | 入口状态 | 候选数 | 正文样本 | 结论 |
| --- | --- | ---: | --- | --- |
| `whitehouse_news` | 正常 | 10 | 成功 | direct section 可用 |
| `ustr_press_releases` | 正常 | 450 | 成功 | direct section 可用，覆盖度很高 |
| `treasury_press_releases` | 正常 | 15 | 成功 | direct section 可用 |
| `ofac_recent_actions` | 正常 | 10 | 成功 | direct section 可用 |
| `bis_news_updates` | 正常 | 29 | 成功 | direct section 可用，覆盖度高 |
| `doe_articles` | 正常 | 13 | 成功 | direct section 可用 |

这里要特别注意：

1. `State/DoD` 已按用户要求从默认采集面完全移除
2. 这一步不是技术兜底，而是产品边界约束
3. 当前默认官方采集面只保留美国官方站点，不碰中国政府网站

## 5. 当前 market snapshot runtime 路径

截至本次更新，`overnight-news-handoff` 已把 `Treasury Yield Curve` 纳入正式 runtime：

1. 当进程环境中存在 `IFIND_REFRESH_TOKEN` 时：
   - provider 顺序为 `iFinD History -> Treasury Yield Curve -> Yahoo Finance Chart`
2. 当进程环境中不存在 `IFIND_REFRESH_TOKEN` 时：
   - provider 顺序为 `Treasury Yield Curve -> Yahoo Finance Chart`
3. 当前已验证并接入映射的 canonical symbol 包括：
   - `^GSPC -> SPY.P`
   - `^IXIC -> IXIC.GI`
   - `^DJI -> DIA.P`
   - `^RUT -> IWM.P`
   - `^VIX -> VIX.GI`
   - `XLK / SOXX / XLF / XLE / XLI / XLV / XLY / XLP`
   - `DX-Y.NYB -> UUP.P`
   - `CNH=X -> USDCNH.FX`
   - `GC=F / SI=F / CL=F / BZ=F / NG=F / HG=F`
   - `^TNX -> Treasury Yield Curve`

本次 rerun 的 market snapshot 工程事实是：

1. `source_name` 已变为 `iFinD History, Treasury Yield Curve`
2. `^TNX` 已通过 Treasury 官方页面解析得到稳定结果
3. `ALI=F` 已通过 `DBB.P` 代理映射进入 iFinD 路径
4. 当前默认 snapshot 已达到 `23/23` 完整采集
5. iFinD adapter 仍必须把“空时间序列”视为失败，不能把 `errorcode=0` 误判成可用

## 6. 当前项目层面的工程结论

### 6.1 已完成

1. 独立项目内已经有 `env-backed live validation` 工具
2. 搜索发现层已经可以直接用本机 env 文件做真实联调
3. `section capture` 已纳入同一个 live validation 报告
4. 默认官方采集面已经切换为 `White House / USTR / Treasury / OFAC / BIS / DOE`
5. `OFAC` 的 search discovery 已通过 live 验证
6. `BIS` 的 direct section capture 已通过 live 验证
7. `^TNX` 已由官方 `Treasury Yield Curve` provider 补齐
8. `OFAC/BIS` article expansion 已保留 `published_at`
9. rerun 下 `market snapshot` 已能捕获 `23/23` 个默认 instrument
10. `White House` / `USTR` / `OFAC` 的弱路径搜索结果已被 source-aware filter 清理

### 6.2 当前明确的缺口

1. `BIS` 的 search discovery 仍是明确禁用状态，且 `2026-04-10` 的定向 probe 已进一步确认当前不适合启用 search fallback
2. `DOE` 的 search discovery 虽已恢复命中，且 query 已扩成 `3` 条，但规模仍偏小，后续仍可继续打磨
3. `Tavily` 在官方站点 query 上仍不稳定，当前不适合当主 discovery provider

## 7. 下一步最应该做的事情

1. 继续优化 `DOE` 的 API 搜索 query 质量
2. 继续扩大 iFinD market snapshot 的 validated code matrix
3. 把 live validation 结果固化到每日 smoke，而不是只在人工会话里验证
4. 后续若要重试 `BIS`，先做 provider probe，再决定是否改 registry
