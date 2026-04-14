## ADDED Requirements

### Requirement: Canonical product identity
The system SHALL present `JusticeThemis` as the canonical product identity across operator-facing product surfaces in this soft-rename phase.

#### Scenario: Operator reads the primary project entrypoint
- **WHEN** an operator opens the repository root documentation or equivalent bootstrap entrypoint
- **THEN** the project identifies itself as `JusticeThemis` and describes the system as an overnight market interpretation engine or equivalent result-first morning product

#### Scenario: API metadata is exposed
- **WHEN** the service exposes application metadata or health identity fields intended for operator inspection
- **THEN** those surfaces use the canonical `JusticeThemis` identity rather than `overnight-news-handoff`

### Requirement: Legacy identifier compatibility mapping
The system SHALL document the relationship between the new canonical product identity and legacy compatibility identifiers during the soft-rename phase.

#### Scenario: Operator encounters mixed old and new names
- **WHEN** documentation or generated runtime surfaces still reference a supported legacy identifier
- **THEN** the project explains whether that identifier is a legacy project name, runtime compatibility marker, or generated artifact compatibility name

### Requirement: Generated operator artifacts default to the new identity
The system SHALL generate new operator-facing artifacts with names aligned to `JusticeThemis`, unless a specific compatibility exception is documented for that surface.

#### Scenario: Operator generates a new launchd template or exported operator artifact
- **WHEN** the operator uses a built-in generation command without overriding names manually
- **THEN** the generated label, output filename, or equivalent operator-facing artifact name reflects the canonical `JusticeThemis` identity
