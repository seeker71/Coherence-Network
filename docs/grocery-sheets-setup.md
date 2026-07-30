# Mirroring the grocery ledger into your own Google Sheet

The ledger lives in the network's graph. Google Sheets is a **mirror** — a
copy that lands in a spreadsheet the hub owns, so the record is readable,
sortable, and shareable by people who will never open the app, and so
leaving the app costs nothing.

Nothing here puts a Google credential in our keystore. You deploy a small
script against your own spreadsheet and hand us a URL; revoking us is
deleting that URL.

## 1. Make the sheet

Create a spreadsheet, or use one you already have. Name the first tab
`Belanja` (or anything — the script writes to the active sheet).

Its id is the long string in the URL:

```
https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
```

Keep that id — step 4 uses it so the app can link a person straight to
their own record.

## 2. Restructure the sheet, once

The ledger as it was had purchases at the top, negative settlement rows
underneath, and a `remaining` row below those — so every new purchase had
to be squeezed in above the settlements, and `remaining` kept getting
pushed around. The app can only append safely if nothing has to move.

The new shape puts the balance on top, where a person looks first, and keeps
an append-only log below it:

```
      A           B          C
 1    Sisa        Rp2,772,000                            <- what is left
 2    Belanja     Rp3,009,300                            <- spent
 3    Isi ulang   Rp5,781,300                            <- topped up
 4    When        Amount     What                        <- header (frozen)
 5    23/07/2026  385000     pasar pagi - sayur & ikan
 6    26/07/2026  -4000000   top up
 7    ...
```

- **`Sisa` is the first thing on the sheet**, at 16pt, because "how much is
  left" is the question the ledger exists to answer. It is a formula
  (`=-SUM($B$5:$B)`) in a fixed cell, so appending can never disturb it, and
  it reads *positive* while there is float left to spend.
- **One row per event**, newest at the bottom, starting at row 5. Nothing is
  ever moved, and rows 1-4 are frozen so the balance stays in view while the
  log scrolls.
- **`Amount` is signed**: a purchase is positive, a top-up negative - the
  same convention the old settlement rows already used, so every existing
  number keeps its meaning.
- **`Paid` is gone.** With top-ups in the same log, the balance answers what
  that column was being used to track.

Two things a sheet carries invisibly, which `restructure` therefore clears —
both were live in the hub's own ledger, where the old `Paid` column left a
34px-wide column C under a `Checkbox` rule spanning `C1:C1000`:

- **`clear()` leaves data validation in place.** A checkbox rule inherited
  from an old column renders every description as an invalid checkbox value.
- **`clear()` leaves column widths and hidden columns in place.** `What` is
  the column the whole app exists to fill, so it is shown and widened
  explicitly.

Run this once - **Extensions -> Apps Script**, paste, then run `restructure`
from the toolbar. It converts the sheet in place and keeps every value:

```javascript
// Hati Suci grocery ledger - the hub's mirror of the network graph.
//
// Shape: the remaining balance sits on top, where a person looks first, and
// the log below is append-only so nothing ever has to move.
//
//   1   Sisa        <formula>     <- what is left to spend
//   2   Belanja     <formula>     <- spent
//   3   Isi ulang   <formula>     <- topped up
//   4   When | Amount | What      <- header (frozen)
//   5+  one row per event, oldest first, newest appended at the bottom
//
// Amount is signed: a purchase is positive, a top-up negative, so Sisa is one
// SUM over one column. Appends land below row 4 and can never disturb the
// totals above it.

const HEADERS = ["When", "Amount", "What"];
const FIRST_DATA_ROW = 5;
const RUPIAH = '"Rp"#,##0';

// One-time: reshape the ledger, keeping every value. Safe to re-run.
function restructure() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheets()[0];
  const values = sheet.getDataRange().getValues();
  const hrow = headerRowOf(sheet);
  const header = values[hrow - 1].map(function (h) { return String(h).trim(); });

  const iWhen = header.indexOf("When");
  var iAmount = header.indexOf("Amount");
  if (iAmount < 0) iAmount = header.indexOf("Cost");
  const iWhat = header.indexOf("What");
  if (iWhen < 0 || iAmount < 0) throw new Error("need a When and a Cost/Amount column");

  const kept = [];
  for (var i = hrow; i < values.length; i++) {
    const when = values[i][iWhen];
    const amount = values[i][iAmount];
    const what = iWhat >= 0 ? String(values[i][iWhat] || "").trim() : "";
    if (amount === "" || amount === null) continue;
    if (what.toLowerCase() === "remaining") continue;        // now a formula
    kept.push([when || "", Number(amount), what.toLowerCase() === "paid" ? "top up" : what]);
  }
  kept.sort(function (a, b) {
    return (a[0] instanceof Date && b[0] instanceof Date) ? a[0] - b[0] : 0;
  });

  // Keep the ledger as it was found, on its own tab, before rewriting.
  const stamp = Utilities.formatDate(new Date(), "Asia/Makassar", "yyyy-MM-dd");
  const backupName = "asli " + stamp;
  if (!ss.getSheetByName(backupName)) {
    const copy = sheet.copyTo(ss);
    copy.setName(backupName);
    ss.setActiveSheet(sheet);
  }

  sheet.clear();

  // The balance, on top.
  sheet.getRange("A1:B3").setValues([
    ["Sisa", "=-SUM($B$" + FIRST_DATA_ROW + ":$B)"],
    ["Belanja", '=SUMIF($B$' + FIRST_DATA_ROW + ':$B,">0")'],
    ["Isi ulang", '=-SUMIF($B$' + FIRST_DATA_ROW + ':$B,"<0")'],
  ]);
  sheet.getRange("A1:A3").setFontWeight("bold");
  sheet.getRange("B1:B3").setNumberFormat(RUPIAH).setFontWeight("bold");
  sheet.getRange("A1:B1").setFontSize(16);
  sheet.getRange("A2:B3").setFontSize(10).setFontColor("#666666");

  // The log.
  sheet.getRange(4, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight("bold");
  if (kept.length) {
    sheet.getRange(FIRST_DATA_ROW, 1, kept.length, 3).setValues(kept);
  }
  sheet.getRange("A" + FIRST_DATA_ROW + ":A").setNumberFormat("dd/MM/yyyy");
  sheet.getRange("B" + FIRST_DATA_ROW + ":B").setNumberFormat(RUPIAH);
  sheet.setFrozenRows(4);
  // The ledger arrived with a hidden column; What is the column that matters,
  // so every column the log uses is made visible before it is measured.
  sheet.showColumns(1, 3);
  sheet.autoResizeColumns(1, 3);
  sheet.setColumnWidth(3, Math.max(260, sheet.getColumnWidth(3)));

  Logger.log("kept " + kept.length + " events; backup tab: " + backupName);
}

// Find the header row by name, so the log can sit anywhere on the sheet and
// the append still lands in the right columns.
function headerRowOf(sheet) {
  const rows = Math.min(12, sheet.getMaxRows());
  const cols = Math.max(3, sheet.getLastColumn());
  const scan = sheet.getRange(1, 1, rows, cols).getValues();
  for (var r = 0; r < scan.length; r++) {
    for (var c = 0; c < scan[r].length; c++) {
      if (String(scan[r][c]).trim() === "When") return r + 1;
    }
  }
  throw new Error("no header row with a When column");
}
```

