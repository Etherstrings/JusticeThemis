## REMOVED Requirements

### Requirement: Tier-aligned prompt bundle exports
**Reason**: The product no longer maintains free-tier and premium-tier analysis variants.
**Migration**: Prompt exports must read from the single canonical analysis artifact and stop accepting access-tier branching for report selection.

### Requirement: Tier-aware MMU premium recommendation export
**Reason**: Premium-only recommendation output is being removed along with the tiered product boundary.
**Migration**: MMU or downstream handoff exports must consume the single canonical analysis artifact and expose one unified recommendation context.

## MODIFIED Requirements

### Requirement: Deterministic fixed-report boundary
The system SHALL keep fixed daily analysis generation deterministic and SHALL NOT require inline external model execution in order to generate the canonical analysis artifact, `yesterday_world_money_flow_payload`, or any optional rendered image derived from that payload.

#### Scenario: External model credentials are absent
- **WHEN** fixed daily analysis generation runs without any external model provider configured
- **THEN** the system still generates the canonical daily analysis artifact and `yesterday_world_money_flow_payload` using the deterministic report-generation path

#### Scenario: Export surfaces are built
- **WHEN** prompt bundles, handoff payloads, or "Yesterday, Where Did The World's Money Go?" outputs are exported
- **THEN** the exports are derived from the single canonical analysis artifact without reintroducing free-tier or premium-tier report branching
