"""Free stock b-roll from Pexels or Pixabay, matched to the script's keywords. Optional: needs your API key in .env.

Clips are cached in cache/broll/ so the same keyword is never downloaded twice (slow internet friendly).
"""
import json
import re

import requests

from . import config

CACHE = config.CACHE_DIR / "broll"
MAX_BYTES = 30_000_000  # skip huge files on a slow connection


def _download(url, dest, log):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        if int(r.headers.get("content-length", 0)) > MAX_BYTES:
            log(f"b-roll file too big, skipped: {url}")
            return None
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def _pexels(query, key):
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key}, timeout=30,
                     params={"query": query, "orientation": "portrait", "per_page": 6, "size": "medium"})
    r.raise_for_status()
    for v in r.json().get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
        # Smallest file that is still at least 720 px wide: good quality, small download.
        files = sorted((f for f in files if f["width"] >= 720), key=lambda f: f["width"] * f["height"])
        if files and v.get("duration", 0) >= 3:
            yield {"id": f"pexels_{v['id']}", "url": files[0]["link"], "credit": f"{v['user']['name']} on Pexels",
                   "page": v.get("url")}


def _pixabay(query, key):
    r = requests.get("https://pixabay.com/api/videos/", timeout=30,
                     params={"key": key, "q": query[:100], "per_page": 6, "safesearch": "true"})
    r.raise_for_status()
    for h in r.json().get("hits", []):
        vid = h["videos"].get("medium") or h["videos"].get("small")
        if vid and vid.get("url") and h.get("duration", 0) >= 3:
            yield {"id": f"pixabay_{h['id']}", "url": vid["url"], "credit": f"{h.get('user')} on Pixabay",
                   "page": h.get("pageURL")}


def fetch(keywords, count, log):
    """Return up to `count` clips: [{path, keyword, credit, page}]. Never raises: b-roll is a nice-to-have."""
    providers = []
    if config.env("PEXELS_API_KEY"):
        providers.append((_pexels, config.env("PEXELS_API_KEY")))
    if config.env("PIXABAY_API_KEY"):
        providers.append((_pixabay, config.env("PIXABAY_API_KEY")))
    if not providers or count <= 0:
        if not providers:
            log("no PEXELS_API_KEY / PIXABAY_API_KEY in .env, so no stock b-roll")
        return []
    CACHE.mkdir(parents=True, exist_ok=True)
    clips, used = [], set()
    for kw in keywords:
        if len(clips) >= count:
            break
        for search, key in providers:
            try:
                cands = [c for c in search(kw, key) if c["id"] not in used]
            except Exception as e:
                log(f"b-roll search failed for '{kw}': {str(e)[:120]}")
                continue
            if not cands:
                continue
            c = cands[0]
            try:
                path = _download(c["url"], CACHE / f"{c['id']}.mp4", log)
            except Exception as e:
                log(f"b-roll download failed for '{kw}': {str(e)[:120]}")
                continue
            if path:
                used.add(c["id"])
                clips.append({"path": str(path), "keyword": kw, "credit": c["credit"], "page": c["page"]})
                break
    return clips


STOP = set("""a an the and or but if then so to of in on at for with from by is are was were be been being
this that these those it its you your yours we our i me my he she they them their there here what which who
how why when where can could should would will just not no yes do does did don't dont doesn't very really
more most less much many some any all every one two three get got make made like about into out up down
than too also only even still because while after before over under again own same such thing things""".split())


def guess_keywords(script, n=4):
    """Fallback when the AI didn't give keywords: the longest meaningful words of the script."""
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", script)]
    seen, out = set(), []
    for w in sorted(words, key=len, reverse=True):
        if w not in STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:n]


def credits_text(clips):
    return json.dumps([{k: c[k] for k in ("keyword", "credit", "page")} for c in clips], indent=1)
