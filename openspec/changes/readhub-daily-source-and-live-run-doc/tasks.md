## 1. Readhub Source Model And Storage

- [x] 1.1 Add failing tests for Readhub canonical-endpoint handling, legacy-alias fallback, lower-priority registry placement, and digest-topic capture.
- [x] 1.2 Extend source item types/schema/repository payloads so source-specific structured context can persist Readhub rank, tags, tracking history, similar events, and aggregated external links.
- [x] 1.3 Implement the dedicated Readhub daily/topic collector path and register Readhub as a non-mission-critical aggregated editorial source.

## 2. Validation And Reporting

- [x] 2.1 Add failing tests for Readhub validation/report output, including daily item counts, sample topic URLs, and enrichment-population visibility.
- [x] 2.2 Implement Readhub validation/reporting coverage so maintainers can prove `readhub.cn/daily` capture works even when `1.readhub.cn/daily` fails.
- [x] 2.3 Add failing tests for a backend-only live-run evidence workflow that emits a Chinese-first Markdown document and remains readable under partial backend failure.

## 3. Backend Evidence Pack

- [x] 3.1 Implement the isolated backend live-run workflow and Markdown evidence writer, reusing existing pipeline summary/report artifacts where practical.
- [x] 3.2 Ensure the generated evidence document includes exact dates, artifact paths, source coverage, Readhub sample hits, daily-analysis status, and explicit failure/warning sections.
- [x] 3.3 Execute one real analysis-date backend run that includes Readhub capture and persist the generated evidence document plus referenced raw artifacts.

## 4. Review And Reproduction Notes

- [x] 4.1 Review the live-run evidence output for consistency with the captured Readhub data, current product identity, and backend-only scope.
- [x] 4.2 Add or update a short technical note describing how to reproduce the Readhub live run and where to inspect the generated evidence document.
