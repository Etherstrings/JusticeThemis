## Context

本地 `JusticeThemis` 目录已经演进成一个可独立运行、可测试、带 OpenSpec 约束的 standalone 项目；当前本地 deterministic 回归可稳定通过，说明它代表了“当前可用实现”。但远端 GitHub 仓库 `Etherstrings/JusticeThemis` 仍保留更早期的工作区形态，包含 `apps/`, `api/`, `src/`, `bot/`, `webui.py` 等多子系统，并持续承载 `main` 分支上的 workflow 与定时任务。

与此同时，本地目录不是 Git 工作树，既没有远端历史，也没有 `origin` 可以直接同步。因此本次问题不是“把本地分支 pull 到最新”，而是“如何把一个当前可用但脱离 Git 历史的 standalone 项目，安全地收敛回一个仍在运行自动化的远端仓库”。

这类收敛同时涉及仓库结构、运行入口、CI/workflow、文档、验证路径和回滚策略，任何一步做错都可能导致：

- 远端 `main` 的现有自动化中断
- 本地当前可用实现被旧结构覆盖
- 未来贡献者不清楚哪个仓库形态才是 canonical target

因此需要在编码前先冻结同步策略、工作区形态和验收门槛。

## Goals / Non-Goals

**Goals:**

- 明确远端 GitHub 仓库是 canonical history source，本地 standalone 项目是待导入的当前实现
- 定义受控的仓库收敛流程，而不是直接在当前目录做不可回放的手工覆盖
- 建立远端/本地结构映射，说明哪些路径保留、替换、迁移或下线
- 定义同步前审计项、阻断条件和同步后验收路径
- 确保完成同步后，仓库仍满足“可启动、可验证、可维护”的当前产品要求

**Non-Goals:**

- 在本次 change 中直接执行 `git clone`、force push、历史改写或远端分支切换
- 保证远端所有历史子系统都原样保留；是否保留必须经过显式映射决策
- 重新设计产品能力、数据模型或市场分析逻辑
- 把所有未来仓库治理问题一次性解决，例如完整 release 流程重构或多环境发布体系

## Decisions

### Decision: 以远端仓库作为历史锚点，以本地 standalone 项目作为内容收敛源

同步目标不是丢弃远端重建新仓库，也不是把本地目录简单初始化成一个新 Git 仓库后覆盖推送。设计上将：

- 视 `Etherstrings/JusticeThemis` 为 canonical history source
- 视当前本地目录为 canonical product content candidate
- 在保留远端历史与协作入口的前提下，把本地当前实现导入远端受控分支完成收敛

这样可以同时保住 GitHub 仓库历史、issue/workflow 入口与当前可用代码状态。

Alternatives considered:

- 本地优先后强推远端：实现快，但会丢失远端仓库连续历史与运行中自动化上下文，风险过高。
- 远端优先后手工把本地改动“补回去”：会把当前 standalone 项目退回旧结构语义，且改动范围不可控。
- 新建全新仓库替代远端：能规避历史冲突，但会造成迁移成本、链接失效和协作上下文断裂。

### Decision: 使用独立同步工作区和收敛分支，而不是直接改当前目录

由于当前本地目录不是 Git 工作树，且远端结构与本地严重分叉，同步必须在独立工作区执行：

- 获取远端仓库副本或 worktree
- 创建专用 convergence 分支
- 在该工作区内导入本地 standalone 内容
- 分阶段完成路径映射、兼容面清理和验证

这样同步过程具备可审查、可重放和可回滚特征。

Alternatives considered:

- 直接在当前目录 `git init` 后添加远端并合并：缺少结构隔离，且容易把本地运行产物与远端历史一并混入。
- 直接在远端默认分支上操作：一旦验证中途失败，会直接影响主线稳定性。

### Decision: 先做结构映射清单，再做文件导入

收敛前必须先形成明确的映射表，覆盖至少以下类别：

