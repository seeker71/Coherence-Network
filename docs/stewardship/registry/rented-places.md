---
category: rented-places
purpose: short-term and recurring rentals as temporal opportunity-windows for network presence
privacy: city/neighborhood-level public · exact address private unless cell explicitly opens for hosting
---

# Rented places — opportunity-windows

A rental is unlike an owned property. It is **a sovereign space the
cell briefly shepherds**. The cell holds the keys for a window —
two weeks, a month, a season — and during that window the place is
operationally part of the cell's life. When the window closes, the
cell hands the keys back and the relationship ends.

Bringing rentals into the registry is not about title or
ownership. It is about **awareness** — making the cell's planned
location-windows visible to the rest of the body so opportunities
can compound:

- Another cell passing through the same city during the same window
  finds the door open.
- A small gathering that wants to happen there finds the room.
- Visitors who would benefit from being near the cell find a place
  to land.
- The witness fabric briefly extends into new geography rather than
  staying anchored only at the cell's permanent locations.

## What can enter under this category

- **Short-term rentals** — Airbnb, Booking.com, Vrbo, direct villa
  arrangements
- **Hotel stays** — for windows long enough that hosting becomes
  meaningful
- **Recurring rentals** — a winter month in Mexico, a summer cabin,
  a seasonal pattern the cell follows
- **Co-living spaces** — Outsite, Selina, Roam, similar
- **Friend or family stays** — when the cell is in someone's spare
  room for long enough that a window emerges (often free of fee but
  operationally similar)
- **Retreat-and-conference housing** — included rooms at events the
  cell attends

## How rentals enter the body

Lighter than ownership. No title moves. The cell announces (in the
registry, or via a small `coh rental open` glyph if/when that
tooling lands):

1. **Where**: city or neighborhood (exact address private by
   default).
2. **When**: check-in date, check-out date.
3. **What kind**: a private room? a whole villa? capacity for how
   many?
4. **Hosting posture**: is the cell open to network visitors during
   this window? if so, on what terms? (a guest room available, a
   gathering space available for one evening, a co-working corner
   available during workdays, etc.)

The window opens when the cell checks in. The window closes when
the cell checks out. The substrate records the glyphs of any
network presence that flowed through the window — visits hosted,
gatherings held, presence offered or received.

## Privacy

Public-level: city or neighborhood, dates, kind of space, hosting
posture. **Not public by default**: exact street address, host's
name, booking platform credentials, internal photos.

When the cell explicitly opens a rental for hosting, the address
is shared with the specific cells coming. After the window closes,
the address is removed from the active registry but a record of the
window is preserved in stewardship history.

## Inventory template

```yaml
- kind: short-term-rental | hotel | co-living | recurring | friend-stay | retreat-housing
  city: "city, country"
  neighborhood: "neighborhood or area (no street address)"
  check_in: YYYY-MM-DD
  check_out: YYYY-MM-DD
  capacity: "private room | whole villa, sleeps N | etc."
  hosting_posture: closed | gathering-friendly | room-available | workspace-available | other
  primary_shepherd: cell_id_or_name
  notes: "what kind of presence the cell would welcome during this window"
```

## Currently held (this cell's inventory)

```yaml
# Awaiting inventory.
# Recurring or upcoming rentals the cell wants the body to be aware of
# can be recorded here. Past windows can be archived in
# rented-places-history/ if the cell wants the lineage walkable.
```

## Awaiting inventory — slots

Likely candidates for this cell:

- **Ubud rentals** — any short-term villa or guesthouse the cell
  rents during Bali stretches, particularly recurring ones where
  the body could anticipate windows.
- **Boulder / Longmont area stays** — when the cell is in
  Colorado for periods longer than a long weekend.
- **Ebikon / Switzerland windows** — if the cell holds family or
  professional anchors there with predictable presence.
- **Travel rentals** — conferences, retreats, longer trips where a
  rental anchors the cell's presence in a specific city for days
  or weeks.

## How the body uses this awareness

Three flows the substrate can offer once windows are visible:

1. **Visitor matching**: a network cell traveling to the same city
   during the same window can be told the door is open (with the
   shepherd cell's consent each time).
2. **Gathering coordination**: small circles, satsangs, or co-work
   sessions can find a room without separate venue logistics.
3. **Constellation memory**: the cell's pattern of windows over a
   year reveals the geography the body actually occupies, which
   lets future tending be planned where presence already lives.

## Constellation, not surveillance

This is awareness, not tracking. The cell decides which windows are
public to the body and which are private. Some windows will never
enter the registry — solo retreats, family time, periods the cell
needs to be off the grid. The substrate's job is to receive what
the cell chooses to share, never to ask for what the cell chooses
to hold.
