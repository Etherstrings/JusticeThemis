# JusticeThemis

[English](README.md)

这是根级中文 bootstrap companion 文档。默认入口仍然是 [README.md](README.md)。

JusticeThemis 是一个独立运行的隔夜国际新闻采集、美国收盘快照、固定中国早晨分析缓存，以及下游 LLM/MMU 导出服务。

它的定位不是一个单纯的下游交接工具，而是面向中国早晨工作流的结果优先型隔夜市场解读引擎。

<!-- readme-parity:what-it-does -->
## 功能概览

- 将精选的隔夜新闻源采集到 SQLite
- 为分析日期构建一份美股收盘市场快照
- 生成固定结构的 `free` 和 `premium` 日报
- 导出供下游模型使用的 prompt bundle 和 MMU handoff payload
- 提供只读 API，以及受保护的变更和 readiness 路由

<!-- readme-parity:runtime-contract -->
## 运行时契约

配置优先级如下：

1. 进程环境变量
2. CLI 显式传入的 `--env-file` 路径
3. 项目本地 `.env.local`
4. 项目本地 `.env`

应用默认不再读取其它仓库里的 env 文件。

<!-- readme-parity:legacy-compatibility-mapping -->
## 兼容映射

- `JusticeThemis`: 文档、API 元数据、健康检查面和新生成 operator 产物的规范产品身份
- `overnight-news-handoff`: 历史项目标识，仍可能出现在旧文档或兼容表面中
- `OVERNIGHT_*`: 当前软改名阶段仍受支持的运行时环境变量契约
- `overnight-news-pipeline` / `overnight-news-launchd-template`: 仍保留兼容性的历史 CLI 别名

<!-- readme-parity:environment-variables -->
## 环境变量

参见 [.env.example](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/.env.example)。

重要变量：

- `OVERNIGHT_PREMIUM_API_KEY`: premium 只读路由必需
- `OVERNIGHT_ADMIN_API_KEY`: `refresh` / `generate` / `readyz` 路由默认必需，除非启用 unsafe 模式
- `OVERNIGHT_ALLOW_UNSAFE_ADMIN`: 仅本地开发可用的逃生阀；生产环境不要启用
- `IFIND_REFRESH_TOKEN`: 强烈建议配置，用于保证完整的美股市场快照覆盖；缺失时在 Yahoo Finance 限流下可能退化为仅有 Treasury 的部分市场快照
- `ALPHA_VANTAGE_API_KEY`: 可选的 premium ticker enrichment provider，用于 regime/mainline 关联的美股股票和 ETF
- `OVERNIGHT_NEWS_DB_PATH`: 可选的 SQLite 路径覆盖

当前阶段仍继续使用 `OVERNIGHT_*` 运行时前缀以维持兼容性。暂时不要求迁移到 `JUSTICE_THEMIS_*`。

<!-- readme-parity:current-output-layers -->
## 当前输出层

- `market_snapshot` 仍保留组装后的 board contract，并新增 `capture_summary.provider_hits`、分层 missing-symbol 诊断、freshness 计数、`market_regimes` 和被抑制的 regime 评估
- `daily_analysis` 保持 free/premium 的顶层结构，同时新增 `market_regimes`、`secondary_event_groups`、`ticker_enrichments` 和 `enrichment_summary`
- `MMU handoff` 现在携带确认后的 mainlines，以及附加的 regime/secondary context 与 premium ticker enrichments，而不破坏当前 prompt payload
- `/api/v1/dashboard` 将 confirmed mainlines 与 `market_regimes`、`secondary_event_groups` 分开展示

<!-- readme-parity:local-startup -->
## 本地启动

安装依赖：

```bash
uv sync --dev
```

规范本地验证命令：

```bash
uv run pytest -q
```

启动 API 服务：

```bash
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

执行一次固定管线：

```bash
uv run justice-themis-pipeline --analysis-date 2026-04-10
```

历史兼容别名依然可用：

```bash
uv run overnight-news-pipeline --analysis-date 2026-04-10
```

<!-- readme-parity:canonical-upstream-and-sync -->
## Canonical Upstream 与同步

版本控制历史的 canonical upstream 是 GitHub 仓库 `Etherstrings/JusticeThemis` 的 `main` 分支。

当前本地目录是现阶段独立实现的 source 目录，但它本身不是 Git worktree。因此仓库收敛必须在从 canonical upstream 克隆出的独立的 Git-backed convergence workspace 中完成，不能在这个目录里直接 `git init` 或执行临时 merge。

当前同步前置条件见 [docs/technical/2026-04-14-remote-repository-convergence.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-14-remote-repository-convergence.md)。在替换远端路径、调整 workflow 或提出同步分支供评审前，应先使用该审计文档。

README 文档包发布到 GitHub 时，`README.md` 与 `README.zh.md` 必须作为同一个 publication unit 一起进入 isolated Git-backed convergence workspace，而不是只同步其中一份。

post-sync verification contract 如下：

- 用 `uv sync --dev` 初始化依赖
- 用 `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 启动服务
- 验证 `GET /healthz`、带鉴权的 `GET /readyz`，以及 `GET /api/v1/news?limit=3`
- 运行规范 deterministic regression 命令 `uv run pytest -q`

