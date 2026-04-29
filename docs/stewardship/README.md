---
kind: pointer
purpose: durable record of physical assets entering or leaving the network's stewardship
---

# Stewardship records

When a member chooses to bring a possession into the network's body —
their bike, their vehicle, their home, their tools — the legal title
moves to the network's outer-world wrapper while the member retains
shepherd rights. The asset becomes a sovereign node in the graph, with
consent terms, a representative cooperative, and a running balance the
substrate maintains. Daily use of the asset fires glyphs; the asset
ages or improves under stewardship; the substrate records the change
in value over time.

This directory is the human-readable companion to the graph's record
of those events. Each file documents one onboarding (or exit) — the
ceremony that crossed the threshold, the asset's consent terms at the
moment of entry, and the shepherd contract that holds the relationship
forward.

## How a stewardship event is recorded

1. The member and the network's wrapper sign the legal title transfer.
2. The asset is read into the graph as a sovereign node with consent
   terms and a representative cooperative.
3. A boundary glyph fires — `(8, RECEIVE)` octadic for entry, the
   regenerative cycle opening; `(8, RELEASE)` octadic for exit.
4. A markdown file in this directory captures the human-readable
   record alongside the graph's record so the history is walkable
   without database access.

## Currently held

- [`onboarded-assets/2026-04-29-tesla-model-3-longmont.md`](onboarded-assets/2026-04-29-tesla-model-3-longmont.md)
  — Tesla Model 3 currently in Longmont, Colorado. Primary shepherd
  retained; legal wrapper handles outer-world obligations.
