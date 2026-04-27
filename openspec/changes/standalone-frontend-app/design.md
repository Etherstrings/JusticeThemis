## Context

`JusticeThemis` 当前后端已经提供较完整的读写接口与固定数据契约，包括 `/api/v1/dashboard`、`/api/v1/news`、`/api/v1/news/{id}`、`/api/v1/sources`、`/api/v1/market/us/daily`、`/api/v1/analysis/daily`、`/readyz`、`/refresh` 等。与此同时，仓库内置的 `app/ui` 仍是随 FastAPI 一起分发的静态 operator panel，只覆盖 `/items` 与 `/handoff` 等较早期接口，缺少独立构建、组件复用、路由组织和本地前端热更新体验。

这次 change 的目标不是重做后端，也不是直接产品化到“泛用户 SaaS”，而是建立一个可持续迭代的独立前端工程，使本地开发者能够同时启动后端与前端，直接在浏览器中查看 dashboard、新闻、日分析等体验，并在保留现有 admin/premium 访问边界的前提下完成联调。

## Goals / Non-Goals

**Goals:**

- 在仓库内建立一个与 Python 后端分离的独立前端 workspace
- 让前端优先复用现有后端 API，而不是引入新的中间层或重构后端契约
- 提供可本地运行的双进程开发路径，让用户可以看到真实页面效果
- 定义首批前端信息架构与核心页面，覆盖 dashboard、新闻浏览、市场/分析查看和本地受保护操作
- 明确 `app/ui` 与新前端之间的角色边界，避免两个主前端长期并行演进

**Non-Goals:**

- 在本次 change 中引入账户体系、登录态、用户数据库或 RBAC
- 在本次 change 中重写现有 `/api/v1/*` 接口或改变 premium/admin shared-key 机制
- 在本次 change 中完成完整设计系统、商业化部署方案或 SSR/SEO 能力
- 在本次 change 中删除 `app/ui`，只要求它退居兼容/过渡位置

## Decisions

### Decision: 在仓库根目录新增 `frontend/` workspace，并采用 Vite + React + TypeScript

独立前端的首要目标是提升本地开发迭代速度和工程可维护性，因此应选择轻量、成熟、对本地联调友好的方案。`Vite + React + TypeScript` 能以较低心智负担提供模块化组件、路由能力、类型约束、快速热更新和常见生态支持，适合作为当前项目的独立前端骨架。

Alternatives considered:

- 继续扩展 `app/ui` 原生静态页面：实现门槛低，但会继续把产品界面耦合进 Python 包数据目录，难以形成独立前端工程节奏。
- 直接使用 Next.js 等更重框架：功能更强，但当前目标是本地联调与独立前端起步，不需要先引入 SSR、服务端 actions 或更重部署模型。

### Decision: 前端通过薄 API client 直接消费现有后端接口，并使用可配置 base URL + 本地 dev proxy

这次 change 不应发明新的 BFF 层。前端应围绕现有 FastAPI 接口建立一个薄的 API client，集中处理 base URL、headers、错误归一化与受保护请求。默认本地开发模式下，前端通过配置或 dev proxy 指向 `http://127.0.0.1:8000`，从而避免手工改源码；在需要远程联调时，可通过显式环境变量切换 API origin。

Alternatives considered:

- 让前端直接在组件中散落 `fetch` 调用：改动快，但会让鉴权头、错误处理和数据映射分散，后续难维护。
- 增加新的前端专属后端聚合层：会扩大后端改动范围，与“优先复用现有 API”目标相冲突。

### Decision: 本地受保护能力延续 header-key 模式，并把密钥输入限制在浏览器本地存储与请求层

后端当前的 admin/premium 边界已由 `X-Admin-Access-Key` 与 `X-Premium-Access-Key` 定义，本次 change 不改变该契约。独立前端需要提供本地开发友好的输入方式，例如顶部控制区或设置抽屉，用于临时输入 key；这些值只保存在浏览器本地存储，并仅在请求受保护接口时附加相应 header。这样既能支持本地调试，也不会把敏感值固化进构建产物或仓库配置。

Alternatives considered:

- 把 key 写入前端构建时环境变量：不适合本地多人开发，也会增加误提交或泄露风险。
- 在这次 change 中同时改造成真正登录系统：超出当前目标，且会显著放大后端范围。

