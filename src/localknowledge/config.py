"""Local-only user settings location; no socket/cloud integration."""
from __future__ import annotations

from pathlib import Path
import os


def data_dir() -> Path:
    override = os.environ.get("LOCALKNOWLEDGE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        return Path(appdata).expanduser() / "LocalKnowledge"
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home).expanduser() / "LocalKnowledge"
    return Path.home() / ".local" / "share" / "LocalKnowledge"
