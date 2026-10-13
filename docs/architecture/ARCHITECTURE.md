# NexusMatch architecture

## Runtime components

- **FastAPI** provides the versioned HTTP API and OpenAPI documentation.
- **PostgreSQL** is the source of truth for player/team identities, registrations, tournaments, brackets, and match results.
- **MongoDB** is reserved for telemetry and flexible event documents; the tournament engine does not use it for transactional state.
- **React/TypeScript** is the planned frontend layer and does not participate in the backend bracket lifecycle.

## Backend boundaries

- `backend/app/api/v1/endpoints/` contains HTTP routing, request validation, SQL orchestration, and HTTP error mapping.
- `backend/app/schemas/` contains the Pydantic request and response contracts.
- `backend/app/db/` owns shared database connection and health-check behavior.
- `backend/app/services/bracket.py` contains deterministic, database-independent bracket layout rules.
- `backend/scripts/migrate.py` applies immutable, numbered SQL migrations from `database/sql/schema/`.
- `backend/tests/` contains unit tests and PostgreSQL-backed integration tests.

The project has not introduced a generic repository or service framework. Bracket layout calculations are pure functions; operations requiring transactional integrity stay in the API handler and PostgreSQL transaction.

## Tournament and bracket flow

1. The registration API accepts entries while a tournament is `registration_open`; PostgreSQL validates capacity, competitor type, uniqueness, and foreign keys.
2. Bracket generation locks the tournament row, accepts only `single_elimination` tournaments still open for registration, and selects `approved` registrations ordered by `registered_at`, then `registration_id`.
3. The engine persists a full power-of-two bracket in the existing `matches` and `match_participants` tables. Bye matches are marked completed with `is_bye=true`, one participant, no score, and no winner-result flag. The entrant is placed in the correct next-round slot immediately.
4. Result submission locks the tournament and match, validates the two persisted participants and the non-tied scores, records completion, advances the winner into a unique next-round slot, and marks the tournament completed after the final. These writes commit or roll back together.
5. The migration adds participant slot uniqueness, a single-winner-per-match index, nonnegative score validation, bye state, and a registration mutation guard after bracket generation. Existing tournament/registration/match composite foreign keys continue to enforce tournament isolation.

PostgreSQL row locks serialize concurrent bracket generation and result submissions. The database unique slot index prevents two concurrent or faulty writes from occupying the same match slot. Registration mutations are blocked after bracket creation so match participants cannot be changed underneath a live bracket; the API also locks tournament status and format against manual changes.

## Configuration and verification

Use `.env.example` as a template for local configuration; do not commit `.env` secrets. Start local services with `docker compose up -d postgres mongodb`, apply migrations with `python backend/scripts/migrate.py`, and run tests only with `NEXUSMATCH_TEST_DATABASE_URL` pointing to a dedicated disposable database.

From the repository root:

```powershell
ruff check backend
$env:NEXUSMATCH_TEST_DATABASE_URL = "postgresql://<user>:<password>@localhost:5432/<dedicated_test_database>"
python -m pytest backend/tests -q
```

CI provisions PostgreSQL, applies the numbered migrations, runs Ruff, and executes the backend test suite.

## Current limitations

- Authentication and authorization are not implemented; API operations use the repository's current trusted local-development model.
- Only single elimination is generated. Double elimination, round robin, and Swiss formats remain outside the engine.
- The score model records one numeric score per competitor and chooses the higher score; tie-breaks, sets/maps, and result correction workflows are not implemented.
- Teams have no captain, roster-size policy, or roster snapshot associated with a registration. Team membership changes do not rewrite bracket entries.
- MongoDB telemetry documents and retention policies remain future work.

## Related documents

- `../../backend/API.md` — API endpoints and request/response contracts.
- `../../backend/API_TOURNAMENTS.md` — tournament lifecycle and bracket behavior.
- `../database/DATABASE_DESIGN.md` — relational schema, constraints, and bracket persistence.
- `../../database/sql/schema/005_single_elimination_brackets.sql` — bracket integrity migration.
