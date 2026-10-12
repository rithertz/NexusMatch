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

An empty update returns `422`. Database integrity conflicts return `409`.

## Common status codes

- `201`: tournament created
- `200`: query or update succeeded
- `404`: tournament or referenced record not found
- `409`: database integrity conflict
- `422`: invalid request payload or query parameters
