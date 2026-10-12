# NexusMatch backend

> Status: Player and team APIs are implemented and covered by database-backed integration tests.

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

## Implementation notes

- The project keeps PostgreSQL as the transactional source of truth.
- DB integrity rules remain enforced in the database; application validation is used for clearer HTTP responses and consistent validation.
- The API follows the existing versioned `/api/v1` pattern and uses the shared database dependency.

## Verification

Run the backend suite from the repository root:

```powershell
$env:NEXUSMATCH_TEST_DATABASE_URL = "postgresql://nexusmatch:change_me_locally@localhost:5432/nexusmatch"
python -m pytest backend/tests -q
```

## Related documents

- `../README.md`
- `API.md`
- `../docs/database/DATABASE_DESIGN.md`
