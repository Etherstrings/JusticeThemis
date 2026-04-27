## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, and the canonical product identity for this project, while describing the product as a source-intelligence module plus analysis-comparison module that outputs "Yesterday, Where Did The World's Money Go?" data and optional rendered media.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, the primary smoke-verification path, the "Yesterday, Where Did The World's Money Go?" output, and the canonical product name `JusticeThemis`

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose, identifies legacy `OVERNIGHT_*` names as the supported compatibility contract for this soft-rename phase, and does not describe a premium-content runtime credential as required product configuration

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command and canonical product identity

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies startup, health, at least one read surface, and one "Yesterday, Where Did The World's Money Go?" payload or rendered artifact.

#### Scenario: Operator follows the smoke path
- **WHEN** an operator executes the documented smoke commands after startup
- **THEN** the operator can verify successful process startup, successful health/readiness response, successful response from a supported read endpoint, and successful generation of one "Yesterday, Where Did The World's Money Go?" payload or rendered artifact
