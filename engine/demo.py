"""./ce demo: one row, start to finish, without any API keys.

Uses the "demo" client (the Mac's built-in voice and a drawn placeholder face, so nobody's likeness is
cloned) and a hand-written script, so no Anthropic key is needed. It walks the row through
Idea -> Script Ready -> (approved for you) -> Rendering -> Review and leaves the reel in ready/.
"""
import shutil

from PIL import Image, ImageDraw, ImageFont

from . import config
from . import sheet as S
from .clients import Client
from .media import ffmpeg
from .worker import run as run_worker

DEMO_SCRIPT = ("Posting every day is exhausting. Here's how I stopped filming every single video. "
               "First, I drop one line ideas into a spreadsheet. "
               "An AI writes the script in my style, and I approve it with one click. "
               "Then my avatar records it in my own cloned voice. "
               "The engine adds captions, zooms, b-roll and music, and checks the sound level. "
               "I watch it once, and it's ready to post. "
               "Follow for more creator tips.")


def ensure_demo_assets():
    d = config.CLIENTS_DIR / "demo"
    logo = d / "logo.png"
    if not logo.exists():
        img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        dr.ellipse((8, 8, 292, 292), fill=(17, 17, 17, 235), outline=(0, 229, 255, 255), width=14)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", 120)
        except OSError:
            font = ImageFont.load_default()
        dr.text((150, 150), "CE", font=font, fill=(255, 255, 255, 255), anchor="mm")
        img.save(logo)
    music = d / "music" / "demo_pad.m4a"
    if not music.exists():
        # A soft synthesised chord loop (royalty-free because we generate it), just to show ducking.
        music.parent.mkdir(exist_ok=True)
        expr = ("0.18*sin(2*PI*220*t)*(0.6+0.4*sin(2*PI*0.25*t))+0.14*sin(2*PI*277.18*t)+"
                "0.12*sin(2*PI*329.63*t)*(0.6+0.4*sin(2*PI*0.5*t))+0.10*sin(2*PI*110*t)")
        ffmpeg("-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d=40", "-af",
               "aecho=0.8:0.7:250|400:0.3|0.2,lowpass=f=1800,volume=0.8", "-c:a", "aac", "-b:a", "128k", music)


def run():
    ensure_demo_assets()
    sheet = S.open_sheet()
    if isinstance(sheet, S.LocalSheet) and not sheet.rows():
        shutil.copy2(config.ROOT / "templates" / "content_calendar.csv", sheet.path)
        sheet = S.open_sheet()
    rows = [r for r in sheet.rows() if r.get("id") == "demo-1"]
    if not rows:
        print(f"Adding row demo-1 to {sheet.describe()}")
        if isinstance(sheet, S.LocalSheet):
            import csv
            with sheet.path.open("a", newline="", encoding="utf-8") as f:
                header = next(csv.reader(sheet.path.open(encoding="utf-8-sig")))
                row = {"id": "demo-1", "client": "demo", "platforms": "instagram, youtube", "status": S.IDEA,
                       "topic": "How I post daily without filming daily", "script": DEMO_SCRIPT,
                       "hashtags": "#contentcreator #aitools #reels #creatortips #automation"}
                keys = [S.ALIASES.get(S._norm(h), h) for h in header]
                csv.writer(f).writerow([row.get(k, "") for k in keys])
        else:
            sheet.ws.append_row(["demo-1", "demo", "", "instagram, youtube", "How I post daily without filming daily",
                                 DEMO_SCRIPT, S.IDEA, "", "", "#contentcreator #aitools #reels"])
    print(f"Demo client ready: {Client('demo').problems() or 'ok'}")
    print("\nStep 1: worker turns the Idea into a script for review")
    run_worker(only_id="demo-1", sheet=sheet)
    row = [r for r in sheet.rows() if r.get("id") == "demo-1"][0]
    if row.status == S.SCRIPT_READY:
        print("\nStep 2: approving the script for you (normally YOU set status = Approved in the sheet)")
        sheet.update(row, status=S.APPROVED)
    print("\nStep 3: worker renders, edits, checks and packages the reel")
    run_worker(only_id="demo-1", sheet=sheet)
    row = [r for r in sheet.rows() if r.get("id") == "demo-1"][0]
    print(f"\nResult: status = {row.status}\n{row.get('engine_notes')}\nVideo: {row.get('video_path')}")
