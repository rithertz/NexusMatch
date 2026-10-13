# NexusMatch

A learning-oriented, full-stack esports tournament management system and
Database Systems course project.

## Project status

**Phase:** Frontend and end-to-end integration (Milestone 6) implemented.

## Stack and verified components

- Frontend: React, TypeScript, Vite, and a responsive tournament operations UI
- API: Python and FastAPI
- Relational database: PostgreSQL
- Document database: MongoDB
- Local services: Docker Desktop and Docker Compose
- Quality: automated tests and GitHub Actions CI

The project currently includes:

- FastAPI services for tournaments, registrations, players, and teams.
- Persisted single-elimination brackets, bye advancement, match-result submission, and tournament completion.
- PostgreSQL-backed relational integrity for players, teams, registrations, match slots, and cross-tournament isolation.
- Docker Compose services for PostgreSQL and MongoDB.
- Backend unit and PostgreSQL integration tests covering health, migrations, tournament, registration, player, team, and bracket flows.
- Browser client for discovery, registration, roster inspection, organizer lifecycle controls, health status, persisted brackets, and server-confirmed match results.

## Learning approach

Build incrementally, understand each design decision, test each milestone,
document it, and push small, meaningful commits to GitHub.

## Getting started

1. Create or update a local `.env` file from `.env.example`; keep real credentials out of source control.
2. Start the required services with `docker compose up -d postgres mongodb`.
3. Apply the current schema with `python backend/scripts/migrate.py`.
4. Set `NEXUSMATCH_TEST_DATABASE_URL` to a separate disposable PostgreSQL test database that has these migrations applied.
5. Run the backend checks with `python -m pytest backend/tests -q` and `ruff check backend`.
6. In a second terminal, run `cd frontend; npm install; npm run dev`. See [frontend/README.md](./frontend/README.md) for API configuration and frontend checks.

Bracket generation only accepts open single-elimination tournaments with at least two approved registrations. Generated brackets are immutable with respect to registration changes; match completion advances winners transactionally. See [backend/API.md](./backend/API.md), [backend/API_TOURNAMENTS.md](./backend/API_TOURNAMENTS.md), and [docs/database/DATABASE_DESIGN.md](./docs/database/DATABASE_DESIGN.md).

## Documentation

Start with:

- `docs/project/PROJECT_CHARTER.md`
- `docs/project/REQUIREMENTS.md`
- `docs/project/ROADMAP.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/learning/LEARNING_ROADMAP.md`
- `CONTRIBUTING.md`

## Evidence and performance

Performance figures will be published only after reproducible measurements.
Targets and measured results will be labelled separately.
