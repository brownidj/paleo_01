from __future__ import annotations

import tkinter.font as tkfont
from tkinter import ttk


class PlanningPhaseWindowPaletteMixin:
    PALETTE = {
        "earth": {
            "dusty_ochre": "#E4C89F",
            "clay_blush": "#E4C0BB",
            "soft_ironstone": "#D8AE9F",
        },
        "vegetation": {
            "eucalypt_sage": "#B8CCBF",
            "spinifex_mint": "#D6E3CA",
            "pale_wattle_green": "#C5D7BC",
        },
        "water_sky": {
            "creek_blue": "#C1D6DC",
        },
        "fossil_bone": {
            "fossil_sand": "#F7F3E8",
            "bone_white": "#FCFAF6",
            "chalk_beige": "#EFE8DC",
            "weathered_stone": "#D7CEC2",
        },
        "text": {
            "deep_gumleaf": "#7C8882",
            "dust_bark": "#9F9B94",
        },
        "status": {
            "muted_rust": "#CD9F93",
            "pale_wattle_green": "#C5D7BC",
        },
    }

    def _apply_palette(self) -> None:
        p = self.PALETTE
        bg = p["fossil_bone"]["fossil_sand"]
        surface = p["fossil_bone"]["bone_white"]
        surface_alt = p["fossil_bone"]["chalk_beige"]
        text_primary = p["text"]["deep_gumleaf"]
        text_secondary = p["text"]["dust_bark"]
        primary = p["vegetation"]["eucalypt_sage"]
        secondary = p["earth"]["dusty_ochre"]
        selected = p["earth"]["clay_blush"]

        self.configure(bg=bg)
        self.option_add("*Background", bg)
        self.option_add("*Foreground", text_primary)
        self.option_add("*Listbox.background", surface)
        self.option_add("*Listbox.foreground", text_primary)
        self.option_add("*Listbox.selectBackground", secondary)
        self.option_add("*Listbox.selectForeground", text_primary)
        self.option_add("*Text.background", surface)
        self.option_add("*Text.foreground", text_primary)
        self.option_add("*Text.insertBackground", text_primary)

        style = ttk.Style(self)
        self._tab_font_normal = tkfont.Font(self, family="Helvetica", size=10, weight="normal")
        self._tab_font_selected = tkfont.Font(self, family="Helvetica", size=11, weight="bold")
        available_themes = set(style.theme_names())
        if "clam" in available_themes:
            style.theme_use("clam")

        style.configure(".", background=bg, foreground=text_primary)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text_primary)

        style.configure(
            "TButton",
            background=primary,
            foreground=text_primary,
            borderwidth=1,
            padding=(10, 5),
        )
        style.map(
            "TButton",
            background=[("active", secondary), ("pressed", p["earth"]["clay_blush"])],
            foreground=[("disabled", text_secondary)],
        )

        style.configure(
            "TNotebook",
            background=bg,
            borderwidth=0,
            tabmargins=(6, 6, 6, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=surface_alt,
            foreground=text_secondary,
            padding=(14, 6),
            font=self._tab_font_normal,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", primary), ("active", secondary)],
            foreground=[("selected", text_primary), ("active", text_primary)],
            padding=[("selected", (14, 10)), ("active", (14, 8))],
            font=[("selected", self._tab_font_selected), ("!selected", self._tab_font_normal)],
        )

        style.configure(
            "Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=text_primary,
            rowheight=24,
        )
        style.map(
            "Treeview",
            background=[("selected", selected)],
            foreground=[("selected", text_primary)],
        )
        style.configure(
            "Treeview.Heading",
            background=surface_alt,
            foreground=text_primary,
            relief="flat",
        )
        style.configure(
            "Trips.Treeview",
            background=surface,
            fieldbackground=surface,
            foreground=text_primary,
            rowheight=24,
        )
        style.map(
            "Trips.Treeview",
            background=[("selected", selected)],
            foreground=[("selected", text_primary)],
        )
        style.configure(
            "Trips.Treeview.Heading",
            background=surface_alt,
            foreground=text_primary,
            relief="flat",
            font=("Helvetica", 10, "bold"),
        )

        style.configure(
            "TEntry",
            fieldbackground=surface,
            foreground=text_primary,
        )
        style.map("TEntry", fieldbackground=[("readonly", surface_alt)])
        style.configure(
            "TCheckbutton",
            background=bg,
            foreground=text_primary,
        )
