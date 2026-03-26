from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import connect
from psycopg.rows import dict_row

from app.auth_models import (
    AdminResetPasswordRequest,
    BasicMessageResponse,
    ChangePasswordRequest,
    DbAuthUser,
    LoginRequest,
    Principal,
    RefreshRequest,
    TokenPairResponse,
    UserResponse,
)
from app.config import Settings, get_settings
from app.passwords import hash_password, verify_password

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

bearer_scheme = HTTPBearer(auto_error=False)


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


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
            "mcp": 1 if principal.must_change_password else 0,
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
            "mcp": 1 if principal.must_change_password else 0,
            "typ": TOKEN_TYPE_REFRESH,
        },
        secret=settings.jwt_refresh_secret,
        ttl=refresh_ttl,
    )
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=int(access_ttl.total_seconds()),
        must_change_password=principal.must_change_password,
    )


def _principal_from_payload(payload: dict[str, Any]) -> Principal:
    username = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    display_name = str(payload.get("name") or username).strip() or username
    must_change_password = int(payload.get("mcp", 0)) == 1
    if not username or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return Principal(
        username=username,
        role=role,
        display_name=display_name,
        must_change_password=must_change_password,
    )


def _load_db_auth_user(username: str, settings: Settings) -> DbAuthUser | None:
    try:
        with connect(settings.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        ua.username AS username,
                        ua.password_hash AS password_hash,
                        ua.role AS role,
                        ua.must_change_password AS must_change_password,
                        tm.name AS display_name,
                        tm.active AS team_active
                    FROM user_accounts ua
                    JOIN team_members tm ON tm.id = ua.team_member_id
                    WHERE lower(ua.username) = lower(%s)
                    LIMIT 1
                    """,
                    (username,),
                )
                row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"auth_db_unavailable: {exc}") from exc

    if not row:
        return None
    return DbAuthUser(
        username=str(row.get("username", "")).strip(),
        password_hash=str(row.get("password_hash", "")),
        role=str(row.get("role", "")).strip().lower(),
        display_name=str(row.get("display_name") or row.get("username") or "").strip() or str(row.get("username")),
        team_active=int(row.get("team_active") or 0) == 1,
        must_change_password=int(row.get("must_change_password") or 0) == 1,
    )


def _load_active_principal(username: str, settings: Settings) -> Principal | None:
    user = _load_db_auth_user(username, settings)
    if not user or not user.team_active:
        return None
    return Principal(
        username=user.username,
        role=user.role,
        display_name=user.display_name,
        must_change_password=user.must_change_password,
    )


def _update_password(
    *,
    username: str,
    password_hash: str,
    must_change_password: bool,
    settings: Settings,
) -> bool:
    with connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_accounts
                SET
                    password_hash = %s,
                    must_change_password = %s,
                    password_changed_at = CURRENT_TIMESTAMP
                WHERE lower(username) = lower(%s)
                """,
                (password_hash, must_change_password, username),
            )
            return cur.rowcount > 0


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    payload = _decode_token(credentials.credentials, secret=settings.jwt_secret, expected_type=TOKEN_TYPE_ACCESS)
    principal = _principal_from_payload(payload)
    active_principal = _load_active_principal(principal.username, settings)
    if not active_principal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or unknown.")
    return active_principal


def require_roles(*allowed_roles: str) -> Callable[[Principal], Principal]:
    allowed = {role.strip().lower() for role in allowed_roles}

    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.must_change_password:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_change_required")
        if principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted.")
        return principal

    return dependency


router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenPairResponse:
    user = _load_db_auth_user(payload.username, settings)
    if not user or not user.team_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    principal = Principal(
        username=user.username,
        role=user.role,
        display_name=user.display_name,
        must_change_password=user.must_change_password,
    )
    return _issue_token_pair(settings=settings, principal=principal)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: RefreshRequest, settings: Settings = Depends(get_settings)) -> TokenPairResponse:
    token_payload = _decode_token(
        payload.refresh_token,
        secret=settings.jwt_refresh_secret,
        expected_type=TOKEN_TYPE_REFRESH,
    )
    principal = _principal_from_payload(token_payload)
    active_principal = _load_active_principal(principal.username, settings)
    if not active_principal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or unknown.")
    return _issue_token_pair(settings=settings, principal=active_principal)


@router.post("/change-password", response_model=BasicMessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    principal: Principal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
) -> BasicMessageResponse:
    user = _load_db_auth_user(principal.username, settings)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or unknown.")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is invalid.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from current.")
    ok = _update_password(
        username=principal.username,
        password_hash=hash_password(payload.new_password),
        must_change_password=False,
        settings=settings,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")
    return BasicMessageResponse(status="ok", message="Password changed.")


@router.post("/admin/reset-password", response_model=BasicMessageResponse)
def admin_reset_password(
    payload: AdminResetPasswordRequest,
    _: Principal = Depends(require_roles("admin")),
    settings: Settings = Depends(get_settings),
) -> BasicMessageResponse:
    ok = _update_password(
        username=payload.username,
        password_hash=hash_password(payload.new_password),
        must_change_password=payload.force_change,
        settings=settings,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")
    return BasicMessageResponse(status="ok", message="Password reset.")


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(get_current_principal)) -> UserResponse:
    return UserResponse(
        username=principal.username,
        role=principal.role,
        display_name=principal.display_name,
        must_change_password=principal.must_change_password,
    )
