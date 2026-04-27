## ADDED Requirements

### Requirement: Standalone frontend workspace
The repository SHALL provide a standalone frontend workspace, separate from the Python package-owned `app/ui` assets, with its own dependency manifest and commands for local development, production build, and preview.

#### Scenario: Operator boots the frontend workspace
- **WHEN** an operator installs the frontend dependencies and runs the documented development command
- **THEN** the repository starts a dedicated frontend development server without requiring edits inside `app/ui`

### Requirement: Configurable backend API origin
The standalone frontend SHALL consume the existing backend through one centralized API-origin configuration surface, with a documented local default that targets the local FastAPI server.

#### Scenario: Local backend is used by default
- **WHEN** the operator starts the backend on the documented local origin and launches the frontend with default local configuration
- **THEN** the frontend sends its API requests to the documented local backend without requiring source-code edits

#### Scenario: Custom backend origin is configured
- **WHEN** the operator provides an explicit frontend environment value for the backend API origin
- **THEN** the frontend uses that configured origin for subsequent API requests

### Requirement: Cross-origin local preview compatibility
The system SHALL support the documented local frontend and backend origins without browser-blocking cross-origin failures for supported read and protected API calls.

#### Scenario: Frontend dev origin calls backend APIs
- **WHEN** the standalone frontend is opened from a documented local development origin and requests a supported backend API
- **THEN** the browser can complete the request successfully under the documented local integration path
