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

The new shape is a plain append-only log with the totals off to one side,
where rows never reach them:

```
      A           B          C                          E            F
 1    When        Amount     What                       Remaining    =-SUM($B$2:$B)
 2    23/07/2026  385000     pasar pagi - sayur & ikan  Spent        =SUMIF($B$2:$B,">0")
 3    26/07/2026  -4000000   top up                     Topped up    =-SUMIF($B$2:$B,"<0")
 4    ...                                               Events       =COUNTA($A$2:$A)
```

- **One row per event**, newest at the bottom. Nothing is ever moved.
- **`Amount` is signed**: a purchase is positive, a top-up negative - the
  same convention the old settlement rows already used, so every existing
  number keeps its meaning.
- **`Remaining` is a formula in a fixed cell**, not a row. Appending cannot
  disturb it. It reads *positive* when there is float left to spend, which
  is the way round a person actually asks the question.
- **`Paid` is gone.** With top-ups in the same log, the balance answers what
  that column was being used to track.

Run this once - **Extensions -> Apps Script**, paste, then run `restructure`
from the toolbar. It converts the sheet in place and keeps every value:

```javascript
// One-time: turn the old When|Cost|Paid|What sheet into an append-only
// When|Amount|What log with the totals in fixed cells. Safe to re-run.
function restructure() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const values = sheet.getDataRange().getValues();
  const header = values[0].map(String);
  const iWhen = header.indexOf("When");
  const iAmount = header.indexOf("Amount") >= 0 ? header.indexOf("Amount") : header.indexOf("Cost");
  const iWhat = header.indexOf("What");
  if (iWhen < 0 || iAmount < 0) throw new Error("need a When and a Cost/Amount column");

  // Keep every row that carries a value; drop the blank filler and the old
  // "remaining" line (its number is now a formula).
  const kept = [];
  for (let i = 1; i < values.length; i++) {
    const when = values[i][iWhen];
    const amount = values[i][iAmount];
    const what = iWhat >= 0 ? String(values[i][iWhat] || "").trim() : "";
    if (amount === "" || amount === null) continue;
    if (what.toLowerCase() === "remaining") continue;         // now a formula
    kept.push([when || "", Number(amount), what.toLowerCase() === "paid" ? "top up" : what]);
  }
  kept.sort((a, b) => (a[0] instanceof Date && b[0] instanceof Date) ? a[0] - b[0] : 0);

  sheet.clear();
  sheet.getRange(1, 1, 1, 3).setValues([["When", "Amount", "What"]]).setFontWeight("bold");
  if (kept.length) sheet.getRange(2, 1, kept.length, 3).setValues(kept);
  sheet.getRange("B2:B").setNumberFormat('"Rp"#,##0');
  sheet.getRange("A2:A").setNumberFormat("dd/MM/yyyy");

  // The totals, in cells no append will ever reach.
  sheet.getRange("E1:F4").setValues([
    ["Remaining", "=-SUM($B$2:$B)"],
    ["Spent", '=SUMIF($B$2:$B,">0")'],
    ["Topped up", '=-SUMIF($B$2:$B,"<0")'],
    ["Events", "=COUNTA($A$2:$A)"],
  ]);
  sheet.getRange("E1:E4").setFontWeight("bold");
  sheet.getRange("F1:F4").setNumberFormat('"Rp"#,##0');
  sheet.setFrozenRows(1);
}
```

## 2b. Add the append script

In the same Apps Script project, add this alongside `restructure`:

```javascript
// Appends one event - a purchase or a top-up - to the bottom of the log.
// Nothing moves, so the totals in E:F stay put.
const SECRET = "";  // optional: same value as grocery_sheet.secret in the keystore

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden");
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);

  // Match columns by NAME, so reordering or adding one never shifts the write.
  const row = new Array(header.length).fill("");
  body.columns.forEach((c) => {
    const at = header.indexOf(c);
    if (at < 0) return;
    row[at] = c === "When" && body.row[c] ? new Date(body.row[c]) : body.row[c];
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

The sheet's **id** is not a credential — it says where the ledger lands, not
who may write — so it goes in the editable config
(`~/.coherence-network/config.json`) instead:

```json
{ "grocery_sheet_id": "<SHEET_ID>" }
```

With that set, `GET /api/grocery/sheet` reports where the mirror lands and
how many entries are still waiting, and the app shows an **Open the sheet**
link so anyone at the hub can read their own record directly.

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

Nothing else is touched. `Remaining`, `Spent`, and `Topped up` are formulas
in fixed cells, so they stay correct no matter how many rows arrive.

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
