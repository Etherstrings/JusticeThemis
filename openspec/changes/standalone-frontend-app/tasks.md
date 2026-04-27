## 1. Frontend Workspace Setup

- [x] 1.1 Create a new `frontend/` workspace with its own package manifest, Vite/React/TypeScript bootstrap, and documented `dev` / `build` / `preview` scripts.
- [x] 1.2 Add centralized frontend configuration for backend API origin, including local-default behavior and any required `.env` or example config files.
- [x] 1.3 Add a shared frontend API client and request utilities that centralize base URL resolution, JSON handling, and protected header injection.

## 2. Backend Integration Support

- [x] 2.1 Add the minimum backend configuration needed for standalone frontend local preview, including controlled CORS or equivalent documented local integration support.
- [x] 2.2 Preserve the current backend API contracts while adding only any strictly necessary compatibility fields or integration helpers discovered during frontend hookup.
- [x] 2.3 Decide and document the ongoing role of legacy `app/ui` as a compatibility/operator surface rather than the primary frontend implementation target.

## 3. Reader Experience Implementation

- [x] 3.1 Implement the dashboard view using the existing `/api/v1/dashboard` response, including hero metrics, signal buckets, source health, and available market-analysis summaries.
- [x] 3.2 Implement the news browsing flow using `/api/v1/news`, `/api/v1/news/{id}`, and `/api/v1/sources`, including filters, list states, and detail rendering.
- [x] 3.3 Implement the analysis view using `/api/v1/market/us/daily`, `/api/v1/analysis/daily`, and related analysis endpoints, including explicit empty/auth-required/error states.
- [x] 3.4 Implement local-only admin and premium access-key controls so protected refresh or premium-analysis actions can be exercised during technical preview without hardcoding secrets.

## 4. Documentation And Verification

- [x] 4.1 Update bootstrap documentation and local startup guidance so operators can start the backend and standalone frontend together and understand the required configuration surfaces.
- [x] 4.2 Add or update verification coverage for frontend build success, local integration expectations, and any backend configuration added for standalone frontend support.
- [x] 4.3 Run the documented local verification flow for backend startup, frontend startup, health/readiness checks, and at least one end-to-end read path through the new frontend.
