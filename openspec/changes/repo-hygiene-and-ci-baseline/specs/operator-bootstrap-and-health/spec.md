## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, canonical product identity, repository-owned content, and generated-artifact boundaries for this project.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, the primary smoke-verification path, the canonical product name `JusticeThemis`, and which paths are maintained as source-owned content

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose and identifies legacy `OVERNIGHT_*` names as the supported compatibility contract for this soft-rename phase

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command, canonical product identity, and a build context that excludes generated local artifacts

#### Scenario: Maintainer needs the canonical repository verification path
- **WHEN** a maintainer prepares to validate repository changes
- **THEN** the bootstrap package points to the canonical baseline verification command used by the repository's local and CI regression path
