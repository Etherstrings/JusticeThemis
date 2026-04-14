## ADDED Requirements

### Requirement: Market provider routing shall be explicit and bucket-aware
The system SHALL route market capture through explicit provider rules that vary by bucket and instrument intent rather than using one global provider ranking for all symbols.

#### Scenario: Treasury yield instruments prefer an official provider
- **WHEN** the system captures a Treasury-yield instrument such as `^TNX`
- **THEN** it first attempts the official Treasury provider before falling back to non-official market providers

#### Scenario: U.S. index or sector instruments use configured market-provider order
- **WHEN** the system captures core U.S. indexes, sectors, or commodities
- **THEN** it applies the configured bucket-specific provider order and records which provider satisfied the observation

### Requirement: Provider symbol overrides shall be preserved
The system SHALL support provider-specific symbol overrides for instruments whose provider symbol differs from the project-facing symbol.

#### Scenario: iFinD requires a proxy or alternate symbol
- **WHEN** an instrument has a configured iFinD symbol override
- **THEN** the router uses the provider-specific symbol for iFinD while preserving the original project-facing symbol in the resulting observation

#### Scenario: No override exists
- **WHEN** an instrument has no provider-specific symbol override
- **THEN** the router uses the instrument's default symbol for that provider

