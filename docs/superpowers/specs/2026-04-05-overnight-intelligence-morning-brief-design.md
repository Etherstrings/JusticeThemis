# 隔夜国际情报晨报系统设计

- 日期：2026-04-05
- 状态：Proposed
- 适用仓库：`daily_stock_analysis`
- 设计主题：面向中国早晨使用场景的隔夜国际金融/政治/宏观情报晨报系统

## 1. 设计结论

本系统的第一版产品形态定义为：

`一个以晨报为主交付形态、以事件账本为核心底座的隔夜国际情报系统。`

系统持续监控美国官方政策、宏观数据、主流市场媒体、市场定价与公司披露源，将隔夜信息整理成可追溯的事件账本，并在北京时间清晨输出分层、去重、带证据链和传导链的晨报。

设计路线选择为：

- 对外：先做“晨报型产品”，满足用户每天早上快速吸收隔夜大事的核心需求。
- 对内：底层按“情报终端底座”设计，采用 `SourceItem -> DocumentFamily -> EventCluster -> AnalysisArtifact` 的事件账本结构，避免未来推倒重来。

本设计明确拒绝以搜索 API 作为主采集骨架。搜索 API 只作为：

- 边缘事件补漏
- 站点故障时兜底
- 新专题发现

## 2. 背景与问题定义

用户处于中国时区，关注美国与全球隔夜金融、政治、宏观与商品信息，希望在早晨用很短时间得到：

- 昨夜发生了什么
- 哪些事件是真正重要的，不是噪音
- 哪些是官方事实，哪些只是媒体解释
- 哪些方向更值得跟踪
- 哪些价格链更可能继续上行
- 哪些结论仍然不确定

现有仓库已经具备以下基础能力：

- 定时运行
- 多渠道通知
- Web 界面
- 搜索服务
- 大模型分析
- 市场复盘基础能力

现有系统的不足在于：

- 以搜索式获取为主，不足以覆盖官方原文、栏目级更新、发布日历、附件与版本修订
- 缺少稳定的事件账本层
- 缺少适合“隔夜情报晨报”场景的优先级与交付策略

## 3. 目标与非目标

### 3.1 目标

- 覆盖隔夜高价值官方源、宏观数据源、主流媒体栏目源、市场定价源与公司披露源
- 把大量异构内容整理成少量可追溯、可更新、可聚类的事件对象
- 对事件做版本跟踪、冲突检测、市场反应补全和传导映射
- 在北京时间清晨输出可读、分层、去重的晨报
- 支持夜间仅对极高优先事件进行提醒
- 为后续主题跟踪、历史回看、回测和个性化打下稳定底座

### 3.2 非目标

- 第一版不追求覆盖全球所有国家与全部英文媒体
- 第一版不追求付费墙全文采集
- 第一版不做完整的研究终端替代品
- 第一版不做过重的个性化排序系统
- 第一版不把所有事件都做深度长文分析

## 4. 产品路线

设计中考虑过三条路线：

### 4.1 搜索聚合型

- 核心方式：使用 Tavily / SerpAPI / Brave 等搜索 API 搜关键词，再交给模型总结
- 优点：开发快
- 缺点：漏官方原件、漏栏目流、漏日历、漏附件、漏版本更新
- 结论：只能作为补漏层

### 4.2 源驱动事件账本型

- 核心方式：接入官方源、媒体栏目源、宏观数据源、市场定价源、披露源，先形成事件账本，再做分析与交付
- 优点：覆盖完整、证据强、可追溯、可长期演进
- 缺点：设计更重
- 结论：作为核心底座

### 4.3 情报终端型

- 核心方式：晨报只是视图之一，重点是长期研究、主题库、知识图谱和深度交互
- 优点：上限最高
- 缺点：第一版过重
- 结论：作为第二阶段延展方向

### 4.4 最终选型

最终采用混合路线：

- 第一版产品形态：晨报型产品
- 第一版底层架构：源驱动事件账本

## 5. 用户场景与交付原则

### 5.1 主要用户路径

系统主要服务三类动作：

1. 起床后 3-5 分钟浏览晨报
2. 对某条头条进一步深挖
3. 回看历史事件与主题演化

### 5.2 用户体验原则

- 先给答案，再给证据
- 先给排序，再给细节
- 先给事件，再给解读
- 明确区分事实、市场反应和推断
- 任何“可能涨价”判断都必须绑定明确传导链
- 不用过强断言替代不确定性披露

