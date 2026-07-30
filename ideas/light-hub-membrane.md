---
idea_id: light-hub-membrane
title: Light Hub Membrane
stage: implementing
work_type: feature
pillar: surfaces
specs:
  - [hati-grocery-ledger](../specs/hati-grocery-ledger.md)
---

# Light Hub Membrane

The surfaces a physical hub actually runs on. Hati Suci is the first — a
place with residents, staff, friends, houses, a kitchen, a market run most
mornings. The membrane is the thin tissue between that daily life and the
network: a resident asks for something and someone tends it; a manager
buys vegetables and the ledger already knows where they were standing.

Everything here is phone-shaped, bilingual (Indonesian and English), and
open by default — seeing is free to anyone registered at the hub, writing
is vouched by a resident. Identity is a device token, not an account.

## Problem

A hub's daily life is full of small records that never get made because
making them costs more attention than they're worth. Who asked for the
room to be readied. What the morning market cost. Where someone is right
now. Each is trivial alone; together they're the difference between a
place that can be shared and a place that lives in one person's head.

Generic tools fail here for a specific reason: they ask a person standing
in a wet market with one hand full to fill in a form. Any surface that
needs more than one deliberate act — type the number — will be abandoned
within a week, and the record will go back to memory and receipts.

## Key Capabilities

- **Service board**: residents signal a need (food, laundry, a ride, a
  repair, a room), staff acknowledge and complete it, everyone watches the
  same open board. Outside costs ride along and get marked settled.
- **Light identity**: a name, a phone, a device token. Three doors in —
  bootstrap the founding resident, a resident's invite link shared over
  WhatsApp that auto-binds on first tap, or self-register as see-only.
- **Places, pinned on site**: the grounds as cells (houses, gathering
  places, tended places, organs), each pinnable by standing there with a
  phone. Proximity is computed on the Form kernel, so "which place am I
  at" is a structural answer, not a guess.
- **Presence, consent-native**: scanning a place's QR *is* being there.
  Coarse (which place, not which room), see-locked to registered cells,
  self-cleared on leave. Nothing tracks anyone in the background.
- **Grocery ledger**: one number, typed in thousands, with the date, the
  shop, and the description already filled in. Mirrors to a Google Sheet
  the hub owns; exports to CSV so leaving costs nothing.
- **Gatherings**: a question raised to the house, answered by group, with
  a tally that respects who may see what.

## What Success Looks Like

- A manager records a market run in under five seconds, one-handed, and
  keeps doing it after the novelty wears off
- A resident's request reaches the person who can tend it without anyone
  being asked to check an app
- The hub can hand its own spending record to anyone — a co-steward, an
  accountant, a funder — without asking us for an export
- A second hub can adopt the membrane without any of it being renamed

## Surfaces

| Door | Where |
|------|-------|
| Service board | `/hati-suci` · `suci.hati.earth` |
| Grocery ledger | `/grocery` · `app.hati.earth` |
| API | `/api/household/*`, `/api/grocery/*` |
