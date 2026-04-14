## ADDED Requirements

### Requirement: Standalone runtime configuration resolution
The system SHALL resolve runtime configuration from standalone project-local or process-provided sources and SHALL NOT implicitly load env files from unrelated repositories.

#### Scenario: Project-local env file is used when process env is absent
- **WHEN** the pipeline or API starts without a needed value in process environment and the value exists in the project's supported env file location
- **THEN** the system loads the project-local value and continues using that value for the relevant feature

#### Scenario: Unrelated repository env files are ignored
- **WHEN** env files exist outside the current project but no explicit path to them is configured
- **THEN** the system ignores those external files and does not treat them as runtime defaults

### Requirement: Feature-scoped configuration availability
The system SHALL degrade optional features independently rather than failing the entire service when only optional provider credentials are missing.

#### Scenario: Market provider credentials are missing
- **WHEN** `IFIND_REFRESH_TOKEN` is absent
- **THEN** the news-capture flow remains runnable and the market-snapshot feature reports itself unavailable with an explicit status

#### Scenario: Premium access key is missing
- **WHEN** `OVERNIGHT_PREMIUM_API_KEY` is absent
- **THEN** free-tier routes remain available and premium-tier routes reject the request with an explicit premium-auth error

### Requirement: Explicit configuration diagnostics
The system SHALL expose configuration-state diagnostics in a sanitized form so operators can distinguish misconfiguration from data-source failure.

#### Scenario: Optional provider keys are missing at startup
- **WHEN** the service starts with one or more optional provider credentials absent
- **THEN** readiness diagnostics identify the affected feature as unavailable without exposing secret values

#### Scenario: Unsafe development override is enabled
- **WHEN** the service starts with an explicit unsafe-development override for admin operations
- **THEN** readiness diagnostics report that unsafe mode is enabled

### Requirement: Soft-rename runtime compatibility
The system SHALL preserve the existing runtime configuration contract during the `JusticeThemis` soft-rename phase so operators can adopt the new product identity without simultaneously migrating deployed configuration.

#### Scenario: Existing environment variables are reused after the rename
- **WHEN** the service starts in an environment that only defines the existing `OVERNIGHT_*` variables
- **THEN** the service accepts those variables as the supported runtime contract for this phase and does not require a renamed environment-variable prefix

#### Scenario: Existing default database path remains in place
- **WHEN** the operator does not provide an explicit database path override
- **THEN** the service continues using the existing compatible default database path rather than requiring a renamed data file path as part of the soft rename
