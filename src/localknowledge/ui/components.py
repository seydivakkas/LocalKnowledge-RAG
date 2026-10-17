"""Reusable Tk-only UI components. No SQL, PDF, OCR, or network operations."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from .theme import FONT, TOKENS, accessible_button
from .routes import ROUTES, RouteId


def text(parent: tk.Misc, value: str, *, size=10, weight="normal", color: str | None = None, bg: str | None = None, **kwargs) -> tk.Label:
    label = tk.Label(parent, text=value, font=(FONT, size, weight), fg=color or TOKENS["text"], bg=bg or TOKENS["card"], **kwargs)
    return label


class Card(tk.Frame):
    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=TOKENS["border"], bd=0, **kwargs)
        self.inner = tk.Frame(self, bg=TOKENS["card"], padx=18, pady=16)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)


class MetricCard(Card):
    def __init__(self, parent, caption: str, value: str, footnote: str):
        super().__init__(parent)
        text(self.inner, caption, size=10, color=TOKENS["muted"]).pack(anchor="w")
        text(self.inner, value, size=25, weight="bold").pack(anchor="w", pady=(4, 2))
        text(self.inner, footnote, size=9, color=TOKENS["muted"], wraplength=153, justify="left").pack(anchor="w")


class StatusPill(tk.Label):
    def __init__(self, parent, label: str, *, kind="warning"):
        styles = {
            "warning": ("#FFF1D8", "#9F5E10"),
            "info": (TOKENS["light_blue"], "#2C569C"),
            "success": ("#DEF5EB", TOKENS["success"]),
            "muted": (TOKENS["soft"], TOKENS["muted"]),
        }
        bg, fg = styles[kind]
        super().__init__(parent, text=label, font=(FONT, 9, "bold"), bg=bg, fg=fg, padx=11, pady=5)


class EmptyState(tk.Frame):
    def __init__(self, parent, title: str, explanation: str, *, bg: str | None = None):
        bg = bg or TOKENS["card"]
        super().__init__(parent, bg=bg, pady=38)
        text(self, "▣", size=26, color=TOKENS["primary"], bg=bg).pack()
        text(self, title, size=14, weight="bold", bg=bg).pack(pady=(8, 5))
        text(self, explanation, size=10, color=TOKENS["muted"], bg=bg, wraplength=380, justify="center").pack()


class TopBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=TOKENS["card"], height=72)
        self.pack_propagate(False)
        self.title = text(self, "Ana Panel", size=19, weight="bold")
        self.title.pack(side="left", padx=(29, 10))
        pill = StatusPill(self, "G08  •  MÜHENDİSLİK ÖNİZLEMESİ", kind="info")
        pill.pack(side="right", padx=(8, 24))
        text(self, "Yerel masaüstü", color=TOKENS["muted"]).pack(side="right", padx=(0, 4))

    def update_title(self, title: str) -> None:
        self.title.configure(text=title)


class SideNav(tk.Frame):
    def __init__(self, parent, *, select_route: Callable[[RouteId], None]):
        super().__init__(parent, bg=TOKENS["nav"], width=248)
        self.pack_propagate(False)
        self.select_route = select_route
        self.nav_buttons: dict[RouteId, tk.Button] = {}
        brand = tk.Frame(self, bg=TOKENS["nav"], height=104)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        tk.Label(brand, text="◇", fg="#55A0FF", bg=TOKENS["nav"], font=(FONT, 29, "bold")).pack(side="left", padx=(22, 14))
        brand_text = tk.Frame(brand, bg=TOKENS["nav"])
        brand_text.pack(side="left", anchor="center", pady=24)
        text(brand_text, "LocalKnowledge", size=14, weight="bold", color="white", bg=TOKENS["nav"]).pack(anchor="w")
        text(brand_text, "Çevrimdışı bilgi merkezi", size=9, color=TOKENS["nav_muted"], bg=TOKENS["nav"]).pack(anchor="w", pady=(4, 0))

        rule = tk.Frame(self, height=1, bg="#284361")
        rule.pack(fill="x")
        canvas = tk.Canvas(self, bg=TOKENS["nav"], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, command=canvas.yview, width=9, relief="flat")
        self.menu = tk.Frame(canvas, bg=TOKENS["nav"])
        window = canvas.create_window((0, 0), window=self.menu, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, pady=10)
        sb.pack(side="right", fill="y")
        self.menu.bind("<Configure>", lambda _evt: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda evt: canvas.itemconfigure(window, width=evt.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120) if e.delta else 0, "units"))
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-2, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(2, "units"))

        last_group = None
        for route in ROUTES:
            if route.group != last_group:
                last_group = route.group
                text(self.menu, route.group, size=8, weight="bold", color="#718CA9", bg=TOKENS["nav"]).pack(anchor="w", padx=24, pady=(14, 6))
            enabled = route.navigable
            label = "  " + route.title
            btn = tk.Button(self.menu, text=label, command=lambda rid=route.route: self.select_route(rid),
                            anchor="w", font=(FONT, 10, "normal"), bg=TOKENS["nav"],
                            fg="#D1DCE9" if enabled else "#71849E",
                            activebackground=TOKENS["nav_hover"], activeforeground="white",
                            bd=0, relief="flat", cursor="hand2" if enabled else "arrow",
                            padx=13, pady=8, state="normal" if enabled else "disabled",
                            disabledforeground="#71849E", highlightthickness=2,
                            highlightbackground=TOKENS["nav"], highlightcolor="#64A9FF", takefocus=enabled)
            btn.pack(fill="x", padx=13, pady=1)
            self.nav_buttons[route.route] = btn

        bottom = tk.Frame(self, bg="#1D3450", padx=14, pady=13)
        bottom.pack(side="bottom", fill="x", padx=14, pady=15)
        text(bottom, "●  Yerel belge deposu", color="#65DCB5", bg="#1D3450", size=9, weight="bold").pack(anchor="w")
        text(bottom, "FTS5/BM25 araması etkin", color="#AFBFD3", bg="#1D3450", size=8).pack(anchor="w", pady=(5, 0))

    def select(self, route: RouteId) -> None:
        for rid, button in self.nav_buttons.items():
            active = rid == route
            enabled = button.cget("state") == "normal"
            button.configure(bg=TOKENS["nav_active"] if active else TOKENS["nav"],
                             fg="white" if active else "#D1DCE9" if enabled else "#71849E")


class ActionRow(tk.Frame):
    def __init__(self, parent, *, title: str, description: str, action, active=True):
        super().__init__(parent, bg=TOKENS["soft"], highlightbackground=TOKENS["border"], highlightthickness=1)
        area = tk.Frame(self, bg=TOKENS["soft"])
        area.pack(side="left", fill="both", expand=True, padx=14, pady=9)
        text(area, title, size=10, weight="bold", bg=TOKENS["soft"]).pack(anchor="w")
        text(area, description, size=9, color=TOKENS["muted"], bg=TOKENS["soft"], wraplength=190, justify="left").pack(anchor="w", pady=(3, 0))
        btn = accessible_button(self, "→", action)
        btn.pack(side="right", padx=(6, 10), pady=5)
        if not active:
            btn.configure(state="disabled")
