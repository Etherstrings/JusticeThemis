## ADDED Requirements

### Requirement: Repository source-owned boundary
The project SHALL define which files and directories are source-owned and which are local generated artifacts so the working tree has a stable engineering boundary.

#### Scenario: Maintainer inspects the repository root
- **WHEN** a maintainer reads the repository bootstrap documentation
- **THEN** the documentation identifies the primary source-owned paths and distinguishes them from generated caches, build outputs, runtime databases, and local export artifacts

### Requirement: Ignore policy for generated artifacts
The repository SHALL provide ignore rules that exclude local generated artifacts from normal source-control and container-build workflows.

#### Scenario: Local runtime artifacts are present
- **WHEN** local caches, `__pycache__`, virtual environments, egg-info directories, SQLite databases, or exported pipeline artifacts exist in the project directory
- **THEN** the repository ignore policy excludes them from the normal tracked working set and container build context unless a path is explicitly designated as source-owned

### Requirement: Generated artifact directories remain reproducible
The repository SHALL treat runtime data and exported deliverables as reproducible local artifacts rather than required source assets.

#### Scenario: Contributor needs to recreate local artifacts
- **WHEN** a contributor starts from a clean checkout without existing `data/` or `output/` artifacts
- **THEN** the project documentation explains that those artifacts can be regenerated through supported runtime commands and are not required as committed source content
