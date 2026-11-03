"""The content calendar: one row per post. Works with a Google Sheet or a local CSV file.

Status flow (the worker only ever moves a row forward, never skips the approval gate unless the
client's brand.json says "auto_approve": true):

    Idea -> Script Ready -> Approved -> Rendering -> Review -> Scheduled -> Posted
                                                   \-> Failed (reason in engine_notes)
"""
import csv
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from . import config

IDEA, SCRIPT_READY, APPROVED, RENDERING, REVIEW, SCHEDULED, POSTED, FAILED = (
    "Idea", "Script Ready", "Approved", "Rendering", "Review", "Scheduled", "Posted", "Failed")
STATUSES = [IDEA, SCRIPT_READY, APPROVED, RENDERING, REVIEW, SCHEDULED, POSTED, FAILED]

COLUMNS = [
    "id",              # any unique text/number, e.g. 1, 2, 3
    "client",          # folder name in clients/, e.g. "me"
    "publish_date",    # 2026-11-10 (optionally with a time: 2026-11-10 18:30)
    "platforms",       # instagram, youtube (comma separated)
    "topic",           # what the post is about / your hook idea
    "script",          # blank = AI writes it; filled = used word for word
    "status",          # see STATUSES
    "on_screen_text",  # big text shown in the first 2 seconds (AI fills it if blank)
    "caption",         # post caption (AI fills it if blank)
    "hashtags",        # #tags (AI fills it if blank)
    "video_path",      # where the finished reel is (engine fills it)
    "review_notes",    # YOUR notes; write "redo: <what to change>" and set status to Idea to re-script
    "engine_notes",    # what the engine did / why something failed
    "posted_url",      # link after posting
    "metrics",         # views / likes etc. (analytics write-back)
    "updated_at",
]


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


ALIASES = {_norm(c): c for c in COLUMNS}
ALIASES.update({_norm(a): c for a, c in [
    ("platform", "platforms"), ("platform(s)", "platforms"), ("topic/hook", "topic"), ("hook", "topic"),
    ("video", "video_path"), ("video_link", "video_path"), ("video_path/link", "video_path"),
    ("notes", "review_notes"), ("on-screen caption", "on_screen_text"), ("onscreen", "on_screen_text"),
    ("posted", "posted_url"), ("date", "publish_date"),
]})


def canonical_status(value):
    v = _norm(value)
    for s in STATUSES:
        if _norm(s) == v:
            return s
    return value.strip() if value and value.strip() else IDEA  # blank status = a new idea


class Row(dict):
    """A sheet row as a dict keyed by canonical column names, plus its position in the sheet."""

    def __init__(self, data, index):
        super().__init__(data)
        self.index = index  # 0-based data row index (header excluded)

    @property
    def status(self):
        return canonical_status(self.get("status", ""))


def _stamp(fields):
    fields = dict(fields)
    fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return fields


class LocalSheet:
    """A CSV file you can open in Numbers/Excel/Google Sheets. Close it before the worker runs."""

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            self.path.write_text(",".join(COLUMNS) + "\n")

    def describe(self):
        return f"local CSV {self.path}"

    def _read(self):
        with self.path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            body = [r for r in reader]
        return header, body

    def rows(self):
        header, body = self._read()
        keys = [ALIASES.get(_norm(h), h) for h in header]
        return [Row({k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)}, n) for n, r in enumerate(body)]

    def update(self, row, **fields):
        header, body = self._read()
        keys = [ALIASES.get(_norm(h), h) for h in header]
        fields = _stamp(fields)
        for k in fields:
            if k not in keys:  # add missing engine columns instead of losing data
                header.append(k)
                keys.append(k)
        line = body[row.index] + [""] * (len(keys) - len(body[row.index]))
        for k, v in fields.items():
            line[keys.index(k)] = "" if v is None else str(v)
            row[k] = line[keys.index(k)]
        body[row.index] = line
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".csv")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(body)
        os.replace(tmp, self.path)  # atomic: a crash never leaves a half-written calendar


class GoogleSheet:
    """A Google Sheet shared with your service account (see docs/GOOGLE_SHEETS_SETUP.md)."""

    def __init__(self, sheet_id, tab, key_file):
        import gspread
        if not Path(key_file).exists():
            raise SystemExit(f"Google service-account key not found at {key_file}. See docs/GOOGLE_SHEETS_SETUP.md")
        gc = gspread.service_account(filename=str(key_file))
        self.book = gc.open_by_key(sheet_id)
        try:
            self.ws = self.book.worksheet(tab)
        except gspread.WorksheetNotFound:
            self.ws = self.book.add_worksheet(tab, rows=500, cols=len(COLUMNS))
            self.ws.update([COLUMNS], "A1")
        self.tab = tab

    def describe(self):
        return f"Google Sheet '{self.book.title}' / tab '{self.tab}'"

    def _header(self):
        header = self.ws.row_values(1)
        if not header:
            self.ws.update([COLUMNS], "A1")
            header = list(COLUMNS)
        return header

    def rows(self):
        values = self.ws.get_all_values()
        if not values:
            return []
        keys = [ALIASES.get(_norm(h), h) for h in values[0]]
        return [Row({k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)}, n)
                for n, r in enumerate(values[1:]) if any(c.strip() for c in r)]

    def update(self, row, **fields):
        from gspread.utils import rowcol_to_a1
        header = self._header()
        keys = [ALIASES.get(_norm(h), h) for h in header]
        fields = _stamp(fields)
        missing = [k for k in fields if k not in keys]
        if missing:  # add engine columns the user deleted, at the end
            start = len(header) + 1
            self.ws.update([missing], rowcol_to_a1(1, start))
            keys += missing
        data = [{"range": rowcol_to_a1(row.index + 2, keys.index(k) + 1), "values": [["" if v is None else str(v)]]}
                for k, v in fields.items()]
        self.ws.batch_update(data)
        row.update({k: "" if v is None else str(v) for k, v in fields.items()})

    def setup(self):
        """Write the header row, a status dropdown and frozen header (safe to run again)."""
        if self.ws.row_values(1) != COLUMNS:
            self.ws.update([COLUMNS], "A1")
        col = COLUMNS.index("status")
        self.book.batch_update({"requests": [
            {"setDataValidation": {
                "range": {"sheetId": self.ws.id, "startRowIndex": 1, "startColumnIndex": col, "endColumnIndex": col + 1},
                "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": s} for s in STATUSES]},
                         "showCustomUi": True, "strict": False}}},
            {"updateSheetProperties": {"properties": {"sheetId": self.ws.id, "gridProperties": {"frozenRowCount": 1}},
                                       "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {"range": {"sheetId": self.ws.id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                            "fields": "userEnteredFormat.textFormat.bold"}},
        ]})


def open_sheet(backend=None, sheet_id=None, tab=None):
    backend = backend or config.env("SHEET_BACKEND", "local")
    if backend == "google":
        sid = sheet_id or config.env("GOOGLE_SHEET_ID")
        if not sid:
            raise SystemExit("GOOGLE_SHEET_ID is empty in .env (or set SHEET_BACKEND=local).")
        return GoogleSheet(sid, tab or config.env("GOOGLE_SHEET_TAB", "Calendar"),
                           config.path_setting("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service-account.json"))
    return LocalSheet(config.path_setting("LOCAL_SHEET_PATH", "calendar.csv"))
