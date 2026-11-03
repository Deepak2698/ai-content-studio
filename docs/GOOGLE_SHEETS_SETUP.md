# Use a Google Sheet as your content calendar

The engine needs its own "robot" Google account (a **service account**) that can edit one sheet. It can only see
sheets you explicitly share with it. About 10 minutes, free.

## 1. Make the sheet

1. Go to [sheets.google.com](https://sheets.google.com) → **Blank spreadsheet**. Name it "Content Calendar".
2. **File → Import → Upload** → choose `content-engine/templates/content_calendar.xlsx` → **Replace spreadsheet**.
   You now have a `Calendar` tab (with the status dropdown) and a `How to use` tab.
3. Copy the sheet ID from the address bar: the long part between `/d/` and `/edit`.

## 2. Create the robot account

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in.
2. Top bar → project picker → **New project** → name it `content-engine` → **Create**, then select it.
3. Search bar → **Google Sheets API** → **Enable**.
4. Menu → **IAM & Admin → Service Accounts** → **Create service account** → name `content-engine` → **Done**
   (skip the optional role steps).
5. Click the new account → **Keys** tab → **Add key → Create new key → JSON**. A `.json` file downloads.
6. Move that file to `content-engine/credentials/service-account.json` (create the `credentials` folder).
   It is a password: never share it, never email it. (It's already excluded from git.)
7. Copy the service account's email (looks like `content-engine@….iam.gserviceaccount.com`).

## 3. Share the sheet with the robot

In your sheet → **Share** → paste the service-account email → **Editor** → untick "Notify people" → **Share**.

## 4. Tell the engine

Open `.env` (`open -e .env`) and set:

```
SHEET_BACKEND=google
GOOGLE_SHEET_ID=<the ID from step 1>
GOOGLE_SHEET_TAB=Calendar
```

Then run:

```bash
./ce sheet-setup
```

```bash
./ce doctor
```

`sheet-setup` checks the headers and adds the status dropdown (safe to run again). `doctor` should show
✅ Google Sheet 'Content Calendar' / tab 'Calendar'.

## Several clients

- **Same sheet, one tab per client:** add a tab (e.g. `Anna`) with the same header row, then in
  `clients/anna/brand.json` set `"sheet": {"backend": "google", "tab": "Anna"}`. Rows there default to that client.
- **A separate sheet per client:** set `"sheet": {"backend": "google", "sheet_id": "<their sheet id>", "tab": "Calendar"}`
  and share their sheet with the same service-account email. Clients can then edit only their own calendar.
