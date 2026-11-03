"""The content-calendar template (CSV for the local mode, XLSX to import into Google Sheets/Excel)."""
import csv

from .config import ROOT
from .sheet import COLUMNS, STATUSES

EXAMPLES = [
    {"id": "1", "client": "me", "publish_date": "2026-11-10 18:30", "platforms": "instagram, youtube",
     "topic": "3 mistakes beginners make with their first 10 reels", "status": "Idea"},
    {"id": "2", "client": "me", "publish_date": "2026-11-12 18:30", "platforms": "instagram",
     "topic": "Why I use an AI version of my own voice (and what it can't do)", "status": "Idea"},
    {"id": "3", "client": "me", "publish_date": "2026-11-14 18:30", "platforms": "youtube",
     "topic": "Own script example", "status": "Idea",
     "script": "Want to post every day without filming every day? Here's my system. I write one line idea in a "
               "spreadsheet. An AI drafts the script in my style, and I approve it. Then my AI avatar records it "
               "in my own voice, with captions and music. I watch it once, and it's scheduled. That's it. "
               "Follow for more behind the scenes."},
]

HELP = [
    ("id", "Any unique number or text. Never reuse one."),
    ("client", "Folder name in content-engine/clients/ (\"me\" for you)."),
    ("publish_date", "When it should go out: 2026-11-10 or 2026-11-10 18:30."),
    ("platforms", "instagram, youtube (comma separated)."),
    ("topic", "Your idea or hook in one line. This is the only thing you must fill."),
    ("script", "Leave blank: the AI writes it. Fill it: used word for word."),
    ("status", "Idea → Script Ready → Approved → Rendering → Review → Scheduled → Posted (or Failed). "
               "You only ever set: Idea, Approved, Scheduled, Posted."),
    ("on_screen_text", "Big text in the first 2 seconds. AI fills it if blank."),
    ("caption", "Post caption. AI fills it if blank."),
    ("hashtags", "AI fills it if blank."),
    ("video_path", "Engine fills it: where the finished reel is."),
    ("review_notes", "Your notes. Write  redo: make it funnier  and set status to Idea to get a new script."),
    ("engine_notes", "What the engine did or why it stopped."),
    ("posted_url", "Link after posting."),
    ("metrics", "Views/likes, filled by ./ce metrics when posting is connected."),
    ("updated_at", "Last time the engine touched the row."),
]


def write_templates():
    out = ROOT / "templates"
    out.mkdir(exist_ok=True)
    with (out / "content_calendar.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for ex in EXAMPLES:
            w.writerow(ex)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Calendar"
    ws.append(COLUMNS)
    for ex in EXAMPLES:
        ws.append([ex.get(c, "") for c in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="222222")
    widths = {"topic": 45, "script": 60, "caption": 40, "engine_notes": 45, "review_notes": 30, "video_path": 30}
    for i, c in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = widths.get(c, 16)
    ws.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
    col = ws.cell(1, COLUMNS.index("status") + 1).column_letter
    dv.add(f"{col}2:{col}1000")
    ws.add_data_validation(dv)
    h = wb.create_sheet("How to use")
    h.append(["column", "what to put"])
    for row in HELP:
        h.append(row)
    h.column_dimensions["A"].width = 18
    h.column_dimensions["B"].width = 110
    for r in h.iter_rows(min_row=2):
        r[1].alignment = Alignment(wrap_text=True)
    wb.save(out / "content_calendar.xlsx")
    print(f"Wrote {out / 'content_calendar.csv'} and {out / 'content_calendar.xlsx'}")