### 5.3 交付层级

系统对用户暴露四层内容：

1. `Flash Alert`
2. `Morning Executive Brief`
3. `Deep Dive Report`
4. `Evidence Ledger`

## 6. 源头策略

### 6.1 设计原则

- 官方源优先于媒体源
- 栏目与专题页优先于关键词搜索
- 可结构化接口优先于网页解析
- 日历类源用于守候“未来会发生的大事”
- 搜索 API 只做补漏和发现，不做主干

### 6.2 信息源分层

系统至少覆盖以下五类主源：

1. 官方政策源
2. 宏观数据与发布时间表源
3. 主流编辑部媒体栏目源
4. 市场定价源
5. 公司披露与财报事件源

### 6.3 官方政策源第一版目录

#### White House

至少盯以下入口：

- News 总入口
- Releases
- Briefings & Statements
- Fact Sheets
- Presidential Actions
- Executive Orders
- Proclamations

#### Federal Reserve

至少盯以下入口：

- News & Events
- Press Releases
- Speeches & Testimony
- Calendar
- FOMC calendars
- RSS feeds

#### Treasury

至少盯以下入口：

- News 总页
- Press Releases
- Remarks and Statements
- International Affairs 相关更新
- Tax / financing / sanctions 相关更新

#### USTR

至少盯以下入口：

- Press Releases
- Fact Sheets
- Tariff related pages
- China / Taiwan 相关贸易页
- Industry & Manufacturing / Supply Chain / Critical Minerals 相关页

#### BIS

至少盯以下入口：

- News Updates
- Export Administration / export control related pages
- 规则或更新页

#### SEC

至少盯以下入口：

- RSS feeds
- EDGAR APIs / Latest Filings

### 6.4 宏观数据与发布时间表第一版目录

#### BLS

- Release Schedule
- `.ics` calendar
- 对应具体发布页

#### BEA

- Schedule
- Open Data / API
- 对应发布页

#### Census

- Economic Indicators
- RSS feeds
- 相关发布页

### 6.5 媒体栏目源第一版目录

#### Reuters

- Topics 总入口
- Markets
- Economics & Central Banking
- Commodities & Energy
- Politics & General News
- Americas / Asia 分区

#### FT

- Markets
- Equities
- Bonds
- Currencies
- Commodities
- Monetary Policy Radar
- US
- China
- US Politics & Policy
- Semiconductors

#### Bloomberg

- Markets
- Politics
- 关键主题分栏

#### CNBC

- World
- Futures / Bonds / FX / Commodities / Tech 相关栏目

#### AP

- Business hub
- Politics hub

### 6.6 市场定价源第一版覆盖

至少覆盖以下市场对象：

- 美股主要指数期货
- 美债 2Y / 10Y
- 美元指数
- USDCNH
- Brent / WTI
- Gold
- Copper
- NatGas
- VIX
- 关键行业 ETF
- 关键受影响公司盘后或盘前波动

### 6.7 公司与财报事件源第一版覆盖

- SEC EDGAR 最新披露
- Nasdaq Earnings Calendar
- 重点公司正式财报稿与指引页

第一版公司事件优先级按以下权重倾斜：

- 指数权重大、能影响行业预期的公司
- 与 AI / 半导体 / 云 / 能源 / 汽车 / 消费链强相关的公司
- 能显著影响全球供应链与价格预期的公司

## 7. 采集入口类型

系统至少支持以下七类入口：

- `rss`
- `json_api`
- `ics_calendar`
- `section_page`
- `article_page`
- `filing_feed`
- `pdf_document`

每类入口都需要单独的采集与解析策略，不能使用单一爬虫统一处理。

## 8. 系统架构

系统拆分为以下五个长期存在的子系统：

1. `Collector`
2. `Ledger Builder`
3. `Market Context Builder`
4. `Analysis Orchestrator`
5. `Delivery System`

### 8.1 Collector

职责：

- 从站点、RSS、API、日历和附件持续采集内容
- 保留原始抓取结果
- 生成候选内容对象

不负责：

- 事件聚类
- 事件分析
- 晨报生成

### 8.2 Ledger Builder

职责：

- 标准化原始内容
- 去重
- 版本跟踪
- 文档家族聚合
- 事件聚类
- 冲突检测
- 事件状态更新

