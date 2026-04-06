# 隔夜源覆盖 Source Coverage v1 设计

- 日期：2026-04-06
- 状态：Approved
- 适用仓库：`daily_stock_analysis`
- 设计主题：把 JusticeThemis 的隔夜源目录从演示级 3 个默认源扩成一套可解释、可观察、适合 A 股盘前使用的覆盖底座

## 1. 设计结论

`Source Coverage v1` 的目标不是在这一轮把全部采集器都写完，而是先把“这套产品到底盯哪些源、为什么盯、现在覆盖到什么程度”做成产品内可见的结构。

这一轮只做三件事：

- 扩展默认源注册表，补齐官方政策、官方数据、主流媒体三层关键源
- 扩展 `/api/v1/overnight/sources` 与 `/api/v1/overnight/health`，让后端能输出覆盖分层与缺口
- 改造前端 `Source Registry` / `Operations` 面板，让用户一眼看出当前覆盖面是否足够

这一轮明确不做：

- 不批量新增 collector 实现
- 不接入新的夜间调度逻辑
- 不先做投递渠道产品化

## 2. 背景与问题

当前 JusticeThemis 已经有晨报页、行动板、变化对照、事件页和健康面板，但默认源目录只有：

- White House News
- Federal Reserve News
- Reuters Topics

这对于“证明产品结构存在”够用，但对于真实的 A 股隔夜判断不够：

- 官方政策面缺 Treasury、USTR 等对贸易、制裁、融资条件更敏感的源
- 宏观数据面缺 BLS、BEA、EIA 等决定通胀、增长、能源成本预期的源
- 媒体面没有形成“官方原文 + 主流快讯”双层覆盖说明
- 页面上虽然有 `Source Registry` 和 `Operations`，但还不能回答“这套源为什么够用、哪里还缺”

## 3. 用户目标

用户早上看这个产品，不只是想知道“昨晚抓到了几条新闻”，而是想知道：

- 关键官方源有没有盯住
- 宏观发布时间表有没有覆盖
- 主流媒体是不是只做辅助而不是替代原文
- 当前晨报如果变薄，是因为昨晚真的没事，还是因为覆盖层本身缺口太大

因此，这一轮的产品目标是把“覆盖面”本身做成可读信息。

## 4. 方案选择

### 4.1 方案 A：Registry-first

- 扩展源注册表
- 扩展 health summary
- 改造 source catalog UI

优点：

- 改动集中，风险可控
- 立刻提升产品可信度和可解释性
- 不依赖新站点解析稳定性

缺点：

- 新增源多数先停留在目录层，不一定立即参与真实采集

### 4.2 方案 B：Registry + Collectors

- 在方案 A 基础上同步补一批新 collector

优点：

- 内容层会更厚

缺点：

- 这一轮边界会明显膨胀
- 需要新增多组 fixture 与解析细节，交付速度会下降

### 4.3 方案 C：Delivery-first

- 先做企业微信 / 飞书 / 邮件的隔夜投递产品化

优点：

- 更接近每天实际使用

缺点：

- 不能解决“当前内容覆盖面还薄”的核心问题

### 4.4 最终选型

采用方案 A，先完成 `Registry-first`。

## 5. Source Coverage v1 范围

### 5.1 官方政策源

- White House News
- Federal Reserve News
- USTR Press Releases
- Treasury Press Releases

这些源负责覆盖：

- 贸易与关税
- 制裁与国际金融政策
- 联储声明、讲话、利率路径
- 白宫政策信号与行政动作

### 5.2 官方数据 / 日历源

- BLS News Releases
- BLS Release Schedule
- BEA News
- EIA Pressroom

这些源负责覆盖：

- CPI / PPI / 就业
- GDP / PCE / 国际收支
- 能源供需、油气价格与库存叙事
- “尚未发布但必须守候”的日历事件

### 5.3 主流媒体源

- Reuters Topics
- AP Politics
- AP Business
- CNBC World

这些源负责：

- 在官方原文之外补充快讯层
- 提供跨市场叙事的编辑部排序
- 对 overnight brief 做第二层解释，但不替代官方证据

## 6. 数据模型调整

`SourceDefinition` 保留现有字段，并补充以下最小元数据：

- `coverage_tier`
  - `official_policy`
  - `official_data`
  - `editorial_media`
- `region_focus`
  - 用于解释该源主要覆盖美国政策、美国宏观、全球市场等哪一层
- `coverage_focus`
  - 用户可读的一句话，说明这个源被纳入的主要原因

这样做的目的不是堆字段，而是为了支撑 API 和前端可见性。

## 7. API 设计

### 7.1 `/api/v1/overnight/sources`

继续返回全部源，但每条源补充：

- `coverage_tier`
- `region_focus`
- `coverage_focus`

### 7.2 `/api/v1/overnight/health`

在现有 `source_health` 上补充：

- `enabled_mission_critical_sources`
- `coverage_tier_counts`
- `source_class_counts`
- `coverage_gaps`

`coverage_gaps` 是用户可读的缺口列表，例如：

- `官方数据源覆盖不足`
- `当前没有日历型 mission-critical 源`
- `当前只覆盖少量主流媒体入口`

目的不是绝对精确，而是帮助用户判断“内容薄”是新闻少还是覆盖少。

## 8. 前端设计

### 8.1 Source Registry

从“按单条源平铺”改成“按覆盖层分组”：

- 官方政策
- 官方数据
- 主流媒体

每张卡继续展示：

- 启用状态
- mission-critical 标签
- 轮询节奏
- 入口 URL

并新增两条可读信息：

- `region focus`
- `coverage focus`

### 8.2 Operations

继续保留当前：

- Sources
- Pipeline
- Delivery
- Avg Confidence
- Evidence Gate

新增：

- 覆盖层计数
- mission-critical 实际启用数
- coverage gaps 提示块

## 9. 成功标准

这一轮完成后，应满足：

- 默认源数量不再是 3，而是一套明显更完整的目录
- `/overnight` 页能直接看出政策 / 数据 / 媒体三层覆盖
- `/api/v1/overnight/health` 能解释当前覆盖缺口
- 所有新增字段都有测试覆盖
- 前端构建继续通过

## 10. 风险与控制

### 10.1 风险

- 新增源如果马上要求真实采集，会把这一轮拖成 collector 工程
- 健康面板如果只报数字，不给解释，仍然无法帮助用户判断

### 10.2 控制

- 这一轮只要求 registry / health / UI 先成立
- collector 支持留到下一轮按源逐个补
- 缺口信息以启发式汇总为主，不追求过度复杂

## 11. 后续阶段

`Source Coverage v2` 再做：

- Treasury / USTR / BLS / BEA / EIA 的 collector fixture 和解析器
- 基于源层的 freshness / fetch failure 统计
- 源级别失败告警
