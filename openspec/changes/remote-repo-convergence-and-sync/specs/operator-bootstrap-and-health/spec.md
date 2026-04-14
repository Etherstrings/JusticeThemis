## MODIFIED Requirements

### Requirement: Operator bootstrap package
The repository SHALL provide a standalone operator bootstrap package that documents configuration, startup, deployment, verification steps, canonical product identity, repository-owned content, generated-artifact boundaries, canonical upstream, and repository convergence prerequisites for this project.

#### Scenario: Operator needs setup instructions
- **WHEN** an operator opens the repository root
- **THEN** a root README describes supported startup modes, required setup steps, the primary smoke-verification path, the canonical product name `JusticeThemis`, which paths are maintained as source-owned content, and which upstream repository shape is treated as canonical

#### Scenario: Operator needs environment variable guidance
- **WHEN** an operator prepares deployment configuration
- **THEN** a project-local environment example file enumerates required and optional environment variables with their purpose and identifies legacy `OVERNIGHT_*` names as the supported compatibility contract for this soft-rename phase

#### Scenario: Operator needs a containerized deployment path
- **WHEN** an operator chooses the documented container deployment path
- **THEN** the repository provides a supported container build file and compose-style startup file that use the canonical application startup command, canonical product identity, and a build context that excludes generated local artifacts

#### Scenario: Maintainer needs the canonical repository verification path
- **WHEN** a maintainer prepares to validate repository changes
- **THEN** the bootstrap package points to the canonical baseline verification command used by the repository's local and CI regression path

#### Scenario: Maintainer prepares a repository synchronization
- **WHEN** a maintainer needs to reconcile local standalone code with the remote GitHub repository
- **THEN** the bootstrap package identifies the canonical upstream, links to the synchronization prerequisites, and states that convergence must happen in an isolated Git-backed workspace rather than the current non-Git local directory

### Requirement: Documented release smoke contract
The project SHALL define one documented release smoke path that verifies startup, health, at least one read surface, and the post-sync usability checks required before a synchronized repository branch is treated as releasable.

#### Scenario: Operator follows the smoke path
- **WHEN** an operator executes the documented smoke commands after startup
- **THEN** the operator can verify successful process startup, successful health/readiness response, and successful response from a supported read endpoint

#### Scenario: Maintainer validates a synchronized repository branch
- **WHEN** a maintainer completes repository convergence in the isolated Git workspace
- **THEN** the documented smoke contract includes the bootstrap, health/readiness, and canonical regression checks required before the branch is proposed for merge
