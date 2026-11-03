"""Publishing. Default: export a ready-to-post package into ready/. Auto-posting is OFF until you enable it.

A platform is only posted to when ALL of these are true:
  - AUTO_POST=true in .env
  - <PLATFORM>_ENABLED=true in .env and its credentials are filled in
  - the row's status is "Scheduled" (you watched and approved the reel) and publish_date has arrived
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .. import config


def slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n] or "post"


def export_ready(row, client, reel, cover, qa, credits):
    """ready/<date>_<client>_<id>_<topic>/  reel.mp4, cover.jpg, caption.txt, post.json"""
    date = (row.get("publish_date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    folder = config.READY_DIR / f"{date}_{client.slug}_{slug(row.get('id'), 12)}_{slug(row.get('topic'))}"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(reel, folder / "reel.mp4")
    if cover and Path(cover).exists():
        shutil.copy2(cover, folder / "cover.jpg")
    caption = (row.get("caption") or "").strip()
    tags = (row.get("hashtags") or "").strip()
    (folder / "caption.txt").write_text(f"{caption}\n\n{tags}\n".strip() + "\n", encoding="utf-8")
    post = {"id": row.get("id"), "client": client.slug, "topic": row.get("topic"),
            "publish_date": row.get("publish_date"), "platforms": platforms_of(row, client),
            "on_screen_text": row.get("on_screen_text"), "caption": caption, "hashtags": tags,
            "script": row.get("script"), "qa": qa, "broll_credits": credits, "published": {}}
    (folder / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False))
    return folder


def platforms_of(row, client):
    raw = row.get("platforms") or ",".join(client.brand.get("platforms", []))
    return [p.strip().lower() for p in re.split(r"[,/;]+", raw) if p.strip()]


def adapters():
    from . import buffer, instagram, youtube
    return {"instagram": instagram, "youtube": youtube, "buffer": buffer}


def status():
    """Human-readable on/off state of every adapter (used by doctor)."""
    out = {"AUTO_POST": config.flag("AUTO_POST")}
    for name, mod in adapters().items():
        out[name] = mod.ready()
    return out


def due(row):
    when = (row.get("publish_date") or "").strip()
    if not when:
        return True
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(when[:16], fmt) <= datetime.now()
        except ValueError:
            continue
    return False


def publish(row, client, folder: Path, log):
    """Post a Scheduled row to its platforms. Returns {platform: url} or raises."""
    if not config.flag("AUTO_POST"):
        return None
    post = json.loads((folder / "post.json").read_text())
    results = {}
    for name in platforms_of(row, client):
        mod = adapters().get(name)
        if not mod:
            log(f"no adapter for platform '{name}'")
            continue
        ok, why = mod.ready()
        if not ok:
            log(f"{name}: not posting ({why})")
            continue
        if name in post["published"]:
            results[name] = post["published"][name]["url"]
            continue
        res = mod.post(folder / "reel.mp4", folder / "caption.txt", post, log)
        post["published"][name] = res
        (folder / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False))
        results[name] = res["url"]
    return results
