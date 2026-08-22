"""Filesystem anchors for the project.

Everything resolves from the repository root, so the app behaves the same no
matter which directory it is started from.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

APP_DIR = BASE_DIR / "app"
SETTINGS_DIR = APP_DIR / "core" / "settings"

DATA_DIR = BASE_DIR / "data"
VAR_DIR = BASE_DIR / "var"

ENV_FILE = BASE_DIR / ".env"


def var_path(*parts: str) -> Path:
    """Return a path under ``var/`` (runtime output), creating its parent."""
    path = VAR_DIR.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
