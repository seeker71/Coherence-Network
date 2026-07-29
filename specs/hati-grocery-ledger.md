---
idea_id: light-hub-membrane
status: active
source:
  - file: api/app/routers/grocery.py
    symbols: [record_spend(), list_spends(), totals(), nearest_shop(), save_shop(), export_csv(), _to_rupiah(), _resolve_description(), _push_to_sheet()]
  - file: api/app/form_recipes/endpoint_grocery_amount.fk
    symbols: [rupiah, scale_frac, pow10]
  - file: web/app/grocery/page.tsx
    symbols: [GroceryPage, previewIdr(), todayLocal()]
  - file: web/middleware.ts
    symbols: [app. host rewrite]
  - file: deploy/hostinger/auto-deploy.sh
    symbols: [coherence-web-hati traefik labels]
requirements:
  - "The manager types an amount in thousands; 123.5 records as 123500 IDR exactly"
  - "The thousands→rupiah conversion runs on the Form kernel, with no float in the path"
  - "A stored shop within ~150m of the phone's GPS fills the description in automatically"
  - "When no shop is near, category icons carry the description and a custom field overrides it"
  - "The entry date defaults to today in the hub's timezone (UTC+8), not UTC"
  - "Entries mirror to a Google Sheet the hub owns, via a webhook URL; a dark sheet never loses an entry"
  - "GET /api/grocery/export.csv returns the whole ledger, so leaving the app costs nothing"
  - "The surface answers on app.hati.earth"
done_when:
  - "POST /api/grocery/spend with amount '123.5' returns amount_idr 123500"
  - "A spend recorded at a pinned shop's coordinates carries that shop's default_description"
  - "A spend recorded 4km from any shop carries no place and uses the icon or note"
  - "Writing requires a household member with write access; seeing is open to any registered cell"
  - "export.csv columns match the Sheets mirror columns exactly"
  - "app.hati.earth serves the ledger with no site chrome"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_grocery_ledger.py -q"
constraints:
  - "Shops reuse the household_place cell with kind=shop — no parallel location system"
  - "Identity reuses the household device token — no second login"
  - "The amount is computed by the recipe only; no Python mirror of the arithmetic"
  - "The graph is the source of truth; Sheets is a mirror, never the store"
  - "No Google service-account credentials in the keystore — the hub owns the webhook"
---

# Spec: Hati Grocery Ledger

## Purpose

The hub's manager buys food most days and the record of it lived nowhere a
second person could read. This is the smallest surface that changes that:
one number typed on a phone in the market, and an entry that already knows
the date, the place, and what it was for. The bar is that recording a spend
costs less attention than not recording it — otherwise the ledger decays
into a shoebox of receipts, which is the failure this replaces.

## Requirements

- [ ] **R1 — The number is the whole interaction.** The manager types in
  thousands, the *ribu* habit they already use at a warung: `123.5` is
  Rp 123.500, `85` is Rp 85.000, `0.25` is Rp 250. The typed string is kept
  alongside the resolved rupiah so the ledger can always show what the thumb
  actually did.

- [ ] **R2 — The conversion is exact.** `123.5` is split into digits
  (`whole=123, frac=5, fraclen=1`) and multiplied as integers on the Form
  kernel. No float touches the money path, so `0.25` is Rp 250 and never
  Rp 249.99999.

- [ ] **R3 — The description arrives before it is typed.** Shops are
  `household_place` cells with `kind="shop"` and a `default_description`.
  When the phone's GPS lands within ~150m (1500 micro-degrees Manhattan) of
  a pinned shop, that shop's description becomes the entry's description.
  Beyond that radius, "nearest" returns nothing rather than a shop 4km away.

- [ ] **R4 — Icons carry it when no shop does.** Eleven categories, each an
  emoji and a bilingual label, cover what a hub buys. Selecting one is the
  description. A custom free-text field overrides both shop and icon —
  whoever typed something specific said the most specific thing.

- [ ] **R5 — The date is the manager's today.** Bali is UTC+8 with no DST.
  An entry made at 07:30 local must file under that morning, not the day
  before, so the API and the web agree on a UTC+8 day boundary.

- [ ] **R6 — The sheet is a mirror, not a cage.** Each entry POSTs a row to
  a webhook URL the hub owns (an Apps Script bound to their own spreadsheet).
  If the webhook is unset or failing, the entry still records with
  `sheet_synced=false`, and `POST /api/grocery/sheet/resync` pushes the
  backlog. `GET /api/grocery/export.csv` is the door out, always open.

- [ ] **R7 — Signal is not a precondition.** A market with no bars must not
  cost the manager their entry: the web queues unsent drafts in localStorage
  and flushes them on the next connection.

## Design Notes

**Why shops are place cells.** The household board already pins places by
GPS in micro-degrees and already computes proximity on the kernel
(`endpoint_place_distance.fk`). A second location system would mean two
pin flows, two distance functions, and two things to keep in sync. A shop
is a place with a `kind` and a stored sentence.

**Why a webhook and not a service account.** A service account would put a
Google credential in our keystore and make the hub's ledger depend on our
key rotation. An Apps Script Web App URL is deployed by the hub against
their own sheet: they own the destination, we hold no secret, and revoking
us is deleting a URL. Setup is documented in `docs/grocery-sheets-setup.md`.

**Why no Python mirror of the arithmetic.** `serve_via_kernel` fails hard
when the kernel is absent, on purpose — so Python never quietly resumes
ownership of a computation the body has moved to Form. Resilience for the
manager belongs at the edge (the offline queue), not as a second
implementation of the money math that could drift from the first.

## Honest Floor

The amount recipe's arithmetic is verified by cases (`123.5 → 123500`,
`0.25 → 250`, `12.05 → 12050`), but it has **not** yet been run four-way:
the `fkwu` runtime is unbuilt where this was authored. Four-way proof for
`endpoint_grocery_amount.fk` is the next rung, and until it lands this
recipe rides the same floor as the household board's kernel recipes.
