"""Analytics write-back: fills the `metrics` column of Posted rows with views/likes from the platforms.

Only runs for platforms whose adapter is enabled and signed in. Run it with  ./ce metrics
"""
import json
from pathlib import Path

from . import publish
from . import sheet as S


def refresh(sheet=None, log=print):
    sheet = sheet or S.open_sheet()
    ads = publish.adapters()
    for row in sheet.rows():
        if row.status != S.POSTED or not row.get("video_path"):
            continue
        post_file = Path(row["video_path"]).parent / "post.json"
        if not post_file.exists():
            continue
        post = json.loads(post_file.read_text())
        parts = []
        for name, info in post.get("published", {}).items():
            mod = ads.get(name)
            if not mod or not mod.ready()[0]:
                continue
            try:
                m = mod.metrics(info["id"])
            except Exception as e:
                log(f"row {row.get('id')}: {name} metrics failed: {e}")
                continue
            parts.append(f"{name}: " + ", ".join(f"{k} {v}" for k, v in m.items()))
        if parts:
            sheet.update(row, metrics=" | ".join(parts))
            log(f"row {row.get('id')}: metrics updated")
