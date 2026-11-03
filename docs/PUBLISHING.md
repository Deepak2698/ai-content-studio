# Publishing

**Default (what happens today):** every finished reel becomes a folder in `ready/`:

```
ready/2026-11-10_me_7_three-mistakes/
  reel.mp4      1080x1920, H.264, AAC, -14 LUFS
  cover.jpg     thumbnail with the hook text
  caption.txt   caption + hashtags, ready to paste
  post.json     everything about the post (script, QA results, b-roll credits)
```

Post it from your phone (AirDrop the folder) or Meta Business Suite / YouTube Studio, which can also schedule it.
Then set the row to `Posted` and paste the link in `posted_url`.

## Auto-posting (off until you turn it on)

The engine posts a row only when **all** of these are true: `AUTO_POST=true`, the platform's `…_ENABLED=true` and its
credentials are filled in `.env`, the row is `Scheduled` (you approved the finished video), and `publish_date` has passed.
Test with one row first: `./ce publish <id>`.

Mark AI content honestly: Instagram asks you to label realistic AI-generated video ("AI info"), and YouTube requires
disclosing altered or synthetic content (the YouTube adapter sets this flag for you).

### YouTube Shorts (YouTube Data API v3)

1. [console.cloud.google.com](https://console.cloud.google.com) → your `content-engine` project → enable **YouTube Data API v3**.
2. **APIs & Services → OAuth consent screen**: External, add your own Google account as a test user.
3. **Credentials → Create credentials → OAuth client ID → Desktop app** → download the JSON to
   `credentials/youtube-client-secret.json`.
4. Run `./ce youtube-login` and sign in in the browser window that opens.
5. In `.env`: `YOUTUBE_ENABLED=true` (and `AUTO_POST=true` when you're ready).

Uploads are **private** by default; set `YOUTUBE_PRIVACY=public` (or `unlisted`) in `.env` when you trust it. Note that
the API's default quota allows roughly 6 uploads per day per project, and an unverified app's uploads may stay private
until Google audits it; check the current rules in Google's YouTube API documentation.

### Instagram Reels (Instagram Graph API)

Needs an Instagram **Professional** (Business or Creator) account.

1. [developers.facebook.com](https://developers.facebook.com) → **Create app** → add the Instagram product
   (API with Instagram Login, or with Facebook Login if your account is linked to a Facebook Page).
2. Grant the permissions for publishing content (`instagram_content_publish` / `instagram_business_content_publish`
   plus basic profile access) and generate a **long-lived access token**.
3. In `.env`: `INSTAGRAM_ACCESS_TOKEN=…`, `INSTAGRAM_USER_ID=…` (your Instagram account's numeric ID),
   `INSTAGRAM_ENABLED=true`. Tokens expire after ~60 days; refresh them.

The adapter uses Instagram's resumable upload, so the video doesn't need to be hosted on a public website.
**It has not been tested against a live account yet**: try `./ce publish <id>` on a throwaway post first.
Meta changes this API often; if it errors, compare `engine/publish/instagram.py` with Meta's current "Content Publishing" docs.

### Buffer / other schedulers

`engine/publish/buffer.py` is a placeholder: Buffer's API changed in 2025 and needs separate access. Fill in `post()` there
if you get access, or use any scheduler manually with the files in `ready/`.

## Analytics write-back

`./ce metrics` fills the `metrics` column of `Posted` rows (views, reach, likes, comments, shares, saves) for posts the
engine published itself. Add it to your routine weekly, or run it after `./ce run`.
