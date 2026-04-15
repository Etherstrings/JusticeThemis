## Context

`2026-04-15` 的真实后端日报已经能产出完整 `free / premium` 报告，但内容层存在明显的“交付质量”问题：

- `direction_calls` 里存在同一批证据驱动多个近似方向的情况，用户读起来像机器枚举而不是结论压缩。
- `headline_news` / `Key News` 目前优先输出 `llm_ready_brief` 或 `impact_summary`，当这两个字段本身是审计串时，Markdown 会直接把机器字段拼接暴露给用户。
- `mainlines / market_regimes` 为空时，固定日报只是在 `input_snapshot` 里给出 `0`，并没有告诉用户是“市场数据不完整导致未确认”还是“确实没有主线”。
- market snapshot 已经在健康层判定 `partial` 且存在 `core_missing_symbols`，但日报 summary 仍可能保持过强的 confidence 和过轻的风险表述。

当前代码路径上，这些问题主要集中在三个地方：

1. `DailyAnalysisService._build_mainline_context()` 只返回 `mainlines / market_regimes / secondary_event_groups`，没有把“为何为空”的 coverage state 下传。
2. `RuleBasedDailyAnalysisProvider` 直接从原始 scored items 生成 `direction_calls / headline_news / summary / narratives`，缺少一个面向用户的内容质量收敛层。
3. `pipeline_markdown.render_daily_report_markdown()` 优先消费 `llm_ready_brief` / `impact_summary`，没有更强的用户摘要字段。

这次 change 是一个纯后端内容质量收紧，不增加前端范围，不引入外部模型，不要求重构抓取面。

## Goals / Non-Goals

**Goals:**

- 让固定日报的用户可见文本优先输出中文可读结论，而不是机器审计串。
- 对重复方向做 deterministic 压缩，让一个宏观驱动不会在报告里展开成多个近似条目。
- 为主线 / regime 的缺失建立显式 coverage state，让日报能解释“为什么没给出 confirmed mainline”。
- 将 market core-board 缺口下传到 summary、confidence、risk watchpoints 和 narrative 文案。
- 保持现有固定日报、Markdown 导出、evidence 文档和 premium/free 分层边界，不引入新的外部依赖。

**Non-Goals:**

- 不新增前端页面、前端 API 或视觉展示要求。
- 不引入任何 LLM 或非确定性摘要器来“美化”日报。
- 不重做 source capture、event clustering 或 Readhub ingestion。
- 不要求每个 analysis date 都必须产出非空 `mainlines / market_regimes`；重点是有则用、无则解释。

## Decisions

### Decision: 在 `RuleBasedDailyAnalysisProvider` 内新增一层 deterministic content-quality pass

日报内容问题主要出现在“原始分析字段直接暴露给用户”这一层，因此内容质量收敛应该发生在 report provider 内，而不是放到 Markdown renderer 或前端里修饰。实现上将保留原始打分和 supporting/audit 字段，但在最终 report 输出前增加一层 deterministic post-processing：

- 原始 `direction_calls` 先按当前逻辑聚合
- 再进入方向去重 / family 压缩
- `headline_news` 从“审计可读”对象再生成“用户可读”摘要字段
- `summary / narratives / risk_watchpoints` 使用收敛后的内容而不是直接引用原始机器串

Alternatives considered:

- 只改 Markdown renderer：能改善展示，但不能改善 API / DB 中的缓存报告内容。
- 交给外部模型重写：可读性更强，但破坏 fixed-report 的 deterministic 边界。

### Decision: 将“用户可见摘要”和“审计字段”分层，而不是互相复用

当前 `headline_news` 同时承担审计和展示职责，导致 `brief` 容易直接落回原始拼接字段。设计上将保留 `supporting_items` 作为富审计层；`headline_news` 则新增用户可见摘要字段，例如：

- `user_brief_cn`
- `why_it_matters_cn`
- `brief_source`

Markdown / HTML preview 等用户面输出优先使用新字段；审计文档、调试或后续 handoff 仍可以读取现有 `impact_summary / llm_ready_brief / evidence_points`。

Alternatives considered:

- 直接覆写 `impact_summary`：会混淆“分析内部字段”和“用户交付字段”的语义。
- 只保留用户字段不保留审计字段：会削弱可追溯性。

### Decision: 为 mainline/regime 增加显式 `coverage_state`，而不是用空数组表达所有失败模式

