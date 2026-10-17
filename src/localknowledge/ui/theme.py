"""Tk-native LocalKnowledge visual tokens, matching reference PNGs."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

TOKENS: dict[str, str] = {
    "nav": "#132238", "nav_hover": "#1B314D", "nav_active": "#2852A0",
    "primary": "#246BDA", "canvas": "#F4F7FB", "card": "#FFFFFF",
    "border": "#E4EAF1", "text": "#17253B", "muted": "#6A798E",
    "success": "#139568", "warn": "#B86F1C", "danger": "#C84149",
    "light_blue": "#EAF2FD", "soft": "#EEF3F9", "nav_muted": "#B2C3DB",
}

FONT = "Segoe UI"


def configure(root: tk.Tk) -> None:
    """Use Windows OS fonts/DPI; no bundled fonts or third-party theme."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("LK.Treeview", font=(FONT, 10), rowheight=35, borderwidth=0, background=TOKENS["card"], fieldbackground=TOKENS["card"])
    style.configure("LK.Treeview.Heading", font=(FONT, 10, "bold"), background=TOKENS["soft"], foreground=TOKENS["text"])
    style.map("LK.Treeview", background=[("selected", TOKENS["light_blue"])], foreground=[("selected", TOKENS["text"])])
    style.configure("LK.TScrollbar", troughcolor=TOKENS["canvas"], borderwidth=0)
    root.configure(bg=TOKENS["canvas"])


def accessible_button(parent, text: str, command, *, primary=False, width=0) -> tk.Button:
    background = TOKENS["primary"] if primary else TOKENS["soft"]
    foreground = "white" if primary else TOKENS["text"]
    return tk.Button(
        parent, text=text, command=command, width=width,
        font=(FONT, 10, "bold"), cursor="hand2", bd=0,
        relief="flat", bg=background, fg=foreground, activebackground=("#1959BF" if primary else TOKENS["light_blue"]),
        activeforeground=foreground, padx=14, pady=10, highlightthickness=2, highlightcolor=TOKENS["primary"],
        highlightbackground=background, takefocus=True,
    )