### 8.3 Market Context Builder

职责：

- 为事件补市场价格快照
- 构建市场链接对象
- 生成传导映射

### 8.4 Analysis Orchestrator

职责：

- 为事件选择分析模板
- 路由到对应 analyst
- 收集分析包
- 执行 skeptical review
- 生成晨报对象

### 8.5 Delivery System

职责：

- 生成并发送 Flash Alert
- 发送 Morning Executive Brief
- 发送 Deep Dive
- 发布 Web 视图
- 记录发送日志

## 9. 顶层对象模型

系统的一等公民对象如下：

- `SourceDefinition`
- `RawRecord`
- `SourceCandidate`
- `SourceItem`
- `NumericFact`
- `DocumentVersion`
- `DocumentFamily`
- `EventCluster`
- `EventUpdate`
- `MarketLinkSet`
- `ReactionSnapshot`
- `TransmissionMap`
- `AnalysisArtifact`
- `FlashAlert`
- `MorningExecutiveBrief`
- `DeepDiveReport`
- `EvidenceLedgerView`
- `DeliveryLog`

## 10. SourceDefinition

每个源定义至少包括：

- `source_id`
- `display_name`
- `organization_type`
- `source_class`
- `region`
- `domain`
- `entry_type`
- `entry_urls`
- `priority`
- `poll_interval_seconds`
- `timezone`
- `parser_profile`
- `supports_rss`
- `supports_api`
- `supports_calendar`
- `supports_attachments`
- `rate_limit_policy`
- `backfill_window_hours`
- `access_mode`
- `evidence_weight`
- `is_mission_critical`
- `event_domains`
- `expected_release_pattern`
- `parser_fallback_order`

## 11. RawRecord

`RawRecord` 用于保留原始抓取证据。

建议字段：

- `raw_id`
- `source_id`
- `fetch_mode`
- `entry_url`
- `resolved_url`
- `fetched_at`
- `http_status`
- `content_type`
- `response_headers`
- `payload_path`
- `payload_hash`
- `extractor_version`
- `parse_attempts`
- `parse_outcome`

## 12. SourceCandidate

`SourceCandidate` 用于承接从栏目页、feed、API 中抽出的候选内容。

建议字段：

- `candidate_id`
- `raw_id`
- `candidate_type`
- `candidate_url`
- `candidate_title`
- `candidate_summary`
- `candidate_published_at`
- `candidate_section`
- `candidate_tags`
- `needs_article_fetch`
- `needs_attachment_fetch`

`candidate_type` 可包括：

- `feed_item`
- `section_card`
- `article_stub`
- `document_stub`
- `filing_entry`
- `calendar_entry`

## 13. SourceItem

`SourceItem` 是标准化后的最小分析单元。

建议字段：

- `item_id`
- `source_id`
- `raw_id`
- `canonical_url`
- `title`
- `subtitle`
- `summary`
- `body_text`
- `body_excerpt`
- `quoted_fragments`
- `published_at_utc`
- `updated_at_utc`
- `first_seen_at_utc`
- `last_seen_at_utc`
- `section_path`
- `tag_list`
- `author_list`
- `language`
- `region_scope`
- `country_scope`
- `entity_ids`
- `numeric_fact_ids`
- `attachment_ids`
- `source_reliability_class`
- `document_type`
- `access_level`
- `content_hash`
- `semantic_hash`
- `normalization_version`

## 14. NumericFact

`NumericFact` 用于把文章中的关键数值事实结构化。

建议字段：

- `fact_id`
- `item_id`
- `fact_type`
- `subject_entity_id`
- `metric_name`
- `value`
- `unit`
- `direction`
- `comparison_type`
- `previous_value`
- `expected_value`
- `effective_date`
- `text_span`
- `confidence`

## 15. 实体标准化

建议维护独立 `Entity Registry`，至少支持以下实体类型：

- `Institution`
- `OfficialPerson`
- `Company`
- `Ticker`
- `Index`
- `ETF`
- `Commodity`
- `Country`
- `Region`
- `Sector`
- `SupplyChainNode`
- `PolicyTool`
- `MacroIndicator`

每个实体至少包含：

- `entity_id`
- `entity_type`
- `canonical_name`
- `aliases`
- `country`
- `market_mapping`
- `sector_mapping`

## 16. DocumentVersion

