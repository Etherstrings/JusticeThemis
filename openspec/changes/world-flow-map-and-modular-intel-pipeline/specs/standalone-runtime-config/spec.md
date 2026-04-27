## MODIFIED Requirements

### Requirement: Feature-scoped configuration availability
The system SHALL degrade optional source or provider features independently rather than failing the entire service when only optional source credentials are missing, and SHALL NOT require a premium-content credential for product read surfaces.

#### Scenario: Market provider credentials are missing
- **WHEN** `IFIND_REFRESH_TOKEN` is absent
- **THEN** the news-capture flow remains runnable and the market-snapshot feature reports itself unavailable with an explicit status

#### Scenario: Admin credential is absent
- **WHEN** `OVERNIGHT_ADMIN_API_KEY` is absent
- **THEN** public read surfaces remain available and privileged mutation routes remain protected unless explicit unsafe-development mode is enabled

### Requirement: Explicit configuration diagnostics
The system SHALL expose configuration-state diagnostics in a sanitized form so operators can distinguish misconfiguration from data-source failure without reporting a premium-content configuration dependency.

#### Scenario: Optional provider keys are missing at startup
- **WHEN** the service starts with one or more optional provider credentials absent
- **THEN** readiness diagnostics identify the affected source or feature as unavailable without exposing secret values

#### Scenario: Unsafe development override is enabled
- **WHEN** the service starts with an explicit unsafe-development override for admin operations
- **THEN** readiness diagnostics report that unsafe mode is enabled
