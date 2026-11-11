# Offering this to clients

The engine is already multi-client: each client is a folder in `clients/`, with its own brand, voice, face, consent,
music and (optionally) its own Google Sheet. What changes when you sell it is **consent, licences, speed and cost**.

## 1. Onboarding a client (checklist)

1. `./ce new-client anna --name "Anna's Bakery"`
2. **Signed consent before anything else.** A short written agreement (keep the signed PDF in `clients/anna/`) covering:
   - permission to clone their **voice** and **likeness**, for **what** (their own social accounts) and **how long**;
   - who may approve scripts and videos (their sign-off on every post, or auto-approve);
   - that they can **withdraw** consent at any time, and you then delete the voice sample, face video and models within N days;
   - AI disclosure: posts are labelled as AI-generated where platforms require it;
   - you never use their voice/face for anyone else, and they confirm they're the person in the recordings.
   Then fill `clients/anna/consent.json` (`voice_consent`, `likeness_consent`, `commercial_use`, `signed_on`, `expires`).
   The engine refuses to render a real person without it.
3. Collect: 30 s voice sample, 20 s face video, logo (PNG), brand colours/fonts, 3-5 example posts they like, a CTA,
   topics they never want to touch. Put the tone, audience and do/don't rules in `brand.json`; paste their example
   scripts into `"examples": [...]` so the AI copies their style.
4. Give them their own calendar (a separate Google Sheet shared with them and the service account, see
   [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)). They add topics and set `Approved` / `Scheduled`; you never chase them on WhatsApp.
5. Keep `auto_approve: false` until they trust the scripts.

## 2. Licences: fix these before charging money

- **Lip-sync face detector:** AI Creator Studio's MuseTalk setup downloads InsightFace weights that are licensed for
  **non-commercial research only**. For paid client work, use a cloud lip-sync model with a commercial licence
  (for example LatentSync, which is Apache-2.0; check the current terms) or a paid lip-sync API.
- **Voice model:** Chatterbox (default) is MIT, so commercial use is fine. Don't switch to F5-TTS or XTTS-v2 for clients
  (non-commercial weights).
- **Music:** only tracks you or the client have a licence for (e.g. a royalty-free library subscription). Platform
  "trending audio" can't be baked into the file; add it in the app when posting.
- **B-roll:** Pexels and Pixabay videos are free for commercial use without attribution; credits are still saved in
  `post.json`. Don't use clips with recognisable brands or people in misleading ways.

## 3. Speed: when the Mac is too slow

On this Mac (Apple M5, 16 GB), voice cloning runs at roughly real time when the Mac is plugged in and awake
(about 1 minute of rendering per minute of speech) but can stall for many minutes on battery or with the screen asleep.
Lip-sync adds several minutes per reel. That's fine for 1-2 reels a day for yourself, not for 10 clients.

Options, cheapest first:

| Option | What runs where | Good for |
|---|---|---|
| Mac only | everything local, overnight with `./ce schedule on` | you + 1-2 clients |
| Mac + cloud GPU for lip-sync | voice + edit on the Mac, lip-sync on a rented NVIDIA GPU | ~5-10 clients |
| All in the cloud | whole worker in a Docker container on a GPU server | many clients, Mac can be off |

- **[RunPod](https://www.runpod.io):** rent a GPU by the hour (an RTX 4090-class card has been around US$0.35-0.70/hour;
  check current prices). Good for batch rendering: start a pod, render the day's reels, stop it.
- **[Modal](https://modal.com):** pay per second, scales to zero when idle, runs Python functions on GPUs. Best fit for
  "send voice.wav + face clip, get talking.mp4 back". The place to plug it in is `engine/render.py` → `render_avatar()`:
  keep the voice step local and replace the lip-sync call with a call to your Modal function.
- Only voice samples and face clips of consenting clients may be uploaded, and choose a region/provider whose data
  terms you can explain to clients.

## 4. Rough cost per reel (45 s, November 2026, verify current prices)

| Item | Approx. cost |
|---|---|
| AI script (ChatGPT or Claude Opus 5.5, ~2k tokens in, ~3k out incl. reasoning) | US$0.02-0.10 |
| Voice clone + edit on your Mac | electricity only |
| Lip-sync on a cloud GPU (2-5 GPU-minutes) | US$0.03-0.15 |
| Stock b-roll (Pexels/Pixabay) | free |
| Music library subscription (shared across clients) | ~US$10-20/month total |
| **Total variable cost** | **roughly US$0.10-0.30 per reel** |

Your real cost is **your time** for review and client communication (budget 5-10 minutes per reel) plus subscriptions.
Price per month per client (e.g. a package of 12 or 20 reels including script approval rounds), not per minute of compute.

## 5. Running it for many clients

- One Google Sheet per client, or one tab per client (`"sheet"` in `brand.json`); `./ce run` reads all of them.
- `MAX_RENDERS_PER_RUN` in `.env` (default 3) stops one run from hogging the Mac; the schedule picks up the rest.
- Back up `clients/` (consent records!) and `ready/` to an encrypted drive. Delete a client's voice/face files the day
  their contract or consent ends, and note the date in `consent.json`.
- Phase 3 ideas: a client portal (they only see their sheet + a review link), Slack/WhatsApp notification when a reel
  is in `Review`, A/B hooks (two `on_screen_text` variants), and reading `metrics` back into the script writer so it
  learns which hooks perform.
