# NexusMatch frontend

React, TypeScript and Vite client for the NexusMatch FastAPI service. It deliberately has no client-side identity or faux authentication: users explicitly choose a player/team and organizer actions are labeled as trusted local-demo operations.

## Visual direction

The interface is tactical and technical rather than generic dashboard UI: charcoal layered surfaces, amber decisive actions, green/red semantic states, Space Grotesk UI typography, and tabular DM Mono metadata. Compact borders and round columns preserve the density and scanability of tournament operations software. Motion is restrained and disabled for reduced-motion users.

## Run

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

`VITE_API_BASE_URL` defaults to `http://localhost:8000/api/v1`. Start PostgreSQL and MongoDB, run migrations, then start FastAPI before using the client. The health chip reflects `/health` and distinguishes full health, degraded dependencies, and an unavailable API.

## Checks

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

## Routes and API coverage

- `/` — list/search/filter actual tournaments.
- `/tournaments/:id` — overview, registrations, persisted bracket, and server-confirmed score entry.
- `/registrations` — all registrations in the identity-free API, including withdrawal.
- `/teams` — team and roster inspection.
- `/organizer` — creation, pending-registration approval/rejection, and bracket generation.

Only `single_elimination` is visualized as a bracket because that is the backend-supported bracket engine. MongoDB telemetry has no read endpoint and is intentionally not faked.
