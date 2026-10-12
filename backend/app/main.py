from app.api.v1.endpoints.players import router as players_router
from app.api.v1.endpoints.registrations import router as registrations_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.tournaments import router as tournaments_router
from app.db.health import check_mongodb, check_postgres
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="NexusMatch API",
    description="Transactional esports tournament management API.",
    version="0.2.0",
)
app.include_router(players_router)
app.include_router(teams_router)
app.include_router(registrations_router)
app.include_router(tournaments_router)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "name": "NexusMatch API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/v1/health", tags=["Health"])
def health():
    postgres_ok = check_postgres()
    mongodb_ok = check_mongodb()

    response = {
        "status": "ok" if postgres_ok and mongodb_ok else "degraded",
        "checks": {
            "postgres": "ok" if postgres_ok else "error",
            "mongodb": "ok" if mongodb_ok else "error",
        },
    }

    status_code = 200 if postgres_ok and mongodb_ok else 503
    return JSONResponse(content=response, status_code=status_code)
