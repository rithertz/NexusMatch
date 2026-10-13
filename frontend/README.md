# NexusMatch frontend

React, TypeScript and Vite client for the NexusMatch FastAPI service. It deliberately has no client-side identity or faux authentication: users explicitly choose a player/team and organizer actions are labeled as trusted local-demo operations.

## Visual direction

The interface is tactical and technical rather than generic dashboard UI: charcoal layered surfaces, amber decisive actions, green/red semantic states, Space Grotesk UI typography, and tabular DM Mono metadata. Compact borders and round columns preserve the density and scanability of tournament operations software. Motion is restrained and disabled for reduced-motion users.

## Run

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

`VITE_API_BASE_URL` defaults to `http://localhost:8000/api/v1`. Start PostgreSQL and MongoDB, run migrations, then start FastAPI before using the client. The health chip reflects `/health` and distinguishes full health, degraded dependencies, and an unavailable API.

## Checks

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

## Browser end-to-end tests

Playwright runs in a real Chromium browser against the Vite app. First install the browser once per machine:

```powershell
npm run e2e:install
npm run e2e
```

`npm run e2e` starts Vite on `http://127.0.0.1:5173` when it is not already running. The browser suite intercepts `http://localhost:8000/api/v1/**` and supplies deterministic API responses for application startup, tournament overview, participants, bracket/bye rendering, loading, empty, and API-error states. These are UI E2E tests with mocked HTTP APIs: they do not prove FastAPI/PostgreSQL integration. That integration remains covered by the backend's PostgreSQL-backed pytest suite.

The E2E suite needs no running API or database and writes no database data. Set `CI=1` in CI to enable retries, a bounded worker count, and the GitHub reporter. On Linux CI, install the browser and system libraries with `npx playwright install --with-deps chromium` before `npm run e2e`. Failure screenshots and traces are saved under ignored `test-results/` and `playwright-report/` directories.

For a real local full-stack smoke check, separately start PostgreSQL/MongoDB, apply migrations, run FastAPI, and run Vite with `VITE_API_BASE_URL` set if the backend is not at the default `http://localhost:8000/api/v1`. The deterministic Playwright suite itself continues to mock API responses.

## Routes and API coverage

- `/` — list/search/filter actual tournaments.
- `/tournaments/:id` — overview, registrations, persisted bracket, and server-confirmed score entry.
- `/registrations` — all registrations in the identity-free API, including withdrawal.
- `/teams` — team and roster inspection.
- `/organizer` — creation, pending-registration approval/rejection, and bracket generation.

Only `single_elimination` is visualized as a bracket because that is the backend-supported bracket engine. MongoDB telemetry has no read endpoint and is intentionally not faked.
