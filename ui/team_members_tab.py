import sqlite3
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars
from ui.team_member_form_dialog import TeamMemberFormDialog


class TeamMembersTab(ttk.Frame):
    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo

        self.team_members_tree = ttk.Treeview(
            self,
            columns=("name", "phone_number", "institution", "active"),
            show="headings",
        )
        self.team_members_tree.heading("name", text="name")
        self.team_members_tree.heading("phone_number", text="phone_number")
        self.team_members_tree.heading("institution", text="institution")
        self.team_members_tree.heading("active", text="active")
        self.team_members_tree.column("name", width=260, anchor="w")
        self.team_members_tree.column("phone_number", width=180, anchor="w")
        self.team_members_tree.column("institution", width=200, anchor="w")
        self.team_members_tree.column("active", width=100, anchor="center")
        attach_auto_hiding_scrollbars(self, self.team_members_tree, padx=10, pady=6)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="New Team Member", command=self.new_team_member).pack(side="left", padx=4)
        self.team_members_tree.bind("<Double-1>", lambda _: self.edit_team_member())

    def load_team_members(self) -> None:
        for item in self.team_members_tree.get_children():
            self.team_members_tree.delete(item)
        try:
            team_members = self.repo.list_team_members()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for team_member in team_members:
            self.team_members_tree.insert(
                "",
                "end",
                iid=str(team_member["id"]),
                values=(
                    team_member.get("name", ""),
                    team_member.get("phone_number", ""),
                    team_member.get("institution", ""),
                    "Yes" if int(team_member.get("active", 0)) == 1 else "No",
                ),
            )

    def new_team_member(self) -> None:
        def save_team_member(payload: dict[str, str]) -> bool:
            if not payload.get("name"):
                messagebox.showerror("Validation Error", "name is required.")
                return False
            try:
                self.repo.create_team_member(
                    payload["name"],
                    payload.get("phone_number", ""),
                    bool(payload.get("active", False)),
                    payload.get("institution", "") or None,
                )
            except sqlite3.Error as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_team_members()
            return True

        TeamMemberFormDialog(self, None, save_team_member)

    def edit_team_member(self) -> None:
        selected = self.team_members_tree.selection()
        if not selected:
            messagebox.showinfo("Edit Team Member", "Select a team member first.")
            return
        team_member_id = int(selected[0])
        try:
            team_member = self.repo.get_team_member(team_member_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not team_member:
            messagebox.showerror("Edit Team Member", "Selected team member no longer exists.")
            self.load_team_members()
            return

        def save_team_member(payload: dict[str, str]) -> bool:
            if not payload.get("name"):
                messagebox.showerror("Validation Error", "name is required.")
                return False
            try:
                self.repo.update_team_member(
                    team_member_id,
                    payload["name"],
                    payload.get("phone_number", ""),
                    bool(payload.get("active", False)),
                    payload.get("institution", "") or None,
                )
            except sqlite3.Error as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_team_members()
            return True

        TeamMemberFormDialog(self, team_member, save_team_member)
