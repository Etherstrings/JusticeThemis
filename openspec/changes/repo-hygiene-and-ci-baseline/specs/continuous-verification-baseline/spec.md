## ADDED Requirements

### Requirement: Canonical verification command
The project SHALL define at least one canonical local verification command that represents the baseline regression gate for repository changes.

#### Scenario: Maintainer checks how to verify the repository
- **WHEN** a maintainer reads the repository bootstrap or contribution guidance
- **THEN** the project documents a canonical verification command and the expected success criterion for that command

### Requirement: Deterministic CI baseline
The repository SHALL provide an automated verification workflow that runs the canonical baseline regression command in a clean environment without requiring live provider credentials.

#### Scenario: Source change triggers the baseline workflow
- **WHEN** a supported CI event runs for a repository change
- **THEN** the workflow installs dependencies in a clean environment and executes the canonical baseline verification command without relying on external market-data tokens or premium credentials

### Requirement: Baseline verification remains secret-independent
The project SHALL keep the initial automated regression baseline scoped to deterministic checks that can pass without repository secrets.

#### Scenario: CI runs without optional provider configuration
- **WHEN** the automated baseline workflow executes in an environment where optional runtime provider credentials are absent
- **THEN** the workflow still completes using the repository's deterministic test path rather than failing solely because optional live integrations are unavailable
