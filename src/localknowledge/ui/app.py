"""G08 Tkinter application: verified original PDF and local text sources."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from .. import __version__
from ..application import AppServices
from .components import Card, MetricCard, EmptyState, ActionRow, SideNav, StatusPill, TopBar, text
from .routes import ROUTE_MAP, RouteId
from .state import Router
from .theme import FONT, TOKENS, accessible_button, configure
from .documents import show_library, show_import, show_history
from .jobs import show_jobs
from .search import show_search
from .source import show_source
from .backup import show_backup


def _windows_dpi() -> None:
    """Request system-aware DPI before constructing Tk. No hardcoded 96dpi."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError, ValueError):
            pass  # Tk still inherits the OS/application DPI defaults.


class LocalKnowledgeApp(tk.Tk):
    def __init__(self, *, services: AppServices | None = None):
        super().__init__()
        self.title("LocalKnowledge — Yerel Belge Kütüphanesi [G08 önizleme]")
        self.geometry("1440x900")
        self.minsize(1100, 720)
        self.router = Router()
        self.ingest_busy = False
        self.backup_busy = False
        self.source_chunk_id = None
        self.source_query = None
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.services = services or AppServices()
        self.services.runner.start(workers=1)
        configure(self)
        self.sidebar = SideNav(self, select_route=self.open_route)
        self.sidebar.pack(side="left", fill="y")
        right = tk.Frame(self, bg=TOKENS["canvas"])
        right.pack(side="left", fill="both", expand=True)
        self.topbar = TopBar(right)
        self.topbar.pack(fill="x")
        tk.Frame(right, height=1, bg=TOKENS["border"]).pack(fill="x")
        self.content_canvas = tk.Canvas(right, bg=TOKENS["canvas"], highlightthickness=0, bd=0)
        self.content_scrollbar = tk.Scrollbar(right, command=self.content_canvas.yview)
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_scrollbar.pack(side="right", fill="y")
        self.content = tk.Frame(self.content_canvas, bg=TOKENS["canvas"])
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda _e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.bind("<Configure>", self._on_canvas_resize)
        self.content_canvas.bind("<MouseWheel>", self._scroll_on_main)
        self.content_canvas.bind("<Button-4>", lambda _: self.content_canvas.yview_scroll(-2, "units"))
        self.content_canvas.bind("<Button-5>", lambda _: self.content_canvas.yview_scroll(2, "units"))
        # The app's disabled actions are still navigable through a truthful placeholder.
        self.bind_all("<Control-1>", lambda _: self.open_route(RouteId.HOME))
        self.bind_all("<Control-l>", lambda _: self.open_route(RouteId.LIBRARY))
        self.bind_all("<Control-o>", lambda _: self.open_route(RouteId.IMPORT))
        self.bind_all("<Control-f>", lambda _: self.open_route(RouteId.SEARCH))
        self.bind_all("<Control-k>", lambda _: self.open_route(RouteId.SEARCH))
        self.bind_all("<Escape>", lambda _: self.focus_set())
        self.open_route(RouteId.HOME)
        self.after_idle(lambda: self.sidebar.nav_buttons[RouteId.HOME].focus_set())

    def _close(self) -> None:
        if self.ingest_busy or self.backup_busy:
            messagebox.showwarning("İşlem sürüyor", "İçe alma veya yedekleme tamamlanmadan pencere kapatılamaz.", parent=self)
            return
        self.services.runner.stop()
        self.destroy()

    def _on_canvas_resize(self, evt: tk.Event) -> None:
        self.content_canvas.itemconfigure(self.content_window, width=evt.width)

    def _scroll_on_main(self, evt: tk.Event) -> None:
        if evt.delta:
            self.content_canvas.yview_scroll(int(-evt.delta / 120), "units")

    def _reset_content(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()
        self.content_canvas.yview_moveto(0)

    def open_route(self, route: RouteId) -> bool:
        if self.backup_busy and self.router.state.current_route is RouteId.BACKUP:
            messagebox.showwarning('Yedekleme sürüyor','Yedekleme/geri yükleme bitmeden sayfa değiştirilemez.',parent=self)
            return False
        if not self.router.open(route):
            return False
        self._reset_content()
        spec = ROUTE_MAP[route]
        self.topbar.update_title(spec.title)
        self.sidebar.select(route)
        if route is RouteId.HOME:
            self._show_home()
        elif route is RouteId.LIBRARY:
            show_library(self)
        elif route is RouteId.IMPORT:
            show_import(self)
        elif route is RouteId.HISTORY:
            show_history(self)
        elif route is RouteId.JOBS:
            show_jobs(self)
        elif route is RouteId.SEARCH:
            show_search(self)
        elif route is RouteId.SOURCE:
            show_source(self)
        elif route is RouteId.BACKUP:
            show_backup(self)
        elif route is RouteId.ABOUT:
            self._show_about()
        else:
            self._show_coming_soon(route)
        return True

    def _page_header(self, subtitle: str):
        holder = tk.Frame(self.content, bg=TOKENS["canvas"])
        holder.pack(fill="x", padx=30, pady=(24, 20))
        text(holder, subtitle, color=TOKENS["muted"], size=11, bg=TOKENS["canvas"]).pack(anchor="w")
        return holder

    def _show_home(self) -> None:
        self._page_header("Belgelerinizden doğrulanabilir bilgiye — tamamen yerel mimari.")
        snap = self.services.dashboard.summary()
        if snap.available:
            metrics = [
                ("Kayıtlı Belge", snap.registered_documents, "SQLite yerel kayıtları"),
                ("Belge Sürümü", snap.stored_versions, "SHA-256 ile saklanmış"),
                ("Metin Bekleyen", snap.pending_index, "G04 çıkarma işleri"),
                ("Aranabilir Bölüm", snap.indexed_chunks, f"{snap.indexed_documents} belgede FTS5"),
            ]
        else:
            metrics = [
                ("Kayıtlı Belge", None, "Veritabanı açılamadı"),
                ("Belge Sürümü", None, "Doğrulanamadı"),
                ("Metin Bekleyen", None, "Doğrulanamadı"),
                ("Aranabilir Bölüm", None, "Doğrulanamadı"),
            ]
        metric_row = tk.Frame(self.content, bg=TOKENS["canvas"])
        metric_row.pack(fill="x", padx=30, pady=(0, 18))
        for i in range(4):
            metric_row.columnconfigure(i, weight=1, uniform="metric")
        for i, (caption, value, footnote) in enumerate(metrics):
            card = MetricCard(metric_row, caption, (str(value) if value is not None else "—"), footnote)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6))

        grid = tk.Frame(self.content, bg=TOKENS["canvas"])
        grid.pack(fill="x", padx=30)
        grid.columnconfigure(0, weight=7, uniform="content")
        grid.columnconfigure(1, weight=4, uniform="content")
        recent = Card(grid)
        recent.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        text(recent.inner, "Son Belgeler", size=14, weight="bold").pack(anchor="w")
        text(recent.inner, "SQLite deposundaki son kayıtlar", size=9, color=TOKENS["muted"]).pack(anchor="w", pady=(3, 10))
        if snap.last_documents:
            for doc in snap.last_documents:
                line = tk.Frame(recent.inner, bg=TOKENS["soft"], padx=12, pady=10)
                line.pack(fill="x", pady=(0, 6))
                text(line, doc.name, size=10, weight="bold", bg=TOKENS["soft"]).pack(side="left")
                text(line, f"{doc.kind} · v{doc.revision} · Kayıtlı", size=9, color=TOKENS["muted"], bg=TOKENS["soft"]).pack(side="right")
        else:
            EmptyState(recent.inner, "Kütüphane henüz boş", "Belge Ekle ile PDF, DOCX veya TXT içe alın. Kayıtlar yerel SQLite veritabanında saklanır.").pack(fill="both", expand=True)

        actions = Card(grid)
        actions.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        text(actions.inner, "Hızlı İşlemler", size=14, weight="bold").pack(anchor="w")
        text(actions.inner, "Hazırlanan ekranlara geçiş", size=9, color=TOKENS["muted"]).pack(anchor="w", pady=(3, 12))
        for title, desc, route in (
            ("Belge Ekle", "Yerel dosyaları içe al", RouteId.IMPORT),
            ("Kaynaklı Ara", "FTS5 / BM25 ile gerçek belge araması", RouteId.SEARCH),
            ("İndeks Durumu", "G04: metin çıkarma ilerlemesi", RouteId.JOBS),
            ("Yedekleme", "G08 kapsamındaki güvenli yedek", RouteId.BACKUP),
        ):
            row = ActionRow(actions.inner, title=title, description=desc, action=lambda r=route: self.open_route(r))
            row.pack(fill="x", pady=(0, 9))

        evidence = Card(self.content)
        evidence.pack(fill="x", padx=30, pady=(18, 24))
        text(evidence.inner, "Kaynak Doğrulama İlkesi", size=14, weight="bold").pack(anchor="w")
        text(evidence.inner, "G07 özgün PDF sayfasını gösterir; yalnız doğrulanmış koordinatlar sarı işaretlenir. Şüpheli konumda işaretleme yoktur.", color=TOKENS["muted"], size=10).pack(anchor="w", pady=(5, 11))
        badges = tk.Frame(evidence.inner, bg=TOKENS["card"])
        badges.pack(anchor="w")
        StatusPill(badges, "Yanlış eşleşmede bağlantı oluşturulmaz", kind="warning").pack(side="left", padx=(0, 9))
        StatusPill(badges, "Dış API gerektirmeyen tasarım", kind="success").pack(side="left")
        text(evidence.inner, "Durum: G07 PDF sayfa görüntüleyicisi ve temkinli işaretleme hazır · LLM ve OCR henüz bağlı değil.", size=9, color=TOKENS["muted"]).pack(anchor="w", pady=(13, 0))

    def _show_coming_soon(self, route: RouteId) -> None:
        spec = ROUTE_MAP[route]
        self._page_header(f"{spec.stage} — Henüz uygulanmayan özellik")
        card = Card(self.content)
        card.pack(fill="x", padx=30)
        EmptyState(card.inner, "Bu ekran geliştirme aşamasında", f"{spec.title} ekranı {spec.stage} kapsamında gerçek servisle bağlanacaktır. Şu anda yalnızca navigasyon ve tasarım sistemi hazır.").pack(fill="x")
        box = tk.Frame(card.inner, bg=TOKENS["card"])
        box.pack(fill="x", pady=(8, 20))
        StatusPill(box, "Henüz kullanılabilir değil", kind="warning").pack(side="left")
        accessible_button(box, "Ana Panele Dön", lambda: self.open_route(RouteId.HOME)).pack(side="right")

    def _show_about(self) -> None:
        self._page_header("Yerel masaüstü proje bilgileri ve mühendislik durumu")
        card = Card(self.content)
        card.pack(fill="x", padx=30)
        text(card.inner, "LocalKnowledge", size=23, weight="bold").pack(anchor="w")
        text(card.inner, f"Sürüm {__version__}", size=11, color=TOKENS["muted"]).pack(anchor="w", pady=(8, 16))
        for title, value in (
            ("Geliştirme aşaması", "G00–G03 temel uygulama · G04 asenkron metin çıkarma"),
            ("Teknoloji", "Python + Tkinter / ttk · SQLite · pdfplumber · python-docx"),
            ("Veritabanı ve arama", "SQLite v3, iş kuyruğu, FTS5/BM25 ve G07 kaynak görüntüleyici hazır"),
            ("Yerel AI / OCR", "P1 ve P2 isteğe bağlı; mevcut değil"),
            ("Çevrimdışı gereksinim", "G03 temel işlevleri ağ gerektirmez; uçtan uca Windows kabulü açık"),
            ("Ticari dağıtım", "HOLD — lisans, paketleme ve gerçek Windows kabulü bekleniyor"),
        ):
            block = tk.Frame(card.inner, bg=TOKENS["card"])
            block.pack(fill="x", pady=7)
            text(block, title, weight="bold").pack(anchor="w")
            text(block, value, color=TOKENS["muted"], wraplength=750, justify="left").pack(anchor="w", pady=(4, 0))
        accessible_button(card.inner, "Ana Panele Dön", lambda: self.open_route(RouteId.HOME), primary=True).pack(anchor="w", pady=(18, 3))


def run() -> int:
    _windows_dpi()
    try:
        app = LocalKnowledgeApp()
    except tk.TclError as exc:
        print(f"Tkinter masaüstü oturumu açılamadı: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        from ..storage.db import DatabaseError
        if not isinstance(exc, DatabaseError):
            raise
        print(f"Yerel belge deposu açılamadı; veri değiştirilmedi: {exc}", file=sys.stderr)
        return 3
    app.mainloop()
    return 0
