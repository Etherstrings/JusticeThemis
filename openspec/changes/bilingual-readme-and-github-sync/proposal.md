## Why

当前仓库已经有一份结构完整的英文 `README.md`，覆盖产品身份、启动方式、验证路径、兼容映射和远端收敛说明；但还没有与之同结构的中文文档，因此中文读者无法用同样稳定的入口获取一致的 bootstrap 信息。同时，这个本地目录本身不是 Git 工作树，README 的任何补充如果没有显式纳入 GitHub 收敛路径，就容易出现“本地有、GH 没有”的文档漂移。

## What Changes

- 新增一份与英文根 README 保持同结构、同导航语义、同关键约束的中文文档，作为仓库级 operator/bootstrap companion surface。
- 定义中英文 README 的结构对齐规则，要求产品身份、运行契约、验证路径、兼容映射、canonical upstream 和 convergence 说明在两个文档中保持一致。
- 要求英文 README 与中文 README 互相链接，并明确哪个文档是默认入口、哪个文档是本地化 companion。
- 把 README 发布范围显式纳入本地目录与 GitHub 仓库的同步契约，说明 README 变更进入 GitHub 时必须沿用独立 Git-backed convergence workspace，而不是假设当前目录可以直接 push。
- 为 README 双语维护增加可验证约束，避免后续只更新英文或只更新中文而导致说明分叉。

## Capabilities

### New Capabilities
- `bilingual-readme-parity`: 定义英文 README 与中文 README 之间的结构对齐、导航互链、关键信息一致性和发布面要求。

### Modified Capabilities
- `operator-bootstrap-and-health`: 根级 bootstrap 文档要求扩展为包含中文 companion README，以及适用于 GitHub 收敛发布的 README 同步说明。

## Impact

- Affected files likely include `README.md`, new `README.zh.md`, selected technical docs under `docs/technical/`, and tests or verification utilities that guard documentation parity.
- Affected systems: local operator/bootstrap documentation surface, GitHub repository publication flow for `Etherstrings/JusticeThemis`, and the existing convergence workspace procedure used to move this non-Git local project into Git history.
- No runtime API, database schema, or market-analysis behavior changes are intended in this change; impact is limited to documentation contract and verification coverage.