建议每次标题、正文或附件变化都生成新版本，不覆盖旧版本。

建议字段：

- `version_id`
- `item_id`
- `version_no`
- `captured_at`
- `title_hash`
- `body_hash`
- `attachment_hashes`
- `delta_type`
- `delta_summary`

## 17. DocumentFamily

`DocumentFamily` 用于聚合同一内容的不同版本、附件与扩展稿。

建议字段：

- `family_id`
- `primary_source`
- `family_type`
- `family_title`
- `member_item_ids`
- `version_chain`
- `attachment_ids`
- `latest_item_id`
- `first_seen_at`
- `last_updated_at`

`family_type` 典型包括：

- `official_release_bundle`
- `wire_flash_to_story`
- `filing_with_exhibits`
- `article_with_pdf`
- `speech_with_transcript`

## 18. EventCluster

`EventCluster` 是系统的核心事件对象。

建议字段：

- `event_id`
- `event_type`
- `event_subtype`
- `core_headline`
- `core_fact`
- `event_time`
- `first_seen_time`
- `latest_update_time`
- `status`
- `source_item_ids`
- `document_family_ids`
- `official_evidence_ids`
- `media_evidence_ids`
- `entities`
- `geographies`
- `assets`
- `sectors`
- `commodities`
- `policy_tools`
- `macro_indicators`
- `reaction_snapshot_id`
- `novelty_score`
- `urgency_score`
- `importance_score`
- `confidence_score`
- `contradiction_flags`

### 18.1 事件状态机

状态建议包括：

- `scheduled`
- `breaking`
- `confirmed`
- `developing`
- `revised`
- `contradictory`
- `closed`

## 19. 事件分类法

### 19.1 一级分类 `event_type`

- `policy_action`
- `macro_release`
- `central_bank_signal`
- `regulatory_action`
- `trade_action`
- `geopolitical_event`
- `commodity_shock`
- `company_disclosure`
- `earnings_event`
- `market_regime_shift`

### 19.2 二级分类 `event_subtype`

第一版至少支持以下子类：

#### `policy_action`

- `executive_order`
- `fact_sheet`
- `formal_statement`
- `subsidy_program`
- `tax_change`
- `industrial_policy`
- `sanctions_action`

#### `macro_release`

- `cpi`
- `ppi`
- `nonfarm_payrolls`
- `unemployment`
- `retail_sales`
- `gdp`
- `pce`
- `trade_balance`
- `productivity`
- `housing`
- `manufacturing`

#### `central_bank_signal`

- `fomc_decision`
- `fed_speech`
- `fed_minutes`
- `balance_sheet_signal`
- `liquidity_operation`

#### `regulatory_action`

- `sec_rule`
- `sec_enforcement`
- `bis_export_control`
- `treasury_sanctions`
- `compliance_update`

#### `trade_action`

- `tariff_announcement`
- `tariff_implementation`
- `export_control_update`
- `import_restriction`
- `supply_chain_resilience_policy`

#### `geopolitical_event`

- `military_escalation`
- `diplomatic_breakthrough`
- `shipping_disruption`
- `election_shock`
- `cross_strait_tension`
- `middle_east_escalation`

#### `commodity_shock`

- `oil_spike`
- `gas_spike`
- `gold_flight_to_safety`
- `copper_demand_signal`
- `agricultural_supply_shock`
- `shipping_rate_shock`

#### `company_disclosure`

- `sec_filing`
- `guidance_update`
- `capex_update`
- `legal_risk_disclosure`
- `management_change`
- `supply_chain_disclosure`

#### `earnings_event`

- `earnings_beat`
- `earnings_miss`
- `guidance_raise`
- `guidance_cut`
- `segment_signal`
- `margin_signal`

#### `market_regime_shift`

- `rates_repricing`
- `usd_breakout`
- `risk_on_rotation`
- `risk_off_rotation`
- `credit_stress_signal`
- `volatility_regime_change`

### 19.3 标签层

除分类外，事件还应维护标签：

- `country_tags`
- `asset_tags`
- `sector_tags`
- `policy_tags`
- `market_state_tags`

## 20. MarketLinkSet

`MarketLinkSet` 用于描述某个事件应观察的市场对象集合。

建议字段：

- `event_id`
- `linked_indices`
- `linked_rates`
- `linked_fx_pairs`
- `linked_commodities`
- `linked_sector_etfs`
- `linked_companies`
- `linked_regions`

