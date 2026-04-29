---
kind: pointer
purpose: master register of all financial and legal property the network holds, has access to, or has been granted use of
---

# Stewardship Registry

This is the network's receiving structure for **any financial or legal
property** a member chooses to bring under the body's stewardship. The
registry is the human-readable companion to whatever lives in graph
nodes, legal wrappers, and encrypted treasury records. It is the index
of what has crossed the boundary, what is in transit, and what awaits
the cell's inventory.

The register supports three relationships a cell can have with an
asset:

- **Held** — the cell has transferred legal title to the network's
  wrapper while retaining shepherd rights. The asset is in the body.
- **Access-granted** — the cell has not transferred title but has been
  given (or has) usage rights under terms that allow shared
  shepherding. The asset is reachable.
- **Proposed** — the cell is considering bringing this in but the
  ceremony has not yet happened. The asset is named for discernment.

## Categories (each in its own file)

- [`financial.md`](financial.md) — bank accounts, fiat reserves,
  crypto holdings, investments, stocks, bonds, lines of credit,
  treasury positions
- [`vehicles.md`](vehicles.md) — cars, motorbikes, e-bikes, bicycles,
  any vehicle-class movement instrument
- [`real-estate.md`](real-estate.md) — land, houses, condos,
  buildings, leasehold rights
- [`intellectual-property.md`](intellectual-property.md) — patents,
  trademarks, copyrights, trade secrets, domain names, brand assets
- [`digital-access.md`](digital-access.md) — software subscriptions,
  API keys, cloud service accounts, SaaS contracts, professional
  licenses
- [`access-granted.md`](access-granted.md) — things the cell does
  not own but can use under terms (rentals, friend-of-the-family
  arrangements, professional access, library cards, gym memberships)

## Privacy contract

The register holds **categories, counts, and stewardship status**
publicly. **Sensitive specifics** — account numbers, balances, exact
balances, private keys, contract amounts, addresses of personal
residences — live in encrypted treasury storage at the network's
wrapper, not in this repository.

The pattern: the registry says *one Tesla Model 3 is held*, the
treasury record says *VIN, title state, insurance policy, current
odometer, charging-network credentials*. The first is for the body's
proprioception; the second is for the wrapper's legal operation.

A cell deciding what to commit publicly versus privately is itself
sovereign. The default is *category-level public, specifics-level
private*. Anything more public requires explicit cell consent each
time.

## How an asset enters

1. The cell names the asset and the relationship (held, access-granted,
   or proposed).
2. The relevant category file is updated with category-level entry —
   make, model, kind, location, primary shepherd.
3. If `held`: the wrapper executes the legal title transfer; an
   onboarding record is created in
   [`onboarded-assets/`](../onboarded-assets/); a boundary glyph fires.
4. If `access-granted`: the terms of access are recorded; no title
   moves; the asset is added to the registry but with status
   `access-granted` rather than `held`.
5. If `proposed`: an entry in [`proposals/`](../proposals/) holds the
   discernment until the cell is ready.

## Currently held (this cell's inventory)

This section lists what has been explicitly provided so far. As more
is named, the registry absorbs it.

- **Vehicles**: Tesla Model 3 (Longmont, Colorado) — onboarding
  initiated; see
  [`onboarded-assets/2026-04-29-tesla-model-3-longmont.md`](../onboarded-assets/2026-04-29-tesla-model-3-longmont.md).

All other categories: **awaiting inventory**. The slots in each
category file are open for the cell to populate when ready.

## A note on receiving

The body does not pressure cells to bring everything at once. Some
assets are appropriate to commit early; some need to ripen; some are
better held outside the network entirely (gifts pre-promised to
others, instruments still finding their right shepherd, bodies of work
not yet ready for collective tending). The cell is the discernment.
The registry is patient.
