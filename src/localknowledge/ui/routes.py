"""Static navigation catalogue and explicit delivery gates.

HOME, LIBRARY, IMPORT, HISTORY and ABOUT implemented through G03. Planned P0 routes
may open an informational placeholder but never a fake functional screen.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RouteId(str, Enum):
    HOME = "UI-01"
    LIBRARY = "UI-02"
    IMPORT = "UI-03"
    SEARCH = "UI-04"
    SOURCE = "UI-05"
    GROUNDED = "UI-06"
    EVIDENCE = "UI-07"
    JOBS = "UI-08"
    SAVED = "UI-09"
    COLLECTIONS = "UI-10"
    QUALITY = "UI-11"
    BACKUP = "UI-12"
    HISTORY = "UI-13"
    SETTINGS = "UI-14"
    OCR = "UI-15"
    ABOUT = "UI-16"


@dataclass(frozen=True, slots=True)
class RouteSpec:
    route: RouteId
    title: str
    group: str
    stage: str
    implemented: bool = False
    navigable: bool = True


ROUTES: tuple[RouteSpec, ...] = (
    RouteSpec(RouteId.HOME, "Ana Panel", "BELGELER", "G02", True),
    RouteSpec(RouteId.LIBRARY, "Belge Kütüphanesi", "BELGELER", "G03", True),
    RouteSpec(RouteId.IMPORT, "Belge Ekle", "BELGELER", "G03", True),
    RouteSpec(RouteId.SEARCH, "Kaynaklı Arama", "BELGELER", "G05", True),
    RouteSpec(RouteId.SOURCE, "Kaynak Görüntüleyici", "BELGELER", "G07", True),
    RouteSpec(RouteId.JOBS, "İş Kuyruğu", "BELGELER", "G04", True),
    RouteSpec(RouteId.HISTORY, "Belge Sürümleri", "BELGELER", "G03", True),
    RouteSpec(RouteId.GROUNDED, "Kanıtlı Yanıtlar", "YAPAY ZEKÂ", "P1", navigable=False),
    RouteSpec(RouteId.EVIDENCE, "Kanıt İnceleme", "YAPAY ZEKÂ", "P1", navigable=False),
    RouteSpec(RouteId.OCR, "Taranmış PDF / OCR", "YAPAY ZEKÂ", "P2", navigable=False),
    RouteSpec(RouteId.SAVED, "Kaydedilmiş Aramalar", "ARAÇLAR", "Öneri", navigable=False),
    RouteSpec(RouteId.COLLECTIONS, "Proje Koleksiyonları", "ARAÇLAR", "Öneri", navigable=False),
    RouteSpec(RouteId.QUALITY, "Kalite / Benchmark", "ARAÇLAR", "G09+"),
    RouteSpec(RouteId.BACKUP, "Yedekleme", "ARAÇLAR", "G08", True),
    RouteSpec(RouteId.SETTINGS, "Ayarlar", "SİSTEM", "G03+"),
    RouteSpec(RouteId.ABOUT, "Hakkında", "SİSTEM", "G02", True),
)

ROUTE_MAP = {route.route: route for route in ROUTES}
assert len(ROUTE_MAP) == 16, "Route IDs must be unique"
