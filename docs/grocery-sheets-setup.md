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

## 2. Add the script

**Extensions → Apps Script**, replace the contents with:

```javascript
// Appends one grocery row in the hub's own ledger shape: When | Cost | Paid | What.
//
// The sheet keeps purchases at the top, negative settlement rows below them,
// and a running balance underneath. A plain appendRow() would drop new
// purchases *under* "remaining" and break that story, so this fills the first
// empty row above the settlement block instead.
const SECRET = "";  // optional: same value as grocery_sheet.secret in the keystore

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden");
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const columns = body.columns;              // ["When", "Cost", "Paid", "What"]
  const values = sheet.getDataRange().getValues();
  const header = values[0].map(String);

  // Find each column by NAME, so reordering or adding a column never
  // shifts where the app writes.
  const at = {};
  columns.forEach((c) => { at[c] = header.indexOf(c); });
  if (at["Cost"] < 0 || at["When"] < 0) {
    return ContentService.createTextOutput("missing When/Cost column");
  }

  // The settlement block begins at the first negative Cost. Purchases go above it.
  let limit = values.length;
  for (let i = 1; i < values.length; i++) {
    const cost = values[i][at["Cost"]];
    if (typeof cost === "number" && cost < 0) { limit = i; break; }
  }

  // Reuse the first blank row above that block; otherwise open one there.
  let target = -1;
  for (let i = 1; i < limit; i++) {
    if (values[i][at["When"]] === "" && values[i][at["Cost"]] === "") { target = i + 1; break; }
  }
  if (target < 0) { sheet.insertRowBefore(limit + 1); target = limit + 1; }

  columns.forEach((c) => {
    if (at[c] < 0) return;
    let v = body.row[c];
    if (c === "When" && v) v = new Date(v);   // a real date, so the column's own format applies
    sheet.getRange(target, at[c] + 1).setValue(v);
  });
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

The app writes the hub's own four columns, matched **by name** — not a
second table beside them:

| Column | What lands there |
|--------|------------------|
| `When` | the day it was spent (hub timezone, UTC+8), as a real date |
| `Cost` | whole rupiah as a **number** — `477300`, never the text `"Rp477,300"`, so the column's currency format and any sums keep working |
| `Paid` | `TRUE` for a purchase; settling stays a separate row, as it already is |
| `What` | the description — the shop's stored sentence, the icon's label, or what the manager typed |

`What` is the column worth the whole app. In the ledger as we found it,
every purchase row had it empty; the amount was recorded and the meaning
was not. Now it arrives filled in without anyone typing it.

Purchases land above the settlement rows, reusing the blank rows already
sitting there, so the running balance underneath stays where it is.

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
