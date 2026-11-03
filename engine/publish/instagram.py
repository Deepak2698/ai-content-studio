"""Instagram Reels via the official Instagram Graph API (Business/Creator account linked to a Facebook Page).

Setup (you do this yourself, see docs/PUBLISHING.md): create a Meta app, add Instagram Graph API, get a
long-lived access token with instagram_basic + instagram_content_publish, and your Instagram user ID.
Uses Instagram's resumable upload, so no public web hosting is needed.
NOT yet tested against a live account: post one test reel manually with  ./ce publish <id>  first.
"""
import time

import requests

from .. import config

GRAPH = "https://graph.facebook.com/" + (config.env("META_GRAPH_VERSION") or "v23.0")


def ready():
    if not config.flag("INSTAGRAM_ENABLED"):
        return False, "INSTAGRAM_ENABLED is not true"
    if not (config.env("INSTAGRAM_ACCESS_TOKEN") and config.env("INSTAGRAM_USER_ID")):
        return False, "INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_USER_ID missing"
    return True, "ready"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API error {r.status_code}: {r.text[:300]}")
    return r.json()


def post(video, caption_file, meta, log):
    token, user = config.env("INSTAGRAM_ACCESS_TOKEN"), config.env("INSTAGRAM_USER_ID")
    caption = caption_file.read_text(encoding="utf-8").strip()[:2200]
    container = _check(requests.post(f"{GRAPH}/{user}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption, "share_to_feed": "true",
        "access_token": token}))["id"]
    data = video.read_bytes()
    up = f"https://rupload.facebook.com/ig-api-upload/{GRAPH.rsplit('/', 1)[1]}/{container}"
    _check(requests.post(up, data=data, timeout=600, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))}))
    log(f"instagram: uploaded {len(data) / 1e6:.1f} MB, waiting for processing")
    for _ in range(60):  # up to ~10 minutes
        st = _check(requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status",
                                                                 "access_token": token}, timeout=30))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing failed: {st.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError(f"Instagram still processing after 10 min (container {container})")
    media = _check(requests.post(f"{GRAPH}/{user}/media_publish", timeout=60,
                                 data={"creation_id": container, "access_token": token}))["id"]
    link = _check(requests.get(f"{GRAPH}/{media}", params={"fields": "permalink", "access_token": token},
                               timeout=30)).get("permalink", "")
    return {"id": media, "url": link}


def metrics(media_id):
    token = config.env("INSTAGRAM_ACCESS_TOKEN")
    r = _check(requests.get(f"{GRAPH}/{media_id}/insights", timeout=30, params={
        "metric": "views,reach,likes,comments,shares,saved", "access_token": token}))
    return {m["name"]: m["values"][0]["value"] for m in r.get("data", [])}
