## ADDED Requirements

### Requirement: Tier-aligned prompt bundle exports
The system SHALL generate prompt bundles from the cached report that matches the requested access tier.

#### Scenario: Free prompt bundle is requested
- **WHEN** a free-tier prompt bundle is generated or requested
- **THEN** the bundle is derived from the free cached report and excludes stock-specific recommendation content

#### Scenario: Premium prompt bundle is requested
- **WHEN** a premium-tier prompt bundle is generated or requested with valid premium authorization
- **THEN** the bundle is derived from the premium cached report and includes premium stock-call context, risk framing, and tier-correct instructions

### Requirement: Tier-aware MMU premium recommendation export
The system SHALL generate premium recommendation handoff context from premium analysis data rather than backfilling from free-only analysis data.

#### Scenario: Premium MMU handoff is requested with valid authorization
- **WHEN** a premium MMU handoff is requested with valid premium authorization
- **THEN** the premium recommendation stage uses premium report direction calls, premium candidate stock pool, and premium-tier risk instructions

#### Scenario: Premium MMU handoff is requested without premium authorization
- **WHEN** a premium MMU handoff is requested without valid premium authorization
- **THEN** the system rejects the request instead of returning premium recommendation context

#### Scenario: Only free analysis is available
- **WHEN** premium recommendation export is requested but no premium analysis report exists for the requested date
- **THEN** the system reports premium export as unavailable instead of synthesizing premium recommendation data from the free report

### Requirement: Deterministic fixed-report boundary
The system SHALL keep fixed daily report generation deterministic and SHALL NOT require inline external model execution in order to generate or cache the daily report.

#### Scenario: External model credentials are absent
- **WHEN** fixed daily report generation runs without any external model provider configured
- **THEN** the system still generates the free and premium cached reports using the deterministic report-generation path

#### Scenario: Prompt and MMU exports are built
- **WHEN** prompt bundles or MMU handoff artifacts are exported
- **THEN** the exports reference downstream-model use without mutating the cached fixed report content
