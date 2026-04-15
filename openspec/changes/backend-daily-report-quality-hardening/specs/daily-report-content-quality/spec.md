## ADDED Requirements

### Requirement: User-visible direction calls shall be deduplicated into distinct theses
The system SHALL collapse near-duplicate direction calls before emitting the fixed daily report so one macro driver does not surface as multiple user-visible conclusions that rely on the same evidence cluster set.

#### Scenario: Overlapping direction siblings are compressed
- **WHEN** two or more candidate direction calls share the same stance, overlapping event-cluster evidence, and the same dominant thesis family
- **THEN** the report emits only the strongest surviving user-visible direction call and suppresses the weaker near-duplicate siblings

#### Scenario: Distinct directions remain separate
- **WHEN** two direction calls are driven by the same broad macro event but retain materially different affected chains or non-overlapping evidence clusters
- **THEN** the report may keep both direction calls and preserves separate rationale and evidence

### Requirement: Key news briefs shall be Chinese-first and reader-ready
The system SHALL emit user-readable Chinese key-news briefs for fixed daily report outputs instead of exposing raw machine audit strings whenever a concise deterministic summary can be built.

#### Scenario: Readable brief is available
- **WHEN** headline news entries are assembled for the daily report
- **THEN** each emitted key-news row includes a concise Chinese brief or equivalent user-facing summary that explains what happened and why it matters

#### Scenario: High-quality Chinese brief cannot be synthesized
- **WHEN** the system cannot build a stable Chinese brief from the available structured fields
- **THEN** it falls back to bounded evidence sentences or follow-up items before exposing raw audit-style concatenated fields

### Requirement: Premium stock calls shall inherit post-dedup direction output
The system SHALL derive premium stock calls from the surviving user-visible direction calls after content-quality compression rather than from the pre-dedup raw direction aggregate.

#### Scenario: Duplicate upstream directions are compressed
- **WHEN** multiple raw positive directions compress into one surviving upstream-energy thesis
- **THEN** the premium report only emits stock mappings for the surviving thesis instead of duplicating stock rows across suppressed siblings
