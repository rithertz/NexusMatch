# CI/CD

## GitHub Actions

`.github/workflows/ci.yml` runs two independent jobs:

- **Frontend:** installs Node dependencies with `npm ci`, runs TypeScript typecheck, ESLint, Vitest, and the Vite production build, then installs Playwright Chromium and Linux browser dependencies and runs the browser E2E suite.
- **Backend:** provisions its PostgreSQL 17 service, installs Python dependencies, runs Ruff, applies numbered SQL migrations, and runs pytest against the dedicated CI database.

The browser E2E tests mock frontend API responses and therefore do not require an additional API process, MongoDB instance, or database service. Real database integration is tested by the backend job. The mocked browser suite must not be described as full-stack verification.

## Local checks

Run frontend checks from `frontend/`:

```powershell
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run e2e:install
npm run e2e
```

Run backend checks from the repository root with PostgreSQL services and a specifically selected disposable `NEXUSMATCH_TEST_DATABASE_URL`; consult `docs/testing/TEST_STRATEGY.md`. Never point automated tests at a manually populated database.

## Related documents

- `../../frontend/README.md` — frontend and Playwright setup.
- `../testing/TEST_STRATEGY.md` — test boundaries and commands.
- `../../backend/README.md` — backend test requirements.
