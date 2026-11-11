# Content Engine

You decide the topics. The engine does the rest:

```
Google Sheet row ──► AI writes the script ──► YOU approve ──► your cloned voice + avatar ──► pro edit ──► quality check ──► ready/ folder
   (topic)            (ChatGPT or Claude)       (status)       (AI Creator Studio)          (captions, zooms,      (length, loudness,     (reel.mp4, cover.jpg,
                                                                                              b-roll, music)          9:16, captions)         caption.txt)
```

Nothing is posted anywhere unless you switch auto-posting on yourself (see [docs/PUBLISHING.md](docs/PUBLISHING.md)).

## Try it now (2 minutes, no accounts needed)

Open Terminal and run:

```bash
cd ~/Documents/reverse-eng-agent/content-engine
```

```bash
./ce demo
```

This adds a row called `demo-1` to the calendar, renders it with the Mac's built-in test voice and a cartoon face,
and puts the finished reel in `ready/`. Open the folder in Finder with `open ready`.

## How you use it every day

1. **Add a row** to the calendar: just fill `client` (`me`), `publish_date`, `platforms` and `topic`. Leave `status` empty or `Idea`.
2. **The engine writes the script** and sets status to `Script Ready`. Read it in the sheet. Edit it if you like.
3. **Set status to `Approved`.** Only approved rows are ever rendered.
4. **The engine renders** (`Rendering`), then sets `Review` and puts the path of the finished reel in `video_path`.
5. **Watch it.** Happy → set `Scheduled`. Not happy → write `redo: shorter, funnier hook` in `review_notes` and set status back to `Idea`.
6. **Post it** from the `ready/` folder (reel.mp4 + caption.txt), then set `Posted` and paste the link in `posted_url`.
   (Or let the engine post it at `publish_date`, once you've set up auto-posting.)

If something goes wrong the row says `Failed` and `engine_notes` explains why in plain words.

| Status | Who sets it | What happens |
|---|---|---|
| `Idea` | you | AI writes script, on-screen text, caption, hashtags |
| `Script Ready` | engine | waits for you |
| `Approved` | you | rendered at the next run |
| `Rendering` | engine | in progress (minutes) |
| `Review` | engine | reel is in `ready/`, waits for you |
| `Scheduled` | you | posted at `publish_date` if auto-posting is on; otherwise you post it |
| `Posted` | you / engine | done; `./ce metrics` can fill in views and likes |
| `Failed` | engine | read `engine_notes`, fix, set `Approved` or `Idea` again |

## One-time setup

### 1. Your voice and face (the `me` client)

Record them in AI Creator Studio's Recording Booth (double-click `ai-creator-studio/Start Studio.command`, then
**🎙️ Recording Booth**). Then copy your best takes into `clients/me/`:

- `clients/me/voice.wav`: your 15-30 s voice sample
- `clients/me/avatar.mp4`: your 10-30 s face video (a `.mov` or a photo also works; change `"avatar"` in `brand.json`)

Open `clients/me/consent.json`, set `"voice_consent": true`, `"likeness_consent": true` and `"signed_on"` to today's date.
That confirms you agree to cloning your own voice and face. The engine refuses to render a real person without it.

Then describe your style in `clients/me/brand.json`: `niche`, `audience`, `tone`, `cta` ("Follow for more…"), `do`/`dont`
lists, and colours (`style.accent` is the highlight colour of the captions). Optional extras in the same folder:
`logo.png` (transparent PNG), `music/` (mp3 files you have the rights to; one is picked per reel and ducks under your voice),
`fonts/` (a .ttf; then set `style.font` to its name), `intro.mp4` / `outro.mp4`.

### 2. Your keys (pasted by you into `.env`)

The `.env` file in this folder holds your private keys. Open it with TextEdit (`open -e .env`) and paste:

