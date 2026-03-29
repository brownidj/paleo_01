from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    display_name: str
    must_change_password: bool
    team_member_id: int


@dataclass(frozen=True)
class DbAuthUser:
    username: str
    password_hash: str
    role: str
    display_name: str
    team_active: bool
    must_change_password: bool
    team_member_id: int


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class AdminResetPasswordRequest(BaseModel):
    username: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    force_change: bool = True


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    must_change_password: bool


class UserResponse(BaseModel):
    username: str
    role: str
    display_name: str
    must_change_password: bool
    team_member_id: int


class BasicMessageResponse(BaseModel):
    status: str
    message: str
