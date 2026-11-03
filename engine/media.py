"""ffmpeg helpers. Uses the ffmpeg that AI Creator Studio installed (it has libass, x264 and loudnorm)."""
import json
import re
import subprocess

from .config import FFMPEG


def run(cmd, cwd=None, quiet=False):
    cmd = [str(c) for c in cmd]
    if not quiet:
        print("  $", " ".join(cmd)[:300], flush=True)
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {res.stderr.strip()[-800:]}")
    return res


def ffmpeg(*args, cwd=None):
    return run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd)


def probe(path):
    """Duration, size, fps and audio presence, parsed from `ffmpeg -i` (no ffprobe is installed)."""
    res = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0, "has_audio": False, "has_video": False}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", res.stderr)
    if m:
        info["duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in res.stderr.splitlines():
        if "Video:" in line and not info["has_video"]:
            info["has_video"] = True
            size = re.search(r", (\d{2,5})x(\d{2,5})", line)
            fps = re.search(r"([\d.]+) fps", line)
            if size:
                info["width"], info["height"] = int(size[1]), int(size[2])
            if fps:
                info["fps"] = float(fps[1])
        if "Audio:" in line:
            info["has_audio"] = True
    return info


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP) of a file's audio."""
    res = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn",
                          "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    if not m:
        return None
    data = json.loads(m.group(0))
    return {"lufs": float(data["input_i"]), "true_peak": float(data["input_tp"]), "lra": float(data["input_lra"])}
