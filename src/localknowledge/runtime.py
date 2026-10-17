"""G09: one executable routes both GUI/CLI and private worker entrypoints.

PyInstaller --onedir freezes sys.executable into the application EXE. Never
spawn `LocalKnowledge.exe -m package.module`, because that launches the GUI.
"""
from __future__ import annotations
import os
import sys

PRIVATE_WORKER_ROUTES = {
    "pdf": "--internal-pdf-worker",
    "extract": "--internal-extract-worker",
}


def worker_command(kind: str, *args: str, executable: str | None = None, frozen: bool | None = None) -> list[str]:
    if kind not in PRIVATE_WORKER_ROUTES:
        raise ValueError("Unknown worker kind")
    exe = executable or sys.executable
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return [exe, PRIVATE_WORKER_ROUTES[kind], *map(str, args)]
    module = "localknowledge.viewer.worker" if kind == "pdf" else "localknowledge.jobs.worker"
    return [exe, "-m", module, *map(str, args)]


def dispatch_private_worker(argv: list[str]) -> int | None:
    if not argv:
        return None
    if argv[0] == PRIVATE_WORKER_ROUTES["pdf"]:
        from .viewer.worker import main
    elif argv[0] == PRIVATE_WORKER_ROUTES["extract"]:
        from .jobs.worker import main
    else:
        return None
    # These worker modules accept the same positional argv as their `-m` mode.
    old = sys.argv
    try:
        sys.argv = [old[0], *argv[1:]]
        return int(main())
    finally:
        sys.argv = old
