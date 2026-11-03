"""Clients: one folder per person/brand in clients/<slug>/ with brand.json, consent.json and their media.

clients/<slug>/
  brand.json      tone of voice, colours, fonts, logo, music, which voice + avatar to use
  consent.json    written permission to clone this person's voice and face (required for real people)
  voice.wav       15-30 s clean voice sample          (or a path pointing elsewhere in brand.json)
  avatar.mp4      10-30 s front-facing video or photo
  logo.png, music/*.mp3, fonts/*.ttf, intro.mp4, outro.mp4   (all optional)
"""
import copy
import json
import shutil
from datetime import date
from pathlib import Path

from .config import CLIENTS_DIR

DEFAULT_BRAND = {
    "name": "",
    "handle": "",
    "language": "English",
    "niche": "",
    "audience": "",
    "tone": "friendly, confident, simple words, no jargon",
    "do": [],
    "dont": [],
    "cta": "Follow for more",
    "voice": {"engine": "clone", "sample": "voice.wav", "sample_text": "", "tts_model": ""},
    "avatar": "avatar.mp4",
    "lipsync": "musetalk",
    "auto_approve": False,
    "platforms": ["instagram", "youtube"],
    "sheet": {"backend": "", "sheet_id": "", "tab": ""},
    "style": {
        "font": "Arial Black", "font_file": "", "primary": "#FFFFFF", "accent": "#FFE500",
        "outline": "#000000", "caption_size": 84, "words_per_line": 3, "caption_y": 0.64,
        "hook_bg": "#000000",
    },
    "logo": "logo.png",
    "intro": "",
    "outro": "",
    "music": "music",
    "music_volume": 0.16,
    "broll": {"enabled": True, "max_clips": 3, "seconds": 2.4},
    "punch_ins": True,
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Client:
    def __init__(self, slug):
        self.slug = slug
        self.dir = CLIENTS_DIR / slug
        if not (self.dir / "brand.json").exists():
            raise ValueError(f"Unknown client '{slug}': create it with  ./ce new-client {slug}")
        self.brand = _merge(DEFAULT_BRAND, json.loads((self.dir / "brand.json").read_text()))
        cpath = self.dir / "consent.json"
        self.consent = json.loads(cpath.read_text()) if cpath.exists() else {}

    def file(self, value):
        """Resolve a brand.json path (relative to the client folder). Returns None if unset or missing."""
        if not value:
            return None
        p = Path(value).expanduser()
        p = p if p.is_absolute() else (self.dir / p).resolve()
        return p if p.exists() else None

    @property
    def voice_engine(self):
        return self.brand["voice"].get("engine", "clone")

    @property
    def voice_sample(self):
        return self.file(self.brand["voice"].get("sample"))

    @property
    def avatar(self):
        return self.file(self.brand.get("avatar"))

    def music_files(self):
        m = self.file(self.brand.get("music"))
        if not m:
            return []
        if m.is_file():
            return [m]
        return sorted(p for p in m.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg"))

    def font_dir(self):
        d = self.dir / "fonts"
        return d if d.is_dir() else None

    def problems(self):
        """Reasons this client can't be rendered yet (empty list = ready)."""
        out = []
        if not self.avatar:
            out.append(f"avatar file missing ({self.brand.get('avatar')})")
        if self.voice_engine == "clone" and not self.voice_sample:
            out.append(f"voice sample missing ({self.brand['voice'].get('sample')})")
        if not self.consent.get("synthetic"):
            # A real person's voice/face: we need their recorded permission before cloning.
            if not (self.consent.get("voice_consent") and self.consent.get("likeness_consent")):
                out.append("consent.json is not signed (voice_consent and likeness_consent must be true)")
            exp = self.consent.get("expires")
            if exp and exp < date.today().isoformat():
                out.append(f"consent expired on {exp}")
        return out


def all_clients():
    return [Client(p.name) for p in sorted(CLIENTS_DIR.iterdir())
            if (p / "brand.json").exists() and not p.name.startswith("_")]


def new_client(slug, name=""):
    dest = CLIENTS_DIR / slug
    if dest.exists():
        raise SystemExit(f"clients/{slug} already exists")
    shutil.copytree(CLIENTS_DIR / "_template", dest)
    brand = json.loads((dest / "brand.json").read_text())
    brand["name"] = name or slug
    (dest / "brand.json").write_text(json.dumps(brand, indent=2, ensure_ascii=False) + "\n")
    return dest
