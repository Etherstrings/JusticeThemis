## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, canonical product identity, supported user cohorts, unsupported user cohorts, current release verdict, and the first-run success path for this project.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, the primary smoke-verification path, the canonical product name `JusticeThemis`, and which user cohort the current release is intended to support

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose and identifies legacy `OVERNIGHT_*` names as the supported compatibility contract for this soft-rename phase

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command and canonical product identity

#### Scenario: Maintainer evaluates whether the project can be handed to users
- **WHEN** a maintainer or reviewer reads the bootstrap package
- **THEN** the package states the current release verdict, the supported user cohort, the unsupported user cohort, and the key blocking reasons that limit broader release claims

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies startup, health, at least one read surface, and the first-run conditions required to conclude the project is usable for its currently supported user cohort.

#### Scenario: Operator follows the smoke path
- **WHEN** an operator executes the documented smoke commands after startup
- **THEN** the operator can verify successful process startup, successful health/readiness response, and successful response from a supported read endpoint

#### Scenario: New technical self-hosted user completes first-run verification
- **WHEN** a new technical user follows the first-run instructions
- **THEN** the release smoke contract explains what counts as success, what degraded-but-acceptable states may appear, and which failures mean the project is not yet ready for that user
