## ADDED Requirements

### Requirement: First-run self-hosted success path
The project SHALL define one first-run path that a new technical self-hosted user can follow from fresh checkout to successful smoke verification.

#### Scenario: New technical user starts from a fresh checkout
- **WHEN** a new technical user follows the documented first-run path
- **THEN** the guidance covers dependency installation, environment setup, service startup, and at least one successful smoke verification step

### Requirement: Degraded-mode explanation for optional integrations
The project SHALL explain how the first-run experience degrades when optional provider credentials are absent so a new user can distinguish partial capability from setup failure.

#### Scenario: Optional market or enrichment credentials are missing
- **WHEN** a new user starts the project without optional provider credentials
- **THEN** the project explains which capabilities remain available, which outputs may be partial, and why that state does not necessarily mean the core service is broken

### Requirement: First-run failure guidance
The project SHALL describe the primary failure modes that block first-run success and the next action the user should take.

#### Scenario: New user cannot pass the first-run smoke
- **WHEN** the documented smoke path fails because of auth, environment, or runtime setup issues
- **THEN** the guidance identifies the likely class of failure and the next troubleshooting step or prerequisite to check
