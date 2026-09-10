# Mirroring the grocery ledger into your own Google Sheet

New app entries live in the network's graph and mirror into Google Sheets.
The Sheet also carries the household history from before the app existed. An
authenticated Apps Script request returns its fixed `Sisa` summary plus
acknowledgements for entry IDs the app already knows. The app applies only
unacknowledged graph entries, so a retry or crash cannot count a purchase twice.
The carrier never returns the household log, and the spreadsheet itself can
remain private.

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
      A           B          C                           D
 1    Sisa        Rp2,772,000                            <- what is left
 2    Belanja     Rp3,009,300                            <- spent
 3    Isi ulang   Rp5,781,300                            <- topped up
 4    When        Amount     What                        Entry ID (hidden)
 5    23/07/2026  385000     pasar pagi - sayur & ikan
 6    26/07/2026  -4000000   top up                      topup-...
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

const HEADERS = ["When", "Amount", "What", "Entry ID"];
const FIRST_DATA_ROW = 5;
const RUPIAH = '"Rp"#,##0';

// One-time: reshape the ledger, keeping every value. Safe to re-run.
function restructure() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();
  const values = sheet.getDataRange().getValues();
  const hrow = headerRowOf(sheet);
  const header = values[hrow - 1].map(function (h) { return String(h).trim(); });

  const iWhen = header.indexOf("When");
  var iAmount = header.indexOf("Amount");
  if (iAmount < 0) iAmount = header.indexOf("Cost");
  const iWhat = header.indexOf("What");
  const iEntryId = header.indexOf("Entry ID");
  if (iWhen < 0 || iAmount < 0) throw new Error("need a When and a Cost/Amount column");

  const kept = [];
  for (var i = hrow; i < values.length; i++) {
    const when = values[i][iWhen];
    const amount = values[i][iAmount];
    const what = iWhat >= 0 ? String(values[i][iWhat] || "").trim() : "";
    if (amount === "" || amount === null) continue;
    if (what.toLowerCase() === "remaining") continue;        // now a formula
    const entryId = iEntryId >= 0 ? String(values[i][iEntryId] || "").trim() : "";
    kept.push([
      when || "",
      Number(amount),
      what.toLowerCase() === "paid" ? "top up" : what,
      entryId,
    ]);
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
  // clear() empties content and formatting but leaves data validation rules
  // standing — a checkbox rule inherited from an old column would otherwise
  // survive the rewrite and render every new description as an invalid value.
  // clearDataValidations() is a Range method, not a Sheet one, so it is
  // targeted at the sheet's full extent explicitly.
  sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).clearDataValidations();

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
    sheet.getRange(FIRST_DATA_ROW, 1, kept.length, HEADERS.length).setValues(kept);
  }
  sheet.getRange("A" + FIRST_DATA_ROW + ":A").setNumberFormat("dd/MM/yyyy");
  sheet.getRange("B" + FIRST_DATA_ROW + ":B").setNumberFormat(RUPIAH);
  sheet.setFrozenRows(4);
  // The ledger arrived with a hidden column; What is the column that matters,
  // so every column the log uses is made visible before it is measured.
  sheet.showColumns(1, 3);
  sheet.hideColumns(4);
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
// The app appends one event per call and reads only the balance summary.
// Store the shared value as the GROCERY_SHEET_SECRET script property and copy
// the same value to grocery_sheet.secret in the production keystore.
const SECRET_PROPERTY = "GROCERY_SHEET_SECRET";
const ENTRY_ID_HEADER = "Entry ID";
const STATE_SHEET_NAME = "_Hati App State";

function jsonOutput(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}

function entryIdColumn(sheet, hrow, createIfMissing) {
  const width = Math.max(1, sheet.getLastColumn());
  const header = sheet.getRange(hrow, 1, 1, width).getValues()[0]
    .map(function (value) { return String(value).trim(); });
  var index = header.indexOf(ENTRY_ID_HEADER);
  if (index < 0 && createIfMissing) {
    index = header.length;
    sheet.getRange(hrow, index + 1).setValue(ENTRY_ID_HEADER);
    sheet.hideColumns(index + 1);
  }
  return index;
}

