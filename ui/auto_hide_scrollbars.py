from tkinter import ttk


class AutoHideScrollbar(ttk.Scrollbar):
    def __init__(self, *args, show, hide, **kwargs):
        super().__init__(*args, **kwargs)
        self._show = show
        self._hide = hide

    def set(self, first: str, last: str) -> None:
        first_f = float(first)
        last_f = float(last)
        if first_f <= 0.0 and last_f >= 1.0:
            self._hide()
        else:
            self._show()
        super().set(first, last)


def attach_auto_hiding_scrollbars(parent, tree, padx: int = 10, pady: int = 6) -> None:
    def _show_vbar() -> None:
        vbar.place(in_=tree, relx=1.0, rely=0.0, relheight=1.0, x=-14, width=14)

    def _hide_vbar() -> None:
        vbar.place_forget()

    def _show_hbar() -> None:
        hbar.place(in_=tree, relx=0.0, rely=1.0, relwidth=1.0, y=-14, height=14)

    def _hide_hbar() -> None:
        hbar.place_forget()

    vbar = AutoHideScrollbar(parent, orient="vertical", command=tree.yview, show=_show_vbar, hide=_hide_vbar)
    hbar = AutoHideScrollbar(parent, orient="horizontal", command=tree.xview, show=_show_hbar, hide=_hide_hbar)
    tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

    tree.pack(fill="both", expand=True, padx=padx, pady=pady)
    _hide_vbar()
    _hide_hbar()
