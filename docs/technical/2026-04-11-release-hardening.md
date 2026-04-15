# 2026-04-11 Release Hardening

> **项目：** `JusticeThemis`  
> **目的：** 把当前“能跑的后端 MVP”收敛成“可独立部署、边界清晰、可自托管上线”的发布基线。

## 当前结论更新

这份文档记录的是 2026-04-11 的 release-hardening 基线，不再单独承担最新 release verdict。

截至 2026-04-16，当前面向用户的正式结论、支持边界、first-run gate、降级说明和阻断项统一记录在 [docs/technical/2026-04-16-user-release-boundary-and-first-run-verdict.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/2026-04-16-user-release-boundary-and-first-run-verdict.md)。

## 已完成

1. 运行时配置已从外部仓库默认依赖中脱钩
2. 现在默认只认本项目 `.env` / `.env.local` 与进程环境变量
3. 新增 admin / premium 两层访问边界
4. `POST /refresh`
5. `POST /api/v1/market/us/refresh`
6. `POST /api/v1/analysis/daily/generate`
7. `GET /readyz`
8. 以上路由现在都不再是默认裸露
9. 新增 `GET /healthz` 与受保护的 `GET /readyz`
10. premium MMU handoff 已支持 `tier=premium` 并使用 premium report
11. 根目录已补 `README.md`、`.env.example`、`Dockerfile`、`compose.yml`
12. 内置 `/ui` 操作页已补 admin key 输入与本地浏览器存储，避免刷新按钮在硬化后恒定 `403`
13. Treasury 官方 10Y 收益率适配已改为显式按年份取数，避免官网默认回到 `1990/1991` 示例页污染 `analysis_date`
14. CLI 明确传入的 `analysis_date` 现在不会再被 market snapshot 返回值反向覆盖

## 当前运行时边界

### 公共读取

1. `GET /healthz`
2. `GET /items`
3. `GET /handoff`
4. `GET /api/v1/dashboard`
5. `GET /api/v1/news`
6. `GET /api/v1/news/{item_id}`
7. `GET /api/v1/sources`
8. `GET /api/v1/pipeline/blueprint`
9. `GET /api/v1/market/us/daily`
10. `GET /api/v1/analysis/daily?tier=free`
11. `GET /api/v1/analysis/daily/prompt?tier=free`
12. `GET /api/v1/mmu/handoff?tier=free`

### Premium 读取

需要 `X-Premium-Access-Key`：

1. `GET /api/v1/analysis/daily?tier=premium`
2. `GET /api/v1/analysis/daily/versions?tier=premium`
3. `GET /api/v1/analysis/daily/prompt?tier=premium`
4. `GET /api/v1/mmu/handoff?tier=premium`

### Admin 操作

需要 `X-Admin-Access-Key`，除非明确开启 `OVERNIGHT_ALLOW_UNSAFE_ADMIN=true`：

1. `POST /refresh`
2. `POST /api/v1/market/us/refresh`
3. `POST /api/v1/analysis/daily/generate`
4. `GET /readyz`

## 回滚说明

1. 如果旧部署依赖了外部项目 env 文件，本次升级后必须迁移到本项目 `.env` / `.env.local`
2. 若升级失败，可回滚到旧 build，并恢复旧环境变量装载方式
3. 不建议通过去掉 admin gate 的方式“热修复”，应恢复 `OVERNIGHT_ADMIN_API_KEY`

## 禁用信源不变量

以下来源仍然必须保持禁用：

1. `state_spokesperson_releases`
2. `dod_news_releases`

## 自托管上线验收

1. 仅使用本项目目录即可启动 API
2. `healthz` 成功
3. 带 admin key 的 `readyz` 成功
4. free 路由无 premium/admin header 仍可读
5. premium 路由无 key 会拒绝，有 key 可读
6. admin 路由无 key 会拒绝，有 key 可执行
7. 固定 pipeline 至少成功跑通一轮

## 验证记录

### 自动化测试

执行命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

结果：

1. `236 passed`
2. 当前 release-hardening 相关回归全部通过

### CLI Pipeline Smoke

执行命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run justice-themis-pipeline --analysis-date 2026-04-11 --db-path /tmp/justice-themis-release-20260411.db --output-path /tmp/justice-themis-release-20260411-summary.json --summary-markdown-path /tmp/justice-themis-release-20260411-summary.md
```

结果摘要：

1. `analysis_date=2026-04-11`
2. `collected_sources=26`
3. `collected_items=151`
4. `recent_total=120`
5. free/premium 固定日报均成功生成
6. market snapshot 日期锚点已恢复正常：`market_date=2026-04-10`，`analysis_date=2026-04-11`

### API Deployment Smoke

启动命令：

```bash
env UV_CACHE_DIR=/tmp/uv-cache OVERNIGHT_NEWS_DB_PATH=/tmp/justice-themis-release-20260411.db OVERNIGHT_ADMIN_API_KEY=release-hardening-admin uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

验证命令：

```bash
curl -s http://127.0.0.1:8011/healthz
curl -s -H "X-Admin-Access-Key: release-hardening-admin" http://127.0.0.1:8011/readyz
curl -s "http://127.0.0.1:8011/api/v1/news?limit=3"
```

结果：

1. `healthz` 返回 `{"status":"ok","service":"JusticeThemis"}`
2. `readyz` 返回数据库状态、auth 状态、feature 可用性、source registry 计数
3. `GET /api/v1/news?limit=3` 成功返回真实新闻数据

## 当前非阻塞限制

1. 当前本项目运行环境中没有配置 `IFIND_REFRESH_TOKEN`
2. 默认 live smoke 下 Yahoo Finance chart 请求会遇到 `429 Too Many Requests`
3. 因此本次 smoke 中 market snapshot 仍是 `partial`，仅成功落库 Treasury 10Y 数据
4. 这不再是日期锚点 bug；若要达到完整 cross-asset market snapshot，自托管部署时应配置 `IFIND_REFRESH_TOKEN`
