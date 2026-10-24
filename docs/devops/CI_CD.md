# CI/CD

## GitHub Actions

`.github/workflows/ci.yml` runs three jobs:

- **Frontend:** installs Node dependencies with `npm ci`, runs TypeScript typecheck, ESLint, Vitest, and the Vite production build, then installs Playwright Chromium and Linux browser dependencies and runs the browser E2E suite.
- **Backend:** provisions a PostgreSQL 17 service using the allowlisted `nexusmatch_ci_isolated_test` database, installs Python dependencies, runs Ruff, applies numbered SQL migrations, and runs pytest.
- **Real-stack integration:** provisions distinct PostgreSQL and MongoDB services, applies migrations to the allowlisted `nexusmatch_e2e_test` database, starts FastAPI, and runs the actual-browser workflow without API interception.

The standard frontend E2E tests mock API responses and do not prove backend integration. The separate real-stack job exercises the browser, API, and PostgreSQL together. CI credentials are fixed test-only values and are not sourced from a developer's `.env`.

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

For the local real-stack run on Windows, use `python backend/scripts/run_real_stack_e2e.py` from the repository root after installing Python/frontend dependencies and Playwright Chromium. It requires Docker Compose and free ports 5433, 27018, 8001, and 5174. It leaves the normal app ports untouched, creates no persistent volumes, verifies the empty database identity before migrations, and stops only its uniquely named test service project.

## Related documents

- `../../frontend/README.md` — frontend and Playwright setup.
- `../testing/TEST_STRATEGY.md` — test boundaries and commands.
- `../../backend/README.md` — backend test requirements.
