## 1. Regression Coverage

- [x] 1.1 Add failing tests for fixed-report direction deduplication, including suppression of near-duplicate sibling directions and premium stock-call dedup after compression.
- [x] 1.2 Add failing tests for Chinese-first `headline_news` brief generation and bounded fallback behavior when no high-quality user brief can be synthesized.
- [x] 1.3 Add failing tests for degraded `mainline / regime` coverage messaging and confidence capping when market snapshots contain core-board gaps.

## 2. Mainline Coverage And Market Completeness Plumbing

- [x] 2.1 Extend `app/services/daily_analysis.py` so `_build_mainline_context()` returns an explicit coverage-state payload with confirmed/degraded/unavailable status and suppression reasons.
- [x] 2.2 Thread market completeness metadata from `market_snapshot.capture_summary` into the daily report generation path so providers can see core missing symbols and partial-board status without re-deriving it downstream.
- [x] 2.3 Persist the new coverage-state and market-context metadata inside cached report payloads without breaking existing `free / premium` report retrieval flows.

## 3. Deterministic Content-Quality Pass

- [x] 3.1 Refactor `app/services/daily_analysis_provider.py` to add a deterministic content-quality pass that compresses overlapping direction families before final report emission.
- [x] 3.2 Ensure premium `stock_calls` are derived from the surviving post-dedup direction calls rather than the raw pre-compression aggregate.
- [x] 3.3 Add user-facing Chinese brief synthesis for `headline_news`, keeping audit-rich `supporting_items` intact and preferring bounded evidence fallback over machine audit strings.
- [x] 3.4 Update summary, narratives, risk watchpoints, and confidence logic so degraded market completeness and absent confirmed mainlines are explained explicitly in the fixed report.

## 4. Export Surfaces And Verification

- [x] 4.1 Update Markdown/export surfaces such as `app/services/pipeline_markdown.py` to prefer the new user-facing brief fields and degraded-market wording.
- [x] 4.2 Run targeted regression tests for daily analysis, market snapshot, and pipeline artifact generation to verify the new report contracts.
- [x] 4.3 Regenerate one representative backend daily report artifact from existing live-run data and confirm the output is less repetitive, more readable, and transparent about market gaps.
