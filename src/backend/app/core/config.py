"""Launcher configuration (doc 02).

Reads ``launcher.config.json`` from the repository root, creating it with
defaults on first run. Also resolves the key filesystem paths the app relies
on: the built SPA directory and the runtime log file.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# app/core/config.py -> app -> backend -> src -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "launcher.config.json"

DEFAULT_PORT = 8700
DEFAULT_ENV_NAME = "authority"


def _default_app_data_root() -> Path:
    """OS-standard per-user app-data directory, deliberately **outside** the
    repo. ``app.json`` holds API keys and the only settings the author has —
    it must not live somewhere a repo-wide ``git clean``, ``rm -rf``, or other
    working-tree operation could sweep it up as if it were disposable build
    output. Windows uses ``%LOCALAPPDATA%`` (not Roaming — this is
    machine-local secret material, not something that should sync via a
    domain roaming profile).
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Authority"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Authority"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "authority"


@dataclass(frozen=True)
class Config:
    port: int
    app_data_root: Path
    env_name: str

    @property
    def frontend_dist(self) -> Path:
        """The Vite build output served statically by the backend."""
        return REPO_ROOT / "src" / "frontend" / "dist"

    @property
    def log_file(self) -> Path:
        return REPO_ROOT / "logs" / "api.log"

    @property
    def app_json(self) -> Path:
        """App-level settings store (user, models, ai, aiJobs) — doc 03."""
        return self.app_data_root / "app.json"


def load_config() -> Config:
    """Load ``launcher.config.json``, writing defaults if it is absent."""
    if not CONFIG_PATH.exists():
        raw = {"port": DEFAULT_PORT, "appDataRoot": str(_default_app_data_root()), "envName": DEFAULT_ENV_NAME}
        CONFIG_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    else:
        on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        raw = {"port": DEFAULT_PORT, "appDataRoot": str(_default_app_data_root()), "envName": DEFAULT_ENV_NAME, **on_disk}

    # A relative appDataRoot (e.g. explicit "./data" for local dev) resolves
    # against the repo root, same as before; an absolute path — the default
    # now — is used as-is.
    configured = Path(raw["appDataRoot"])
    app_data_root = configured if configured.is_absolute() else (REPO_ROOT / configured).resolve()

    return Config(
        port=int(raw["port"]),
        app_data_root=app_data_root,
        env_name=str(raw["envName"]),
    )