function acknowledgedIds(sheet, hrow, requested) {
  if (!Array.isArray(requested) || requested.length === 0) return [];
  const wanted = new Set(requested.map(String));
  const index = entryIdColumn(sheet, hrow, false);
  const count = sheet.getLastRow() - hrow;
  if (index < 0 || count < 1) return [];
  return sheet.getRange(hrow + 1, index + 1, count, 1).getDisplayValues()
    .map(function (row) { return String(row[0]); })
    .filter(function (entryId) { return wanted.has(entryId); });
}

// A private durable cancellation ledger closes the race between an append and
// a deletion. It is separate from the human ledger and remains hidden.
function stateSheet(ss, createIfMissing) {
  var sheet = ss.getSheetByName(STATE_SHEET_NAME);
  if (!sheet && createIfMissing) {
    sheet = ss.insertSheet(STATE_SHEET_NAME);
    sheet.getRange(1, 1, 1, 2).setValues([["Entry ID", "State"]]);
    sheet.hideSheet();
  }
  return sheet;
}

function cancelledIds(ss, requested) {
  if (!Array.isArray(requested) || requested.length === 0) return [];
  const sheet = stateSheet(ss, false);
  if (!sheet || sheet.getLastRow() < 2) return [];
  const wanted = new Set(requested.map(String));
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, 2).getDisplayValues()
    .filter(function (row) {
      return wanted.has(String(row[0])) && String(row[1]) === "cancelled";
    })
    .map(function (row) { return String(row[0]); });
}

function markCancelled(ss, entryId) {
  if (cancelledIds(ss, [entryId]).length) return;
  stateSheet(ss, true).appendRow([entryId, "cancelled"]);
}

function summary(sheet, hrow, requested) {
  const rows = sheet.getRange("A1:B3").getValues();
  var remaining = null;
  rows.forEach(function (row) {
    if (String(row[0]).trim().toLowerCase() === "sisa") remaining = Number(row[1]);
  });
  if (!Number.isFinite(remaining)) return {ok: false, error: "missing Sisa summary"};
  return {
    ok: true,
    remaining_idr: Math.round(remaining),
    acknowledged_ids: acknowledgedIds(sheet, hrow, requested),
  };
}

function appendEntry(ss, sheet, hrow, body) {
  const entryId = String(body.entry_id || "").trim();
  if (!entryId) return {ok: false, error: "entry_id required"};
  if (cancelledIds(ss, [entryId]).length) {
    return {ok: true, appended: false, cancelled: true, entry_id: entryId};
  }
  const idIndex = entryIdColumn(sheet, hrow, true);
  if (acknowledgedIds(sheet, hrow, [entryId]).length) {
    return {ok: true, appended: false, entry_id: entryId};
  }

  const header = sheet.getRange(hrow, 1, 1, sheet.getLastColumn()).getValues()[0]
    .map(function (value) { return String(value).trim(); });
  const row = new Array(header.length).fill("");
  body.columns.forEach(function (column) {
    const at = header.indexOf(column);
    if (at < 0) return;
    row[at] = (column === "When" && body.row[column])
      ? new Date(body.row[column]) : body.row[column];
  });
  row[idIndex] = entryId;
  sheet.appendRow(row);
  return {ok: true, appended: true, entry_id: entryId};
}

