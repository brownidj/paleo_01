from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg import connect
from psycopg.rows import dict_row

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
    start_date: str | None = None
    end_date: str | None = None
    team: str | None = None
    location: str | None = None
    notes: str | None = None


class TeamMemberSummary(BaseModel):
    id: int
    name: str


class TripLocationSummary(BaseModel):
    id: int
    name: str


class TripCollectionEventSummary(BaseModel):
    id: int
    collection_name: str
    event_year: int | None = None


class TripDetailResponse(BaseModel):
    id: int
    trip_name: str
    start_date: str | None = None
    end_date: str | None = None
    team: str | None = None
    location: str | None = None
    notes: str | None = None
    can_view_details: bool
    team_members: list[TeamMemberSummary] = Field(default_factory=list)
    locations: list[TripLocationSummary] = Field(default_factory=list)
    collection_events: list[TripCollectionEventSummary] = Field(default_factory=list)
    find_count: int | None = None


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


def _ensure_mobile_team_member(principal: Principal) -> int:
    if principal.team_member_id <= 0:
        raise HTTPException(status_code=403, detail="Team membership is required.")
    return principal.team_member_id


@app.get(
    "/v1/trips",
    response_model=list[TripSummary],
)
def list_trips(
    principal: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> list[TripSummary]:
    _ensure_mobile_team_member(principal)
    settings = get_settings()
    with connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trip_name, start_date, end_date, team, location, notes
                FROM trips
                WHERE COALESCE(NULLIF(split_part(CAST(end_date AS text), 'T', 1), ''), '9999-12-31')
                      > to_char(CURRENT_DATE, 'YYYY-MM-DD')
                ORDER BY start_date DESC NULLS LAST, trip_name ASC, id ASC
                """
            )
            rows = cur.fetchall()
    return [
        TripSummary(
            id=int(row.get("id") or 0),
            trip_name=str(row.get("trip_name") or ""),
            start_date=str(row.get("start_date") or "") or None,
            end_date=str(row.get("end_date") or "") or None,
            team=str(row.get("team") or "") or None,
            location=str(row.get("location") or "") or None,
            notes=str(row.get("notes") or "") or None,
        )
        for row in rows
    ]


@app.get(
    "/v1/trips/{trip_id}",
    response_model=TripDetailResponse,
)
def get_trip_detail(
    trip_id: int,
    principal: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> TripDetailResponse:
    team_member_id = _ensure_mobile_team_member(principal)
    settings = get_settings()
    with connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trip_name, start_date, end_date, team, location, notes
                FROM trips
                WHERE id = %s
                  AND COALESCE(NULLIF(split_part(CAST(end_date AS text), 'T', 1), ''), '9999-12-31')
                      > to_char(CURRENT_DATE, 'YYYY-MM-DD')
                LIMIT 1
                """,
                (trip_id,),
            )
            trip_row = cur.fetchone()
            if not trip_row:
                raise HTTPException(status_code=404, detail="Trip not found.")

            cur.execute(
                """
                SELECT 1
                FROM trip_team_members
                WHERE trip_id = %s AND team_member_id = %s
                LIMIT 1
                """,
                (trip_id, team_member_id),
            )
            can_view_details = cur.fetchone() is not None

            if not can_view_details:
                return TripDetailResponse(
                    id=int(trip_row.get("id") or 0),
                    trip_name=str(trip_row.get("trip_name") or ""),
                    start_date=str(trip_row.get("start_date") or "") or None,
                    end_date=str(trip_row.get("end_date") or "") or None,
                    team=str(trip_row.get("team") or "") or None,
                    location=str(trip_row.get("location") or "") or None,
                    notes=str(trip_row.get("notes") or "") or None,
                    can_view_details=False,
                )

            cur.execute(
                """
                SELECT tm.id, tm.name
                FROM trip_team_members ttm
                JOIN team_members tm ON tm.id = ttm.team_member_id
                WHERE ttm.trip_id = %s
                ORDER BY tm.name ASC
                """,
                (trip_id,),
            )
            team_rows = cur.fetchall()

            cur.execute(
                """
                SELECT l.id, l.name
                FROM trip_locations tl
                JOIN locations l ON l.id = tl.location_id
                WHERE tl.trip_id = %s
                ORDER BY l.name ASC, l.id ASC
                """,
                (trip_id,),
            )
            location_rows = cur.fetchall()

            cur.execute(
                """
                SELECT id, collection_name, event_year
                FROM collection_events
                WHERE trip_id = %s
                ORDER BY event_year DESC NULLS LAST, id ASC
                """,
                (trip_id,),
            )
            event_rows = cur.fetchall()

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM finds f
                JOIN collection_events ce ON ce.id = f.collection_event_id
                WHERE ce.trip_id = %s
                """,
                (trip_id,),
            )
            find_count = int(cur.fetchone().get("count") or 0)

    return TripDetailResponse(
        id=int(trip_row.get("id") or 0),
        trip_name=str(trip_row.get("trip_name") or ""),
        start_date=str(trip_row.get("start_date") or "") or None,
        end_date=str(trip_row.get("end_date") or "") or None,
        team=str(trip_row.get("team") or "") or None,
        location=str(trip_row.get("location") or "") or None,
        notes=str(trip_row.get("notes") or "") or None,
        can_view_details=True,
        team_members=[
            TeamMemberSummary(id=int(row.get("id") or 0), name=str(row.get("name") or ""))
            for row in team_rows
        ],
        locations=[
            TripLocationSummary(id=int(row.get("id") or 0), name=str(row.get("name") or ""))
            for row in location_rows
        ],
        collection_events=[
            TripCollectionEventSummary(
                id=int(row.get("id") or 0),
                collection_name=str(row.get("collection_name") or ""),
                event_year=int(row.get("event_year")) if row.get("event_year") is not None else None,
            )
            for row in event_rows
        ],
        find_count=find_count,
    )


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
