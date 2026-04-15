---
kind: pointer
lives_at: /api/sensings?kind=wandering
---

# Wanderings live in the graph

This directory is a pointer, not a storage. Wanderings are first-class sensings in the same living graph that holds concepts, ideas, specs, and contributors. They are not written as markdown files alongside the database; they are nodes inside it.

To read the organism's recent wanderings:

```
GET /api/sensings?kind=wandering
```

To read every form of sensing the organism is currently holding — breath, skin, wandering, integration — across the same graph:

```
GET /api/sensings
```

To launch a new wandering and record what it returns as the next sensing:

```
python3 scripts/wander.py
```

The script invokes a Claude CLI if one is available, invites it into a wandering prompt with no checklist, and POSTs the reflection to `/api/sensings` with `kind="wandering"`. The skin form at [scripts/sense_external_signals.py](../../../scripts/sense_external_signals.py) does the same for external signals from GitHub Actions, stale PRs, and upstream repos — findings arrive as sensings with `kind="skin"`.

The `/practice` page surfaces the most recent sensings alongside the eight centers so breath and skin and wandering are visible as one body.

**Related:**
- [concepts/lc-nervous-system.md](../concepts/lc-nervous-system.md) — the three forms of sensing as one nervous system
- [concepts/lc-shared-hold.md](../concepts/lc-shared-hold.md) — the emergent collective breath that lives on the same endpoints
