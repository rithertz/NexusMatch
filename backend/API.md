# NexusMatch API

Base path: `/api/v1`

Interactive documentation is available at `/docs` while the API server is running.

## Registration rules

- A registration references exactly one player or team.
- Individual tournaments require a player; team tournaments require a team.
- New registrations are accepted only when tournament status is `registration_open`.
- New registrations start as `pending`.
- `pending` and `approved` registrations consume capacity.
- `rejected` and `withdrawn` registrations do not consume capacity.
- PostgreSQL enforces integrity and capacity under concurrent requests.

## Endpoints

### Player endpoints

`POST /api/v1/players`

Create a player profile:

```json
{
  "username": "siren",
  "display_name": "Siren Nova",
  "email": "siren@example.com"
}
```

`GET /api/v1/players?limit=20&offset=0`

List players with basic pagination and optional filters for `username`, `display_name`, and `email`.

`GET /api/v1/players/{player_id}`

Fetch a specific player profile. Returns `404` when the player is not found.

`PATCH /api/v1/players/{player_id}`

Update profile fields such as `display_name`, `username`, or `email`.

### Team endpoints

`POST /api/v1/teams`

Create a team:

```json
{
  "team_name": "Storm Breakers"
}
```

`GET /api/v1/teams?limit=20&offset=0`

List teams with pagination and an optional `team_name` filter.

`GET /api/v1/teams/{team_id}`

Fetch a team by ID. Returns `404` when the team is absent.

`PATCH /api/v1/teams/{team_id}`

Update a team name.

`GET /api/v1/teams/{team_id}/members`

List the members currently assigned to the team.

`POST /api/v1/teams/{team_id}/members`

Add a player to a team:

```json
{
  "player_id": 42
}
```

Responses:
- `201 Created` when membership is inserted.
- `404 Not Found` when the team or player does not exist.
- `409 Conflict` when the player is already on the team.

`DELETE /api/v1/teams/{team_id}/members/{player_id}`

Remove a player from a team. Returns `404` if that player is not a current member.

### Single-elimination bracket endpoints

#### Generate a bracket

`POST /api/v1/tournaments/{tournament_id}/bracket`

The tournament must use `single_elimination`, be in `registration_open` status, and have at least two approved registrations. Only approved registrations enter the bracket; pending, rejected, and withdrawn registrations are excluded. Registrations are ordered by `registered_at`, then `registration_id`.

The response is `201 Created` and contains all rounds and persisted matches. A power-of-two bracket with `N` entrants contains `N - 1` matches. Other entrant counts are padded to the next power of two; the earliest registrations receive the required first-round byes. A bye is represented by a completed match with `is_bye: true`, one participant, no score, and no winner result. That competitor is placed into its next-round slot automatically.

Responses:
- `404 Not Found` — tournament does not exist.
- `409 Conflict` — tournament is not open, fewer than two registrations are approved, or a bracket already exists.
- `422 Unprocessable Entity` — the tournament format is not single elimination.

#### Retrieve a bracket

`GET /api/v1/tournaments/{tournament_id}/bracket`

Returns the persisted bracket grouped into rounds. Each match includes its ID, round and match numbers, status, bye flag, timestamps, winner registration ID (if decided), and participants with slot, competitor type/ID, display name, score, and winner flag.

Returns `404 Not Found` if the tournament or generated bracket does not exist.

Example response:

```json
{
  "tournament_id": 12,
  "rounds": [
    {
      "round_number": 1,
      "matches": [
        {
          "match_id": 100,
          "round_number": 1,
          "match_number": 1,
          "status": "scheduled",
          "is_bye": false,
          "scheduled_at": null,
          "started_at": null,
          "completed_at": null,
          "winner_registration_id": null,
          "participants": [
            {
              "registration_id": 45,
              "slot_number": 1,
              "competitor_type": "player",
              "competitor_id": 45,
              "display_name": "Siren Nova",
              "score": null,
              "is_winner": false
            },
            {
              "registration_id": 46,
              "slot_number": 2,
              "competitor_type": "player",
              "competitor_id": 46,
              "display_name": "Nova Echo",
              "score": null,
              "is_winner": false
            }
          ]
        }
      ]
    }
  ]
}
```

