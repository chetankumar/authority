"""Launcher configuration (doc 02).

Reads ``launcher.config.json`` from the repository root, creating it with
defaults on first run. Also resolves the key filesystem paths the app relies
on: the built SPA directory and the runtime log file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# app/core/config.py -> app -> backend -> src -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "launcher.config.json"

DEFAULT_CONFIG = {
    "port": 8700,
    "appDataRoot": "./data",
    "envName": "authority",
}


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
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        raw = dict(DEFAULT_CONFIG)
    else:
        raw = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}

    app_data_root = (REPO_ROOT / raw["appDataRoot"]).resolve()
    return Config(
        port=int(raw["port"]),
        app_data_root=app_data_root,
        env_name=str(raw["envName"]),
    )
