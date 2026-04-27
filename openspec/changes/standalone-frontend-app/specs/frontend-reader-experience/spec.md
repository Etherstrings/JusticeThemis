## ADDED Requirements

### Requirement: Dashboard overview experience
The standalone frontend SHALL provide a dashboard view that consumes the existing dashboard API and presents the current hero metrics, signal buckets, source health, and top market-analysis context in a browser-readable layout.

#### Scenario: Dashboard loads current snapshot
- **WHEN** a user opens the dashboard view
- **THEN** the frontend requests the existing dashboard API and renders the returned hero counts, lead signals, watchlist, background, source health, and available market-analysis summaries

### Requirement: News exploration experience
The standalone frontend SHALL provide a news browsing experience that uses the existing news list, news detail, and sources APIs for list viewing, filtering, and detail inspection.

#### Scenario: User filters the news list
- **WHEN** a user changes one or more supported news filters such as tab, analysis status, coverage tier, source, search text, or pool mode
- **THEN** the frontend requests the existing news list API with the corresponding query parameters and refreshes the visible result set

#### Scenario: User opens one news item
- **WHEN** a user selects a news item from the list
- **THEN** the frontend requests the existing news detail API for that item and renders the returned item payload in a dedicated detail view or equivalent detail panel

### Requirement: Daily analysis and market snapshot experience
The standalone frontend SHALL provide an analysis view that can read the existing U.S. market snapshot and fixed daily analysis surfaces without requiring backend contract changes.

#### Scenario: User views the latest free analysis
- **WHEN** a user opens the analysis view without providing a premium credential
- **THEN** the frontend loads the existing market snapshot and free daily analysis surfaces and renders their available content with explicit empty or unavailable states where data is absent

#### Scenario: User views premium analysis with credential
- **WHEN** a user supplies a valid premium credential through the frontend's local protected-access controls
- **THEN** the frontend can request the existing premium daily analysis surface and render the authorized premium response

### Requirement: Local protected access controls
The standalone frontend SHALL provide local-only controls for admin and premium access headers so that protected backend routes can be exercised during technical preview without embedding secrets in source files.

#### Scenario: Admin operation is submitted from the frontend
- **WHEN** a user has entered a local admin access key and invokes a protected admin action supported by the frontend
- **THEN** the frontend attaches the admin header only to that protected request and surfaces the backend success or authorization failure clearly

#### Scenario: Protected content is requested without credential
- **WHEN** a user requests a protected premium or admin-backed frontend action without the required credential
- **THEN** the frontend shows an explicit authorization-required or failure state instead of silently failing or crashing