- 根入口文件和 CLI/服务入口
- 文档与 README/bootstrap 面
- CI/workflows 与 scheduled automation
- 目录级模块对应关系，如远端 `src/`, `apps/`, `api/` 与本地 `app/`, `scripts/`, `tests/`, `docs/`
- 需要保留的历史资产、需要迁移的能力和可下线的旧面

只有在映射表完成后，才能进入具体导入和删除动作。

Alternatives considered:

- 先复制文件再边看边修：短期快，但会把结构冲突推迟到最后，导致难以判断哪些删除是安全的。

### Decision: 同步 readiness 以“阻断式审计”管理高风险差异

本次设计将同步前审计定义为硬门槛，而不是可选检查。以下任一未决项目都应阻断同步实施：

- 远端仍在使用而本地缺失的关键运行入口
- 远端 workflow 对路径或命令有强依赖但尚未重写
- 本地 deterministic 验证无法在导入目标工作区复现
- 无法说明旧目录被替换后的迁移路径

这保证“能合并”不等于“允许合并”。

Alternatives considered:

- 先完成代码导入再补审计：会把高风险决定拖到最贵的阶段。
- 把审计仅作为文档建议：无法形成真正的变更门槛。

### Decision: 同步后的验收以 bootstrap、health、baseline regression 三层验证为准

同步完成后，项目是否“可用完整”需要以三层验收确认：

- bootstrap 层：README / env example / canonical upstream 说明完整
- runtime 层：服务能按当前支持路径启动并通过 health/readiness smoke
- regression 层：deterministic baseline（当前为 `uv run pytest -q`）在收敛后的 Git 工作区中可通过

只有三层都满足，才允许将收敛分支作为进入远端主线的候选。

Alternatives considered:

- 只看测试通过：无法覆盖启动文档、环境约束和远端协作可维护性。
- 只看服务可启动：不能说明代码面没有回归。

## Risks / Trade-offs

- [远端仍有正在使用的旧子系统，但在收敛时被误判为可删除] → 先做路径映射与 workflow 依赖审计，把删除动作延后到明确替代关系之后。
- [本地 standalone 结构与远端目录体系差异过大，导致导入成本高] → 采用兼容期策略，允许短期保留少量桥接文件或目录说明，而不是一次性追求理想结构。
- [同步工作在单一工作区中夹带本地运行产物] → 只在独立 Git 工作区导入内容，并复用已建立的 ignore 规则与 deterministic baseline。
- [远端自动化使用的命令与本地当前 README 不一致] → 把 workflow 和 bootstrap 一起纳入收敛范围，同步后以单一 canonical verification path 收口。
- [把远端当历史锚点会提高首次收敛成本] → 成本高于新建仓库，但能保留协作与操作连续性，整体更稳妥。

## Migration Plan

1. 记录远端 `main` 当前基线，包括默认分支、最近提交、关键 workflow、根目录结构和现有运行入口。
2. 为远端仓库建立独立同步工作区与 convergence 分支，确保不会直接污染当前本地目录或远端主线。
3. 生成远端/本地结构映射与风险清单，明确保留、替换、迁移、下线路径。
4. 在同步工作区中导入本地当前 standalone 项目，并补齐必要的桥接文件、文档和 workflow 调整。
5. 执行 bootstrap、health/readiness 和 deterministic regression 验证，记录结果。
6. 通过评审后再考虑将 convergence 分支合入远端主线；如验证失败，则丢弃同步分支并保留远端 `main` 不变。

## Open Questions

- 远端仓库中的哪些旧目录仍具有必须保留的运行价值，哪些只是历史残留？
- 是否需要为 scheduled workflows 提供兼容层，以避免在仓库结构收敛过程中中断定时任务？
- 收敛后的目标形态是否完全以当前本地 standalone 目录为主，还是保留远端部分 monorepo 包装层？
- 首次同步是否需要额外生成一份 `CONTRIBUTING` 或仓库迁移说明，帮助未来维护者理解结构变更？
