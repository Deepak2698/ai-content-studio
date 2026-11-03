"""./ce doctor: checks everything the engine needs and says, in plain words, what to fix."""
import shutil
import subprocess

from . import config, publish, render, schedule
from .clients import all_clients

OK, WARN, BAD = "✅", "🟡", "❌"


def line(mark, text, fix=""):
    print(f"{mark} {text}" + (f"\n     → {fix}" if fix else ""))
    return mark


def run():
    marks = []
    print("Content Engine check-up\n")

    print("Render engine (AI Creator Studio)")
    probs = render.studio_problems()
    if probs:
        marks.append(line(BAD, probs[0], "Check STUDIO_DIR in .env"))
    else:
        marks.append(line(OK, f"found at {config.STUDIO_DIR}"))
        res = subprocess.run([config.FFMPEG, "-hide_banner", "-filters"], capture_output=True, text=True)
        need = ["subtitles", "loudnorm", "sidechaincompress", "zoompan", "overlay"]
        missing = [f for f in need if f" {f} " not in res.stdout]
        marks.append(line(BAD if missing else OK, "ffmpeg editing filters" + (f" missing: {missing}" if missing else " ok")))
        r = subprocess.run([str(config.STUDIO_PYTHON), "-c", "import mlx_audio, mlx_whisper"], capture_output=True)
        marks.append(line(OK if r.returncode == 0 else WARN, "voice cloning + caption timing installed"
                          if r.returncode == 0 else "voice cloning not installed",
                          "" if r.returncode == 0 else "In ai-creator-studio run: ./setup.sh voice"))
        marks.append(line(OK if render.lipsync_installed() else WARN,
                          "lip-sync installed" if render.lipsync_installed() else "lip-sync not installed (reels render without lip movement)",
                          "" if render.lipsync_installed() else "In ai-creator-studio run: ./setup.sh lipsync"))

    print("\nAI script writer")
    if config.env("ANTHROPIC_API_KEY"):
        marks.append(line(OK, f"Anthropic key present, model {config.env('CLAUDE_MODEL', 'claude-opus-5-5')}"))
    else:
        marks.append(line(WARN, "no ANTHROPIC_API_KEY: rows need a hand-written script",
                          "Paste your key into .env (console.anthropic.com → API Keys)"))

    print("\nContent calendar")
    try:
        from .sheet import open_sheet
        sh = open_sheet()
        rows = sh.rows()
        marks.append(line(OK, f"{sh.describe()}: {len(rows)} rows"))
    except SystemExit as e:
        marks.append(line(BAD, str(e)))
    except Exception as e:
        marks.append(line(BAD, f"can't open the calendar: {str(e)[:200]}", "See docs/GOOGLE_SHEETS_SETUP.md"))

    print("\nClients")
    for c in all_clients():
        probs = c.problems()
        mark = OK if not probs else WARN
        extra = []
        if not c.music_files():
            extra.append("no music")
        if not c.file(c.brand.get("logo")):
            extra.append("no logo")
        marks.append(line(mark, f"{c.slug}: " + ("ready" if not probs else "; ".join(probs)) +
                          (f" ({', '.join(extra)})" if extra else ""),
                          "" if not probs else f"See clients/{c.slug}/ and README → 'Your voice and face'"))

    print("\nStock b-roll")
    keys = [k for k in ("PEXELS_API_KEY", "PIXABAY_API_KEY") if config.env(k)]
    marks.append(line(OK if keys else WARN, f"keys: {', '.join(keys)}" if keys else "no Pexels/Pixabay key: reels have no b-roll",
                      "" if keys else "Free key: pexels.com/api, then paste into .env"))

    print("\nPublishing")
    st = publish.status()
    print(f"   auto-posting is {'ON' if st.pop('AUTO_POST') else 'OFF (finished reels go to ready/)'}")
    for name, (ok, why) in st.items():
        print(f"   {name}: {'enabled' if ok else 'off'} ({why})")

    print("\nMachine")
    free = shutil.disk_usage(config.ROOT).free / 1e9
    marks.append(line(OK if free > 20 else WARN, f"{free:.0f} GB free disk"))
    batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    on_ac = "AC Power" in batt
    marks.append(line(OK if on_ac else WARN, "plugged in" if on_ac else "on battery: renders can be 10x slower",
                      "" if on_ac else "Plug in the Mac before rendering"))
    print(f"   schedule: {'installed' if schedule.installed() else 'not installed (./ce schedule on)'}")

    print()
    if BAD in marks:
        print("Some things need fixing (❌) before the engine can run.")
        return 1
    print("Ready." + (" Some optional extras are missing (🟡)." if WARN in marks else ""))
    return 0
