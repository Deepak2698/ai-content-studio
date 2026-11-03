"""Automatic quality checks on a finished reel. Hard failures stop the row; warnings go to the reviewer."""
import json
from pathlib import Path

from .config import H, W
from .media import loudness, probe


def check(video, words_path=None, platforms=("instagram", "youtube")):
    info = probe(video)
    errors, warnings = [], []
    if not info["has_video"] or not info["has_audio"]:
        errors.append("missing video or audio track")
    if (info["width"], info["height"]) != (W, H):
        errors.append(f"resolution is {info['width']}x{info['height']}, expected {W}x{H} (9:16)")
    d = info["duration"]
    if d < 5:
        errors.append(f"too short ({d:.1f} s)")
    elif d < 15:
        warnings.append(f"short reel ({d:.1f} s); 30-60 s usually performs better")
    if d > 90:
        errors.append(f"{d:.0f} s is longer than Instagram Reels' 90 s limit")
    elif d > 60:
        warnings.append(f"{d:.0f} s is over 60 s: fine for Shorts up to 3 min, but long for Reels")
    if info["fps"] and not 23.5 <= info["fps"] <= 60.5:
        warnings.append(f"unusual frame rate {info['fps']}")

    loud = loudness(video)
    if not loud:
        errors.append("could not measure loudness")
    else:
        if loud["lufs"] < -60:
            errors.append("audio is silent")
        elif abs(loud["lufs"] + 14) > 1.5:
            warnings.append(f"loudness {loud['lufs']:.1f} LUFS (target -14)")
        if loud["true_peak"] > -0.5:
            warnings.append(f"true peak {loud['true_peak']:.1f} dBTP may clip on phones")

    if words_path and Path(words_path).exists():
        words = json.loads(Path(words_path).read_text())
        if not words:
            errors.append("no caption words")
        else:
            back = sum(1 for a, b in zip(words, words[1:]) if b["s"] < a["s"] - 0.01)
            if back:
                errors.append(f"{back} caption word(s) out of order")
            if words[-1]["e"] > d + 0.5:
                errors.append("captions run past the end of the video")
            gaps = [round(b["s"] - a["e"], 1) for a, b in zip(words, words[1:]) if b["s"] - a["e"] > 1.5]
            if gaps:
                warnings.append(f"{len(gaps)} pause(s) over 1.5 s in the voice (captions blank there)")
            fast = [w["w"] for w in words if w["e"] - w["s"] < 0.06]
            if len(fast) > len(words) * 0.15:
                warnings.append("many caption words flash very quickly; check timing")
    size_mb = Path(video).stat().st_size / 1e6
    if size_mb > 250:
        warnings.append(f"file is {size_mb:.0f} MB (large upload)")
    return {"passed": not errors, "errors": errors, "warnings": warnings, "duration": round(d, 2),
            "resolution": f"{info['width']}x{info['height']}", "fps": info["fps"],
            "loudness_lufs": loud and round(loud["lufs"], 1), "true_peak": loud and round(loud["true_peak"], 1),
            "size_mb": round(size_mb, 1)}
