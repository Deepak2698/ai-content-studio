"""The worker: reads the calendar and moves every row one or more steps forward.

  Idea          -> AI writes script, on-screen text, caption, hashtags   -> Script Ready
                   (or Approved straight away if the client has "auto_approve": true)
  Script Ready  -> waits for YOU to read it and set the status to Approved
  Approved      -> Rendering -> cloned voice + avatar + edit + QA -> package in ready/ -> Review
  Review        -> waits for YOU to watch it; set Scheduled when happy (or Approved to re-render,
                   or Idea + "redo: ..." in review_notes to rewrite the script)
  Scheduled     -> posted automatically at publish_date ONLY if auto-posting is enabled; otherwise
                   you post the files from ready/ yourself and set Posted + posted_url
"""
import fcntl
import json
import re
import traceback
from datetime import datetime

from . import broll, config, publish, scriptwriter
from . import sheet as S
from .clients import Client
from .edit import edit_reel
from .qa import check
from .render import render_avatar


class Log:
    def __init__(self):
        config.LOGS_DIR.mkdir(exist_ok=True)
        self.file = (config.LOGS_DIR / "worker.log").open("a")

    def __call__(self, msg):
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
        print(line, flush=True)
        self.file.write(line + "\n")
        self.file.flush()


def job_dir(client, row):
    rid = re.sub(r"[^A-Za-z0-9_-]+", "-", str(row.get("id") or row.index + 1))
    return config.OUTPUT_DIR / f"{client.slug}_{rid}"


def fallback_overlay(script):
    first = re.split(r"(?<=[.!?])\s+", script.strip())[0]
    words = first.rstrip(".!?").split()
    return " ".join(words[:6])


# ---------------------------------------------------------------- steps

def step_script(sheet, row, client, log):
    notes = row.get("review_notes", "")
    redo = notes[len("redo:"):].strip() if notes.lower().startswith("redo:") else ""
    have_script = bool(row.get("script", "").strip()) and not redo
    work = job_dir(client, row)
    work.mkdir(parents=True, exist_ok=True)
    fields = {}
    if have_script:
        # You wrote the script: keep it word for word, only fill the empty extras.
        script = row["script"].strip()
        if not row.get("on_screen_text"):
            fields["on_screen_text"] = fallback_overlay(script)
        if not row.get("caption"):
            fields["caption"] = row.get("topic", "")
        log(f"row {row.get('id')}: using your script ({len(script.split())} words)")
        (work / "script.json").write_text(json.dumps({"script": script, "broll_keywords": broll.guess_keywords(script)}))
    else:
        if not row.get("topic", "").strip():
            return
        log(f"row {row.get('id')}: AI is writing a script about: {row['topic'][:80]}")
        out = scriptwriter.write_script(row["topic"], client.brand, notes=redo)
        fields = {"script": out.script, "on_screen_text": out.on_screen_text, "caption": out.caption,
                  "hashtags": " ".join(out.hashtags)}
        if redo:
            fields["review_notes"] = f"(applied) {notes}"
        (work / "script.json").write_text(json.dumps(out.model_dump(), indent=1, ensure_ascii=False))
    secs = scriptwriter.word_count_seconds(fields.get("script", row.get("script", "")))
    auto = client.brand.get("auto_approve")
    fields["status"] = S.APPROVED if auto else S.SCRIPT_READY
    fields["engine_notes"] = (f"script ~{secs:.0f} s. " +
                              ("Auto-approved (client setting)." if auto else "Read it, then set status to Approved."))
    sheet.update(row, **fields)


def step_render(sheet, row, client, log):
    problems = client.problems()
    if problems:
        sheet.update(row, status=S.FAILED, engine_notes="Can't render: " + "; ".join(problems))
        log(f"row {row.get('id')}: blocked: {problems}")
        return
    script = row.get("script", "").strip()
    if not script:
        sheet.update(row, status=S.FAILED, engine_notes="No script. Set status to Idea so the AI writes one.")
        return
    work = job_dir(client, row)
    work.mkdir(parents=True, exist_ok=True)
    tries = work / "render_attempts"
    n = int(tries.read_text()) + 1 if tries.exists() else 1
    tries.write_text(str(n))
    if n > 3:
        sheet.update(row, status=S.FAILED, engine_notes=f"Render failed {n - 1} times; see {work / 'render.log'}")
        tries.unlink()
        return
    sheet.update(row, status=S.RENDERING, engine_notes=f"rendering started {datetime.now():%H:%M}")
    log(f"row {row.get('id')}: rendering voice + avatar ({client.slug}) in {work}")
    manifest = render_avatar(client, script, work, log)

    meta = json.loads((work / "script.json").read_text()) if (work / "script.json").exists() else {}
    keywords = meta.get("broll_keywords") or broll.guess_keywords(script)
    bcfg = client.brand.get("broll", {})
    clips = broll.fetch(keywords, int(bcfg.get("max_clips", 3)), log) if bcfg.get("enabled", True) else []

    log(f"row {row.get('id')}: editing")
    reel = work / "reel.mp4"
    info = edit_reel(manifest, client, row, clips, work, reel, log)
    qa = check(reel, work / "words_clean.json", publish.platforms_of(row, client))
    (work / "qa.json").write_text(json.dumps(qa, indent=1))
    if not qa["passed"]:
        sheet.update(row, status=S.FAILED, video_path=str(reel),
                     engine_notes="QA failed: " + "; ".join(qa["errors"]))
        return
    folder = publish.export_ready(row, client, reel, info["cover"], qa, clips)
    tries.unlink(missing_ok=True)
    note = (f"QA passed: {qa['duration']} s, {qa['resolution']}, {qa['loudness_lufs']} LUFS"
            f"{', lip-sync' if manifest.get('lipsync') != 'none' else ', no lip-sync'}"
            f"{', music' if info['music'] else ''}{f', {len(clips)} b-roll' if clips else ''}. ")
    if qa["warnings"]:
        note += "Check: " + "; ".join(qa["warnings"]) + ". "
    note += "Watch it, then set status to Scheduled (or write review notes)."
    sheet.update(row, status=S.REVIEW, video_path=str(folder / "reel.mp4"), engine_notes=note)
    log(f"row {row.get('id')}: ready for review -> {folder}")