`mainlines=[]` 与 `market_regimes=[]` 目前混合了多种完全不同的含义：无市场数据、市场数据不完整、无触发 regime、无可链接 event group、或确实没有 confirmed overnight narrative。为了让 summary 和 narratives 能解释这些差异，`DailyAnalysisService._build_mainline_context()` 将返回额外的 coverage 状态对象，例如：

- `status`: `confirmed` / `degraded` / `unavailable`
- `market_data_status`: `complete` / `partial` / `missing`
- `suppression_reasons`: 如 `core_market_gap`, `no_triggered_regime`, `no_linked_event_group`
- `secondary_group_count`

provider 用这个状态来决定：

- 是否把主线写进 headline / core_view
- 当未确认时给出什么降级文案
- 是否把 secondary context 写进 narratives

Alternatives considered:

- 继续依赖 `mainline_count=0` 由调用方自行猜测：无法支撑稳定用户文案。
- 在 renderer 里现算 suppression reason：会让业务语义散落在展示层。

### Decision: 用“market completeness cap” 收紧 confidence 和风险文案

固定日报的高/中/低 confidence 不能只看官方条数和方向数量，还必须看 market snapshot 的 completeness。设计上引入一个简单明确的 cap 规则：

- 如果 `core_missing_symbols` 非空，则 summary confidence 最高为 `medium`
- 如果同时没有 confirmed mainline/regime，且方向主要来自编辑源或弱确认，则降为 `low`
- `risk_watchpoints` 自动注入一条市场缺口 watchpoint，避免用户忽略快照不完整这一事实
- `narratives.market_view` / `summary.core_view` 明确指出 market board 为 partial 或缺少核心板块

Alternatives considered:

- 只在 evidence doc 里提示市场缺口：对真正读取日报的用户不够。
- 完全阻止日报生成：会降低产品可用性，不符合当前“允许部分成功但必须透明”的路线。

### Decision: 方向去重采用“family 映射 + 证据重叠”双重压缩，而不是纯字符串去重

重复方向并不是简单的重名问题，而是多个标签共享同一宏观驱动与同一事件簇。设计上将引入一个受控的 family 压缩层：

- 先用 curated family map 把明显重叠的方向放入同一用户语义族，例如上游能源受益链、能源成本通胀链等
- 再结合 `event_cluster_ids / evidence_mainline_ids / evidence_regime_ids` 的重叠程度，判定 sibling directions 是否应压缩
- 保留 strongest surviving direction 作为用户可见条目
- `stock_calls` 只从 surviving directions 派生，避免 premium 报告重复映射同一逻辑

这个层不追求完全自动语义理解，而是先解决真实跑数里最常见、最伤阅读体验的重复。

Alternatives considered:

- 只看字符串别名：无法处理不同名字但同一证据簇的问题。
- 完全依赖 embeddings/语义模型：超出当前 deterministic 范围。

## Risks / Trade-offs

- [方向 family 映射需要维护] → 先覆盖高频重叠方向，配回归测试，避免试图一次解决所有行业语义。
- [压缩过强可能误删真实独立方向] → family 压缩必须同时满足证据重叠阈值，不仅靠手工分类。
- [报告 payload 增长] → 新增 `coverage_state` 和用户摘要字段时保持字段有界，避免复制完整审计串。
- [旧版缓存报告与新版内容风格不一致] → 不做历史回填；新版本报告自然覆盖旧版版本号。
- [市场缺口 cap 降低结论“锋利度”] → 这是有意的产品收紧，优先保证透明度和可信度。

## Migration Plan

1. 先补针对方向去重、可读 news brief、market completeness cap、mainline coverage 文案的失败测试。
2. 扩展 `DailyAnalysisService._build_mainline_context()`，让它返回 coverage state 和 suppression reasons。
3. 在 `RuleBasedDailyAnalysisProvider` 中加入 content-quality pass，改写 `direction_calls / headline_news / summary / narratives / risk_watchpoints / stock_calls` 的最终生成顺序。
4. 更新 Markdown/export surfaces，使其优先消费新的用户摘要字段和 degraded-market 表达。
5. 用现有 `2026-04-15` 类似 fixture 或真实路径做 regression，确认输出比旧版更可读且不会掩盖缺口。
6. 不做 schema migration；旧 report JSON 保持可读，新生成版本自然带上新增字段。

## Open Questions

- 方向 family 的初始覆盖面要控制在“真实高频重复项”，避免把实现阶段拖成行业本体工程。
- secondary event groups 在 fixed report 中是进入 summary/narrative 还是只进入 narrative/risk 层，实施时需要结合测试样例定最终粒度。
