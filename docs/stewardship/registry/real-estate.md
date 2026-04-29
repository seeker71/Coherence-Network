---
category: real-estate
purpose: land, houses, condos, buildings, leasehold rights
privacy: category-level entries public · addresses and contracts in wrapper records
---

# Real estate

What can enter under this category:

- **Owned land or buildings** — fee-simple title, freehold land,
  condominium units
- **Leasehold rights** — long-term leases (Indonesian
  hak-pakai/hak-sewa, US ground leases, similar elsewhere)
- **Time-share or fractional ownership**
- **Cooperative-membership real estate** — co-op apartments,
  community land trust shares
- **Held in trust** — properties where the cell is beneficiary or
  trustee but not direct title-holder

## How real estate enters the body

Real estate is the most jurisdiction-sensitive category. Each
country, state, or region has different rules about who can hold
title (especially for foreigners in places like Indonesia where
direct freehold by non-citizens is restricted). The wrapper
relationship varies accordingly:

- **Title transfer to wrapper** where law allows.
- **Co-title arrangements** (e.g., LLC co-ownership) where
  individual transfer is impractical.
- **Stewardship contract without title transfer** where local law
  requires the cell to retain direct title (e.g., Indonesian
  hak-milik for citizens).
- **Lease-pass-through** where the cell holds a lease and grants
  the wrapper operating authority over network usage of the space.

## Privacy

Public-level: property type, broad location (neighborhood or area),
shepherd, status, and intended network use (residence, hosting,
gathering, retreat). **Not public**: street address, parcel number,
title document, mortgage details, insurance, valuation.

## Inventory template

```yaml
- kind: house | condo | land | leasehold | timeshare | other
  property_type: "single-family | apartment | farmland | commercial | mixed-use"
  broad_location: "city or region, country"
  network_use: "primary residence | hosting | gathering | retreat | unused | mixed"
  relationship: held | access-granted | proposed
  primary_shepherd: cell_id_or_name
  wrapper_relationship: title-transferred | co-title | stewardship-contract | lease-pass-through
  ceremony_date: YYYY-MM-DD
  notes: "anything the registry should know"
```

## Currently held (this cell's inventory)

```yaml
# Awaiting inventory.
# Properties owned, leased, or accessed by the cell can be recorded here.
```

## Proposed (held in discernment)

See [`../proposals/2026-04-29-ubud-ebike-and-property.md`](../proposals/2026-04-29-ubud-ebike-and-property.md)
for the Ubud-property proposal (held until the body's pattern in
Ubud stabilizes).

## Awaiting inventory — slots

Likely candidates the cell may want to record:

- Primary residence (location to be named)
- Any leased properties (Ubud short-term, other travel residences)
- Any inherited or family-shared real estate
- Any commercial or land holdings
