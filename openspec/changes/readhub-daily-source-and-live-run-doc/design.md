## Context

用户这次要求的是两件非常具体的事：

1. 判断 `1.readhub.cn/daily` / `readhub.cn/daily` 这种 Readhub 每日早报页面能不能被当前项目稳定拉取，以及如果能拉，应该怎么增强；
2. 不依赖前端，真实跑一天后端内容，并把效果沉淀成一个文档给人看。

基于 `2026-04-15` 的实际探测，当前结论已经足够明确：

- `https://1.readhub.cn/daily` 在当前环境下 TLS 失败，不能作为可靠 canonical endpoint
- `https://readhub.cn/daily` 返回 `200`，页面 title 为 `每日早报 - Readhub`
- `daily` 页面本身已经包含服务端渲染列表以及内嵌 `articles` 数据，至少能直接拿到当天日期、标题、摘要、topic 链接和 entity 列表
- `topic/<id>` 详情页还暴露 `tagList`、`trackingList`、`similarEventList` 和 `newsList`

与此同时，当前项目的 collector 体系主要面向：

- `rss`
- `section_page`
- `calendar_page`

现有通用 `SectionCollector` 会把 `/topic/<id>` 形态视为 hub path，并不会把它当成最终文章型 URL；当前落库层也没有通用字段来存 Readhub 特有的 `trackingList/newsList/similarEventList` 这类结构化上下文。因此这不是简单“加一个 URL 到 registry”就能完成的事情，而是一个小型的数据面扩展。

第二个问题同样不是“跑一下命令给你看”这么简单。仓库里虽然已经存在历史的全量运行 Markdown 样例，但还没有一个被规范化的、面向指定 analysis date 的 backend-only evidence 输出合同。用户要的是一个可以复跑、可审计、能看清效果和限制的文档，而不是一次性聊天记录。

## Goals / Non-Goals

**Goals:**

- 把 `readhub.cn/daily` 明确定义为可抓取的聚合晨报源，并对 `1.readhub.cn/daily` 的失败做兼容说明
- 新增一条专门适配 Readhub daily/topic 的采集与 enrichment 路径
- 为 Readhub topic 元数据提供结构化持久化能力，而不是只留一段平面摘要
- 在不引入前端工作的前提下，建立一条真实跑一天后端并生成 Markdown 证据文档的标准路径
- 保持项目“官方源优先”的总体定位，不让 Readhub 聚合源覆盖官方政策/数据源

**Non-Goals:**

- 本次 change 不实现任何前端页面或可视化界面
- 本次 change 不把 Readhub 外链涉及的所有第三方站点纳入自动全文抓取
- 本次 change 不重构整个 pipeline 或日报生成逻辑
- 本次 change 不把 Readhub 提升为官方事实源或 mission-critical source

## Decisions

### Decision: 以 `https://readhub.cn/daily` 作为 canonical endpoint，把 `https://1.readhub.cn/daily` 视为 legacy alias / probe

`2026-04-15` 的实测里，`1.readhub.cn/daily` 在当前环境下 TLS 失败，而 `readhub.cn/daily` 返回 `200` 并完整渲染每日早报内容。因此设计上不再把 `1.readhub.cn/daily` 当成主入口，而是：

- 使用 `https://readhub.cn/daily` 作为 canonical daily endpoint
- 将 `https://1.readhub.cn/daily` 仅作为 legacy alias 或可选 probe
- 当 legacy alias 失败时，只记录非阻断诊断，不让整个 source refresh 失败

Alternatives considered:

- 继续硬编码 `1.readhub.cn/daily`：与当前真实网络表现不符，失败率过高。
- 同时把两个域名都当主入口：会增加重复抓取与 canonicalization 复杂度。

### Decision: 新增 dedicated Readhub collector，而不是复用通用 `SectionCollector`

当前通用 `SectionCollector` 对 `/topic/<id>` 不友好，且无法可靠读取 Readhub 页面内嵌的 Next.js 流式 JSON。设计上将新增一条 dedicated collector / parser 路径，优先消费页面里已经结构化暴露的数据：

- `daily` 页负责提供当天 issue date、rank、title、summary、topic url、entityList
- `topic` 页负责提供 tags、tracking、similar events、aggregated news links

这样可以减少对脆弱 CSS selector 的依赖。

Alternatives considered:

- 强行扩展 `SectionCollector` 去适配 Readhub：会让一个本来面向通用 section page 的 collector 背负站点特判，边界变差。
- 只抓 DOM 文本，不读内嵌数据：可以工作，但丢失太多可用结构化字段。

### Decision: 以 Readhub topic 页面作为 canonical captured item，而不是跟随 `newsList` 外链逐站抓正文

