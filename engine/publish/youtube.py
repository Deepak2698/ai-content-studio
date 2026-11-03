"""YouTube Shorts via the official YouTube Data API v3 (a vertical video under 3 min is a Short).

Setup (you do this yourself, see docs/PUBLISHING.md): create a Google Cloud OAuth client (Desktop app),
enable "YouTube Data API v3", save the JSON as credentials/youtube-client-secret.json, then run
./ce youtube-login  once to sign in in your browser.
Uploads are PRIVATE by default (YOUTUBE_PRIVACY=private) so nothing goes public by surprise.
"""
import json

import requests

from .. import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def _token_file():
    return config.path_setting("YOUTUBE_TOKEN_FILE", "credentials/youtube-token.json")


def ready():
    if not config.flag("YOUTUBE_ENABLED"):
        return False, "YOUTUBE_ENABLED is not true"
    if not _token_file().exists():
        return False, "not signed in: run ./ce youtube-login"
    return True, "ready"


def login():
    from google_auth_oauthlib.flow import InstalledAppFlow
    secret = config.path_setting("YOUTUBE_CLIENT_SECRET_FILE", "credentials/youtube-client-secret.json")
    if not secret.exists():
        raise SystemExit(f"Download your OAuth client JSON to {secret} first (docs/PUBLISHING.md).")
    creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(port=0)
    _token_file().parent.mkdir(parents=True, exist_ok=True)
    _token_file().write_text(creds.to_json())
    print(f"Saved YouTube sign-in to {_token_file()}")


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(str(_token_file()), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        _token_file().write_text(creds.to_json())
    return creds


def post(video, caption_file, meta, log):
    creds = _creds()
    caption = caption_file.read_text(encoding="utf-8").strip()
    title = (meta.get("on_screen_text") or meta.get("topic") or "New Short").strip()
    title = (title[:90] + " #Shorts")[:100]
    body = {"snippet": {"title": title, "description": caption[:4900], "categoryId": "22",
                        "tags": [t.lstrip("#") for t in (meta.get("hashtags") or "").split() if t.startswith("#")][:15]},
            "status": {"privacyStatus": config.env("YOUTUBE_PRIVACY", "private"),
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Type": "video/mp4"}
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                      headers=headers, data=json.dumps(body), timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube API error {r.status_code}: {r.text[:300]}")
    up = requests.put(r.headers["Location"], data=video.read_bytes(), timeout=1800,
                      headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "video/mp4"})
    if up.status_code >= 400:
        raise RuntimeError(f"YouTube upload failed {up.status_code}: {up.text[:300]}")
    vid = up.json()["id"]
    log(f"youtube: uploaded as {body['status']['privacyStatus']} video {vid}")
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}"}


def metrics(video_id):
    creds = _creds()
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=30,
                     params={"part": "statistics", "id": video_id}, headers={"Authorization": f"Bearer {creds.token}"})
    items = r.json().get("items", [])
    return {k: int(v) for k, v in items[0]["statistics"].items()} if items else {}
