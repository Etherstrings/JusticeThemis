## ADDED Requirements

### Requirement: Mainline coverage state shall be explicit in fixed daily reports
The system SHALL expose whether confirmed mainlines and regimes are available, degraded, or unavailable when building fixed daily reports, instead of leaving downstream consumers to infer meaning from empty arrays alone.

#### Scenario: Confirmed market grounding exists
- **WHEN** confirmed mainlines or triggered regimes are available for the analysis date
- **THEN** the fixed report summary and narratives reference them as confirmed market grounding context

#### Scenario: Confirmed market grounding is absent
- **WHEN** no confirmed mainline or regime is emitted for the analysis date
- **THEN** the fixed report includes an explicit degraded or unavailable explanation that names the suppression reason, such as missing market confirmation, incomplete core observations, or lack of linked event groups

### Requirement: Secondary context shall remain visible when confirmed grounding is absent
The system SHALL preserve important downgraded event context in fixed daily reports when confirmed mainlines are unavailable so the user still sees what the pipeline considered relevant overnight.

#### Scenario: Secondary event groups exist without confirmed mainlines
- **WHEN** confirmed mainlines are absent but secondary event groups are available
- **THEN** the report may surface the strongest downgraded theme or an explicit secondary-context note instead of implying that no overnight theme existed
