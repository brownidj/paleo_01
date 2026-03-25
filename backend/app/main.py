from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.db import check_database

app = FastAPI(title="Paleo API", version="0.1.0")


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
