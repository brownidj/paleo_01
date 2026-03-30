from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ui.login_dialog as login_dialog


class _RepoStub:
    def __init__(self, members):
        self._members = members

    def list_active_team_members(self):
        return self._members


class _ParentStub:
    def __init__(self, repo=None):
        self.repo = repo


class LoginDialogPreferencesTests(unittest.TestCase):
    def test_list_active_team_members_normalizes_and_sorts(self):
        parent = _ParentStub(_RepoStub(["D. Browning", " Zoe ", "alice", "", "Bob Jones", "alice"]))
        self.assertEqual(login_dialog._list_active_team_members(parent), ["alice", "b.jones", "d.browning", "zoe"])

    def test_load_and_save_last_login_name(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pref_path = Path(tmp_dir) / "prefs.json"
            old_path = login_dialog._LOGIN_PREFS_PATH
            login_dialog._LOGIN_PREFS_PATH = pref_path
            try:
                self.assertEqual(login_dialog._load_last_login_name(), "")
                login_dialog._save_last_login_name("  Alice  ")
                self.assertEqual(login_dialog._load_last_login_name(), "Alice")
            finally:
                login_dialog._LOGIN_PREFS_PATH = old_path

    def test_team_member_name_to_login(self):
        self.assertEqual(login_dialog._team_member_name_to_login("D. Browning"), "d.browning")
        self.assertEqual(login_dialog._team_member_name_to_login("Alice"), "alice")


if __name__ == "__main__":
    unittest.main()
