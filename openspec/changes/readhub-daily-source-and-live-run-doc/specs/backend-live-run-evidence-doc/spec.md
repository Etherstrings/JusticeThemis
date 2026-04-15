## ADDED Requirements

### Requirement: Isolated backend live-run workflow
The system SHALL provide a backend-only workflow for one requested `analysis_date` that runs against an isolated SQLite database and isolated output paths without requiring frontend code.

#### Scenario: Maintainer requests one-day backend evidence
- **WHEN** a maintainer invokes the documented live-run workflow for a specific `analysis_date`
- **THEN** the system runs capture and downstream backend stages against an isolated database/output target rather than the default long-lived local database

### Requirement: Chinese-first Markdown evidence document
The system SHALL emit a Chinese-first Markdown evidence document for the requested backend live run.

#### Scenario: Live run finishes
- **WHEN** the backend live-run workflow completes
- **THEN** it writes a Markdown document that includes run start/end timestamps, the requested `analysis_date`, the database path, the generated artifact paths, and the overall backend outcome

### Requirement: Readhub effectiveness section
The evidence document SHALL make Readhub's actual contribution visible when the run includes the Readhub source.

#### Scenario: Readhub captured topics in the live run
- **WHEN** the live run captures one or more Readhub topics
- **THEN** the evidence document includes Readhub hit counts plus sample topic titles/URLs, digest-rank or issue metadata, and a summary of topic enrichment availability

### Requirement: Failure-transparent backend evidence
The evidence document SHALL render even when one or more backend stages fail or degrade, and it SHALL explicitly describe what failed.

#### Scenario: Market snapshot or provider stage fails
- **WHEN** market snapshot, provider access, or another backend stage fails or only partially succeeds during the live run
- **THEN** the document still renders and explicitly lists the blocking failures, warnings, and which stages still succeeded

### Requirement: Auditable generated artifacts
The live-run workflow SHALL produce or reference machine-readable artifacts alongside the human-readable evidence document so the result can be audited without UI work.

#### Scenario: Maintainer reviews the generated evidence pack
- **WHEN** the live-run workflow writes the evidence document
- **THEN** it also writes or references the corresponding raw summary artifact and any generated daily-report Markdown artifacts needed to audit the run
