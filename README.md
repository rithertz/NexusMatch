# NexusMatch

**A learning-oriented, full-stack esports tournament management system and Database Systems course project.**

NexusMatch models tournament operations: discover tournaments, register players or teams, manage registrations, generate a persisted single-elimination bracket, and submit match results that advance winners. The project emphasizes relational integrity, transaction-safe changes, reproducible migrations, automated testing, and incremental engineering.

> **Status:** The tournament-management MVP and frontend Playwright E2E setup are implemented. GitHub Actions CI is passing. Current Playwright tests mock API responses; they complement, but do not replace, live browser-to-backend integration tests.
**Phase:** Frontend and end-to-end integration (Milestone 6) implemented.

## Contents

- [Highlights](#highlights)
- [Technology stack](#technology-stack)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Features and current scope](#features-and-current-scope)
- [Data model](#data-model)
- [Prerequisites](#prerequisites)
- [Local setup on Windows](#local-setup-on-windows)
- [Run the application](#run-the-application)
- [API overview](#api-overview)
- [Testing and CI](#testing-and-ci)
- [Database safety](#database-safety)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Development workflow](#development-workflow)
- [Limitations and next steps](#limitations-and-next-steps)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Highlights

- Tournament discovery with search and status/game filters.
- Tournament detail pages and registration for individual players or teams.
- Registration status management and capacity-aware rules.
- Persisted single-elimination brackets, including byes.
- Match-result submission with score validation and winner advancement.
- PostgreSQL-backed relational integrity and transaction-aware bracket/result operations.
- PostgreSQL and MongoDB development services orchestrated with Docker Compose.
- FastAPI backend with OpenAPI documentation.
- React, TypeScript, and Vite frontend.
- Backend tests, frontend unit tests, static checks, production build, and Playwright browser tests in CI.

## Technology stack

| Area | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite |
| Routing | React Router |
| Frontend quality | TypeScript compiler, ESLint, Vitest |
| Browser E2E | Playwright with Chromium |
| Backend | Python, FastAPI |
| Relational database | PostgreSQL 17 |
| Document database service | MongoDB 8 |
| Database access | Psycopg |
| Schema evolution | Ordered SQL migrations |
| Local services | Docker Compose |
| CI | GitHub Actions |

Consult the dependency manifests and Compose configuration for exact versions and service definitions in the current checkout.

## Architecture

```text
Browser
  |
  v
React / TypeScript frontend (Vite, normally :5173)
  |
  | HTTP /api/v1/*
  v
FastAPI backend (normally :8000)
  |
  +---- PostgreSQL: relational tournament and bracket state
  |
  +---- MongoDB: provisioned project document-database service
```

The frontend and backend are separate applications. Vite serves the frontend during development. The browser calls the configured versioned API. FastAPI validates requests and applies business rules; PostgreSQL stores the relational tournament state. MongoDB is provisioned as a project service—consult the implementation before assuming a particular feature persists data there.

### Typical request flow

1. The user opens the frontend and browses tournaments.
2. The frontend sends a request under `/api/v1`.
3. FastAPI validates the request and enforces workflow rules.
4. PostgreSQL stores or retrieves tournament, registration, bracket, and result data.
5. The frontend renders the response and refreshes relevant views after successful actions.

## Repository layout

```text
NexusMatch/
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   ├── core/
│   │   ├── schemas/
│   │   └── main.py
│   ├── scripts/migrate.py
│   ├── tests/
│   ├── requirements.txt
│   └── API_TOURNAMENTS.md
├── database/sql/schema/       # Ordered SQL migrations
├── docs/
│   ├── architecture/
│   ├── database/
│   ├── devops/
│   ├── learning/
│   ├── project/
│   └── testing/
├── frontend/
│   ├── src/app/
│   ├── src/lib/
│   ├── src/types/
│   ├── tests/unit/
│   ├── tests/e2e/
│   ├── playwright.config.ts
│   ├── package.json
│   └── README.md
├── docker-compose.yml
├── README.md
└── CONTRIBUTING.md
```

This is a guide to the principal areas; consult the actual repository tree if files or directories evolve.

## Features and current scope

### Tournament discovery
- Lists tournaments returned by the API.
- Searches by tournament name or game.
- Filters by status and game.
- Provides loading, error/retry, and empty-result states.

### Tournament details and registration
- Displays tournament format, game, status, start date, and entry limit.
- Supports registration with an existing player or team record.
- Displays registration status and resolves participant names when corresponding player/team records are available.
- Shows an explicit fallback when a participant name cannot be resolved.
- Registration acceptance is governed by backend rules, including tournament status and capacity.

### Bracket management
- Supports persisted single-elimination brackets.
- Represents rounds, matches, participant slots, and byes.
- Displays participants, scores, and winners.
- Accepts match results through the backend and advances winners according to server-side rules.
- Bracket generation has backend preconditions; see `backend/API_TOURNAMENTS.md` and the database design document.

### Automated quality
- Backend linting and tests.
- Frontend unit tests.
- Typechecking and linting.
- Production frontend build.
- Playwright Chromium tests for discovery, tournament detail, participant names, bracket rendering, empty states, loading, and API errors.
- GitHub Actions runs frontend and backend jobs independently.

## Data model

PostgreSQL holds the relational tournament state. The schema lives in `database/sql/schema/`; `backend/scripts/migrate.py` applies migrations in order and records migration history.

Core concepts include:

- **Tournaments:** competition metadata, format, status, start time, and capacity.
- **Players:** individual competitors.
- **Teams:** team competitors.
- **Team membership:** relationships between teams and players.
- **Registrations:** player/team entry into a tournament, status, and timestamp.
- **Matches:** persisted bracket matches, round/match numbering, status, bye state, and winner.
- **Match participants:** registration slots and score/winner information.

Relational constraints protect valid relationships and tournament isolation. Backend operations enforce workflow rules that span records. See [`docs/database/DATABASE_DESIGN.md`](docs/database/DATABASE_DESIGN.md) for the detailed schema rationale.

Apply migrations only after verifying the configured database:

```powershell
python backend/scripts/migrate.py
```

## Prerequisites

Install Git, Python 3.13, Node.js 24 with npm, Docker Desktop with Docker Compose, and a modern browser. CI currently uses Python 3.13 and Node 24.

```powershell
git --version
python --version
node --version
npm --version
docker --version
docker compose version
```

## Local setup on Windows

Commands below assume Windows PowerShell and a repository clone.

### 1. Clone

```powershell
git clone https://github.com/rithertz/NexusMatch.git
Set-Location NexusMatch
```

For an existing checkout, update the shared branch before starting new work:

```powershell
git switch main
git pull origin main
```

### 2. Configure environment

Inspect the repository for its environment template (for example, `.env.example`) and copy it to `.env` only if the template exists and a local `.env` is not already present. Configure the variables required by `backend/app/core/config.py` and the Compose file.

**Never commit `.env`, passwords, tokens, or connection strings containing credentials.** Do not paste secrets into issues, PRs, screenshots, or shared logs.

### 3. Start database services

From the repository root:

```powershell
docker compose up -d postgres mongodb
docker compose ps
```

The current development setup has used containers named `nexusmatch-postgres` and `nexusmatch-mongodb`; confirm the actual service/container names with `docker compose ps`.

### 4. Set up the backend

From the repository root:

```powershell
python -m venv backend/.venv
.ackend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

If activation is blocked, invoke the virtual environment's Python directly:

```powershell
.ackend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Configure the database connection, confirm the target database name, then apply migrations:

```powershell
python backend/scripts/migrate.py
```

### 5. Set up the frontend

Open a second terminal:

```powershell
Set-Location frontend
npm ci
```

`npm ci` installs the versions recorded in `package-lock.json`.

### 6. Run backend and frontend

**Terminal A — backend**, from the repository root with the backend virtual environment active:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

**Terminal B — frontend:**

```powershell
Set-Location frontend
npm run dev
```

Typical local URLs:

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/api/v1/health`

If the frontend cannot reach the API, check the configured Vite API base URL and the backend's actual host/port.

## API overview

The API is versioned under `/api/v1`. The running Swagger UI at `http://localhost:8000/docs` is the best source for exact paths, request schemas, response models, validation rules, and status codes.

Implemented API areas include:

| Resource | Capability |
|---|---|
| Health | Check application/dependency status |
| Tournaments | List, retrieve, create, and update tournaments |
| Players | List player records |
| Teams | List teams and inspect team members |
| Registrations | List, create, update status, and withdraw registrations |
| Brackets | Retrieve or generate a tournament bracket |
| Match results | Submit scores and a winner |

See [`backend/API_TOURNAMENTS.md`](backend/API_TOURNAMENTS.md) for the project's API details. The running OpenAPI contract takes precedence over this summary.

## Testing and CI

Run commands from the specified directory. Backend tests must target a dedicated disposable test database.

### Backend

From the repository root with the backend virtual environment active:

```powershell
ruff check backend
python -m pytest backend/tests -v
```

Apply migrations to the intended test database when required:

```powershell
python backend/scripts/migrate.py
```

### Frontend

From `frontend/`:

```powershell
npm ci
npm test
npm run typecheck
npm run lint
npm run build
```

### Playwright

Install Chromium once:

```powershell
npm run e2e:install
```

Run browser tests:

```powershell
npm run e2e
```

**Important:** current Playwright tests intercept API requests and return fixtures. They verify frontend rendering and interactions without requiring live FastAPI calls or database writes. They do not prove full browser-to-backend integration.

### GitHub Actions

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

- **Frontend checks:** dependency installation, typecheck, lint, unit tests, production build, Chromium installation, and Playwright E2E.
- **Backend checks:** PostgreSQL 17 service, Python dependency installation, Ruff, migrations, and backend tests.

A green CI run means the configured jobs passed for that commit; it does not prove every possible workflow or deployment configuration.

## Database safety

Database safety is mandatory.

- Use a dedicated disposable database for automated tests.
- Set `NEXUSMATCH_TEST_DATABASE_URL` to the intended test database as expected by the test configuration.
- Confirm the target database name before running migrations or tests.
- Never use a manually populated development database as an automated-test target.
- Do not drop databases, reset schemas, remove Docker volumes, or run destructive cleanup without explicitly reviewing the target and consequences.
- `docker compose down -v` can remove Compose-managed volumes and destroy persistent data; do not use it casually.
- Keep credentials out of source control and logs.

Before database-related commands, inspect the target database name without printing the full connection string. Never share a DSN containing a password.

## Configuration

Exact settings are defined by `backend/app/core/config.py`, the environment template, and `docker-compose.yml`. Common PostgreSQL settings include:

| Variable | Purpose |
|---|---|
| `POSTGRES_HOST` | PostgreSQL hostname |
| `POSTGRES_PORT` | PostgreSQL port |
| `POSTGRES_DB` | Application database name |
| `POSTGRES_USER` | PostgreSQL role |
| `POSTGRES_PASSWORD` | Database password; keep secret |
| `NEXUSMATCH_TEST_DATABASE_URL` | Dedicated database DSN for automated tests |

The frontend API base URL is configured through Vite environment configuration (for example, `VITE_API_BASE_URL`). Confirm exact names/defaults in the current code and environment template before changing configuration.

## Troubleshooting

### Frontend loads, but API requests fail
- Confirm FastAPI is running.
- Open `http://localhost:8000/api/v1/health`.
- Check the frontend API base URL.
- Inspect browser developer tools and backend logs for the failing request.

### PostgreSQL connection/authentication fails
- Run `docker compose ps`.
- Inspect service logs with `docker compose logs postgres`.
- Verify host, port, database, username, and password.
- Confirm the app and migration runner target the intended database.
- Do not drop or recreate a database containing useful data to resolve a connection issue.

### Migration fails
- Read the first database error and identify the migration.
- Confirm the target database before retrying.
- Inspect migration history and runner output.
- Prefer a new forward migration over casually editing a migration that has already been applied.

### Backend tests fail
- Confirm the virtual environment is active.
- Install `backend/requirements.txt`.
- Check that `NEXUSMATCH_TEST_DATABASE_URL` points to a dedicated test database with the required migrations.
- Do not point tests at a manually populated database just to make them pass.

### Playwright cannot launch Chromium
```powershell
npm run e2e:install
npm run e2e
```

For failing browser tests, inspect Playwright traces and screenshots generated on failure and open the failed CI job logs.

### Port already in use
Identify the process using the port before stopping it, or configure an alternate port and update dependent URLs accordingly.

## Development workflow

Use focused feature branches and pull requests.

### Start work

```powershell
git switch main
git pull origin main
git switch -c feat/short-description
```

Examples: `feat/registration-validation`, `fix/bracket-rendering`, `test/live-integration`.

### Validate and commit

```powershell
git status --short --branch
git diff --check
git diff
```

Stage explicit paths when practical, then inspect the staged changes:

```powershell
git add path/to/file another/path
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "feat: describe the change"
git push -u origin feat/short-description
```

Open a PR targeting `main`, wait for CI, and review the combined diff. After merge, the feature branch can normally be deleted; keep `main` as the shared baseline.

Commit prefixes:
- `feat:` new functionality
- `fix:` bug fix
- `test:` tests
- `docs:` documentation
- `refactor:` code restructuring
- `chore:` tooling and maintenance

## Limitations and next steps

Treat these as limitations/future work unless code and tests have changed:

- **Live browser-to-backend integration:** Playwright currently mocks API responses. Add separate integration coverage using an isolated database.
- **Authentication and authorization:** the frontend explicitly indicates authentication is not implemented. Add identity and server-side permission checks before production use.
- **Participant lookup pagination:** the participant view currently requests up to 100 registrations and up to 100 players or teams for name resolution. Larger datasets may need pagination or a backend response that includes competitor names.
- **Production deployment:** local Compose and CI are development/verification infrastructure, not a full production deployment.
- **Operations:** define production logging, monitoring, backup/restore, and secret management before deployment.
- **MongoDB usage:** MongoDB is provisioned as a service; verify current application code before assuming it is used by a particular feature.

Update this section when limitations are resolved. Do not describe planned work as implemented.

## Documentation

- [`backend/API_TOURNAMENTS.md`](backend/API_TOURNAMENTS.md) — tournament API details.
- [`docs/database/DATABASE_DESIGN.md`](docs/database/DATABASE_DESIGN.md) — relational schema and design rationale.
- [`docs/testing/TEST_STRATEGY.md`](docs/testing/TEST_STRATEGY.md) — testing strategy.
- [`docs/devops/CI_CD.md`](docs/devops/CI_CD.md) — CI/CD workflow.
- [`frontend/README.md`](frontend/README.md) — frontend scripts and testing.
- [`docs/project/PROJECT_CHARTER.md`](docs/project/PROJECT_CHARTER.md) — project purpose and scope.
- [`docs/project/REQUIREMENTS.md`](docs/project/REQUIREMENTS.md) — requirements.
- [`docs/project/ROADMAP.md`](docs/project/ROADMAP.md) — roadmap.
- [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) — architecture overview.
- [`docs/learning/LEARNING_ROADMAP.md`](docs/learning/LEARNING_ROADMAP.md) — learning-oriented plan.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution guidance.

If a linked document is absent in a checkout, inspect the repository tree and update the link list rather than assuming it exists.

## Contributing

Contributions should be focused, tested, and documented. Before opening a PR:

1. Describe the behavior being added or changed.
2. Put schema changes in forward migrations.
3. Add or update backend/frontend tests.
4. Run the relevant local checks.
5. Confirm no secrets or local data are included.
6. Update API/architecture documentation when behavior changes.
7. Describe verification and known limitations in the PR.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for repository-specific guidance.

## Security

NexusMatch is a course project and should not be considered production-hardened without further review.

- Never commit secrets, tokens, passwords, private connection strings, or populated database dumps.
- Keep `.env` files local; commit only safe example templates.
- Validate input and enforce permissions on the backend, not only in the UI.
- Use isolated test databases and avoid destructive database commands against valuable data.
- Review dependency and deployment security before exposing services publicly.
- Report vulnerabilities privately to maintainers rather than publishing exploit details in an issue.

See the repository's GitHub **Security** tab for current disclosure options and policy.

## License

This README does not assert a license. Check for a `LICENSE` file and confirm project ownership/licensing before reusing or redistributing the code.
