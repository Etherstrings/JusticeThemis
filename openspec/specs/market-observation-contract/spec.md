## ADDED Requirements

### Requirement: Normalized market observations shall exist beneath assembled market snapshots
The system SHALL represent captured cross-asset market data as normalized market observations before assembling a persisted market snapshot.

#### Scenario: Provider data is converted into a reusable observation
- **WHEN** a market provider returns data for one instrument
- **THEN** the system stores or exposes a normalized observation that includes symbol, provider identity, market timestamp, and normalized price-change fields

#### Scenario: Assembled snapshots are derived from observations
- **WHEN** the market snapshot is generated for an analysis date
- **THEN** the system assembles the snapshot from normalized observations instead of treating provider payloads as the only durable representation

### Requirement: Observation provenance shall be preserved
The system SHALL preserve provider provenance and primary-vs-fallback status for each observation.

#### Scenario: A fallback provider is used
- **WHEN** the preferred provider cannot satisfy one instrument and a fallback provider succeeds
- **THEN** the resulting observation identifies the fallback provider and records that the primary provider was not used

#### Scenario: A primary provider succeeds
- **WHEN** the preferred provider succeeds for one instrument
- **THEN** the resulting observation is marked as primary-provider sourced