### Decision: 首批前端信息架构围绕三个主视图展开，而不是复制现有 `/ui` 单页面板

独立前端的首批页面应以真实消费体验为中心，而不是把当前 operator panel 原样搬过去。推荐最小但完整的信息架构为：

- `Dashboard`: 聚合 `/api/v1/dashboard`，展示 hero 指标、lead/watch/background、source health、market board、mainlines
- `News`: 使用 `/api/v1/news`、`/api/v1/news/{id}`、`/api/v1/sources` 提供列表、筛选、详情
- `Analysis`: 使用 `/api/v1/market/us/daily`、`/api/v1/analysis/daily`、`/api/v1/analysis/daily/versions` 展示日分析与市场快照

这样能直接覆盖“本地看到效果”的核心价值，同时保留后续继续扩展 handoff、pipeline blueprint 等更操作型页面的空间。

Alternatives considered:

- 只做一个长页面把所有数据堆在一起：实现更快，但信息架构会迅速失控，不利于后续演进。
- 先完全复刻 `app/ui`：能较快迁移，但无法体现现有 `/api/v1/*` 的 richer contract，也无法解决产品前端与 operator panel 的定位问题。

### Decision: 后端只做最小必要适配，重点是跨域与文档，而不是新增大批 API

独立前端上线本地预览后，最可能阻塞的是跨域与启动文档，而不是缺少接口。因此后端变更应保持克制，聚焦：

- 为文档化的本地前端 origin 增加可控的 CORS 支持
- 保持现有 API shape 稳定
- 必要时仅增加极少量前端消费友好的兼容字段，而不是重开一批新接口

Alternatives considered:

- 顺手重做一轮后端 API 契约：成本高，且会把这次 change 从“前端独立化”拖成“全栈协议重构”。

### Decision: `app/ui` 保留为兼容 operator surface，新前端成为主要产品界面演进面

立即删除 `app/ui` 会放大回滚风险，也可能影响现有操作流程。更稳妥的路径是保留其兼容地位，但在文档和实现中把新 `frontend/` 明确为主要前端工程；后续若独立前端稳定，再单独评估是否缩减或移除旧 surface。

Alternatives considered:

- 直接删除 `app/ui`：边界更干净，但风险更高，且不利于渐进迁移。

## Risks / Trade-offs

- [引入 Node 前端工具链会增加仓库复杂度] → 把职责限制在 `frontend/`，并用简洁命令与 README 说明降低摩擦。
- [跨域与本地代理处理不当会导致“页面能开但接口全失败”] → 明确固定本地 origin、dev proxy 与后端 CORS 白名单，纳入 smoke 路径。
- [现有 API 更偏后端导向，前端展示时可能暴露字段不一致或空值问题] → 在前端 API client 层统一做解析与空态处理，必要时只补充极少量兼容字段。
- [保留 `app/ui` 会造成双前端并存一段时间] → 文档中明确角色分工，新需求默认进入 `frontend/`，避免继续扩展旧 UI。
- [header-key 模式在浏览器端仍然偏 operator-oriented] → 明确这只是本地开发与技术用户预览方案，不把它表述为最终终端用户鉴权体验。

## Migration Plan

1. 新增 `frontend/` workspace，建立 package manifest、dev/build scripts、基础路由和 API client。
2. 为后端补充支持独立前端本地联调所需的配置，例如受控 CORS origin 与相关文档。
3. 实现首批页面：dashboard、news、analysis，以及本地 admin/premium key 输入能力。
4. 更新 README 与本地 smoke 路径，明确双进程启动、验证步骤和旧 `app/ui` 的兼容定位。
5. 验证前端 build、后端启动、核心页面加载和受保护调用行为；若独立前端失败，回滚可先停用 `frontend/` 相关入口，不影响现有后端与 `app/ui`。

## Open Questions

- 独立前端的生产部署模式是否也要在这次 change 中定下来，还是只先覆盖本地开发与静态构建产物？
- 分析页首版是否需要直接支持 premium/free 切换与版本切换，还是先以 free + latest 为默认路径？
- `handoff`、`pipeline blueprint` 这类更 operator-oriented 页面是否应该进入首批前端范围，还是等核心阅读体验稳定后再补？