## 21. ReactionSnapshot

`ReactionSnapshot` 用于记录事件在多个关键时间点的市场反应。

建议字段：

- `snapshot_id`
- `event_id`
- `snapshot_time`
- `price_panel`
- `rate_panel`
- `fx_panel`
- `commodity_panel`
- `equity_panel`
- `sector_panel`
- `company_panel`

### 21.1 抓取时间点

对高优先事件，建议至少抓以下时间点：

- `T_detect`
- `T_confirm`
- `T_plus_15m`
- `T_plus_60m`
- `T_market_transition`
- `T_digest_cutoff`

## 22. TransmissionMap

`TransmissionMap` 用于表达事件如何传导到资产、价格、行业与区域。

建议字段：

- `map_id`
- `event_id`
- `primary_shock_type`
- `channels`
- `first_order_effects`
- `second_order_effects`
- `third_order_effects`
- `speed`
- `duration`
- `confidence`
- `regional_links`
- `commodity_links`
- `sector_links`
- `company_links`
- `china_mapping_notes`

`primary_shock_type` 建议包括：

- `policy_shock`
- `macro_shock`
- `liquidity_shock`
- `commodity_shock`
- `geopolitical_shock`
- `earnings_shock`
- `regulatory_shock`

## 23. Collector 内部模块

Collector 至少拆成以下模块：

- `SourceScheduler`
- `Fetcher`
- `Extractor`
- `LinkResolver`
- `AttachmentFetcher`
- `CalendarWatcher`
- `BackfillRunner`
- `RateLimitController`

### 23.1 调度模式

建议支持：

- `poll`
- `release_window_guard`
- `backfill`
- `morning_final_sweep`
- `manual_recheck`

## 24. Ledger Builder 流水线

建议按以下顺序执行：

1. `candidate expansion`
2. `source item normalization`
3. `version detection`
4. `family assignment`
5. `entity & numeric extraction`
6. `event assignment`
7. `contradiction check`
8. `status update`
9. `event emit`

顺序不能打乱，尤其不能在实体与数值事实尚未抽取前强做事件聚类。

## 25. 去重与聚类

建议做四级去重：

1. `URL 级`
2. `文本级`
3. `家族级`
4. `事件级`

### 25.1 聚类原则

聚类采用“规则优先，语义补充”：

- 主语相同
- 动作相同
- 对象相同
- 时间窗口接近
- 数值不冲突
- 政策工具一致
- 标题和正文语义相似
- 实体集合高度重叠

### 25.2 领域约束

- 官方源优先定义事件边界
- 宏观数据一律按“指标 + 发布时间”聚类
- 财报事件按“公司 + 财季 + 事件类型”聚类
- 关税与出口管制按“机构 + 动作 + 覆盖对象”聚类

## 26. EventUpdate

事件更新建议显式化为 `EventUpdate` 对象。

建议字段：

- `event_update_id`
- `event_id`
- `update_type`
- `created_at`
- `triggering_item_ids`
- `changed_fields`
- `priority_recompute_required`
- `analysis_recompute_required`
- `delivery_check_required`

`update_type` 典型包括：

- `new_evidence_added`
- `official_confirmation_added`
- `version_revised`
- `market_reaction_changed`
- `contradiction_detected`
- `priority_upgraded`
- `priority_downgraded`
- `status_closed`

## 27. 冲突检测

建议实现专门的 `ContradictionEngine`，检查以下冲突：

- `numeric_conflict`
- `scope_conflict`
- `timing_conflict`
- `authority_conflict`
- `status_conflict`
- `market_conflict`

冲突结果至少包含：

- `conflict_type`
- `conflict_fields`
- `conflicting_evidence_ids`
- `severity`
- `resolved_flag`

## 28. 优先级引擎

### 28.1 基础打分项

- `source_quality_score`
- `officiality_score`
- `freshness_score`
- `evidence_strength_score`
- `market_reaction_score`
- `impact_breadth_score`
- `impact_depth_score`
- `novelty_score`
- `contradiction_penalty`
- `duplication_penalty`

### 28.2 输出项

- `importance_score`
- `urgency_score`
- `confidence_score`
- `attention_cost_score`
- `priority_level`
- `importance_band`
- `display_rank`
- `delivery_policy`

### 28.3 优先级层级

