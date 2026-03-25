from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.auth import Principal, get_current_principal, require_roles, router as auth_router
from app.bootstrap import bootstrap_postgres_auth
from app.config import get_settings
from app.db import check_database

app = FastAPI(title="Paleo API", version="0.1.0")
app.include_router(auth_router)


@app.on_event("startup")
def startup_bootstrap() -> None:
    bootstrap_postgres_auth()


class TripSummary(BaseModel):
    id: int
    trip_name: str


class CollectionEventSummary(BaseModel):
    id: int
    collection_name: str


class FindCreateRequest(BaseModel):
    collection_event_id: int = Field(gt=0)
    source: str = Field(min_length=1, max_length=200)
    accepted_name: str = Field(min_length=1, max_length=200)


class FindCreateResponse(BaseModel):
    status: str
    message: str


@app.get("/v1/health")
def health() -> dict[str, str]:
    settings = get_settings()
    try:
        check_database()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database_unavailable: {exc}") from exc
    return {"status": "ok", "database": "up", "env": settings.app_env}


@app.get("/v1")
def root() -> dict[str, str]:
    return {"service": "paleo-api", "status": "running"}


@app.get(
    "/v1/trips",
    response_model=list[TripSummary],
)
def list_trips(
    _: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> list[TripSummary]:
    return []


@app.get(
    "/v1/collection-events",
    response_model=list[CollectionEventSummary],
)
def list_collection_events(
    _: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> list[CollectionEventSummary]:
    return []


@app.post(
    "/v1/finds",
    response_model=FindCreateResponse,
)
def create_find(
    payload: FindCreateRequest,
    principal: Principal = Depends(require_roles("admin", "team", "planner", "field_member")),
) -> FindCreateResponse:
    _ = payload
    return FindCreateResponse(
        status="accepted",
        message=f"Find create scaffold accepted for user '{principal.username}'.",
    )


@app.get("/v1/whoami")
def whoami(principal: Principal = Depends(get_current_principal)) -> dict[str, str]:
    return {"username": principal.username, "role": principal.role}
