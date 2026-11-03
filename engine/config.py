"""Paths and settings. Values come from .env (see .env.example); nothing secret is hard-coded."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
OUTPUT_DIR = ROOT / "output"   # work folders (in-between files) per post
READY_DIR = ROOT / "ready"     # finished, ready-to-post packages
CACHE_DIR = ROOT / "cache"     # downloaded b-roll
LOGS_DIR = ROOT / "logs"

W, H, FPS = 1080, 1920, 25


def load_env(path=ROOT / ".env"):
    """Tiny .env reader (KEY=value per line). Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


load_env()


def env(key, default=""):
    return os.environ.get(key, default).strip()


def flag(key):
    return env(key).lower() in ("1", "true", "yes", "on")


def path_setting(key, default):
    p = Path(env(key, default)).expanduser()
    return p if p.is_absolute() else (ROOT / p).resolve()


STUDIO_DIR = path_setting("STUDIO_DIR", "../ai-creator-studio")
STUDIO_PYTHON = STUDIO_DIR / ".venv" / "bin" / "python"
FFMPEG = str(STUDIO_DIR / "bin" / "ffmpeg")