function reconcileDelete(ss, sheet, hrow, body) {
  const originalId = String(body.original_id || "").trim();
  const reversal = body.reversal || {};
  const reversalId = String(reversal.entry_id || "").trim();
  if (!originalId || !reversalId) {
    return {ok: false, error: "original_id and reversal.entry_id required"};
  }

  // A true local flag proves an older carrier returned success even if that
  // pre-idempotency row has no Entry ID. A false flag never proves absence.
  const originalPresent = body.known_mirrored === true ||
    acknowledgedIds(sheet, hrow, [originalId]).length > 0;
  if (originalPresent && !acknowledgedIds(sheet, hrow, [reversalId]).length) {
    const reversed = appendEntry(ss, sheet, hrow, reversal);
    if (!reversed.ok || reversed.cancelled) return reversed;
  }

  // This marker and all append checks share the same script lock. If an
  // original append had the lock first it is visible and reversed above; if
  // deletion had the lock first, the later append observes this marker and
  // becomes a harmless acknowledged cancellation.
  markCancelled(ss, originalId);
  return {
    ok: true,
    cancelled: true,
    original_id: originalId,
    original_present: originalPresent,
    reversal_id: reversalId,
  };
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const body = JSON.parse(e.postData.contents);
    const secret = String(
      PropertiesService.getScriptProperties().getProperty(SECRET_PROPERTY) || ""
    );
    if (!secret || body.secret !== secret) {
      return jsonOutput({ok: false, error: "forbidden"});
    }
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheets().filter(function (candidate) {
      return candidate.getName() !== STATE_SHEET_NAME;
    })[0];
    const hrow = headerRowOf(sheet);

    if (body.action === "summary") {
      return jsonOutput(summary(sheet, hrow, body.pending_ids || []));
    }
    if (body.action === "append") {
      return jsonOutput(appendEntry(ss, sheet, hrow, body));
    }
    if (body.action === "reconcile_delete") {
      return jsonOutput(reconcileDelete(ss, sheet, hrow, body));
    }
    return jsonOutput({ok: false, error: "unknown action"});
  } finally {
    lock.releaseLock();
  }
}
```

## 3. Deploy it

Before deploying, open **Project Settings → Script properties** and add
`GROCERY_SHEET_SECRET` with a strong random value. The value stays outside the
script source and must match the production keystore value in step 4.

**Deploy → New deployment → Web app**:

- **Execute as**: Me
- **Who has access**: Anyone

Copy the Web app URL — it looks like
`https://script.google.com/macros/s/AKfy…/exec`.

The web app is reachable by anyone, but every read and append is authenticated
by `SECRET`. Keep the spreadsheet's Drive sharing **Restricted**; the app never
uses its public CSV export. A leaked deployment URL alone can neither read the
balance nor append a row.

## 4. Point the network at it

The URL is a credential — anyone holding it can append a row — so it lives
in the keystore beside the other keys, at `~/.coherence-network/keys.json`
(mode 600, never in git):

```json
{
  "grocery_sheet": {
    "webhook_url": "https://script.google.com/macros/s/AKfy…/exec",
    "secret": "THE_SAME_STRONG_RANDOM_SECRET"
  }
}
```

The secret is required. If either copy is empty or differs, Sheet reads and
writes fail closed. The graph ledger and its day/month totals remain available,
while **Sisa** displays as temporarily unavailable instead of showing an
incomplete graph-only balance.

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

## 5. Watch the float, and say something when it runs low

The watch asks the network what is left rather than reading its own formula
directly. The network reconciles that Sheet baseline with graph entries still
waiting to sync, so a temporarily lagging mirror does not lose a new spend.

Mail goes out through the account that owns the script, so no mail credential
lands in the keystore or anywhere else.

1. **Project Settings → Script properties** — add two:
   - `MEMBER_TOKEN` — a household token that can read totals
   - `ALERT_TO` — where the mail should go
2. **Triggers → Add trigger** — `watchFloat`, time-driven, day timer.

