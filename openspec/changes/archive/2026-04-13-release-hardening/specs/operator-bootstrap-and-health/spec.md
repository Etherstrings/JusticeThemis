## ADDED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, and verification steps for this project.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, and the primary smoke-verification path

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command

### Requirement: Public liveness and sanitized readiness reporting
The service SHALL expose a minimal public liveness route and a sanitized readiness route suitable for release verification.

#### Scenario: Liveness is checked
- **WHEN** a caller requests the liveness endpoint
- **THEN** the service returns a minimal success response without exposing secrets, provider tokens, or detailed internal state

#### Scenario: Readiness is checked by an authorized operator
- **WHEN** an authorized operator requests the readiness endpoint
- **THEN** the service returns database availability, runtime mode, feature availability, and high-level source-registry readiness without exposing secret values

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies startup, health, and at least one read surface.

#### Scenario: Operator follows the smoke path
- **WHEN** an operator executes the documented smoke commands after startup
- **THEN** the operator can verify successful process startup, successful health/readiness response, and successful response from a supported read endpoint
