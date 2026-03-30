from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog
from tkinter import ttk

from app.api_auth import ApiAuthClient, ApiAuthError

_LOGIN_PREFS_PATH = Path(__file__).resolve().parents[1] / "data" / "ui_login_preferences.json"


class _CredentialsDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, active_team_members: list[str], last_login_name: str):
        self._active_team_members = active_team_members
        self._last_login_name = last_login_name
        super().__init__(parent)

    def body(self, master: tk.Misc):
        self.title("Sign In")
        tk.Label(master, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.username_var = tk.StringVar(value=self._initial_name_value())
        self.username_combo = ttk.Combobox(
            master,
            textvariable=self.username_var,
            values=self._active_team_members,
            width=32,
            state="readonly" if self._active_team_members else "normal",
        )
        self.username_combo.grid(row=0, column=1, pady=(4, 4))
        password_row = 1
        tk.Label(master, text="Password").grid(row=password_row, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.password_entry = tk.Entry(master, width=32, show="*")
        self.password_entry.grid(row=password_row, column=1, pady=(4, 4))
        self.username_combo.focus_set()
        self.result: tuple[str, str] | None = None
        return self.username_combo

    def apply(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_entry.get()
        self.result = (username, password)

    def _initial_name_value(self) -> str:
        if self._last_login_name:
            for member in self._active_team_members:
                if member == self._last_login_name:
                    return member
        if self._active_team_members:
            return self._active_team_members[0]
        return self._last_login_name

    def buttonbox(self) -> None:
        box = tk.Frame(self)
        sign_in_button = tk.Button(box, text="Sign in", width=10, command=self.ok, default=tk.ACTIVE)
        sign_in_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()


class _ChangePasswordDialog(simpledialog.Dialog):
    def body(self, master: tk.Misc):
        self.title("Change Password")
        tk.Label(master, text="Current password").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.current_entry = tk.Entry(master, width=32, show="*")
        self.current_entry.grid(row=0, column=1, pady=(4, 4))
        tk.Label(master, text="New password").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.new_entry = tk.Entry(master, width=32, show="*")
        self.new_entry.grid(row=1, column=1, pady=(4, 4))
        self.current_entry.focus_set()
        self.result: tuple[str, str] | None = None
        return self.current_entry

    def apply(self) -> None:
        self.result = (self.current_entry.get(), self.new_entry.get())


def login_interactive(client: ApiAuthClient, parent: tk.Tk) -> bool:
    active_team_members = _list_active_team_members(parent)
    last_login_name = _load_last_login_name()
    while True:
        dialog = _CredentialsDialog(
            parent,
            active_team_members=active_team_members,
            last_login_name=last_login_name,
        )
        creds = dialog.result
        if creds is None:
            return False
        username, password = creds
        if not username or not password:
            messagebox.showerror("Login Failed", "Username and password are required.", parent=parent)
            continue
        try:
            login_response = client.login(username, password)
        except ApiAuthError as exc:
            messagebox.showerror("Login Failed", str(exc), parent=parent)
            continue
        if bool(login_response.get("must_change_password")):
            if not _change_password_flow(client, parent):
                return False
        try:
            client.whoami()
            _save_last_login_name(username)
            return True
        except ApiAuthError as exc:
            messagebox.showerror("Login Failed", str(exc), parent=parent)


def _change_password_flow(client: ApiAuthClient, parent: tk.Tk) -> bool:
    while True:
        messagebox.showinfo("Password Required", "You must change your password before continuing.", parent=parent)
        dialog = _ChangePasswordDialog(parent)
        payload = dialog.result
        if payload is None:
            return False
        current_password, new_password = payload
        if not current_password or not new_password:
            messagebox.showerror("Change Password", "Both password fields are required.", parent=parent)
            continue
        if current_password == new_password:
            messagebox.showerror("Change Password", "New password must differ from current.", parent=parent)
            continue
        if len(new_password) < 8:
            messagebox.showerror("Change Password", "New password must be at least 8 characters.", parent=parent)
            continue
        try:
            client.change_password(current_password=current_password, new_password=new_password)
            return True
        except ApiAuthError as exc:
            messagebox.showerror("Change Password Failed", str(exc), parent=parent)


def _list_active_team_members(parent: tk.Misc) -> list[str]:
    repo = getattr(parent, "repo", None)
    list_members = getattr(repo, "list_active_team_members", None)
    if not callable(list_members):
        return []
    try:
        raw_members = list_members()
    except Exception:
        return []
    unique: list[str] = []
    seen: set[str] = set()
    for raw in raw_members:
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(name)
    usernames = [_team_member_name_to_login(name) for name in unique]
    usernames = [u for u in usernames if u]
    usernames = sorted(set(usernames), key=str.lower)
    return usernames


def _load_last_login_name() -> str:
    try:
        payload = json.loads(_LOGIN_PREFS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(payload.get("last_login_name") or "").strip()


def _save_last_login_name(name: str) -> None:
    trimmed = str(name).strip()
    if not trimmed:
        return
    try:
        _LOGIN_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOGIN_PREFS_PATH.write_text(
            json.dumps({"last_login_name": trimmed}, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return


def _team_member_name_to_login(name: str) -> str:
    cleaned = " ".join(str(name).strip().split())
    if not cleaned:
        return ""
    normalized = cleaned.lower()
    normalized = normalized.replace(",", " ").replace(";", " ")
    parts = [part.strip(".-_ ") for part in normalized.split() if part.strip(".-_ ")]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    first = parts[0][0] if parts[0] else ""
    last = parts[-1]
    if first and last:
        return f"{first}.{last}"
    return parts[0]