## 2b. Add the append script

In the same Apps Script project, add this alongside `restructure`:

```javascript
// The app appends one event per call - a purchase or a top-up.
const SECRET = "";  // set to the same value as grocery_sheet.secret

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden");
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  const hrow = headerRowOf(sheet);
  const header = sheet.getRange(hrow, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);

  // Match columns by NAME, so reordering or adding one never shifts the write.
  const row = new Array(header.length).fill("");
  body.columns.forEach(function (c) {
    const at = header.indexOf(c);
    if (at < 0) return;
    row[at] = (c === "When" && body.row[c]) ? new Date(body.row[c]) : body.row[c];
  });
  sheet.appendRow(row);
  return ContentService.createTextOutput("ok");
}
```

## 3. Deploy it

**Deploy → New deployment → Web app**:

- **Execute as**: Me
- **Who has access**: Anyone

Copy the Web app URL — it looks like
`https://script.google.com/macros/s/AKfy…/exec`.

"Anyone" means anyone with the URL can append a row. The URL is the
secret. If that's too loose for you, set `SECRET` in the script and
`grocery_sheet.secret` in the keystore to the same value — then a leaked
URL alone can't write.

## 4. Point the network at it

The URL is a credential — anyone holding it can append a row — so it lives
in the keystore beside the other keys, at `~/.coherence-network/keys.json`
(mode 600, never in git):

```json
{
  "grocery_sheet": {
    "webhook_url": "https://script.google.com/macros/s/AKfy…/exec",
    "secret": ""
  }
}
```

Set `secret` only if you set `SECRET` in the script.

The sheet's **id** is already set. It ships in `api/config/api.json` under
`grocery.sheet_id`, so a fresh deploy points at the hub's ledger with
nothing to configure. `GET /api/grocery/sheet` reports where the mirror
lands and how many entries are waiting, and the app shows an **Open the
sheet** link.

To point a different hub at a different sheet, override it in the editable
config (`~/.coherence-network/config.json`):

```json
{ "grocery_sheet_id": "<OTHER_SHEET_ID>" }
```

The next entry appends a row. A running API caches config until
`reset_config_cache()`, so restart it if you set these while it's up.

## What the sheet gets

One appended row per event, matched **by column name**:

| Column | What lands there |
|--------|------------------|
| `When` | the day it happened (hub timezone, UTC+8), as a real date |
| `Amount` | whole rupiah as a **number** - positive for a purchase, negative for a top-up. Never the text `"Rp477,300"`, so the format and the formulas keep working |
| `What` | the description - the shop's stored sentence, the icon's label, or what the manager typed |

`What` is the column worth the whole app. In the ledger as we found it,
every purchase row had it empty; the amount was recorded and the meaning
was not. Now it arrives filled in without anyone typing it.

Nothing else is touched. `Sisa`, `Belanja`, and `Isi ulang` are formulas in
fixed cells above the log, so they stay correct no matter how many rows
arrive — and the append finds its columns by looking up the header row by
name, so the balance block can grow without breaking the write.

## When the sheet is dark

A failing or unset webhook never costs an entry. The record lands in the
graph with `sheet_synced=false`, and:

```bash
curl -X POST https://api.coherencycoin.com/api/grocery/sheet/resync \
  -H 'Content-Type: application/json' \
  -d '{"actor_token":"<a resident or staff token>"}'
```

pushes everything the sheet hasn't seen. The response says how many were
pending, how many landed, and whether a webhook is configured at all.

## The door out

```
GET /api/grocery/export.csv?token=<your token>
```

The whole ledger as a CSV file — **ten** columns, not the sheet's four:
date, amount_typed, amount_idr, currency, description, category, place, by,
recorded_at, id. The sheet shows what the hub reads; the export carries
everything the ledger knows, including which shop, which category, and who
recorded it. Also linked at the bottom of the app. Use it to move to any
other tool, at any time, without asking us for anything.
