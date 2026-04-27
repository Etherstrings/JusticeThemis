## ADDED Requirements

### Requirement: Source modules separate news intelligence from market data intelligence
The system SHALL expose a dedicated source-intelligence layer that separates news-source ingestion from market-data ingestion while presenting both through one normalized product-facing interface.

#### Scenario: News source module runs independently
- **WHEN** the system refreshes news inputs for one analysis date
- **THEN** it collects, normalizes, and persists news items without requiring the market-data collectors to succeed in the same execution step

#### Scenario: Market data module runs independently
- **WHEN** the system refreshes cross-asset market inputs for one analysis date
- **THEN** it collects, normalizes, and persists market observations without requiring the news-source collectors to succeed in the same execution step

### Requirement: Existing source websites and ingestion logic shall be preserved during the refactor
The system SHALL preserve the current configured source websites, source registry entries, and existing data-acquisition logic during the modular refactor unless one source is explicitly removed by a separate change.

#### Scenario: Source modules are reorganized
- **WHEN** the refactor moves code into the new source-intelligence module structure
- **THEN** all previously configured source websites and their active acquisition paths remain represented in the new module boundaries rather than being silently dropped

#### Scenario: A source is degraded but not removed
- **WHEN** one existing source cannot currently fetch complete data
- **THEN** the refactor keeps that source in the registry and reports its degraded state instead of deleting its definition or acquisition logic

### Requirement: Source modules produce one normalized intelligence payload
The system SHALL expose one normalized source-intelligence payload that combines usable news items, market observations, source status, and refresh diagnostics for downstream analysis.

#### Scenario: Downstream analysis reads normalized inputs
- **WHEN** the analysis-comparison module requests source inputs for one analysis date
- **THEN** it receives normalized news items, normalized market observations, source health, and refresh-state metadata from one product-facing payload rather than raw provider-specific responses

#### Scenario: One source is degraded
- **WHEN** one configured source is stale, unavailable, or partially captured
- **THEN** the normalized source-intelligence payload keeps the successful inputs available and marks the affected source with explicit degraded status instead of failing the whole payload

### Requirement: Source modules shall apply layered filtering before downstream analysis
The system SHALL apply importance layering, deduplication, topic grouping, and noise filtering inside the source-intelligence layer before emitting product-facing inputs.

#### Scenario: Multiple similar items are captured
- **WHEN** the source-intelligence layer captures multiple items that describe the same event, move, or company update
- **THEN** it groups or compresses those items into one clearer product-facing entry instead of passing obvious duplicates through unchanged

#### Scenario: Low-signal items are mixed with important items
- **WHEN** one refresh contains both high-signal and low-signal items
- **THEN** the source-intelligence layer assigns a readable importance tier or bucket so downstream analysis can distinguish what matters first

### Requirement: Source modules shall provide short human-readable explanations
The system SHALL provide a short human-readable explanation for each product-facing source-intelligence entry so the first module is readable without requiring the second module to decode raw inputs.

#### Scenario: A product-facing news entry is emitted
- **WHEN** one normalized news entry is exposed by the source-intelligence layer
- **THEN** the entry includes a concise explanation of why it matters, what changed, or which market area it touches

#### Scenario: A product-facing market observation is emitted
- **WHEN** one normalized market observation is exposed by the source-intelligence layer
- **THEN** the observation includes a concise explanation of what the move means in plain language rather than only raw price fields

### Requirement: Source modules preserve provenance and freshness at item level
The system SHALL preserve provenance, capture path, and freshness fields for each normalized news item and market observation.

#### Scenario: A normalized news item is exposed
- **WHEN** a downstream consumer reads one normalized news item
- **THEN** the item includes its source identity, capture timestamp, publication timestamp when available, and freshness or delay indicators

#### Scenario: A normalized market observation is exposed
- **WHEN** a downstream consumer reads one normalized market observation
- **THEN** the observation includes provider identity, market timestamp, normalized move fields, and primary-vs-fallback provenance when applicable
