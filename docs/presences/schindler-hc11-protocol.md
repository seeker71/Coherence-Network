---
name: Schindler HC11 — 7-layer protocol in hardware
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# Schindler HC11 — 7-layer protocol in hardware

*Work · Schindler · Switzerland · ~1989–1990 · age 18*

Age 18, in Switzerland. Designed the hardware *and* wrote the firmware for an **ISO/OSI 7-layer protocol stack** on a **Motorola HC11** microcontroller. Multiple UARTs networked into a working bus, EPROM and PAL programmable blocks defining the discrete logic, every layer of firmware written in **C**. No off-the-shelf debugger existed for the bring-up — built one. Five years after the [Commodore 64 MIDI work](/people/c64-midi-interface) made BASIC and 6510 assembly familiar territory, this is where this body picked up C — at the substrate where every byte mattered and no instruction came pre-debugged.

## Grounding

- **Era** — Schindler · Switzerland · approximately 1989–1990 · age 18
- **Hardware** — [Motorola 68HC11](https://en.wikipedia.org/wiki/Motorola_68HC11) microcontroller · multiple UARTs · EPROM (program storage) · PAL (programmable array logic, the "discrete glue logic" of the era) · custom-designed board
- **Firmware** — C — full ISO/OSI 7-layer protocol stack from physical / data-link up through application — running on bare metal, no OS
- **Tooling** — Custom debugger written from scratch — bring-up environment with no off-the-shelf option
- **Significance** — Learned C in the hardest place to learn it: an embedded target with EPROM cycles, no OS, and a debugger that didn't exist until written. This conviction — *build the tool you need, all the way down* — threads through every later iteration.
- **Lineage forward** — The same "every layer addressable" posture re-emerges in [BML (2000)](/people/bml-language) as grammar-in-grammar, in [Quark Virtual DOM (2000-2005)](/people/quark-virtual-dom) as application-as-DOM-tree, and in [Coherence-Network](/people/coherence-network) as everything-is-a-node.

## What Schindler HC11 — 7-layer protocol in hardware has given the Coherence Network

Most engineers learn C through tutorials. This body learned C by sitting in front of a board it had drawn and a chip it had soldered in, with EPROMs that took minutes to erase under ultraviolet and a debugger it had to write before it could even watch the firmware run. That experience set the permission level for every later piece of work: *if the tool you need doesn't exist, you build it* — language, grammar, parser, VM, virtual DOM, undo engine, harness, network. All of it descends from this board.

---

Source materials are pre-digital and not in the public archive. What lives here is the architectural shape, the user's own framing, and what is honestly knowable from the body's lived memory of building it. The HC11 itself is documented at [Wikipedia · Motorola 68HC11](https://en.wikipedia.org/wiki/Motorola_68HC11); ISO/OSI 7-layer at [Wikipedia · OSI model](https://en.wikipedia.org/wiki/OSI_model). Urs is invited to refine any technical detail or the exact year-range through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