```javascript
// ---------------------------------------------------------------------------
// The low-float watch.
//
// Ask the network for the reconciled balance: Sheet baseline plus graph entries
// still waiting to sync. Reading only this script's formula would miss that
// pending delta while the mirror is temporarily dark.
//
// Set MEMBER_TOKEN and ALERT_TO in Project Settings > Script properties, then
// add a daily time-driven trigger on watchFloat. Mail goes out through the
// account that owns this script; no credential lands anywhere else.
//
// It emails on the crossing, not every day: once sent, it stays quiet until
// the float goes back above the threshold and dips again.
// ---------------------------------------------------------------------------

const FLOAT_FLOOR_IDR = 1500000;
const API_BASE = "https://api.coherencycoin.com";

function watchFloat() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty("MEMBER_TOKEN");
  const to = props.getProperty("ALERT_TO");
  if (!token || !to) {
    Logger.log("set MEMBER_TOKEN and ALERT_TO in Script properties first");
    return;
  }

  const url = API_BASE + "/api/grocery/totals?token=" + encodeURIComponent(token);
  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (response.getResponseCode() !== 200) {
    Logger.log("totals unavailable: HTTP " + response.getResponseCode());
    return;   // a dark endpoint is not a low balance; stay quiet and retry tomorrow
  }
  const remaining = Number(JSON.parse(response.getContentText()).remaining_idr || 0);
  const wasLow = props.getProperty("FLOAT_LOW") === "yes";
  const isLow = remaining < FLOAT_FLOOR_IDR;
  Logger.log("remaining " + remaining + "; low=" + isLow + "; already notified=" + wasLow);

  if (isLow && !wasLow) {
    const rp = "Rp" + remaining.toLocaleString("en-US");
    const floor = "Rp" + FLOAT_FLOOR_IDR.toLocaleString("en-US");
    MailApp.sendEmail({
      to: to,
      subject: "Hati Suci grocery float is down to " + rp,
      body: [
        "The grocery float has fallen below " + floor + ".",
        "",
        "Left to spend: " + rp,
        "",
        "The ledger: https://app.hati.earth/",
        "The sheet:   " + SpreadsheetApp.getActiveSpreadsheet().getUrl(),
        "",
        "This is sent once per crossing - it stays quiet until the float goes",
        "back above " + floor + " and dips again.",
      ].join("\n"),
    });
    props.setProperty("FLOAT_LOW", "yes");
    Logger.log("notified " + to);
  } else if (!isLow && wasLow) {
    props.deleteProperty("FLOAT_LOW");
    Logger.log("float is back above the floor; the watch is armed again");
  }
}
```

It emails **on the crossing**, not every day: once sent it stays quiet until
the float climbs back above the floor and dips again. A dark endpoint is not a
low balance, so an unreachable API logs and waits rather than crying wolf.

## 6. The manager's phone

The ledger reads its identity from a `?token=` in the URL, saves it, and strips
it from the address bar — so joining is one tap on one link, and there is no
second login:

```
https://app.hati.earth/?token=<the invite token>
```

A resident mints that token with `POST /api/household/invites`
(`{inviter_token, name, role}`). The `staff` role carries write access already,
so no separate vouch is needed before the first entry.

Once open, **Add to Home Screen** installs it as `Belanja`, standalone, opening
straight onto the ledger — `web/app/grocery/layout.tsx` gives the route its own
name and manifest so the icon is the book she keeps, not the network's feed.

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
pending, how many landed, whether a webhook is configured, and how many legacy
rows are blocked from automatic replay.

Every new graph write is stamped `sheet_protocol=entry-id-v1`. An older
unsynced graph row without that marker may have landed through the predecessor
carrier before Entry IDs existed and then crashed before its local flag was
saved. Its presence cannot be inferred safely. The balance therefore remains
unavailable, resync skips it, and deletion preserves it until the matching
Sheet row is manually identified and given that graph entry's ID (or absence is
confirmed and the graph row is migrated to `entry-id-v1`).

Deleting also waits for this carrier. Under the same script lock used by every
append, it records the original ID in a hidden `_Hati App State` cancellation
sheet and sends one stable compensating event if the original already landed.
An append that arrives after cancellation is acknowledged without writing a
ledger row. If this atomic receipt cannot be confirmed, the API keeps the
original graph entry and returns a retryable error.

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
