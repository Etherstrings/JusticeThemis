## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, the canonical product identity for this project, and the supported path for local standalone-frontend preview when that frontend workspace is present.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported backend startup modes, the primary frontend preview path when available, required setup steps, the primary smoke-verification path, and the canonical product name `JusticeThemis`

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** the project documents required and optional backend environment variables with their purpose and identifies any frontend API-origin or preview configuration surface needed for local integration

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command and canonical product identity

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies backend startup, standalone frontend preview startup when supported, health/readiness, and at least one supported read surface through the documented local integration flow.

#### Scenario: Operator follows the smoke path
- **WHEN** an operator executes the documented smoke commands after startup
- **THEN** the operator can verify successful backend process startup, successful frontend preview startup when applicable, successful health/readiness response, and successful response from a supported read endpoint under the documented local preview workflow
