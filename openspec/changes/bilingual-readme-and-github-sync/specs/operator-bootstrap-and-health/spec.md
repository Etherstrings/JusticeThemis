## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, the canonical product identity, a Chinese companion README, and the GitHub publication path for this project.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, the primary smoke-verification path, the canonical product name `JusticeThemis`, and a link to the Chinese companion README

#### Scenario: Chinese-speaking operator needs setup instructions
- **WHEN** an operator opens the Chinese companion README from the repository root
- **THEN** that document describes the same supported startup modes, required setup steps, primary smoke-verification path, and canonical product name in Chinese

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose and identifies legacy `OVERNIGHT_*` names as the supported compatibility contract for this soft-rename phase

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command and canonical product identity

#### Scenario: Maintainer needs GitHub publication guidance
- **WHEN** a maintainer prepares the bootstrap package for GitHub publication
- **THEN** the package states that the current local directory is not a Git worktree and that bootstrap-document publication must occur through the isolated Git-backed convergence workspace for `Etherstrings/JusticeThemis`

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies startup, health, and at least one read surface, and that smoke contract SHALL remain aligned across the English and Chinese bootstrap documents.

#### Scenario: Operator follows the smoke path from the English README
- **WHEN** an operator executes the documented smoke commands from `README.md` after startup
- **THEN** the operator can verify successful process startup, successful health/readiness response, and successful response from a supported read endpoint

#### Scenario: Operator follows the smoke path from the Chinese README
- **WHEN** an operator executes the documented smoke commands from `README.zh.md` after startup
- **THEN** the operator can verify the same successful process startup, health/readiness response, and supported read-endpoint response contract