- **One AI key for script writing**, either:
  - `OPENAI_API_KEY` (ChatGPT): from [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
    A ChatGPT Plus subscription does **not** include this; the API is billed separately, pay as you go
    (a few US cents per script). The model is set by `OPENAI_MODEL`.
  - or `ANTHROPIC_API_KEY` (Claude): from [console.anthropic.com](https://console.anthropic.com) → API Keys
    (about 5-10 US cents per script with Claude Opus 5.5).

  If both are filled in, ChatGPT is used (set `SCRIPT_WRITER=claude` to switch). Without a key, write scripts
  into the `script` column yourself, for example by pasting the topic into the ChatGPT app.
- `PEXELS_API_KEY` (free, [pexels.com/api](https://www.pexels.com/api/)) and/or `PIXABAY_API_KEY` (free): stock b-roll.
  Without them, reels have no b-roll shots.

Never send this file to anyone.

### 3. The calendar

- **Today:** the engine uses `calendar.csv` in this folder. You can open it in Numbers or Excel, but **close it before the
  engine runs**, and save it as CSV.
- **Recommended:** a Google Sheet you can edit from your phone. Follow [docs/GOOGLE_SHEETS_SETUP.md](docs/GOOGLE_SHEETS_SETUP.md)
  (about 10 minutes). The template to import is `templates/content_calendar.xlsx` (it has a "How to use" tab).

### 4. Check everything

```bash
./ce doctor
```

✅ = fine, 🟡 = optional thing missing, ❌ = must fix. It tells you what to do for each.

### 5. Run it automatically

```bash
./ce schedule on --every 30
```

Or just double-click **`Run Engine Now.command`** in Finder whenever you like.

With the schedule on, the engine checks the calendar every 30 minutes while you're logged in (`./ce schedule off` stops it). Keep the Mac
**plugged in**: voice cloning and lip-sync are many times slower on battery. Run it by hand any time with `./ce run`.

## All commands

| Command | What it does |
|---|---|
| `./ce doctor` | health check |
| `./ce run` | process the calendar once (`--id 7` for one row) |
| `./ce demo` | the demo above |
| `./ce schedule on --every 30` / `off` | automatic runs via macOS launchd |
| `./ce new-client anna --name "Anna's Bakery"` | new client folder from the template |
| `./ce sheet-setup` | headers + status dropdown in your Google Sheet |
| `./ce template` | rewrite the template files |
| `./ce publish 7` | post one Scheduled row now (only with auto-posting on) |
| `./ce youtube-login` | sign in to YouTube once (auto-posting) |
| `./ce metrics` | write views/likes back into the sheet |

## What the edit does

- **Hook:** big text for the first 2 seconds (from `on_screen_text`), and the script's first sentence is written as a hook.
- **Jump cuts:** a cut at every sentence, alternating a normal shot and a 16 % punch-in on your face.
- **B-roll:** up to 3 stock clips matched to the script's keywords, shown full screen while your voice continues.
- **Captions:** 3 big words at a time, the spoken word pops in your accent colour, inside the Reels/Shorts safe zone
  (clear of the app's buttons and caption area). The script's own spelling is used.
- **Audio:** rumble filter and gentle compression on the voice, background music that dips whenever you talk,
  then two-pass loudness normalisation to −14 LUFS (the level Instagram, YouTube and TikTok play at).
- **Branding:** logo top-right, call-to-action box in the last 2 seconds, optional intro/outro clips.
- **Cover:** `cover.jpg` with the hook text, for the thumbnail.
- **QA:** checks 1080×1920, 5-90 s length, loudness, silence, true peak and caption timing before anything reaches `Review`.

In-between files for each post are in `output/<client>_<id>/` (`voice.wav`, `words.json`, `cut_plan.json`, `captions.ass`,
`render.log`). The cloned voice is reused if only the edit changes, so re-rendering is quick.

## Files

```
ce                    the command (./ce ...)
engine/               the code: worker, scriptwriter, edit, qa, sheet, clients, publish/, doctor
studio_bridge.py      runs AI Creator Studio's voice + lip-sync steps (Studio itself is never modified)
clients/<name>/       brand.json, consent.json, voice, avatar, logo, music, fonts
templates/            content_calendar.csv / .xlsx
calendar.csv          your local calendar (when not using Google Sheets)
ready/                finished packages: reel.mp4, cover.jpg, caption.txt, post.json
output/               work folders     logs/   worker.log
docs/                 Google Sheets setup, publishing, offering this to clients
```

## Turning this into a service

See [docs/SELLING_AS_A_SERVICE.md](docs/SELLING_AS_A_SERVICE.md): multi-client setup, consent, cloud GPUs and cost per reel.
