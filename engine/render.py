"""Step 1 of rendering: script -> cloned voice -> word timings -> (lip-synced) avatar clip, via AI Creator Studio."""
import json
import subprocess
from pathlib import Path

from . import config


def studio_problems():
    out = []
    if not (config.STUDIO_DIR / "studio.py").exists():
        out.append(f"AI Creator Studio not found at {config.STUDIO_DIR} (set STUDIO_DIR in .env)")
    elif not config.STUDIO_PYTHON.exists():
        out.append("AI Creator Studio isn't set up yet: run  ./setup.sh base  inside it")
    return out


def lipsync_installed():
    return (config.STUDIO_DIR / "vendor" / "fast-lipsync" / "lipsync.sh").exists()


def render_avatar(client, script, job: Path, log):
    """Returns the bridge manifest: {voice, words, video, duration}."""
    if problems := studio_problems():
        raise RuntimeError("; ".join(problems))
    lipsync = client.brand.get("lipsync", "musetalk")
    if lipsync != "none" and not lipsync_installed():
        log("lip-sync model not installed in AI Creator Studio, rendering without lip-sync")
        lipsync = "none"
    v = client.brand["voice"]
    spec = {
        "studio_dir": str(config.STUDIO_DIR), "job": str(job), "script": script,
        "voice_engine": "say" if client.voice_engine == "say" else "clone",
        "voice_sample": str(client.voice_sample) if client.voice_sample else None,
        "voice_sample_text": v.get("sample_text"), "tts_model": v.get("tts_model"),
        "whisper_model": client.brand.get("whisper_model"),
        "avatar": str(client.avatar), "lipsync": lipsync,
    }
    job.mkdir(parents=True, exist_ok=True)
    (job / "bridge_job.json").write_text(json.dumps(spec, indent=1))
    with (job / "render.log").open("a") as f:
        proc = subprocess.run([str(config.STUDIO_PYTHON), "-u", str(config.ROOT / "studio_bridge.py"),
                               str(job / "bridge_job.json")], cwd=config.STUDIO_DIR, stdout=f, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        tail = (job / "render.log").read_text()[-600:]
        raise RuntimeError(f"AI Creator Studio render failed (see {job / 'render.log'}): {tail}")
    return json.loads((job / "manifest.json").read_text())
