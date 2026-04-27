## Why

当前仓库已经具备可本地启动的 FastAPI 后端和一组明确的前端消费接口，但用户只能通过后端内嵌的 `/ui` 静态页面查看有限结果，无法以现代独立前端工程的方式快速迭代页面、组件和交互。要让这个项目真正进入“前后端分离、可本地看到效果”的开发节奏，需要把前端从后端包内静态资源提升为单独工程，并明确它如何消费现有 API、如何在本地联调、以及哪些用户流应优先落地。

## What Changes

- 新增一个与当前 Python 后端并列的独立前端项目，用于承接 `JusticeThemis` 现有 API，而不是继续把产品界面耦合在 `app/ui` 静态资源目录里。
- 定义前端首批必须覆盖的用户流，包括总览 dashboard、新闻列表/详情、日分析查看，以及本地开发时可选的 admin/premium header 输入能力。
- 定义前端与后端的集成边界，要求优先复用现有 `/api/v1/*`、`/healthz`、`/readyz`、`/refresh` 等接口，而不是在本次 change 中重做后端数据契约。
- 定义本地开发和预览路径，使操作者可以同时启动后端与独立前端，在浏览器中直接验证页面效果和接口联调结果。
- 明确将现有 `app/ui` 降级为兼容性 operator surface，不再作为主要产品前端演进面。

## Capabilities

### New Capabilities
- `standalone-frontend-workspace`: 提供一个独立前端工程及其本地开发、构建、环境配置和后端联调约束。
- `frontend-reader-experience`: 定义前端必须提供的核心浏览体验，包括 dashboard、新闻浏览、分析查看和受保护操作的本地输入方式。

### Modified Capabilities
- `operator-bootstrap-and-health`: 扩展 bootstrap 文档与本地 smoke 路径，使其涵盖“后端 API + 独立前端”双进程联调与预览。

## Impact

- Affected systems: 前端项目目录与构建配置、后端 CORS/静态资源边界、README 与本地启动文档、以及与页面数据装配相关的 API 消费层。
- Likely implementation surface: 新增 Node-based frontend workspace，补充环境变量与 dev proxy 配置，必要时为 FastAPI 增加跨域/前端入口兼容设置，并更新本地开发说明与验证步骤。
- Product impact: high. 该 change 会把项目从“后端附带一个静态 operator 页”推进到“可独立开发和本地预览的前端产品骨架”。
