## ADDED Requirements

### Requirement: Canonical Readhub daily endpoint
The system SHALL treat `https://readhub.cn/daily` as the canonical Readhub daily digest endpoint and SHALL tolerate failures from the legacy alias `https://1.readhub.cn/daily` without aborting the whole source refresh.

#### Scenario: Canonical endpoint is available
- **WHEN** the Readhub daily source refresh runs and `https://readhub.cn/daily` responds successfully
- **THEN** the system fetches the daily digest from that canonical endpoint and records the daily issue metadata for downstream processing

#### Scenario: Legacy alias fails
- **WHEN** `https://1.readhub.cn/daily` fails TLS or network negotiation during a probe or compatibility check
- **THEN** the system records a non-blocking diagnostic and continues using `https://readhub.cn/daily`

### Requirement: Daily digest topic capture
The system SHALL capture one source item per Readhub daily topic using the canonical topic URL together with daily-rank metadata from the digest page.

#### Scenario: Daily page exposes embedded topic records
- **WHEN** the Readhub daily page exposes topic records in rendered HTML or embedded page data
- **THEN** the system stores each topic's title, summary, canonical topic URL, daily issue date, rank/order, and entity names as one captured source item

### Requirement: Topic enrichment context persistence
The system SHALL enrich captured Readhub topic items with structured topic-page context and preserve that context in source-specific stored metadata.

#### Scenario: Topic page expansion succeeds
- **WHEN** the system expands a captured Readhub topic page
- **THEN** it preserves tags, tracking history, aggregated external coverage links/origins, and similar-event comparison context in structured source metadata rather than flattening all of it into one summary string

### Requirement: Aggregated-source priority boundary
The system SHALL classify Readhub as a non-mission-critical aggregated editorial source that does not outrank official policy or official data sources in default refresh selection.

#### Scenario: Source selection orders default sources
- **WHEN** the default source registry is built and ordered for refresh
- **THEN** official policy/data sources remain ahead of Readhub and Readhub is treated as a lower-priority aggregated source

### Requirement: Readhub capture validation visibility
The system SHALL expose a validation or run-report surface that proves Readhub digest capture viability and topic enrichment population.

#### Scenario: Maintainer validates Readhub capture
- **WHEN** a maintainer runs the documented Readhub validation or backend evidence flow
- **THEN** the output reports the daily item count, sample topic URLs, and whether structured topic enrichment fields were populated
