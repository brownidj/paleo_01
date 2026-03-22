import sqlite3
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.user_form_dialog import UserFormDialog


class UsersTab(ttk.Frame):
    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo

        self.users_tree = ttk.Treeview(
            self,
            columns=("name", "phone_number", "active"),
            show="headings",
        )
        self.users_tree.heading("name", text="name")
        self.users_tree.heading("phone_number", text="phone_number")
        self.users_tree.heading("active", text="active")
        self.users_tree.column("name", width=260, anchor="w")
        self.users_tree.column("phone_number", width=180, anchor="w")
        self.users_tree.column("active", width=100, anchor="center")
        self.users_tree.pack(fill="both", expand=True, padx=10, pady=6)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New User", command=self.new_user).pack(side="left", padx=4)
        self.users_tree.bind("<Double-1>", lambda _: self.edit_user())

    def load_users(self) -> None:
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        try:
            users = self.repo.list_users()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for user in users:
            self.users_tree.insert(
                "",
                "end",
                iid=str(user["id"]),
                values=(
                    user.get("name", ""),
                    user.get("phone_number", ""),
                    "Yes" if int(user.get("active", 0)) == 1 else "No",
                ),
            )

    def new_user(self) -> None:
        def save_user(payload: dict[str, str]) -> bool:
            if not payload.get("name"):
                messagebox.showerror("Validation Error", "name is required.")
                return False
            try:
                self.repo.create_user(
                    payload["name"],
                    payload.get("phone_number", ""),
                    bool(payload.get("active", False)),
                )
            except sqlite3.Error as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_users()
            return True

        UserFormDialog(self, None, save_user)

    def edit_user(self) -> None:
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Edit User", "Select a User first.")
            return
        user_id = int(selected[0])
        try:
            user = self.repo.get_user(user_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not user:
            messagebox.showerror("Edit User", "Selected User no longer exists.")
            self.load_users()
            return

        def save_user(payload: dict[str, str]) -> bool:
            if not payload.get("name"):
                messagebox.showerror("Validation Error", "name is required.")
                return False
            try:
                self.repo.update_user(
                    user_id,
                    payload["name"],
                    payload.get("phone_number", ""),
                    bool(payload.get("active", False)),
                )
            except sqlite3.Error as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_users()
            return True

        UserFormDialog(self, user, save_user)
