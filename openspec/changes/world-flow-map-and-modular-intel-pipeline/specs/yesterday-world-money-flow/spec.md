## ADDED Requirements

### Requirement: The system shall generate one render-ready "Yesterday, Where Did The World's Money Go?" payload per analysis run
The system SHALL generate a single render-ready `yesterday_world_money_flow_payload` for each completed analysis run.

#### Scenario: Analysis completes successfully
- **WHEN** the system completes one analysis run for an analysis date
- **THEN** it generates one `yesterday_world_money_flow_payload` artifact for that date in addition to the structured analysis payload

#### Scenario: The payload is requested later
- **WHEN** a caller or export flow requests the `yesterday_world_money_flow_payload` artifact for a completed date
- **THEN** the system serves the most recently generated payload for that date without requiring the analysis to rerun

### Requirement: The payload shall answer where global money moved yesterday
The generated payload SHALL present the major overnight flow picture across global macro and policy signals, geopolitics, global equities, sector leadership, rates and FX, key commodities, and major tech or company events in one view.

#### Scenario: A reader opens the rendered output
- **WHEN** a reader views content rendered from `yesterday_world_money_flow_payload`
- **THEN** the output shows the direction and strength of the main cross-asset moves and highlights the primary overnight flow message in human-readable language

#### Scenario: Multiple money-related themes are available
- **WHEN** the structured analysis captures policy, geopolitical, market, commodity, and major-company signals in the same time window
- **THEN** the payload groups them into stable global sections so one rendered image can explain what happened during that overnight window without collapsing into one flat list

### Requirement: The payload shall support external rendering workflows
The system SHALL structure the payload so it can be rendered either by an internal image generator, a local template project such as `stockComImage`, or an external AI-image workflow.

#### Scenario: Internal renderer is unavailable
- **WHEN** no internal SVG or PNG renderer is configured
- **THEN** the system still exports the render-ready payload with stable fields, ordering, and text blocks so an external rendering workflow can consume it directly

#### Scenario: A local rendering template is used
- **WHEN** the operator provides a local rendering template or project input contract
- **THEN** the system can map the payload into that contract without changing the underlying analysis logic

### Requirement: The payload shall degrade gracefully when one input group is missing
The system SHALL keep the `yesterday_world_money_flow_payload` available even when one or more input groups are degraded, while explicitly marking missing sections.

#### Scenario: One asset group is unavailable
- **WHEN** an expected asset group such as commodities or rates is missing for the analysis date
- **THEN** the payload keeps the remaining groups visible and marks the unavailable group with an explicit unavailable or delayed state

#### Scenario: News inputs are stronger than market inputs
- **WHEN** the market inputs are partial but the news inputs still support a limited overnight read
- **THEN** the payload keeps the overall headline and available sections while reducing confidence wording for the missing market-driven sections
