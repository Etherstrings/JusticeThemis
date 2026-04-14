## ADDED Requirements

### Requirement: Ticker enrichment shall be trigger-based and non-blocking
The system SHALL only run ticker enrichment for explicit triggers and SHALL NOT require enrichment success for the core overnight board to be produced.

#### Scenario: A regime-triggered enrichment is eligible
- **WHEN** a configured overnight market regime or high-priority mainline implies a focused watchlist
- **THEN** the system may run enrichment for the eligible symbols tied to that trigger

#### Scenario: Enrichment providers are unavailable
- **WHEN** enrichment providers fail or are not configured
- **THEN** the core market snapshot and free daily report still remain producible and the system reports enrichment degradation explicitly

### Requirement: Premium flows may consume richer enrichment context
The system SHALL allow premium-tier downstream outputs to consume stored ticker enrichment context without forcing that context into free-tier outputs.

#### Scenario: Premium export requests enrichment-backed context
- **WHEN** a premium-tier report or MMU export is generated and enrichment records exist for that analysis date
- **THEN** the premium flow may use those records while preserving free/premium output boundaries

