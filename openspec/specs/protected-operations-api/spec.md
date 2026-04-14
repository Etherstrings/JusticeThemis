## ADDED Requirements

### Requirement: Admin authentication for privileged mutation routes
The system SHALL require a valid admin credential for routes that refresh captured data, refresh market snapshots, generate cached analysis, or expose detailed operational readiness, unless an explicit unsafe-development override is enabled.

#### Scenario: Mutation route is called without admin credential
- **WHEN** a privileged mutation route is requested without a valid admin credential and unsafe-development override is not enabled
- **THEN** the system rejects the request with an authorization error

#### Scenario: Mutation route is called with valid admin credential
- **WHEN** a privileged mutation route is requested with a valid admin credential
- **THEN** the system allows the operation to proceed

### Requirement: Premium authentication for premium read surfaces
The system SHALL require a valid premium credential for premium analysis and premium export surfaces while preserving free read access for free-tier consumers.

#### Scenario: Premium analysis is requested without premium credential
- **WHEN** a premium-tier analysis or premium-tier export route is requested without a valid premium credential
- **THEN** the system rejects the request with an authorization error

#### Scenario: Free analysis is requested without premium credential
- **WHEN** a free-tier analysis route is requested without a premium credential
- **THEN** the system serves the free-tier response if the resource exists

### Requirement: Unsafe development mode is explicit and observable
The system SHALL only allow unauthenticated privileged operations when an explicit unsafe-development mode is enabled, and that mode SHALL be observable in sanitized operator diagnostics.

#### Scenario: Unsafe mode is disabled
- **WHEN** the service runs without unsafe-development mode enabled
- **THEN** privileged routes remain protected even if no admin credential has been configured

#### Scenario: Unsafe mode is enabled for local development
- **WHEN** the service runs with unsafe-development mode enabled
- **THEN** privileged routes may remain callable without admin authentication and readiness diagnostics report unsafe mode as enabled