- `P0`
- `P1`
- `P2`
- `P3`
- `P4`

### 28.4 重要度分带

- `systemic`
- `high`
- `medium`
- `background`

### 28.5 交付策略

- `silent_archive`
- `brief_only`
- `deep_dive_only`
- `morning_brief_highlight`
- `night_alert_and_brief`
- `urgent_interrupt`

### 28.6 直接进入 P0 候选的情况

- White House / Fed / USTR / BIS / SEC / BLS / BEA 的重大正式发布
- 关键商品异常冲击
- 利率与美元出现明显跨资产联动
- 巨型公司盘后披露触发行业级重估
- 地缘事件升级并影响能源、航运或风险偏好

### 28.7 直接降级的情况

- 只有低权重单一媒体提及且无官方确认
- 纯评论文章，无新增事实
- 与前 24 小时事件高度重复且无增量
- 市场完全无反应且证据弱
- 存在重大冲突但尚未解决

## 29. 分析角色

建议至少包含以下角色：

- `Policy Analyst`
- `Macro Analyst`
- `Rates & Liquidity Analyst`
- `Commodities Analyst`
- `Sector & Supply Chain Analyst`
- `Skeptical Reviewer`
- `Synthesis Editor`

### 29.1 路由规则

- `policy_action` -> Policy Analyst + Sector Analyst + Skeptical Reviewer
- `macro_release` -> Macro Analyst + Rates Analyst + Skeptical Reviewer
- `commodity_shock` -> Commodities Analyst + Sector Analyst + Skeptical Reviewer
- `company_disclosure` -> Sector Analyst + Skeptical Reviewer
- `earnings_event` -> Sector Analyst + Skeptical Reviewer
- `geopolitical_event` -> Policy Analyst + Commodities Analyst + Rates Analyst + Skeptical Reviewer
- `market_regime_shift` -> Rates Analyst + Macro Analyst + Skeptical Reviewer

### 29.2 输出必须结构化

每个 analyst 输出结构化对象，而不是自由文本长文。

## 30. Skeptical Reviewer

该角色只做约束和反驳，不做观点加码。

必须检查：

- 是否把匿名消息当正式政策
- 是否把评论当事实
- 是否忽略附件
- 是否忽略市场不买账
- 是否把短期盘前异动外推成长期方向
- 是否把单一事件过度映射到过多方向
- 是否混淆旧版本和新版本
- 是否在证据不足时给出过高置信度

建议输出：

- `challenge_points`
- `downgrade_reasons`
- `uncertainty_disclosures`
- `blocked_claims`
- `approved_claims`

## 31. Synthesis Editor

职责：

- 选择晨报头条
- 压缩重复事件
- 组织栏目顺序
- 生成多版本交付对象

硬规则：

- 不引入未出现在证据层的新事实
- 不绕过 skeptical review
- 不重复描述同一事件簇
- 若存在重大冲突，必须显式披露不确定性
- “哪些方向可能涨价”必须绑定明确传导链

## 32. 晨报对象

### 32.1 FlashAlert

建议字段：

- `alert_id`
- `event_id`
- `headline`
- `core_fact`
- `market_reaction`
- `watch_next`
- `sent_at`

### 32.2 MorningExecutiveBrief

建议字段：

- `brief_id`
- `digest_date`
- `cutoff_time`
- `topline`
- `top_events`
- `cross_asset_snapshot`
- `likely_beneficiaries`
- `likely_pressure_points`
- `what_may_get_more_expensive`
- `policy_radar`
- `macro_radar`
- `sector_transmission`
- `risk_board`
- `today_watchlist`
- `evidence_links`
- `generated_at`
- `version_no`

### 32.3 DeepDiveReport

建议字段：

- `report_id`
- `digest_date`
- `event_cards`
- `appendix`
- `generated_at`
- `version_no`

### 32.4 EvidenceLedgerView

建议字段：

- `ledger_view_id`
- `digest_date`
- `event_ids`
- `source_item_ids`
- `document_family_ids`
- `official_evidence_ids`
- `media_evidence_ids`
- `market_snapshot_ids`
- `analysis_artifact_ids`
- `generated_at`
- `version_no`

## 33. 晨报栏目设计

`Morning Executive Brief` 建议固定结构：

