# NexusMatch

A learning-oriented, full-stack esports tournament management system and
Database Systems course project.

## Project status

**Phase:** Player and Team Management (Milestone 4) implemented and verified.

## Stack and verified components

- Frontend: React and TypeScript
- API: Python and FastAPI
- Relational database: PostgreSQL
- Document database: MongoDB
- Local services: Docker Desktop and Docker Compose
- Quality: automated tests and GitHub Actions CI

The project currently includes:

- FastAPI services for tournaments, registrations, players, and teams.
- PostgreSQL-backed relational integrity for player profiles, teams, team membership, tournaments, and registrations.
- Docker Compose services for PostgreSQL and MongoDB.
- Automated backend tests covering health, migration runner, tournament, registration, player, and team flows.

## Learning approach

Build incrementally, understand each design decision, test each milestone,
document it, and push small, meaningful commits to GitHub.

## Getting started

1. Create or update a local `.env` file from the sample environment values used by the backend.
2. Start the required services with `docker compose up -d postgres mongodb`.
3. Apply the current schema with `python backend/scripts/migrate.py`.
4. Run the backend checks with `python -m pytest backend/tests -q`.

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
