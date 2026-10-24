# NexusMatch backend

> Status: Player/team management, registrations, tournaments, and the single-elimination engine are implemented.

## Purpose

The backend exposes the NexusMatch API using FastAPI and PostgreSQL. It is responsible for tournament lifecycle management, registration integrity, and the player/team domain that supports both individual and team competitions.

## Current API surface

- `POST /api/v1/players` — create a player profile.
- `GET /api/v1/players` — list players with pagination and filtering.
- `GET /api/v1/players/{player_id}` — fetch a single player.
- `PATCH /api/v1/players/{player_id}` — update profile details.
- `POST /api/v1/teams` — create a team.
- `GET /api/v1/teams` — list teams with pagination and filtering.
- `GET /api/v1/teams/{team_id}` — fetch a team.
- `PATCH /api/v1/teams/{team_id}` — update team details.
- `GET /api/v1/teams/{team_id}/members` — list team membership.
- `POST /api/v1/teams/{team_id}/members` — add a player to a team.
- `DELETE /api/v1/teams/{team_id}/members/{player_id}` — remove a player from a team.
- `POST /api/v1/registrations` and related routes — manage tournament registrations while respecting PostgreSQL constraints and capacity checks.
- `POST /api/v1/tournaments/{tournament_id}/bracket` — generate a deterministic bracket from approved registrations.
- `GET /api/v1/tournaments/{tournament_id}/bracket` — retrieve matches grouped by round.
- `POST /api/v1/tournaments/{tournament_id}/matches/{match_id}/result` — complete a match, advance its winner, and complete the tournament after the final.

## Implementation notes

- The project keeps PostgreSQL as the transactional source of truth.
- DB integrity rules remain enforced in the database; application validation is used for clearer HTTP responses and consistent validation.
- PostgreSQL row locks serialize bracket creation and results. Slot uniqueness and cross-tournament foreign keys remain database-enforced.
- Approved registrations are ordered by approval-independent registration time (`registered_at`, then `registration_id`); the earliest entrants receive any required first-round byes.
- Bye matches are persisted as completed with `is_bye=true`, have one participant and no invented score or winner result, and advance that participant to the appropriate next-round slot.
- Match corrections, tie scores, and scores not corresponding to the two persisted participants are rejected. There is no authentication or authorization layer yet.
- The API follows the existing versioned `/api/v1` pattern and uses the shared database dependency.

## Verification

Run the backend suite from the repository root against a dedicated disposable PostgreSQL database. The test configuration accepts only local databases named `nexusmatch_ci_isolated_test` or `nexusmatch_e2e_test`; it verifies the actual connected database before tests run and rejects protected names. Do not point this variable at a manually maintained or production database:

```powershell
$env:NEXUSMATCH_TEST_DATABASE_URL = "postgresql://nexusmatch_ci:<password>@localhost:5432/nexusmatch_ci_isolated_test"
python -m pytest backend/tests -q
ruff check backend
```

For a fully configured local run without editing `.env`, install dependencies and run `python backend/scripts/run_real_stack_e2e.py` from the repository root. It provisions an ephemeral, empty test database, applies/checks migrations, runs the full backend suite, then executes the real browser integration test. It refuses if the database identity cannot be verified and never connects to the development database.

## Related documents

- `../README.md`
- `API.md`
- `API_TOURNAMENTS.md`
- `../docs/database/DATABASE_DESIGN.md`
- `../docs/architecture/ARCHITECTURE.md`
