from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from app.api_auth import ApiAuthClient, ApiAuthError


class _CredentialsDialog(simpledialog.Dialog):
    def body(self, master: tk.Misc):
        self.title("Sign In")
        tk.Label(master, text="Username").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.username_entry = tk.Entry(master, width=32)
        self.username_entry.grid(row=0, column=1, pady=(4, 4))
        tk.Label(master, text="Password").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 4))
        self.password_entry = tk.Entry(master, width=32, show="*")
        self.password_entry.grid(row=1, column=1, pady=(4, 4))
        self.username_entry.focus_set()
        self.result: tuple[str, str] | None = None
        return self.username_entry

    def apply(self) -> None:
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        self.result = (username, password)


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
    while True:
        dialog = _CredentialsDialog(parent)
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
            profile = client.whoami()
            name = str(profile.get("display_name") or profile.get("username") or "user")
            messagebox.showinfo("Signed In", f"Signed in as {name}.", parent=parent)
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