1. `Overnight Topline`
2. `Top Events`
3. `Cross-Asset Snapshot`
4. `Likely Beneficiaries`
5. `Likely Pressure Points`
6. `What May Get More Expensive`
7. `Official Policy Radar`
8. `Need Confirmation`
9. `Today Watchlist`
10. `Primary Sources`

### 33.1 Topline 生成规则

Topline 必须同时反映：

- 昨夜主线
- 主驱动
- 市场首先定价的对象

### 33.2 Today Watchlist 结构

建议分为：

- `待确认`
- `待定价`
- `待发布`
- `待观察`

## 34. 详细事件卡

每张 `Deep Dive Event Card` 建议固定为：

- `标题`
- `事件级别`
- `核心事实`
- `为什么重要`
- `证据链`
- `时间线`
- `版本变化`
- `已知数字`
- `市场即时反应`
- `传导链`
- `受益方向`
- `受损方向`
- `价格影响`
- `持续性判断`
- `反方风险`
- `置信度`
- `原文链接`

## 35. “方向”与“涨价”板块

### 35.1 Direction Board

系统应每日生成以下方向面板：

- `Rates-sensitive directions`
- `Commodity-linked directions`
- `Policy beneficiaries`
- `Policy pressure points`
- `Supply-chain reallocation`
- `Risk-off / defensive watch`

每个方向至少应包含：

- `驱动事件`
- `传导链`
- `受益/受损逻辑`
- `置信度`
- `持续性判断`

### 35.2 Price Pressure Board

系统应每日生成价格压力面板，至少覆盖：

- `直接涨价`
- `上游成本传导`
- `预期性涨价`

每条记录必须绑定：

- 触发事件
- 价格对象
- 传导阶段
- 市场是否已部分定价
- 置信度
- 持续性判断

### 35.3 持续性判断

统一采用以下枚举：

- `headline_only`
- `short_term`
- `multi_day`
- `structural`
- `unclear`

## 36. 运行模式

系统建议支持：

1. `continuous service mode`
2. `scheduled batch mode`
3. `manual replay mode`

第一版可先采用 `scheduled batch mode`，但对象模型不得写死为一次性脚本结构。

## 37. 调度平面

建议单独维护 `Orchestration Plane`。

统一任务字段：

- `task_id`
- `task_type`
- `scheduled_for`
- `started_at`
- `finished_at`
- `status`
- `attempt_no`
- `priority`
- `target_scope`
- `upstream_dependency_ids`
- `result_summary`

`task_type` 典型包括：

- `poll_source`
- `expand_candidate`
- `fetch_attachment`
- `build_ledger`
- `refresh_market_snapshot`
- `run_analysis`
- `generate_digest`
- `send_delivery`

## 38. 端到端时序

### 38.1 夜间运行窗口

建议按北京时间划分：

- `20:00-23:00`：准备与守候
- `23:00-03:00`：高价值发现窗口
- `03:00-06:30`：补细节、补附件、补市场反应
- `06:30-07:30`：终扫与晨报生成
- `07:30 后`：发送正式晨报与必要补编

### 38.2 重大事件生命周期

1. `发现`
2. `确认`
3. `扩充`
4. `定价`
5. `映射`
6. `排序`
7. `分析`
8. `交付`

## 39. 数据保留策略

建议分四层保留：

1. `raw payload retention`
2. `normalized item retention`
3. `ledger retention`
4. `delivery retention`

原则：

- 原始层可回放
- 账本层可分析
- 交付层可回看

## 40. 存储形态

逻辑上建议至少区分：

- `object store`
- `relational store`
- `search/index layer`
- `time-series or snapshot store`

## 41. 可观测性

至少监控以下四类：

- `source health`
- `pipeline health`
- `content quality`
- `delivery health`

## 42. 关键告警

建议对以下情况主动告警：

- mission critical 源长时间无成功抓取
- 官方源发布窗口到点但无内容进入系统
- 晨报生成失败
- 高优先事件未进入最终晨报
- 去重异常导致事件数爆炸
- 市场快照抓取异常
- Telegram / Email 连续发送失败
- parser 解析成功率骤降

## 43. 质量门禁

晨报生成前建议强制检查：

- `critical source coverage gate`
- `minimum evidence gate`
- `duplication gate`
- `contradiction disclosure gate`
- `delivery completeness gate`

未通过时应降级，而不是伪装为正常输出。

## 44. 测试策略

建议至少包含五层：