def step_publish(sheet, row, client, log):
    if not config.flag("AUTO_POST") or not publish.due(row):
        return
    folder = config.ROOT / row.get("video_path", "") if row.get("video_path") else None
    folder = folder.parent if folder and folder.suffix == ".mp4" else folder
    if not folder or not (folder / "post.json").exists():
        sheet.update(row, engine_notes="Scheduled, but the ready/ package is missing. Set Approved to re-render.")
        return
    urls = publish.publish(row, client, folder, log)
    if urls:
        sheet.update(row, status=S.POSTED, posted_url=" ".join(urls.values()),
                     engine_notes=f"posted to {', '.join(urls)} {datetime.now():%Y-%m-%d %H:%M}")


# ---------------------------------------------------------------- main loop

def run(only_id=None, max_renders=None, sheet=None):
    log = Log()
    config.LOGS_DIR.mkdir(exist_ok=True)
    lock = (config.LOGS_DIR / "worker.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another worker is already running; exiting")
        return
    max_renders = int(max_renders if max_renders is not None else config.env("MAX_RENDERS_PER_RUN", "3"))
    budget = {"renders": max_renders}
    for sh, default_client in [(sheet, None)] if sheet else sources(log):
        process_sheet(sh, default_client, only_id, budget, log)
    log("worker done")


def sources(log):
    """The main calendar, plus any client that has its own sheet or tab in brand.json ("sheet": {...})."""
    from .clients import all_clients
    out, seen = [], set()
    main = (config.env("SHEET_BACKEND", "local"), config.env("GOOGLE_SHEET_ID"), config.env("GOOGLE_SHEET_TAB", "Calendar"))
    out.append((S.open_sheet(), None))
    seen.add(main)
    for c in all_clients():
        cfg = c.brand.get("sheet") or {}
        if not (cfg.get("sheet_id") or cfg.get("tab")):
            continue
        key = (cfg.get("backend") or "google", cfg.get("sheet_id") or main[1], cfg.get("tab") or main[2])
        if key in seen:
            continue
        seen.add(key)
        try:
            out.append((S.open_sheet(*key), c.slug))
        except Exception as e:
            log(f"client {c.slug}: can't open its sheet: {e}")
    return out


def process_sheet(sheet, default_client, only_id, budget, log):
    log(f"calendar: {sheet.describe()}")
    for row in sheet.rows():
        if only_id and str(row.get("id")) != str(only_id):
            continue
        if not (row.get("topic", "").strip() or row.get("script", "").strip()):
            continue
        status = row.status
        try:
            client = Client((row.get("client") or default_client or config.env("DEFAULT_CLIENT", "me")).strip())
        except ValueError as e:
            sheet.update(row, status=S.FAILED, engine_notes=str(e))
            continue
        try:
            if status == S.IDEA:
                step_script(sheet, row, client, log)
                status = row.status
            if status == S.RENDERING:
                log(f"row {row.get('id')}: was interrupted while rendering; retrying")
                status = S.APPROVED
            if status == S.APPROVED:
                if budget['renders'] <= 0:
                    log(f"row {row.get('id')}: render limit for this run reached; next run")
                    continue
                budget['renders'] -= 1
                step_render(sheet, row, client, log)
            elif status == S.SCHEDULED:
                step_publish(sheet, row, client, log)
        except scriptwriter.NeedsSetup as e:
            log(f"row {row.get('id')}: waiting: {e}")
            sheet.update(row, engine_notes=f"Waiting: {e}")
        except Exception as e:
            log(f"row {row.get('id')}: FAILED {e}\n{traceback.format_exc()}")
            sheet.update(row, status=S.FAILED, engine_notes=f"{type(e).__name__}: {str(e)[:400]}")
