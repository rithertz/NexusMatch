# Tournament API

Base path: `/api/v1/tournaments`

## Create a tournament

`POST /api/v1/tournaments`

```json
{
  "name": "VCT Campus Open",
  "game_name": "Valorant",
  "tournament_type": "team",
  "format": "single_elimination",
  "max_entries": 16,
  "starts_at": null
}
```

Returns `201 Created`. The database default status is `draft`.
`name` is required, trimmed before persistence, must not be blank, and must contain
3–150 characters. Names are returned as the canonical display label; tournament IDs
remain stable route and relationship identifiers.

## List tournaments

`GET /api/v1/tournaments`

Optional query parameters:
- `tournament_type`: `individual` or `team`
- `status`: `draft`, `registration_open`, `in_progress`, `completed`, or `cancelled`
- `game_name`: case-insensitive exact game-name filter
- `limit`: 1–100, default 50
- `offset`: non-negative, default 0

## Get one tournament

`GET /api/v1/tournaments/{tournament_id}`

Returns `404` when the tournament does not exist.

## Update a tournament

`PATCH /api/v1/tournaments/{tournament_id}`

Only supplied fields are changed. Supported fields: `name`, `game_name`, `format`,
`max_entries`, `starts_at`, and `status`. `tournament_type` is immutable through this
endpoint to avoid invalidating existing registrations. PostgreSQL constraints and triggers
remain authoritative for capacity and referential integrity.

Set `{"status":"registration_open"}` through this endpoint to open registration. The
organizer UI reflects the returned server state and does not open registration locally.

An empty update returns `422`. Database integrity conflicts return `409`.

## Single-elimination brackets

### Generate

`POST /api/v1/tournaments/{tournament_id}/bracket`

Generation requires an open single-elimination tournament with at least two approved registrations. The engine orders approved entries by `registered_at`, then `registration_id`. For a non-power-of-two field, the earliest registrations receive first-round byes. All rounds and matches are persisted in the existing match tables.

The endpoint returns `201` and the full persisted bracket. It returns `409` for a tournament in the wrong lifecycle state, insufficient approved entrants, or duplicate generation; non-single-elimination formats return `422`.

### Retrieve

`GET /api/v1/tournaments/{tournament_id}/bracket`

Returns rounds and matches with participant slots, competitor labels, scores, winner, status, and bye state. A tournament without a generated bracket returns `404`.

### Record a result

`POST /api/v1/tournaments/{tournament_id}/matches/{match_id}/result`

Example:

```json
{
  "winner_registration_id": 45,
  "scores": [
    { "registration_id": 45, "score": 2 },
    { "registration_id": 46, "score": 1 }
  ]
}
```

Scores are nonnegative, distinct, and must reference the two persisted participants; the higher score must identify the winner. Bye and completed matches cannot accept results. In one transaction the API records the result, completes the match, advances the winner to the next derived slot, and marks the tournament completed after the final. Completed results cannot be corrected through this API. The tournament and match locks plus PostgreSQL's unique slot constraint serialize concurrent submissions.

The engine creates a complete power-of-two bracket of `P - 1` matches for `P` slots. Bye matches are completed with `is_bye=true` and one participant, but no fabricated score or winner flag. Registration changes are prevented once match rows exist; tournament format and status can no longer be changed manually after generation.

See [API.md](./API.md) for complete request/response shapes and status-code details.

## Common status codes

- `201`: tournament created
- `200`: query, update, or match result succeeded
- `404`: tournament or referenced record not found
- `409`: database integrity conflict
- `422`: invalid request payload or query parameters
