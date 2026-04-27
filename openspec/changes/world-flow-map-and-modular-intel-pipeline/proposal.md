## Why

当前项目把新闻采集、市场数据、日报分析、free/premium 分层和多种展示出口混在一起，结果是产品定位不清，输出也不像一个人会真正拿来用的信息产品。现在需要把它收拢成两个清晰模块：前面负责拿到全球所有和钱相关的新闻与数据，并先做一轮筛选整理；后面负责把这些输入整理成可对照、可读、可解释的结论，同时产出一张名为“昨天世界钱往哪里”的核心结果图或成图数据。

## What Changes

- **BREAKING** 移除 free / premium 双层产品边界，日报、方向判断、导出内容统一回到单一版本，不再按访问层级拆内容。
- 把项目拆成两个主模块：
  - 来源模块：负责全球宏观/政策、地缘、权益市场、行业板块、利率、汇率、商品、AI/科技和大公司事件的采集、标准化、分层筛选、去重压缩、简短解释和来源管理。
  - 分析对照模块：负责把来源输入、分析结论、方向判断和对应证据放到同一个可对照结构里，避免“只有结论没有来由”。
- 明确保留当前所有网站、信源、数据获取入口和已有采集逻辑；这次重构是重组和标准化，不是删源或换源。
- 新增“昨天世界钱往哪里”输出能力，每次分析至少准备一份适合成图的数据，优先回答“这段时差里世界上发生了什么，钱主要往哪边走了”；如果内部成图链路成熟，可以继续导出图片。
- 重写产品主叙事：从“日报分层服务”切换成“隔夜情报总览 / 昨天世界钱往哪里”。
- 调整 API 和导出物，使其围绕单一情报产品组织，而不是围绕 tier 和权限分层组织。

## Capabilities

### New Capabilities
- `source-intel-modules`: 定义新闻与市场数据的来源模块、标准化字段、分层筛选、简短解释、来源状态和统一输出边界。
- `analysis-summary-comparison`: 定义分析总结对照模块，要求每条主结论都能回看对应输入、驱动、证据和不确定性说明。
- `yesterday-world-money-flow`: 定义“昨天世界钱往哪里”输出，包括成图所需数据、可选图片产物、必须呈现的全球主题组、方向、强弱和跨资产关联。

### Modified Capabilities
- `premium-analysis-alignment`: 现有按 free / premium 拆分日报、prompt、MMU 的要求需要改成单一分析产物。
- `protected-operations-api`: 去掉 premium 只读内容鉴权要求，只保留管理操作鉴权边界。
- `standalone-runtime-config`: 去掉对 `OVERNIGHT_PREMIUM_API_KEY` 的运行时依赖，把配置收敛到来源采集和管理操作所需的最小集合。
- `operator-bootstrap-and-health`: 启动文档、健康检查说明和产物说明需要切换到“来源模块 + 对照模块 + 昨天世界钱往哪里”的新结构。

## Impact

- Affected code: `app/services/` 下的采集、市场快照、日报分析、MMU/export、runtime config、API access 与图卡导出链路。
- Affected outputs: `daily_analysis`、prompt bundle、MMU handoff、成图数据载荷、可选导出图卡、可能的 CLI 导出命令。
- Breaking surface: 依赖 free/premium 字段、premium key、tier 路由或 premium 导出物的调用方都需要迁移到单一版本。
- Product impact: 高。项目会从“后台数据服务附带双层日报”重构成“来源采集 + 分析对照 + 昨天世界钱往哪里”的单一产品。
