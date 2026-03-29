from fastapi import Depends, FastAPI, HTTPException, status
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


class TripDetail(BaseModel):
    id: int
    trip_name: str
    start_date: str | None
    end_date: str | None
    location: str | None
    team: str | None
    notes: str | None
    can_view_details: bool
    team_members: list["TeamMemberSummary"] = Field(default_factory=list)
    locations: list["TripLocationSummary"] = Field(default_factory=list)
    collection_events: list["TripCollectionEventSummary"] = Field(default_factory=list)
    find_count: int = 0


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
    principal: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> list[TripSummary]:
    settings = get_settings()
    try:
        with connect(settings.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        t.id AS id,
                        t.trip_name AS trip_name
                    FROM user_accounts ua
                    JOIN team_members tm ON tm.id = ua.team_member_id
                    JOIN trip_team_members ttm ON ttm.team_member_id = tm.id
                    JOIN trips t ON t.id = ttm.trip_id
                    WHERE lower(ua.username) = lower(%s)
                      AND tm.active = TRUE
                      AND (t.end_date IS NULL OR t.end_date > CURRENT_DATE)
                    ORDER BY t.trip_name ASC, t.start_date ASC
                    """,
                    (principal.username,),
                )
                rows = cur.fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"trips_db_unavailable: {exc}",
        ) from exc

    return [
        TripSummary(
            id=int(row["id"]),
            trip_name=str(row.get("trip_name") or ""),
        )
        for row in rows
    ]


@app.get(
    "/v1/trips/{trip_id}",
    response_model=TripDetail,
)
def get_trip_detail(
    trip_id: int,
    principal: Principal = Depends(require_roles("admin", "team", "planner", "reviewer", "field_member")),
) -> TripDetail:
    settings = get_settings()
    try:
        with connect(settings.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        t.id AS id,
                        t.trip_name AS trip_name,
                        t.start_date::text AS start_date,
                        t.end_date::text AS end_date,
                        t.location AS location,
                        t.team AS team,
                        t.notes AS notes
                    FROM user_accounts ua
                    JOIN team_members tm ON tm.id = ua.team_member_id
                    JOIN trip_team_members ttm ON ttm.team_member_id = tm.id
                    JOIN trips t ON t.id = ttm.trip_id
                    WHERE lower(ua.username) = lower(%s)
                      AND tm.active = TRUE
                      AND t.id = %s
                      AND (t.end_date IS NULL OR t.end_date > CURRENT_DATE)
                    LIMIT 1
                    """,
                    (principal.username, trip_id),
                )
                row = cur.fetchone()
                if row:
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
                    collection_event_rows = cur.fetchall()

                    cur.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM finds f
                        JOIN collection_events ce ON ce.id = f.collection_event_id
                        WHERE ce.trip_id = %s
                        """,
                        (trip_id,),
                    )
                    find_count = int((cur.fetchone() or {}).get("count") or 0)
                else:
                    team_rows = []
                    location_rows = []
                    collection_event_rows = []
                    find_count = 0
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"trip_detail_db_unavailable: {exc}",
        ) from exc

    if not row:
        raise HTTPException(status_code=404, detail="Trip not found.")

    return TripDetail(
        id=int(row["id"]),
        trip_name=str(row.get("trip_name") or ""),
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        location=row.get("location"),
        team=row.get("team"),
        notes=row.get("notes"),
        can_view_details=True,
        team_members=[
            TeamMemberSummary(id=int(r.get("id") or 0), name=str(r.get("name") or ""))
            for r in team_rows
        ],
        locations=[
            TripLocationSummary(id=int(r.get("id") or 0), name=str(r.get("name") or ""))
            for r in location_rows
        ],
        collection_events=[
            TripCollectionEventSummary(
                id=int(r.get("id") or 0),
                collection_name=str(r.get("collection_name") or ""),
                event_year=int(r["event_year"]) if r.get("event_year") is not None else None,
            )
            for r in collection_event_rows
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