当前 merge-ready 分支计划与评审备注见 [docs/technical/2026-04-14-convergence-review-summary.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-14-convergence-review-summary.md)。

<!-- readme-parity:repository-hygiene -->
## 仓库卫生

这个仓库现在将 source-owned 内容与本地生成产物视为两类不同文件。

<!-- readme-parity:source-owned-paths -->
### Source-owned 路径

- `app/`
- `tests/`
- `docs/`
- `openspec/`
- `.github/`
- 根级配置文件，例如 `pyproject.toml`、`Dockerfile`、`compose.yml`、`.env.example`、`README.md` 和 `README.zh.md`

<!-- readme-parity:generated-local-artifacts -->
### 本地生成产物

- `.venv/`、`.pytest_cache/` 和 `__pycache__/`
- `*.egg-info/`
- `data/` 运行时数据库
- `output/` 导出的管线结果
- 本地日志、coverage 输出以及类似机器生成文件

这些生成文件属于可重现的本地产物，不属于预期的 source-owned 工作集，因此默认被 `.gitignore` 和 `.dockerignore` 排除。

<!-- readme-parity:verification-baseline -->
### 验证基线

- 用 `uv sync --dev` 初始化依赖
- 用 `uv run pytest -q` 运行规范 deterministic regression 命令
- 仓库 CI 基线运行相同的 deterministic 测试命令，不依赖 live provider 凭据或 premium/admin secrets

内置 `/ui` operator 面板现在只会把 admin key 存在浏览器 local storage 中，并在 `/refresh` 请求时携带。若只需要只读视图，请保持该字段为空。

<!-- readme-parity:auth-surfaces -->
## 鉴权面

公开只读路由：

- `GET /healthz`
- `GET /items`
- `GET /handoff`
- `GET /api/v1/dashboard`
- `GET /api/v1/news`
- `GET /api/v1/news/{item_id}`
- `GET /api/v1/sources`
- `GET /api/v1/pipeline/blueprint`
- `GET /api/v1/market/us/daily`
- `GET /api/v1/analysis/daily?tier=free`
- `GET /api/v1/analysis/daily/versions?tier=free`
- `GET /api/v1/analysis/daily/prompt?tier=free`
- `GET /api/v1/mmu/handoff?tier=free`

Premium 只读路由需要 `X-Premium-Access-Key`：

- `GET /api/v1/analysis/daily?tier=premium`
- `GET /api/v1/analysis/daily/versions?tier=premium`
- `GET /api/v1/analysis/daily/prompt?tier=premium`
- `GET /api/v1/mmu/handoff?tier=premium`

Admin 路由需要 `X-Admin-Access-Key`，除非 `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`：

- `POST /refresh`
- `POST /api/v1/market/us/refresh`
- `POST /api/v1/analysis/daily/generate`
- `GET /readyz`

<!-- readme-parity:smoke-check -->
## Smoke Check

启动 API 后，运行：

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s -H "X-Admin-Access-Key: $OVERNIGHT_ADMIN_API_KEY" http://127.0.0.1:8000/readyz
curl -s http://127.0.0.1:8000/api/v1/news?limit=3
```

预期结果：

- `healthz` 返回 `{"status":"ok","service":"JusticeThemis"}`
- `readyz` 返回已脱敏的运行状态、source-registry 计数，以及 search、market snapshot 和 ticker enrichment 的 provider availability
- `/api/v1/news` 即使数据为空也返回 JSON

完整 CLI smoke 可运行：

```bash
uv run python -m app.pipeline --analysis-date 2026-04-11 --output-path /tmp/justice-themis-summary.json
```

如果没有配置 `IFIND_REFRESH_TOKEN`，管线仍然可以完成，但由于 live run 中 Yahoo Finance chart 请求可能被限流，`market_snapshot.capture_status` 可能保持为 `partial`。

<!-- readme-parity:container-startup -->
## 容器启动

使用 Compose 构建并启动：

```bash
docker compose up --build
```

API 会监听在 `http://127.0.0.1:8000`。

Docker build context 受 `.dockerignore` 过滤，因此本地缓存、运行时数据库和导出结果不会进入镜像构建路径。

<!-- readme-parity:rollback-notes -->
## 回滚说明

- 如果 release hardening 破坏了现有本地工作流，首先检查实例是否此前依赖外部仓库 env 文件。
- 回滚应通过重新部署上一版 image/build 并恢复旧 env 契约来完成。
- 不要为了图快在生产环境移除 admin gate；请使用 `OVERNIGHT_ADMIN_API_KEY`。

<!-- readme-parity:disabled-source-invariants -->
## Disabled-Source 不变量

以下 source id 在本项目中仍故意保持禁用，release 工作期间不应重新启用：

- `state_spokesperson_releases`
- `dod_news_releases`

<!-- readme-parity:self-hosted-acceptance-criteria -->
## 自托管验收标准

- API 可以仅依赖本仓库和项目本地 env 文件启动
- `healthz` 与带鉴权的 `readyz` 都成功
- 公开只读路由无需 premium/admin header 即可使用
- premium 路由在未鉴权时拒绝请求，提供 premium key 后成功
- admin 变更路由在未鉴权时拒绝请求，提供 admin key 后成功
- 至少有一次端到端管线运行成功完成
