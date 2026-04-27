## MODIFIED Requirements

### Requirement: Admin authentication for privileged mutation routes
The system SHALL require a valid admin credential for routes that refresh source-intelligence inputs, refresh market snapshots, regenerate the canonical analysis artifact, rebuild the `yesterday_world_money_flow_payload` or any optional rendered image, or expose detailed operational readiness, unless an explicit unsafe-development override is enabled.

#### Scenario: Mutation route is called without admin credential
- **WHEN** a privileged mutation route is requested without a valid admin credential and unsafe-development override is not enabled
- **THEN** the system rejects the request with an authorization error

#### Scenario: Mutation route is called with valid admin credential
- **WHEN** a privileged mutation route is requested with a valid admin credential
- **THEN** the system allows the operation to proceed

## REMOVED Requirements

### Requirement: Premium authentication for premium read surfaces
**Reason**: The product no longer distinguishes read content by premium tier.
**Migration**: Read surfaces must become single-version read endpoints and callers must stop sending premium credentials for content access.
