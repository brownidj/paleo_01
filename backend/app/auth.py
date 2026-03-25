from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    username: str
    password: str
    role: str
    display_name: str
    enabled: bool = True


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    display_name: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserResponse(BaseModel):
    username: str
    role: str
    display_name: str


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _parse_users(settings: Settings) -> dict[str, AuthUser]:
    try:
        raw_users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AUTH_USERS_JSON is invalid JSON.") from exc

    users: dict[str, AuthUser] = {}
    for row in raw_users:
        username = str(row.get("username", "")).strip()
        if not username:
            continue
        users[username] = AuthUser(
            username=username,
            password=str(row.get("password", "")),
            role=str(row.get("role", "")).strip(),
            display_name=str(row.get("display_name", username)).strip() or username,
            enabled=bool(row.get("enabled", True)),
        )
    return users


def _encode_token(payload: dict[str, Any], *, secret: str, ttl: timedelta) -> str:
    now = _now_utc()
    claims = dict(payload)
    claims["iat"] = int(now.timestamp())
    claims["exp"] = int((now + ttl).timestamp())
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def _decode_token(token: str, *, secret: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    if payload.get("typ") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
    return payload


def _issue_token_pair(*, settings: Settings, principal: Principal) -> TokenPairResponse:
    access_ttl = timedelta(minutes=settings.jwt_access_minutes)
    refresh_ttl = timedelta(days=settings.jwt_refresh_days)

    access_token = _encode_token(
        {
            "sub": principal.username,
            "role": principal.role,
            "name": principal.display_name,
            "typ": TOKEN_TYPE_ACCESS,
        },
        secret=settings.jwt_secret,
        ttl=access_ttl,
    )
    refresh_token = _encode_token(
        {
            "sub": principal.username,
            "role": principal.role,
            "name": principal.display_name,
            "typ": TOKEN_TYPE_REFRESH,
        },
        secret=settings.jwt_refresh_secret,
        ttl=refresh_ttl,
    )
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=int(access_ttl.total_seconds()),
    )


def _principal_from_payload(payload: dict[str, Any]) -> Principal:
    username = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    display_name = str(payload.get("name") or username).strip() or username
    if not username or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return Principal(username=username, role=role, display_name=display_name)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    payload = _decode_token(credentials.credentials, secret=settings.jwt_secret, expected_type=TOKEN_TYPE_ACCESS)
    return _principal_from_payload(payload)


def require_roles(*allowed_roles: str) -> Callable[[Principal], Principal]:
    allowed = set(allowed_roles)

    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted.")
        return principal

    return dependency


router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenPairResponse:
    users = _parse_users(settings)
    user = users.get(payload.username)
    if not user or not user.enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    if not secrets.compare_digest(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    principal = Principal(username=user.username, role=user.role, display_name=user.display_name)
    return _issue_token_pair(settings=settings, principal=principal)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: RefreshRequest, settings: Settings = Depends(get_settings)) -> TokenPairResponse:
    token_payload = _decode_token(
        payload.refresh_token,
        secret=settings.jwt_refresh_secret,
        expected_type=TOKEN_TYPE_REFRESH,
    )
    principal = _principal_from_payload(token_payload)
    return _issue_token_pair(settings=settings, principal=principal)


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(get_current_principal)) -> UserResponse:
    return UserResponse(
        username=principal.username,
        role=principal.role,
        display_name=principal.display_name,
    )
