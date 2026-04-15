## ADDED Requirements

### Requirement: Core market-data gaps shall downgrade fixed daily report certainty
The system SHALL propagate core market-data completeness gaps into fixed daily report confidence and risk framing instead of confining those gaps to health or validation surfaces.

#### Scenario: Core market board is incomplete
- **WHEN** the market snapshot for an analysis date is partial and includes one or more core missing symbols
- **THEN** the fixed daily report caps its confidence, adds an explicit market-completeness caveat, and exposes at least one related risk or follow-up item

#### Scenario: Core market board is complete
- **WHEN** the market snapshot for an analysis date contains no core missing symbols
- **THEN** the fixed daily report may use the normal confidence and narrative path without forced market-gap downgrade messaging
