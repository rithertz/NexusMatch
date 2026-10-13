# NexusMatch test strategy

## Test layers

- **Frontend unit tests:** Vitest tests small frontend units and the API client. Run with `cd frontend; npm test`.
- **Browser E2E tests:** Playwright exercises the React app in Chromium using deterministic intercepted API responses. Run with `cd frontend; npm run e2e:install` once, then `cd frontend; npm run e2e`.
- **Backend unit and API tests:** pytest covers schema, migration runner, and FastAPI behaviors.
- **PostgreSQL integration tests:** pytest validates constraints, triggers, transactions, and tournament workflows against the explicitly selected `NEXUSMATCH_TEST_DATABASE_URL`.

The Playwright tests do not connect to FastAPI, PostgreSQL, or MongoDB. They validate the real frontend application/browser interactions but do not establish backend integration. Backend/PostgreSQL tests remain the source of evidence for data integrity and API/database behavior. Neither suite should use manually maintained databases.

## Browser scenarios

`frontend/tests/e2e/tournaments.spec.ts` covers:

- Application startup without an uncaught browser exception.
- Tournament discovery and tournament detail overview.
- Player display names in the participant list.
- Persisted bracket display, participants, round headings, and byes.
- Loading, empty, missing-bracket, and API error states.

All responses are local test fixtures registered through Playwright `page.route`; the fixture fields mirror the current API response contracts.

## Commands

From the repository root:

```powershell
cd frontend
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run e2e:install
npm run e2e
```

GitHub Actions runs the frontend checks and mocked browser tests in the frontend job. It installs Chromium and its Linux dependencies there. The separate backend job runs migrations and PostgreSQL tests.

## Diagnostics

Playwright retains failure screenshots and traces in ignored `frontend/test-results/` and `frontend/playwright-report/` paths. Ensure Chromium is installed with `npm run e2e:install`. The E2E server uses port 5173 and reuses an already running Vite server locally; stop a stale Vite process if the page does not reflect the current source.

## Related documents

- `../../frontend/README.md` — setup and frontend/browser commands.
- `../devops/CI_CD.md` — CI workflow.
- `../../backend/API.md` — API response contracts exercised by frontend fixtures.
