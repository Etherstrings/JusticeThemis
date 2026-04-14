## ADDED Requirements

### Requirement: Soft-rename runtime compatibility
The system SHALL preserve the existing runtime configuration contract during the `JusticeThemis` soft-rename phase so operators can adopt the new product identity without simultaneously migrating deployed configuration.

#### Scenario: Existing environment variables are reused after the rename
- **WHEN** the service starts in an environment that only defines the existing `OVERNIGHT_*` variables
- **THEN** the service accepts those variables as the supported runtime contract for this phase and does not require a renamed environment-variable prefix

#### Scenario: Existing default database path remains in place
- **WHEN** the operator does not provide an explicit database path override
- **THEN** the service continues using the existing compatible default database path rather than requiring a renamed data file path as part of the soft rename
