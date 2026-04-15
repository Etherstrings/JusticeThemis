## Context

当前仓库根目录只有英文 `README.md`，而这份 README 已经承担了 operator/bootstrap package 的职责：它覆盖 `JusticeThemis` 的产品身份、环境变量契约、本地启动命令、smoke check、canonical upstream、repository hygiene、鉴权边界和自托管验收标准。用户现在要求“参照这个的格式，一样的，要有中文文档，然后本地和 GH 都有”，这意味着目标不是新增一份自由发挥的中文说明，而是把现有根 README 的结构、关键命令和发布面扩展成一个双语文档包。

另一个约束是，这个本地目录不是 Git 工作树。现有 README 和 `docs/technical/2026-04-14-remote-repository-convergence.md` 已经明确说明：GitHub 仓库更新必须通过独立的 Git-backed convergence workspace 完成，而不是在当前目录直接 push。因此设计必须同时解决两件事：

- 在本地 source 目录中建立稳定的中英 README companion surface
- 把这对 README 绑定到现有 GitHub 收敛流程，避免再次出现“本地文档更新了，GH 没同步”的漂移

## Goals / Non-Goals

**Goals:**

- 让根 README 形成一个中英文成对的 bootstrap surface，并保持与现有英文 README 同级、同结构、同关键命令
- 明确英文 README 是默认入口，中文 README 是根级 companion 文档，两者互相链接
- 为 README 双语维护建立可验证的结构对齐机制，而不是只依赖人工记忆
- 把 README 的 GitHub 发布路径写入文档契约，延续现有 isolated convergence workspace 流程

**Non-Goals:**

- 本次 change 不要求把 `docs/technical/`、`docs/api/` 或其它深层文档全部翻译成中文
- 本次 change 不重构 runtime、API、数据库或 market-analysis 逻辑
- 本次 change 不改变 GitHub 收敛的总体策略，不把当前目录改造成 Git 工作树
- 本次 change 不要求建立完整 i18n 文档站点或 docs 生成系统

## Decisions

### Decision: 以现有英文 `README.md` 作为结构基线，新增根级 `README.zh.md` 作为镜像 companion

用户明确要求“参照这个的格式一样的”，因此中文文档不能只是简版介绍或额外 runbook，而必须沿用当前英文 README 的章节骨架。设计上将：

- 保留 `README.md` 作为默认根入口
- 新增根级 `README.zh.md`
- 要求中文文档覆盖与英文 README 相同的关键主题：产品身份、运行契约、环境变量、启动方式、canonical upstream 与 sync、repository hygiene、鉴权面、smoke check 和 acceptance criteria

Alternatives considered:

- 只在 `docs/` 下增加中文说明：可行，但不满足“根 README 同格式”的要求，而且 discoverability 较差。
- 把中文内容直接混写进同一份 README：会让根入口过长，也难以维持清晰的语言切换体验。

### Decision: 用显式的 parity marker / section identity 保证中英文 README 结构可验证

“格式一样”如果只靠人工约束，后续很容易演变成英文 README 更新了章节，中文 README 没跟上。设计上将为两个 README 引入轻量的结构标识，例如固定顺序的 parity markers 或等价 section identity，使验证逻辑可以确认：

- 两个 README 覆盖了相同的根级章节集合
- 章节顺序一致
- 关键命令与关键发布说明仍同时存在于两个文档中

这比要求两份文档的标题文本完全相同更合理，因为中文标题需要本地化。

Alternatives considered:

- 只做人审：成本低，但无法稳定防止漂移。
- 用单独的 heading-mapping 文件维护中英对照：可行，但会增加第三份元数据，维护成本更高。

### Decision: 在 README 顶部建立双向语言导航，并在英文入口上声明默认语义

根级双语文档需要非常低成本地被发现。设计上要求：

- `README.md` 顶部显式链接 `README.zh.md`
- `README.zh.md` 顶部显式链接 `README.md`
- 英文文档说明自己是默认根入口，中文文档说明自己是 companion localized entrypoint

这样既保留 GitHub 默认展示英文根 README 的惯例，也满足中文读者在本地和远端快速切换。

Alternatives considered:

- 只在文末放语言切换链接：发现成本高，不适合作为 bootstrap surface。
- 只在 README 中提一句“另见中文文档”：不够明确，也不利于验证。

### Decision: GitHub 发布约束直接复用现有 convergence workspace，而不是新增一套 README 特例流程

当前目录不是 Git 工作树，这一点已经在现有收敛文档中冻结。README 双语化不能引入一套与之冲突的“手动传到 GH”流程，因此设计上将：

- 在 README 文档包中复述 GitHub 发布必须走 isolated Git-backed convergence workspace
- 把 `README.md` 与 `README.zh.md` 视为一个 publication unit
- 要求进入 GitHub 的 README 变更同时携带两份文档

Alternatives considered:

- 仅要求本地有 `README.zh.md`，远端以后再说：会直接违背用户“本地和 GH 都有”的目标。
- 为 README 单独开一条绕过 convergence 的 push 路径：与当前仓库现实不符，风险也更高。

## Risks / Trade-offs

- [中文文档在后续迭代中滞后于英文文档] → 引入结构标识和 deterministic parity verification，把漂移从“人工发现”变成“验证失败”。
- [根 README 顶部导航和 parity 标识增加少量 Markdown 噪音] → 使用简短的导航块和最小化标识，避免影响可读性。
- [读者误以为当前本地目录可以直接同步 GitHub] → 在 README 双语包中重复说明 non-Git 现实与 convergence workspace 要求。
- [为了保证同结构而导致中文措辞不够自然] → 允许本地化措辞，但不允许关键章节、关键命令和关键约束缺失。

## Migration Plan

1. 在本地 source 目录中为现有 `README.md` 增加语言导航和结构标识。
2. 新增根级 `README.zh.md`，按相同章节骨架写出中文 companion 文档。
3. 增加 README parity 验证，至少覆盖语言互链、章节标识顺序和关键 bootstrap 命令/说明。
4. 更新相关技术文档或 README 段落，明确 GitHub README 发布仍走 isolated convergence workspace。
5. 在 Git-backed convergence workspace 中携带 `README.md` 与 `README.zh.md` 一起进入 review/merge 流程。

## Open Questions

- GitHub 远端默认展示仍以英文 `README.md` 为主，这个默认入口是否需要在中文 README 中进一步解释？
- 是否需要在后续 change 中把关键 `docs/technical/` 文档也扩展成双语，还是先把范围限制在根 README 文档包？
