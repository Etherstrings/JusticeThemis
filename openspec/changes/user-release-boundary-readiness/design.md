## Context

`JusticeThemis` 当前已经有较强的工程可验证性：本地 deterministic 回归通过 `275` 个测试，README 定义了 `uv sync --dev`、`uv run pytest -q`、`uvicorn` 启动命令、容器启动路径，以及 `healthz` / `readyz` / `news` smoke。release-hardening 文档也已经说明 admin/premium 鉴权、项目内 env 解析边界和自托管验收标准。

但这些能力主要面向“懂部署、懂环境变量、能处理 optional provider 缺失”的技术操作者。项目当前仍使用共享 header key 作为 premium/admin 访问边界，Compose 也只是单服务自托管路径，内置 `/ui` 更偏 operator panel 而非面向泛用户的产品前台。这意味着项目虽然已经达到“可自托管试用”的工程门槛，但还没有正式定义自己是否已经适合交给更广义的用户。

这次变更需要解决的是产品边界定义问题：明确当前支持的用户层级，定义第一次上手的验收路径，并把“不支持什么”写成契约而不是隐含在技术细节里。

## Goals / Non-Goals

**Goals:**

- 把当前发布判断从模糊的“能用/不能用”转成明确的用户层级结论
- 定义项目当前支持的用户画像与不支持的用户画像
- 建立首次上手 readiness gate，确保新用户能知道如何启动、如何验收、缺少 provider 时会怎样降级
- 把 release verdict、阻断项和不支持场景纳入 bootstrap / smoke 文档和测试约束

**Non-Goals:**

- 在本次 change 中实现完整账户体系、租户隔离、Web 注册登录或面向公众的 SaaS 交付
- 在本次 change 中消除所有技术门槛，例如 secret 管理、反向代理、HTTPS、商业化部署流程
- 把当前 operator-oriented `/ui` 改造成面向普通终端用户的完整产品前台
- 改写现有 premium/admin shared-key 机制为更复杂的身份系统

## Decisions

### Decision: 使用分级 release verdict，而不是单一 yes/no 判断

本次设计将“用户可用性”拆成至少两个层级：

- `self-hosted technical user / internal operator`: 当前可支持的用户层级
- `general end user / low-touch external user`: 当前不应宣称已支持的用户层级

这样可以忠实反映现状，避免因为工程面通过测试和 smoke 就误判为已经可面向泛用户交付。

Alternatives considered:

- 只给一个“可以/不可以”结论：无法表达项目已经适合技术型用户试用但仍不适合泛用户交付的中间态。

### Decision: 首次上手 gate 以 fresh self-host flow 为中心

首次上手 readiness 不应依赖维护者的隐性知识，而应围绕一个 fresh checkout 的成功路径定义：

- 准备 `.env`
- 安装依赖
- 启动服务
- 执行 smoke
- 理解 premium/admin 访问边界
- 理解 optional provider 缺失时的降级行为

只有这条路径明确，项目才算对“新技术用户”具备真实可用性。

Alternatives considered:

- 只保留现有 README 片段：信息已存在但分散，难以形成明确 verdict。

### Decision: 把“为什么还不能给泛用户”显式写出来

当前阻止项目进入泛用户直接交付状态的因素必须成为第一类文档内容，而不是只在维护者脑中存在，例如：

- 鉴权仍是共享 header key，而非用户账户体系
- 部署方式仍偏自托管 operator workflow
- 降级模式解释主要面向技术语义
- 没有定义“非技术用户首次成功”的交互路径

这能防止外部对项目成熟度产生错误预期。

Alternatives considered:

- 只写支持什么，不写不支持什么：容易让项目被误用到超出边界的场景。

### Decision: 先用文档与测试收紧边界，再决定是否进入更重的产品化

这次 change 先定义“当前可交付给谁”，并通过文档和测试约束固化；不直接跳到更重的产品化建设。这样既能立刻提高对外判断的诚实度，也能为后续是否做泛用户能力建设提供清晰缺口清单。

Alternatives considered:

- 直接开始做用户体系或更复杂 UI：投入大，但在边界尚未冻结前容易方向漂移。

## Risks / Trade-offs

- [把支持边界写得过窄，可能让当前项目看起来更保守] → 用已验证证据支撑“技术型自托管用户可用”，避免过度否定已有能力。
- [把支持边界写得过宽，可能让用户误以为是通用产品] → 明确列出 unsupported audience 和 blocking gaps。
- [文档化 verdict 但没有测试约束，后续容易回退] → 把关键 release-boundary 结论纳入 bootstrap/readiness 测试。
- [先做边界定义会延后真正的泛用户功能建设] → 这是有意取舍，先让当前项目的对外承诺真实可信。

## Migration Plan

1. 盘点当前发布证据与阻断项，形成用户边界审计。
2. 在 README / technical docs 中加入支持用户层级、unsupported 场景和 first-run verdict。
3. 为 bootstrap / readiness 文档增加测试约束，确保这些结论不会悄悄漂移。
4. 以审计结果为基础，决定后续是否要单独启动“泛用户产品化” change。

## Open Questions

- 进入“泛用户可直接交付”状态的最低门槛应包含哪些额外能力：账户体系、托管部署、错误引导，还是更强的数据 SLA？
- 当前 `/ui` 是否应继续明确定位为 operator panel，而不是用户产品前台？
- 首次上手 gate 是否需要单独的 CLI / API 自检命令，而不仅是文档 smoke？
