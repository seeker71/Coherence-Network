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
// Appends one grocery row. Called by the Coherence API on each entry.
const SECRET = "";  // optional: same value as grocery_sheet.secret in the keystore

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (SECRET && body.secret !== SECRET) {
    return ContentService.createTextOutput("forbidden").setMimeType(
      ContentService.MimeType.TEXT,
    );
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const columns = body.columns;

  // First write lays down the header row.
  if (sheet.getLastRow() === 0) sheet.appendRow(columns);

  sheet.appendRow(columns.map((c) => body.row[c]));
  return ContentService.createTextOutput("ok").setMimeType(
    ContentService.MimeType.TEXT,
  );
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

One row per entry, in this column order:

| Column | Meaning |
|--------|---------|
| `date` | the day it was spent (hub timezone, UTC+8) |
| `amount_typed` | what the manager typed — `123.5` |
| `amount_idr` | what it means — `123500` |
| `currency` | `IDR` |
| `description` | the shop's default, the icon's label, or the typed note |
| `category` | the icon key, when one was picked |
| `place` | the shop, when GPS found one nearby |
| `by` | who recorded it |
| `recorded_at` | when it reached the ledger |
| `id` | the entry's id, for reconciling |

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

The whole ledger, same columns, as a CSV file. Also linked at the bottom
of the app. Use it to move to any other tool, at any time, without asking
us for anything.
