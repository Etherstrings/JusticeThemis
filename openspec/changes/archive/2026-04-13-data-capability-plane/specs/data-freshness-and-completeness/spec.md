## ADDED Requirements

### Requirement: Market-data health shall distinguish core coverage from optional degradation
The system SHALL classify market instruments by operational importance so health and readiness can distinguish hard board failures from optional enrichment degradation.

#### Scenario: A core instrument is missing
- **WHEN** one or more configured core-board instruments are missing for an analysis date
- **THEN** market-data health reports a blocking failure or equivalent hard degradation

#### Scenario: Only optional enrichment instruments are missing
- **WHEN** optional enrichment or proxy instruments are missing while the core board remains intact
- **THEN** market-data health reports a warning or degraded-but-usable state instead of a full failure

### Requirement: Readiness and validation shall expose freshness and provider behavior
The system SHALL expose sanitized operational diagnostics for market freshness, provider coverage, and fallback behavior.

#### Scenario: Live validation runs after a market capture
- **WHEN** market validation is executed
- **THEN** the validation output includes missing symbols, bucket coverage, and enough provider-routing detail to distinguish primary success from fallback success

#### Scenario: Readiness is queried
- **WHEN** readiness diagnostics are requested
- **THEN** the response identifies whether core market capture, enrichment capability, and provider configuration are available without leaking secrets