#### Submit a match result

`POST /api/v1/tournaments/{tournament_id}/matches/{match_id}/result`

Submit scores for both persisted match participants. The higher score must match the specified winner; ties and negative scores are invalid.

```json
{
  "winner_registration_id": 45,
  "scores": [
    { "registration_id": 45, "score": 2 },
    { "registration_id": 46, "score": 1 }
  ]
}
```

The API derives the next-round slot from the persisted round/match position; clients cannot choose the next opponent. Recording the scores, completing the match, advancing the winner, and completing the tournament after the final occur in one transaction. Completed results cannot be overwritten.

Responses:
- `200 OK` — result recorded and match returned.
- `404 Not Found` — tournament or match in that tournament does not exist.
- `409 Conflict` — tournament or match is not playable, match is a bye/already completed, or bracket advancement conflicts with persisted state.
- `422 Unprocessable Entity` — malformed/tied scores, mismatched score registration IDs, or winner is not a match participant.

After bracket generation, registration changes and changes to the tournament status or format are rejected. Authentication and authorization are not implemented; the API retains the existing trusted development model.

### Create a registration

`POST /api/v1/registrations`

Individual request:

```json
{
  "tournament_id": 12,
  "player_id": 45
}
```

Team request:

```json
{
  "tournament_id": 12,
  "team_id": 8
}
```

Responses:
- `201 Created` — registration created.
- `404 Not Found` — a referenced tournament, player, or team does not exist.
- `409 Conflict` — duplicate registration, closed tournament, or full tournament.
- `422 Unprocessable Entity` — invalid payload or competitor type mismatch.

### List registrations

`GET /api/v1/registrations`

Query parameters:

| Parameter | Required | Description |
|---|---|---|
| `tournament_id` | No | Filter by tournament ID |
| `status` | No | Filter by `pending`, `approved`, `rejected`, or `withdrawn` |
| `limit` | No | Page size from 1 to 100; default 50 |
| `offset` | No | Number of records to skip; default 0 |

Example:

```http
GET /api/v1/registrations?tournament_id=12&status=pending&limit=20&offset=0
```

Responses:
- `200 OK` — returns a JSON array, possibly empty.
- `422 Unprocessable Entity` — invalid query parameter.

### Get a registration

`GET /api/v1/registrations/{registration_id}`

Example:

```http
GET /api/v1/registrations/101
```

Responses:
- `200 OK` — registration returned.
- `404 Not Found` — registration does not exist.

### Approve or reject a registration

`PATCH /api/v1/registrations/{registration_id}/status`

Approve:

```json
{
  "status": "approved"
}
```

Reject:

```json
{
  "status": "rejected"
}
```

Only a registration currently in `pending` status can be approved or rejected.

Responses:
- `200 OK` — status updated.
- `404 Not Found` — registration does not exist.
- `409 Conflict` — registration is no longer pending.
- `422 Unprocessable Entity` — invalid status value.

### Withdraw a registration

`POST /api/v1/registrations/{registration_id}/withdraw`

No request body is required.

Example:

```http
POST /api/v1/registrations/101/withdraw
```

Only `pending` or `approved` registrations can be withdrawn.

Responses:
- `200 OK` — registration withdrawn.
- `404 Not Found` — registration does not exist.
- `409 Conflict` — registration cannot be withdrawn from its current status.

## Registration response format

Successful create, get, status-update, and withdrawal operations return a registration object similar to:

```json
{
  "registration_id": 101,
  "tournament_id": 12,
  "player_id": 45,
  "team_id": null,
  "status": "pending",
  "registered_at": "2026-10-12T09:00:00Z"
}
```

The timestamp is illustrative. PostgreSQL supplies the actual value.

## Concurrency and integrity

PostgreSQL is the source of truth for registration integrity and tournament capacity. Database triggers serialize competing registration attempts for capacity. Status-changing endpoints should lock the target registration row before checking and applying a status transition. These behaviors should be verified through database and HTTP integration tests.
