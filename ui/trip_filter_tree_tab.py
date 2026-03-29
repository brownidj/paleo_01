import sqlite3
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import messagebox, ttk
from typing import Mapping

from repository.trip_repository import TripRepository
from ui.auto_hide_scrollbars import attach_auto_hiding_scrollbars


class TripFilterTreeTab(ttk.Frame):
    def __init__(
        self,
        parent,
        repo: TripRepository,
        list_columns: Sequence[str],
        widths: dict[str, int],
        fetch_rows: Callable[[int | None], list[Mapping[str, object]]],
    ):
        super().__init__(parent)
        self.repo = repo
        self._list_columns = tuple(list_columns)
        self._fetch_rows = fetch_rows
        self._trip_filter_trip_id: int | None = None
        self._current_trip_id_provider = None
        self._trip_filter_hint_label: ttk.Label | None = None

        self.trip_filter_var = tk.IntVar(value=0)
        self._trip_filter_header = ttk.Frame(self)
        self._trip_filter_header.pack(fill="x", padx=10, pady=(10, 4))
        trip_filter_radio = ttk.Radiobutton(self._trip_filter_header, text="Trip filter", variable=self.trip_filter_var, value=1)
        trip_filter_radio.pack(side="left", anchor="w")
        trip_filter_radio.bind("<Button-1>", self._on_trip_filter_click, add="+")

        self.tree = ttk.Treeview(self, columns=self._list_columns, show="headings")
        for col in self._list_columns:
            self.tree.heading(col, text=col.replace("_", " "))
            self.tree.column(col, width=widths.get(col, 120), anchor="w")
        attach_auto_hiding_scrollbars(self, self.tree, padx=10, pady=6)

    def set_trip_filter_hint(self, text: str, font: tuple[str, int, str] | None = None) -> None:
        if self._trip_filter_hint_label is None:
            self._trip_filter_hint_label = ttk.Label(self._trip_filter_header, text=text)
            self._trip_filter_hint_label.pack(side="right", anchor="e")
        else:
            self._trip_filter_hint_label.configure(text=text)
        if font is not None:
            self._trip_filter_hint_label.configure(font=font)

    def load_rows(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            active_trip_id = self._active_trip_filter_trip_id()
            use_trip_filter = self.trip_filter_var.get() == 1 and active_trip_id is not None
            rows = self._fetch_rows(active_trip_id if use_trip_filter else None)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=tuple((row.get(col) or "") for col in self._list_columns),
            )

    def activate_trip_filter(self, trip_id: int) -> None:
        self._trip_filter_trip_id = trip_id
        self.trip_filter_var.set(1)
        self.load_rows()

    def _on_trip_filter_click(self, _event) -> str:
        currently_on = self.trip_filter_var.get() == 1
        if currently_on:
            self.trip_filter_var.set(0)
        else:
            provider_trip_id = self._get_provider_trip_id()
            if provider_trip_id is not None:
                self._trip_filter_trip_id = provider_trip_id
            self.trip_filter_var.set(1)
        self.load_rows()
        return "break"

    def set_current_trip_provider(self, provider) -> None:
        self._current_trip_id_provider = provider

    def _get_provider_trip_id(self) -> int | None:
        if not callable(self._current_trip_id_provider):
            return None
        trip_id = self._current_trip_id_provider()
        if trip_id is None:
            return None
        try:
            return int(trip_id)
        except (TypeError, ValueError):
            return None

    def _active_trip_filter_trip_id(self) -> int | None:
        provider_trip_id = self._get_provider_trip_id()
        if provider_trip_id is not None:
            self._trip_filter_trip_id = provider_trip_id
        return self._trip_filter_trip_id
