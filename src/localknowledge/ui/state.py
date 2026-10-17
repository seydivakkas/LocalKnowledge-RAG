"""Pure view-model state; separate from Tk widgets for headless testing."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .routes import RouteId, ROUTE_MAP


class ViewStatus(str, Enum):
    IDLE = "IDLE"
    LOADING = "LOADING"
    EMPTY = "EMPTY"
    READY = "READY"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    STALE = "STALE"


@dataclass(slots=True)
class AppState:
    current_route: RouteId = RouteId.HOME
    view_status: ViewStatus = ViewStatus.EMPTY
    status_message: str = "Yerel FTS5/BM25 araması hazır; kaynak kanıtı doğrulanır."
    query: str = ""
    selected_document_id: str | None = None
    selected_version_sha: str | None = None


@dataclass(slots=True)
class Router:
    state: AppState = field(default_factory=AppState)

    def open(self, route: RouteId) -> bool:
        if route not in ROUTE_MAP or not ROUTE_MAP[route].navigable:
            return False
        self.state.current_route = route
        self.state.view_status = (ViewStatus.EMPTY if ROUTE_MAP[route].implemented else ViewStatus.DISABLED)
        self.state.status_message = ("Yerel FTS5/BM25 araması hazır; kaynak kanıtı doğrulanır." if ROUTE_MAP[route].implemented else f"{ROUTE_MAP[route].stage} kapsamında geliştirilecek.")
        return True
