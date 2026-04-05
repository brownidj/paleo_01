from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth_models import Principal
from app.config import Settings
from app.main import FindCreateRequest, create_find


class _FakeCursor:
    def __init__(self, store: dict[tuple[str, str], dict[str, str]]):
        self._store = store
        self._fetchone: dict[str, str] | None = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None):
        params = params or ()
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("select trip_id from collection_events"):
            self._fetchone = {"trip_id": 77}
            self.rowcount = 1
            return
        if normalized.startswith("select 1 from trip_team_members"):
            self._fetchone = {"?column?": 1}
            self.rowcount = 1
            return
        if normalized.startswith("select response_status, response_message from api_idempotency_keys"):
            username, idempotency_key = str(params[0]), str(params[1])
            self._fetchone = self._store.get((username, idempotency_key))
            self.rowcount = 1 if self._fetchone else 0
            return
        if normalized.startswith("insert into api_idempotency_keys"):
            username, idempotency_key, status, message = (
                str(params[0]),
                str(params[1]),
                str(params[2]),
                str(params[3]),
            )
            key = (username, idempotency_key)
            if key in self._store:
                self.rowcount = 0
                return
            self._store[key] = {
                "response_status": status,
                "response_message": message,
            }
            self.rowcount = 1
            return
        raise AssertionError(f"Unexpected SQL in test fake: {sql}")

    def fetchone(self):
        return self._fetchone


class _FakeConnection:
    def __init__(self, store: dict[tuple[str, str], dict[str, str]]):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._store)


class TestBackendFindIdempotency(unittest.TestCase):
    def setUp(self):
        self.store: dict[tuple[str, str], dict[str, str]] = {}
        self.principal = Principal(
            username="field.user",
            role="field_member",
            display_name="Field User",
            must_change_password=False,
            team_member_id=10,
        )
        self.payload = FindCreateRequest(
            collection_event_id=123,
            source="Field",
            accepted_name="Taxon A",
        )

    def _fake_connect(self, *_, **__):
        return _FakeConnection(self.store)

    def test_same_user_same_idempotency_key_returns_stable_response(self):
        with mock.patch("app.main.connect", side_effect=self._fake_connect):
            first = create_find(
                payload=self.payload,
                principal=self.principal,
                idempotency_key="idem-1",
                settings=Settings(database_url="postgresql://test"),
            )
            second = create_find(
                payload=self.payload,
                principal=self.principal,
                idempotency_key="idem-1",
                settings=Settings(database_url="postgresql://test"),
            )

        self.assertEqual(first.status, "accepted")
        self.assertEqual(second.status, first.status)
        self.assertEqual(second.message, first.message)
        self.assertEqual(len(self.store), 1)
        self.assertIn(("field.user", "idem-1"), self.store)

    def test_different_users_can_reuse_same_idempotency_key(self):
        other_principal = Principal(
            username="other.user",
            role="field_member",
            display_name="Other User",
            must_change_password=False,
            team_member_id=11,
        )

        with mock.patch("app.main.connect", side_effect=self._fake_connect):
            create_find(
                payload=self.payload,
                principal=self.principal,
                idempotency_key="idem-shared",
                settings=Settings(database_url="postgresql://test"),
            )
            create_find(
                payload=self.payload,
                principal=other_principal,
                idempotency_key="idem-shared",
                settings=Settings(database_url="postgresql://test"),
            )

        self.assertEqual(len(self.store), 2)
        self.assertIn(("field.user", "idem-shared"), self.store)
        self.assertIn(("other.user", "idem-shared"), self.store)

    def test_without_idempotency_key_preserves_existing_response_shape(self):
        with mock.patch("app.main.connect", side_effect=self._fake_connect):
            response = create_find(
                payload=self.payload,
                principal=self.principal,
                idempotency_key=None,
                settings=Settings(database_url="postgresql://test"),
            )

        self.assertEqual(response.status, "accepted")
        self.assertIn("field.user", response.message)
        self.assertEqual(len(self.store), 0)


if __name__ == "__main__":
    unittest.main()
