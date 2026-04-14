## ADDED Requirements

### Requirement: Overnight market regimes shall be derived from normalized observations
The system SHALL derive a deterministic set of overnight market-regime signals from normalized market observations before narrative analysis is generated.

#### Scenario: Technology risk-on regime is detected
- **WHEN** normalized observations show a positive technology-led overnight structure according to configured regime rules
- **THEN** the system emits a technology-focused regime signal that downstream analysis can use as grounding context

#### Scenario: No configured regime is triggered
- **WHEN** normalized observations do not satisfy any configured regime rule strongly enough
- **THEN** the system emits no positive regime claim rather than inferring one from narrative sources alone

### Requirement: Mainlines shall be assembled from regimes first and event groups second
The system SHALL assemble confirmed overnight mainlines from computed market regimes plus supporting event groups, rather than promoting topic-tagged events directly into top mainlines without market confirmation.

#### Scenario: Regime-backed mainline is built
- **WHEN** normalized observations trigger a technology-led overnight regime and related event groups discuss semiconductor or AI-demand explanations
- **THEN** the system emits a technology mainline that references the regime as grounding input and the event groups as explanation input

#### Scenario: Confirmed mainline carries regime grounding
- **WHEN** a top mainline is emitted as confirmed overnight narrative output
- **THEN** that mainline includes at least one grounding `regime_id` rather than relying only on topic-tagged event grouping

#### Scenario: Event group lacks market confirmation
- **WHEN** an event group maps to a thematic bucket but normalized observations do not support a corresponding regime strongly enough
- **THEN** the system does not elevate that event group into a confirmed top mainline and keeps it only as secondary narrative context

### Requirement: Regime evaluation shall be auditable and completeness-aware
The system SHALL evaluate regime rules against normalized observations with explicit completeness, freshness, and conflict semantics so operators can explain why a regime was triggered, downgraded, or suppressed.

#### Scenario: Required observations are missing
- **WHEN** a regime rule depends on required observations that are missing or stale beyond configured freshness policy
- **THEN** the system suppresses or downgrades that regime and records a structured reason rather than emitting a fully confirmed regime

#### Scenario: Conflicting observations weaken a regime
- **WHEN** supportive observations point in one direction but disqualifying observations point in the opposite direction
- **THEN** the emitted regime confidence or direction reflects the configured conflict policy rather than ignoring the conflict

### Requirement: Regime grounding shall support, not replace, narrative analysis
The system SHALL provide regime outputs as structured grounding inputs to downstream analysis while preserving the existing fixed-report, handoff, and MMU product surfaces.

#### Scenario: Daily analysis is generated with regime context available
- **WHEN** the daily report is generated for an analysis date with computed regimes
- **THEN** the report-generation path can reference those regimes as structured input without requiring a new outward-facing report schema

#### Scenario: Handoff and MMU bundles include regimes additively
- **WHEN** structured handoff payloads are built for an analysis date with computed regimes
- **THEN** the payload may expose `market_regimes` or equivalent additive regime context without removing `market_snapshot` or `mainlines`

### Requirement: Unconfirmed event groups shall remain visible as secondary context
The system SHALL surface important event groups that lack sufficient market confirmation through additive secondary-context outputs instead of dropping them entirely or mixing them into confirmed top mainlines.

#### Scenario: Secondary context is exposed in downstream payloads
- **WHEN** a notable event group has high document importance but does not satisfy regime-backed promotion rules
- **THEN** downstream reports or handoff payloads may expose that group under `secondary_event_groups` or an equivalent additive field with a downgrade reason
