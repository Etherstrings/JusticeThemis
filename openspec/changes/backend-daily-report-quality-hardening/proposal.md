## Why

`2026-04-15` 的真实后端运行已经证明系统能稳定产出日报，但当前产物还没有达到“可以长期直接给用户看”的内容质量。主要问题不是缺内容，而是内容表达仍偏机器化：方向结论重复、`Key News` 摘要不够像人写的中文、`mainlines / market_regimes` 为空时缺少显式解释、以及 market core-board 缺口没有充分下传到日报置信度与风险提示。

## What Changes

- 为固定日报新增一层内容质量约束，要求用户可见文本优先输出中文可读摘要、去重后的方向结论、以及和结论绑定的核心证据与待确认项。
- 收紧日报的方向聚合逻辑，避免多个方向条目仅因为命名不同却复用同一批证据和同一事件簇，导致读者感受到“机器枚举”。
- 为 `headline_news` / `Key News` 增加用户可读的中文 brief 合成或选择规则，不再默认回退到原始字段拼接。
- 明确 `mainlines / market_regimes` 在日报里的表达合同：当存在足够市场与事件支撑时应进入报告主叙事；当由于市场不完整或证据不足而未产出时，日报必须解释抑制原因，而不是静默显示零值。
- 把 market snapshot 的 core-board 缺口传递到固定日报的 summary、confidence、narratives 和 risk watchpoints，避免在核心市场上下文不完整时仍给出过强、未标注限制的结论。

## Capabilities

### New Capabilities
- `daily-report-content-quality`: 约束固定日报的中文可读摘要、方向去重、核心新闻 brief 和用户可见证据组织方式。

### Modified Capabilities
- `regime-and-mainline-grounding`: 收紧主线与 regime 的下游表达要求，要求日报在未产出 confirmed mainline / regime 时显式给出抑制原因或降级上下文。
- `data-freshness-and-completeness`: 扩展 freshness/completeness 的下游影响，要求 core market gaps 能下传到日报置信度和风险表达，而不仅停留在健康诊断层。

## Impact

- Affected code will likely include `app/services/daily_analysis_provider.py`, `app/services/daily_analysis.py`, `app/services/mainline_engine.py`, `app/services/market_snapshot.py`, and `app/services/pipeline_markdown.py`.
- Affected tests will likely include `tests/test_daily_analysis.py`, `tests/test_pipeline_runner.py`, `tests/test_market_snapshot.py`, and new regression tests around direction deduplication and readable report briefs.
- Downstream report artifacts such as `daily-free.md`, `daily-premium.md`, and backend evidence exports will change in content quality and degraded-market phrasing, but this change does not introduce new frontend scope.