1. `parser tests`
2. `normalization tests`
3. `dedup and clustering tests`
4. `priority and delivery tests`
5. `golden digest tests`

## 45. Replay Corpus

建议从第一版起建立可回放样本库，覆盖：

- 关键官方源样本
- 媒体栏目页样本
- CPI / NFP / FOMC / USTR / BIS 等大事件样本
- 财报事件样本
- 地缘冲击与商品冲击样本

用于：

- 回放新 parser
- 回放新聚类规则
- 回放新优先级与晨报结果

## 46. 失败与降级策略

必须允许局部失败而整体继续：

- 源失败：重试、退避、告警
- 解析失败：保留 raw，进入修复队列
- 聚类失败：保留审计轨迹，允许后修
- 分析失败：降级到事实层与已完成角色结果
- 发送失败：重试或切换渠道

核心原则：

`局部失败，不阻断整份晨报。`

## 47. 历史回看与最小 Web 视图

第一版 Web 至少提供：

- `Morning Brief Page`
- `Event Detail Page`
- `History Page`
- `Topic Page`

历史应支持三种视角：

- 按天看
- 按事件看
- 按主题看

## 48. 用户反馈闭环

第一版预留轻量反馈能力：

- `有用 / 无用`
- `这条太重复`
- `这条不重要却排太高`
- `这条应该更靠前`
- `这条结论过强`
- `漏了某件大事`

反馈先进入 review 队列，不直接自动学习。

## 49. 分阶段路线图

### 阶段 0：设计冻结

目标：

- 确认产品路线
- 确认对象模型
- 确认第一版边界

### 阶段 1：采集与账本底座

目标：

- 关键源采集稳定
- 能生成 SourceItem、DocumentFamily、EventCluster

### 阶段 2：市场上下文与优先级

目标：

- 引入市场快照
- 引入 TransmissionMap
- 建立 PriorityEngine

### 阶段 3：分析与晨报

目标：

- 引入多角色分析
- 生成 Morning Executive Brief、Deep Dive、Flash Alert

### 阶段 4：交付与历史回看

目标：

- 打通 Telegram / Email / Web
- 提供按天、按事件、按主题回看

### 阶段 5：质量、回放与迭代

目标：

- 建立 Replay Corpus
- 建立 Golden Digest Tests
- 建立质量指标与持续优化闭环

## 50. 第一版成功标准

第一版被视为成功，至少满足：

- 关键源覆盖稳定
- 重大隔夜事件明显漏报率低
- 事件去重与聚类基本可信
- 优先级排序大致符合人类判断
- 晨报在固定时间稳定产出
- 头条结论有明确证据链
- 夜间提醒稀疏但关键事件不漏
- 用户能够连续使用一个月

## 51. 风险与约束

主要风险：

- 源结构变动
- 误去重
- 漏聚类
- 版本混淆
- 过度分析
- 市场映射过宽
- 夜间打扰过多
- 优先级错排

缓解措施：

- mission critical 源健康监控
- Replay Corpus 回放
- Golden Digest Tests
- skeptical review
- 强制不确定性披露
- delivery policy 与质量门禁

## 52. 第一版范围冻结

第一版必须做：

- Source registry
- 多采集器
- 标准化 SourceItem
- DocumentFamily
- EventCluster
- 版本跟踪
- 冲突检测基础版
- 市场反应快照
- 传导映射基础版
- 优先级评分
- 多角色分析基础版
- Telegram / Email / Web 分层交付

第一版可以暂缓：

- 全球非美核心区域广覆盖
- 复杂知识图谱
- 全自动反馈学习
- 重度终端检索交互
- 过多个性化配置

## 53. 与现有仓库的关系

该设计应优先复用仓库现有能力：

- 定时调度与运行模式
- 通知渠道能力
- Web 界面基础设施
- 市场数据获取能力
- LLM 调用能力
- 现有搜索服务作为补漏层

不建议直接把现有搜索式新闻逻辑扩展为主干采集层。应新增更稳定的源驱动采集与事件账本链路，再决定如何复用已有 `search_service` 作为辅助组件。

## 54. 冻结后的下一步

本设计冻结后，下一步应为：

1. 进行 spec review
2. 根据 review 修订设计
3. 在用户确认后进入 implementation planning

在 implementation planning 之前，不应继续扩散产品语义，也不应重新打开本设计已经冻结的边界。
