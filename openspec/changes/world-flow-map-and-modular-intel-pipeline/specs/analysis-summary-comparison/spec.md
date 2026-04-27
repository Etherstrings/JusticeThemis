## ADDED Requirements

### Requirement: Analysis summary output shall be comparison-based rather than summary-only
The system SHALL generate a single analysis-summary-comparison output that places each top conclusion alongside its linked news inputs, linked market observations, confidence, key drivers, and optional uncertainty note.

#### Scenario: A top conclusion is emitted
- **WHEN** the system generates the daily analysis output
- **THEN** each top conclusion includes a readable conclusion sentence plus linked supporting inputs, linked market observations, confidence, key drivers, and optional uncertainty note

#### Scenario: Supporting evidence is weak or incomplete
- **WHEN** the system emits a conclusion without strong or complete supporting inputs
- **THEN** the comparison output downgrades confidence or marks the conclusion as provisional instead of presenting it as fully confirmed

### Requirement: The product shall expose one single analysis artifact without tier branching
The system SHALL expose one single product-facing analysis artifact for one analysis date and SHALL NOT branch that artifact into free-tier and premium-tier variants.

#### Scenario: Daily analysis is requested
- **WHEN** a caller requests the current daily analysis artifact
- **THEN** the system returns one canonical analysis payload for that date without requiring an access-tier parameter

#### Scenario: Export surfaces read analysis content
- **WHEN** prompt, handoff, or image-export surfaces consume the daily analysis output
- **THEN** they read from the same canonical analysis artifact rather than selecting between free and premium variants

### Requirement: Analysis comparison output shall include actionable reading order
The system SHALL organize the canonical analysis artifact in a reader-friendly order that answers what happened, where money moved, how the signals connect, and what remains uncertain.

#### Scenario: Image export reads the canonical analysis artifact
- **WHEN** the image-export flow loads the current analysis output
- **THEN** the payload provides fields for headline conclusion, flow summary, key drivers, cross-asset links, and uncertainty notes in a stable order suitable for direct rendering into a single image

#### Scenario: Source gaps affect readability
- **WHEN** one or more expected inputs are missing
- **THEN** the canonical analysis artifact still renders a readable structure and explicitly marks the missing area instead of omitting the section silently
