## Why

当前 `JusticeThemis` 已经具备稳定工程基线：本地 deterministic 回归通过 `275` 个测试，README 与 release-hardening 文档也已定义自托管 smoke、admin/premium 边界和容器启动路径。但这些证据只能证明它“可由技术操作者部署和验证”，还不能自动推出它已经适合交付给广义用户，因为项目尚未显式声明支持的用户类型、首轮上手边界、降级模式解释和不支持场景。

这意味着“这个项目现在能不能给用户使用”不能继续停留在口头判断上。需要把发布边界冻结成可验证契约，明确哪些用户现在可支持，哪些用户仍不应作为承诺对象，以及达到更广泛用户可用之前还缺什么。

## What Changes

- 定义一套正式的用户发布边界，区分“技术型自托管/内部操作者可用”与“泛用户可直接交付”两种不同结论，并给出客观判定条件。
- 定义首轮上手 readiness gate：新用户第一次拿到仓库时，必须能理解所需环境、已支持路径、已知降级模式和成功验收方式。
- 把当前项目的 release verdict 显式写入 bootstrap 文档和相关 readiness 文档，而不是只留下分散的测试与 smoke 记录。
- 产出一份用户边界审计，明确当前阻止项目成为“通用用户可用产品”的缺口，例如共享 header key 鉴权、面向操作者的部署方式、以及对 optional provider 缺失时的降级体验仍偏技术化。

## Capabilities

### New Capabilities
- `user-release-boundary`: 定义当前项目支持的用户类型、明确不支持的用户类型，以及发布结论必须依据的客观边界。
- `first-run-readiness-gate`: 定义新用户首次接触项目时必须获得的启动路径、降级解释、验收步骤和失败反馈。

### Modified Capabilities
- `operator-bootstrap-and-health`: 扩展 bootstrap 与 smoke 语义，使其不仅说明如何运行项目，还必须说明当前支持的用户边界、已知不支持场景和 release verdict。

## Impact

- Affected systems: `README.md`, release-hardening / technical docs, readiness and operator guidance, first-run acceptance flow, and any tests that validate bootstrap or release-boundary claims.
- Likely implementation surface: bootstrap docs, technical audit docs, readiness guidance, smoke/acceptance tests, and possibly API/UI wording where user-facing expectations need to be clarified.
- Product impact: high. This change determines whether `JusticeThemis` can honestly be handed to a real user today, and if so, which user cohort that statement applies to.
