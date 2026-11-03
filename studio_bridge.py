#!/usr/bin/env python3
"""Runs INSIDE AI Creator Studio's Python (it has the voice-clone, caption-timing and lip-sync models).

Calls studio.py's stages 1-4 (voice -> word timings -> avatar clip -> lip-sync) and stops there,
because the Content Engine does its own, richer final edit. Writes <job>/manifest.json.
Studio's files are only imported, never modified.

usage: <studio>/.venv/bin/python studio_bridge.py job.json
"""
import hashlib
import json
import os
import sys
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text())
studio_dir = Path(spec["studio_dir"])
sys.path.insert(0, str(studio_dir))
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # models come from ./setup.sh; online checks hang on slow links
import studio  # noqa: E402

job = Path(spec["job"])
job.mkdir(parents=True, exist_ok=True)
script = spec["script"].strip()
key = hashlib.sha256(json.dumps([script, spec["voice_engine"], spec.get("voice_sample"), spec.get("tts_model")],
                                sort_keys=True).encode()).hexdigest()[:16]
voice = job / "voice.wav"
stamp = job / "voice.key"

# The cloned voice is the slow part: reuse it when only the edit settings changed.
if voice.exists() and stamp.exists() and stamp.read_text() == key:
    print("1/4 voice (reused from earlier run)", flush=True)
else:
    print("1/4 voice", flush=True)
    studio.stage_voice(script, spec.get("voice_sample"), job, spec["voice_engine"],
                       spec.get("tts_model") or studio.DEFAULT_TTS_MODEL, spec.get("voice_sample_text") or None)
    stamp.write_text(key)
print("2/4 word timings", flush=True)
words = studio.stage_words(voice, script, job, spec.get("whisper_model") or studio.DEFAULT_WHISPER_MODEL)
duration = studio.audio_duration(voice)
print("3/4 avatar clip", flush=True)
base = studio.stage_avatar(spec["avatar"], duration, job)
print("4/4 lip-sync" + (" (off)" if spec["lipsync"] == "none" else ""), flush=True)
talking = studio.stage_lipsync(base, voice, job, spec["lipsync"])
(job / "manifest.json").write_text(json.dumps({
    "voice": str(voice), "words": str(job / "words.json"), "video": str(talking),
    "duration": duration, "lipsync": spec["lipsync"]}, indent=1))
print("bridge done", flush=True)