Readhub topic 页本身已经是一个聚合摘要和上下文容器，里面外链站点分布广且不在当前 registry allowlist 范围内。设计上将：

- 把 `https://readhub.cn/topic/<id>` 作为 canonical captured item URL
- 把 `newsList` 保留为结构化引用列表
- 默认不自动继续抓取 `newsList` 指向的第三方站点正文

这能把范围稳定在“新增一个聚合信源”而不是“顺便接入几十个额外媒体域名”。

Alternatives considered:

- 对 `newsList` 全量自动扩展正文：信息更多，但会把本次变更扩成一个大规模跨域抓取工程。
- 只保留 daily 页面，不抓 topic 页：实现更快，但丢掉了 tags、历史追踪和聚合外链这些真正有增强价值的数据。

### Decision: 为 source-specific enrichment 增加结构化持久化字段

当前 `overnight_source_items` 只有 `summary / normalized_entities / normalized_numeric_facts`，不足以表示 Readhub 的 `tagList / trackingList / newsList / similarEventList`。设计上将扩展 source item 数据面，增加一个 source-specific context JSON（命名可在实现时决定），用于持久化：

- daily issue date / rank
- entity names from Readhub
- topic tags
- aggregated external links and origins
- historical tracking rows
- similar-event comparison rows

这样 downstream report / API / evidence doc 才能真正消费这些增强信息。

Alternatives considered:

- 全部压平进 summary 文本：落库简单，但信息损失严重，也不利于后续 API 或 evidence doc 结构化展示。
- 单独建多张 Readhub 专用表：结构更强，但对当前项目而言过重。

### Decision: Readhub 进入默认 registry，但保持低优先级、非 mission-critical、聚合编辑源定位

用户要看真实效果，因此 Readhub 不能只停留在手工 probe；但项目的核心定位仍然是官方源优先。设计上将：

- 把 Readhub 放入默认 registry，便于真实运行
- 将其标记为非 mission-critical
- 保持低于 `official_policy` / `official_data` 的优先级
- 在 source selection 中不允许它压过官方源

Alternatives considered:

- 完全不进默认 registry，只能 source whitelist 单独跑：对“真实跑一天看效果”不够直接。
- 直接给高优先级：会污染现有官方优先策略。

### Decision: 用 isolated DB + generated Markdown evidence doc 固化“跑一天效果”

用户明确说“可以只跑后端内容，形成一个文档，前端我再去写”。因此这次不会走 UI，而是设计一条 backend-only evidence flow：

- 针对一个明确的 `analysis_date` 运行 capture / market snapshot / daily analysis
- 使用 isolated SQLite DB 与 date-specific output path
- 输出一份中文优先的 Markdown 文档
- 文档中明确展示运行时间、命中情况、Readhub 效果、日报状态和失败/限制

这条路径将尽量复用现有 pipeline summary / daily report markdown exporter，而不是再造一套完全独立的渲染逻辑。

Alternatives considered:

- 只提供 JSON，不写 Markdown：机器可读，但不满足“给我看效果”的人类审阅需求。
- 直接要求前端展示：与用户“前端我再去写”的要求冲突。

## Risks / Trade-offs

- [Readhub 页面结构或内嵌 JSON 键名变化] → 优先解析稳定的结构化块，同时保留必要的 DOM fallback，并用 live validation/tests 及时暴露漂移。
- [聚合源摘要被误当成官方事实] → 将 Readhub 固定为低优先级 aggregated editorial source，不允许压过官方源。
- [topic enrichment 数据量过大，导致落库和返回膨胀] → 对 `trackingList/newsList/similarEventList` 做有界截断和摘要化持久化。
- [真实运行时市场快照或其他 provider 失败，文档难看] → 证据文档必须 failure-transparent，允许部分成功、部分失败。
- [一旦自动抓外链，范围迅速膨胀] → 明确只保留外链引用，不自动全文抓取第三方站点。

## Migration Plan

1. 为 Readhub source 和 source-specific context 按 TDD 增加失败测试。
2. 扩展 source item 数据面，支持结构化 Readhub enrichment 持久化。
3. 实现 dedicated Readhub daily/topic collector，并把该 source 接入 registry。
4. 增加 Readhub validation/reporting 覆盖，证明 canonical endpoint 可抓、legacy alias 失败可降级、topic enrichment 已落库。
5. 实现 backend-only live run evidence 输出路径。
6. 针对一个真实 analysis date 执行后端运行，生成 Markdown evidence doc 和相关 raw artifacts。

## Open Questions

- `trackingList` / `similarEventList` 的持久化上限应是多少条，既能保留信息，又不至于让 source_context 过大？
- 真实运行生成的 evidence doc 最终只保留在 `output/` 作为本地生成产物，还是还需要一份 source-owned 技术摘要写入 `docs/technical/`？
