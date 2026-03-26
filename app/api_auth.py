from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


class ApiAuthError(RuntimeError):
    pass


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str


class ApiAuthClient:
    def __init__(self, base_url: str, verify_tls: bool = False, timeout_seconds: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._ssl_context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
        self._tokens: AuthTokens | None = None

    def login(self, username: str, password: str) -> dict:
        body = self._request_json(
            "POST",
            "/v1/auth/login",
            {"username": username, "password": password},
            include_auth=False,
        )
        access_token = str(body.get("access_token") or "")
        refresh_token = str(body.get("refresh_token") or "")
        if not access_token or not refresh_token:
            raise ApiAuthError("Login response did not include tokens.")
        self._tokens = AuthTokens(access_token=access_token, refresh_token=refresh_token)
        return body

    def change_password(self, current_password: str, new_password: str) -> dict:
        return self._request_json(
            "POST",
            "/v1/auth/change-password",
            {"current_password": current_password, "new_password": new_password},
            include_auth=True,
        )

    def whoami(self) -> dict:
        return self._request_json("GET", "/v1/auth/me", include_auth=True)

    def request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        return self._request_json(method, path, payload=payload, include_auth=True)

    def _refresh_access_token(self) -> None:
        if self._tokens is None:
            raise ApiAuthError("Missing refresh token.")
        body = self._request_json(
            "POST",
            "/v1/auth/refresh",
            {"refresh_token": self._tokens.refresh_token},
            include_auth=False,
        )
        access_token = str(body.get("access_token") or "")
        refresh_token = str(body.get("refresh_token") or "")
        if not access_token or not refresh_token:
            raise ApiAuthError("Refresh response did not include tokens.")
        self._tokens = AuthTokens(access_token=access_token, refresh_token=refresh_token)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        include_auth: bool = True,
        _retried: bool = False,
    ) -> dict:
        data_bytes = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if include_auth:
            if self._tokens is None:
                raise ApiAuthError("Not authenticated.")
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data_bytes,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds, context=self._ssl_context) as response:
                text = response.read().decode("utf-8")
                if not text:
                    return {}
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            detail = _extract_detail(body)
            if include_auth and exc.code == 401 and not _retried:
                self._refresh_access_token()
                return self._request_json(
                    method,
                    path,
                    payload=payload,
                    include_auth=include_auth,
                    _retried=True,
                )
            raise ApiAuthError(f"{method.upper()} {path} failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise ApiAuthError(f"Cannot reach API at {self._base_url}: {exc.reason}") from exc


def _extract_detail(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        return "empty response"
    try:
        payload = json.loads(text)
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        return text
    except json.JSONDecodeError:
        return text
