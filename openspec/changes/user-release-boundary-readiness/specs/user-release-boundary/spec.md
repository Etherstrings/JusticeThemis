## ADDED Requirements

### Requirement: Release audience classification
The project SHALL explicitly classify which user cohorts are currently supported and which are not supported for release claims.

#### Scenario: Technical self-hosted user evaluates the project
- **WHEN** a technical user reviews the primary release and bootstrap guidance
- **THEN** the project states whether self-hosted operators or internal technical users are currently supported as a release audience

#### Scenario: General end user evaluates the project
- **WHEN** a non-operator or low-touch external user reviews the same release guidance
- **THEN** the project states whether that user cohort is supported or unsupported rather than implying universal readiness

### Requirement: Release verdict must be evidence-based
The project SHALL tie its current release verdict to objective evidence such as verification commands, startup smoke, auth boundaries, and documented limitations.

#### Scenario: Maintainer claims the project is usable for a user cohort
- **WHEN** the maintainer publishes a release-readiness statement
- **THEN** the statement references the concrete verification path and boundary conditions that justify that verdict

### Requirement: Blocking gaps for broader release SHALL be disclosed
The project SHALL disclose the concrete gaps that prevent the project from being represented as ready for broader or less technical users.

#### Scenario: Broader release is not yet supported
- **WHEN** the project stops short of claiming general-user readiness
- **THEN** the release-boundary guidance lists the key blocking gaps and unsupported assumptions that explain the limit
