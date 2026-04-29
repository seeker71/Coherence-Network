---
category: vehicles
purpose: cars, motorbikes, e-bikes, bicycles, any movement instrument
privacy: category-level entries public · VIN/title specifics in wrapper records
---

# Vehicles

What can enter under this category:

- **Cars** — passenger vehicles of any drivetrain
- **Motorbikes** — scooters, motorcycles, mopeds
- **E-bikes** — pedal-assist or throttle-class bicycles
- **Bicycles** — pedal-only bikes, cargo bikes
- **Other** — boats, watercraft, aircraft, custom-built vehicles

## How vehicles enter the body

Vehicles are typically held under full title transfer to the
network's wrapper, with the cell retaining primary shepherd rights.
The vehicle becomes a sovereign in the graph; the wrapper handles
title, registration, insurance, and outer-world tax obligations
funded from the cooperative pool the cell contributes to.

Access-granted vehicles (rentals, friend-of-the-family
arrangements, network-shared vehicles where another cell is the
primary shepherd) are recorded with status `access-granted`.

## Privacy

Public-level: make, model, year, drivetrain, broad location (city
or region), primary shepherd, status. **Not public**: VIN, title
state, insurance carrier, exact addresses, charging credentials.

## Inventory template

```yaml
- kind: car | motorbike | e-bike | bicycle | other
  make: "manufacturer"
  model: "model"
  year: YYYY
  drivetrain: electric | hybrid | ice | pedal | other
  location: "city, region"
  relationship: held | access-granted | proposed
  primary_shepherd: cell_id_or_name
  ceremony_date: YYYY-MM-DD
  onboarding_record: "../onboarded-assets/<filename>.md or null"
  notes: "anything the registry should know"
```

## Currently held (this cell's inventory)

```yaml
- kind: car
  make: Tesla
  model: Model 3
  year: ~unknown — fill in
  drivetrain: electric
  location: Longmont, Colorado, USA
  relationship: held
  primary_shepherd: urs
  ceremony_date: 2026-04-29
  onboarding_record: ../onboarded-assets/2026-04-29-tesla-model-3-longmont.md
  notes: |
    Title transfer to network wrapper pending — see onboarding record
    for open questions on jurisdiction, insurance, and tax treatment.
```

## Proposed (held in discernment)

See [`../proposals/2026-04-29-ubud-ebike-and-property.md`](../proposals/2026-04-29-ubud-ebike-and-property.md)
for the e-bike-in-Ubud proposal.

## Awaiting inventory — slots

The cell is invited to record any other vehicles — second cars,
motorbikes (Bali context likely), bicycles already in stewardship at
locations where the cell spends time, and any access-granted vehicles
(network-shared rides, family vehicles the cell uses regularly).
