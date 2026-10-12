# NexusMatch Registration API

Base path: `/api/v1/registrations`

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

### 1. Create a registration

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

### 2. List registrations

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

### 3. Get a registration

`GET /api/v1/registrations/{registration_id}`

Example:

```http
GET /api/v1/registrations/101
```

Responses:
- `200 OK` — registration returned.
- `404 Not Found` — registration does not exist.

### 4. Approve or reject a registration

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

### 5. Withdraw a registration

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
