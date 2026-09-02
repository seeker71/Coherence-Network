---
idea_id: light-hub-membrane
status: active
source:
  - file: api/app/routers/grocery.py
    symbols: [record_spend(), list_spends(), totals(), nearest_shop(), save_shop(), export_csv(), _to_rupiah(), _resolve_description(), _push_to_sheet()]
  - file: api/app/form_recipes/endpoint_grocery_amount.fk
    symbols: [rupiah, scale_frac, pow10]
  - file: web/app/grocery/page.tsx
    symbols: [BalanceCard, GroceryPage, previewIdr(), todayLocal()]
  - file: web/tests/hati-grocery-layout.test.ts
    symbols: [Hati grocery balance layout]
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
  - "Buys and top-ups append to one signed ledger the hub owns; remaining is a single sum; a dark sheet never loses an entry"
  - "On a phone the remaining balance sits directly below the header before the entry pad; on a laptop it stays in the ledger column"
  - "GET /api/grocery/export.csv returns the whole ledger, so leaving the app costs nothing"
  - "The surface answers on app.hati.earth"
done_when:
  - "POST /api/grocery/spend with amount '123.5' returns amount_idr 123500"
  - "A spend recorded at a pinned shop's coordinates carries that shop's default_description"
  - "A spend recorded 4km from any shop carries no place and uses the icon or note"
  - "Writing requires a household member with write access; seeing is open to any registered cell"
  - "the mirror appends When/Amount/What rows; remaining is a fixed-cell formula, never a row; export.csv stays the fuller record"
  - "app.hati.earth serves the ledger with no site chrome"
  - "a 390x844 viewport shows the remaining balance in the first screen before the entry pad"
  - "all tests pass"
test: "cd api && .venv/bin/python -m pytest tests/test_grocery_ledger.py -q"
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

- [ ] **R6 — The sheet is a mirror, not a cage — and appending must be safe.**
  The hub's ledger was purchases on top, negative settlements below, and a
  `remaining` row under those, so every entry had to be squeezed in and the
  balance kept moving. Restructured to an append-only `When | Amount | What`
  log: one row per event, newest at the bottom, `Amount` signed (a buy
  positive, a top-up negative), and `Remaining`/`Spent`/`Topped up` as
  formulas in fixed cells that rows never reach. `Amount` goes as a number
  so the currency format and the sums keep working. If the webhook is unset
  or failing, the entry still records with `sheet_synced=false`, and
  `POST /api/grocery/sheet/resync` pushes the backlog. `GET
  /api/grocery/export.csv` is the door out, always open, and carries the
  fuller ten-column record.

- [ ] **R7 — Both directions, one ledger.** Money in (`POST /grocery/topup`)
  and money out (`POST /grocery/spend`) are the same cell with a `kind`, so
  "what is left to spend" is one signed sum rather than two tables to
  reconcile by hand. The app leads with that number, because it is what a
  manager asks before walking to the market.

- [ ] **R8 — A wrong number is fixable by the person who typed it.**
  `DELETE /grocery/spend/{id}` removes an entry for its recorder, or any
  entry for a resident, and says whether the sheet already has the row — we
  never reach into the hub's own document to edit what we handed over.

- [ ] **R9 — Signal is not a precondition.** A market with no bars must not
  cost the manager their entry: the web queues unsent drafts in localStorage
  and flushes them on the next connection.

## Files to Create/Modify

- `api/app/routers/grocery.py` — ledger routes, totals, places, export, and sheet mirror.
- `api/app/form_recipes/endpoint_grocery_amount.fk` — exact thousands-to-rupiah recipe.
- `api/tests/test_grocery_ledger.py` — API and ledger-flow acceptance coverage.
- `web/app/grocery/page.tsx` — contained phone and laptop grocery surface.
- `web/tests/hati-grocery-layout.test.ts` — responsive balance-placement invariant.
- `web/middleware.ts` — `app.hati.earth` host routing.
- `deploy/hostinger/auto-deploy.sh` — public grocery host labels.

## Acceptance Tests

- `api/tests/test_grocery_ledger.py` proves exact amounts, signed totals, permissions, places, deletion, export, and sheet resilience.
- `web/tests/hati-grocery-layout.test.ts` proves the phone balance precedes the entry pad and the laptop balance stays in the ledger column.
- Manual validation at a 390x844 viewport confirms the visible balance card is fully inside the first screen.

## Verification

```bash
cd api && .venv/bin/python -m pytest tests/test_grocery_ledger.py -q
cd web && npm test -- --run tests/hati-grocery-layout.test.ts tests/hati-grocery-handoff.test.ts
cd web && npm run build
./scripts/verify_worktree_local_web.sh --start
```

## Out of Scope

- The responsive placement change preserves the ledger arithmetic, graph storage, household identity, and sheet-mirror contracts.
- The grocery surface remains a focused household ledger rather than a general accounting application.

## Risks and Assumptions

- Tailwind's `lg` breakpoint remains the boundary between the phone-first balance card and the laptop ledger column; the source test and rendered viewport proof guard both sides.
- The graph totals route remains the source of the displayed amount; layout visibility never substitutes a locally computed balance.

## Known Gaps and Follow-up Tasks

- Follow-up task: complete the standard receipt already named in Honest Floor by observing the amount recipe through c-bootstrap `form-cli` on Windows and Android metal.

## Design Notes

**What the hub's own ledger taught us.** Reading the live sheet reshaped
this: every one of its eight purchase rows had `What` **empty** — the amount
recorded, the meaning lost. That column is the app's whole reason to exist,
and it is why the description is computed rather than requested. The amounts
there (`385`, `477.3`, `351`, `125`, `443`, `197`, `869`, `162` in thousands)
also confirm the *ribu* typing convention against real use, and the negative
settlement rows show a float ledger the mirror must not disturb.

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

`endpoint_grocery_amount.fk` **runs on the c-bootstrapped `fkwu`** — built
from the pinned kernel's `runtime/fkwu-uni.c` with a single `cc -O2`, gated
on the bootstrap grounds (`ground.fk` → 42, `ground-recursive.fk 10` → 55,
`ground-numeric-list.fk` → `[1, 2.5, [3, 4]]`). Every amount case is the
kernel's own answer, `runtime: fkwu`:

| typed | fkwu |
|---|---|
| `123.5` | 123500 |
| `85` | 85000 |
| `0.25` | 250 |
| `12.05` | 12050 |
| `1.234` | 1234 |
| `1000.75` | 1000750 |

The full flow suite passes against that kernel — 25 tests across this
ledger and the household board it borrows its places from.

It also **crosses four-way**. Go, Rust, TypeScript, and fkwu return the
same integer on all nine cases — `fourth arm: 9 case(s) four-way, 0
divergent`, no unsupported op (the band uses only `add`/`sub`/`mul`/`div`/
`lt` and recursion). Full table in
[`commit_evidence_2026-07-29_grocery_amount_four_way.json`](../docs/system_audit/commit_evidence_2026-07-29_grocery_amount_four_way.json).

The rung still above this is the **standard receipt** — this band observed
through c-bootstrap `form-cli` on mac, windows, and android metal. Those
rows are pending; four-way in a Linux container is a real rung below them.
