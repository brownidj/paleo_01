import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import AutoHideScrollbar, attach_auto_hiding_scrollbars
from ui.geology_form_dialog import GeologyFormDialog


class GeologyTab(ttk.Frame):
    LIST_COLUMNS = (
        "location_name",
        "early_interval",
        "formation",
        "environment",
        "lithology_summary",
    )

    def __init__(self, parent, repo: TripRepository):
        super().__init__(parent)
        self.repo = repo
        self._records_by_iid: dict[str, dict] = {}

        self.tree = ttk.Treeview(self, columns=self.LIST_COLUMNS, show="headings")
        column_widths = {
            "location_name": 220,
            "early_interval": 110,
            "formation": 130,
            "environment": 220,
            "lithology_summary": 220,
        }
        for col in self.LIST_COLUMNS:
            self.tree.heading(col, text=col.replace("_", " "))
            self.tree.column(col, width=column_widths.get(col, 120), anchor="w")
        attach_auto_hiding_scrollbars(self, self.tree, padx=10, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda _: self.edit_selected())

        self._toast_hide_after_id: str | None = None
        self._toast = tk.Label(
            self,
            text="",
            bg="#2B6E59",
            fg="#FFFFFF",
            font=("Helvetica", 12, "bold"),
            bd=2,
            relief="solid",
            padx=14,
            pady=8,
        )
        self._toast.place_forget()

        details = ttk.LabelFrame(self, text="Selected Geology Details")
        details.pack(fill="x", padx=10, pady=(0, 10))
        details_container = ttk.Frame(details)
        details_container.pack(fill="both", expand=True, padx=10, pady=8)
        self.details_text = tk.Text(
            details_container,
            height=8,
            wrap="word",
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        def _show_details_vbar() -> None:
            self._details_scroll.place(in_=self.details_text, relx=1.0, rely=0.0, relheight=1.0, x=-14, width=14)

        def _hide_details_vbar() -> None:
            self._details_scroll.place_forget()

        self._details_scroll = AutoHideScrollbar(
            details_container,
            orient="vertical",
            command=self.details_text.yview,
            show=_show_details_vbar,
            hide=_hide_details_vbar,
        )
        self.details_text.configure(yscrollcommand=self._details_scroll.set)
        self.details_text.pack(side="left", fill="both", expand=True)
        _hide_details_vbar()
        self._set_details_text("Select a row to view details.")

    def load_geology(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._records_by_iid.clear()
        try:
            records = self.repo.list_geology_records()
        except sqlite3.Error as e:
            self._set_details_text(f"Database Error: {e}")
            return
        for idx, record in enumerate(records, 1):
            iid = str(idx)
            self._records_by_iid[iid] = record
            values = tuple((record.get(col) or "") for col in self.LIST_COLUMNS)
            self.tree.insert("", "end", iid=iid, values=values)
        if records:
            first_iid = self.tree.get_children()[0]
            self.tree.selection_set(first_iid)
            self._show_selected_details()
        else:
            self._set_details_text("No geology records found.")

    def _show_selected_details(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self._set_details_text("Select a row to view details.")
            return
        record = self._records_by_iid.get(selected[0])
        if not record:
            self._set_details_text("Select a row to view details.")
            return

        lithology_rows = record.get("lithology_rows") or []
        if lithology_rows:
            lith_lines: list[str] = []
            for lith in lithology_rows:
                slot = lith.get("slot")
                parts = [
                    str(lith.get("lithology") or "").strip(),
                    str(lith.get("minor_lithology") or "").strip(),
                    str(lith.get("lithology_adjectives") or "").strip(),
                    str(lith.get("lithification") or "").strip(),
                ]
                parts = [p for p in parts if p]
                base = ", ".join(parts) if parts else "n/a"
                fossils_from = str(lith.get("fossils_from") or "").strip()
                if fossils_from:
                    base = f"{base} | fossils_from: {fossils_from}"
                lith_lines.append(f"  slot {slot}: {base}")
            lithology_text = "\n".join(lith_lines)
        else:
            lithology_text = "  n/a"

        text = (
            f"Location: {record.get('location_name') or 'n/a'}\n"
            f"Age: {record.get('early_interval') or 'n/a'} to {record.get('late_interval') or 'n/a'}\n"
            f"Ma: {record.get('max_ma') or 'n/a'} to {record.get('min_ma') or 'n/a'}\n"
            f"Stratigraphy: formation={record.get('formation') or 'n/a'}, "
            f"group={record.get('stratigraphy_group') or 'n/a'}, member={record.get('member') or 'n/a'}\n"
            f"Environment: {record.get('environment') or 'n/a'}\n"
            f"Lithology:\n{lithology_text}\n"
            f"Reference No: {record.get('source_reference_no') or 'n/a'}"
        )
        self._set_details_text(text)

    def _on_tree_select(self, _event) -> None:
        self._show_selected_details()
        if self.tree.selection():
            self._show_toast("Double-click to edit.")

    def _show_toast(self, message: str, duration_ms: int = 1400) -> None:
        self._toast.configure(text=message)
        self._toast.place(in_=self.tree, relx=0.5, rely=1.0, anchor="s", y=-18)
        if self._toast_hide_after_id is not None:
            self.after_cancel(self._toast_hide_after_id)
        self._toast_hide_after_id = self.after(duration_ms, self._hide_toast)

    def _hide_toast(self) -> None:
        self._toast.place_forget()
        self._toast_hide_after_id = None

    def _set_details_text(self, text: str) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", text)
        self.details_text.configure(state="disabled")

    def edit_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Edit Geology", "Select a geology record first.")
            return
        record = self._records_by_iid.get(selected[0])
        if not record:
            messagebox.showerror("Edit Geology", "Selected geology record no longer exists.")
            self.load_geology()
            return
        geology_id = int(record["geology_id"])
        try:
            fresh = self.repo.get_geology_record(geology_id)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        if not fresh:
            messagebox.showerror("Edit Geology", "Selected geology record no longer exists.")
            self.load_geology()
            return

        def save(payload: dict[str, object]) -> bool:
            try:
                self.repo.update_geology_record(geology_id, payload)
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Save Error", str(e))
                return False
            self.load_geology()
            return True

        GeologyFormDialog(self, fresh, save, title="Edit Geology")
