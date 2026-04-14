# 2026-04-10 BIS / DOE Search Validation Addendum

> **日期：** 2026-04-10  
> **项目：** `overnight-news-handoff`  
> **目的：** 补做 `BIS` 与 `DOE` 的 search-discovery 定向验证，确认哪些 source 可以继续增强，哪些 source 应继续保持禁用。

## 1. 验证命令

本次补充验证使用了两类命令。

### 1.1 Provider 级 query probe

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m app.live_validation --include-section-capture --max-results 5 --days 14
```

另补做了 provider 级定向 query probe，用于单独验证 `BIS` 与 `DOE` 在 `SerpAPI / Bocha / Tavily` 下的真实返回。

### 1.2 当前读取的 env 文件

1. `~/Projects/JusticePlutus/.env`
2. `~/Projects/JusticePlutus/.env.local`

已确认实际加载：

1. `BOCHA_API_KEYS`
2. `SERPAPI_API_KEYS`
3. `TAVILY_API_KEYS`

## 2. DOE 定向验证结论

### 2.1 有效 query

以下 query 在本机当前 provider 环境下能拿到 `energy.gov/articles` 同域正文页：

1. `site:energy.gov/articles Department of Energy loan office energy dominance financing loan commitment`
2. `site:energy.gov/articles Department of Energy LNG grid coal reliability manufacturing`

### 2.2 无效或弱 query

以下 query 在本轮 probe 中没有拿到更好的同域正文：

1. `site:energy.gov/articles Department of Energy strategic petroleum reserve power grid battery manufacturing`

### 2.3 工程处理

项目内已把 DOE 的 search query 从 `2` 条扩成 `3` 条，保留原因如下：

1. 第三条 query 在 provider 级 probe 中确实返回了 `energy.gov/articles` 正文页
2. 它覆盖了 `LNG / grid reliability / coal plant / manufacturing` 这一组更偏能源安全与工业链的主题
3. 即便本轮 `SearchDiscoveryService.discover()` 最终仍只保留 `2` 条候选，这条 query 仍有补位价值

### 2.4 当前 live 结果

以 `--max-results 5 --days 14` 运行时：

1. `doe_articles`
   - `query_count=3`
   - `total_candidates=2`
   - `same_domain_candidates=2`
   - provider 仍主要来自 `SerpAPI`

当前结论：

1. DOE search discovery 已可用
2. DOE search discovery 仍不是高覆盖 source
3. 后续优化方向应是继续补主题 query，而不是扩大 provider 范围

## 3. BIS 定向验证结论

### 3.1 probe 过的 query

本次额外验证过的 `BIS` query 包括：

1. `site:media.bis.gov/news-updates BIS export controls semiconductor press release`
2. `site:media.bis.gov/press-release BIS semiconductor export enforcement entity list`
3. `site:bis.gov BIS export administration regulations semiconductor China press release`
4. `site:media.bis.gov/press-release "BIS" "semiconductor"`
5. `site:media.bis.gov/press-release "entity list" BIS press release`
6. `site:media.bis.gov/press-release "export controls" BIS`
7. `site:media.bis.gov/press-release "Applied Materials" BIS`
8. `site:media.bis.gov/press-release "China" semiconductor BIS`
9. `site:media.bis.gov/press-release bis reaches administrative enforcement settlement`

### 3.2 实际 provider 表现

1. `SerpAPI`
   - 大多返回 `0` 条
   - 唯一较接近的命中是 `https://www.bis.gov/news-updates`
   - 这是 listing 页，不是单篇正文页
2. `Bocha`
   - 基本返回离题或离域结果
   - 当前不具备稳定的 `BIS` 官方正文发现能力
3. `Tavily`
   - 本轮仍以 `http_432` 为主

### 3.3 工程结论

当前不应启用 `bis_news_updates.search_discovery_enabled`，原因很明确：

1. 没有稳定的 article-level same-domain 发现结果
2. 当前可拿到的最佳同域结果仍是 `news-updates` 栏目页
3. 在这种状态下启用 fallback，只会把低价值入口页送入后续管道

因此当前最稳妥的策略仍然是：

1. `BIS` 继续依赖 direct section capture
2. `BIS` search discovery 继续保持 disabled
3. 如果后续要重试，应先做 provider 级 probe，再决定是否改 registry

## 4. 本轮补充验证后的冻结结论

1. `White House / USTR / Treasury / OFAC / DOE` 的 search discovery 都已经过 live 验证
2. `BIS` 当前仍只适合 direct section capture，不适合启用 search fallback
3. `Tavily` 在官方站点 query 上依旧不稳定，当前只能保留为次级 provider
4. `DOE` 已补入第三条 query，但当前 live 结果仍说明它属于“可用但不高覆盖”的 source
