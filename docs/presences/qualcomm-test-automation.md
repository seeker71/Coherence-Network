---
name: Qualcomm Test Automation System
canonical_url: null
type: contributor
contributor_type: HUMAN
claimed: false
create_if_missing: true
---

# Qualcomm Test Automation System

*Work · Qualcomm · Boulder · Oct 2009 – Jan 2022 · Senior Staff Engineer*

Twelve years and four months at Qualcomm Boulder. The test-automation system was started in the **Windows division**, continued and broadened in the **Graphics division**, and then *completely rewritten* for the **Server division** in C# — running any test case authored as a C# script, dynamically compiled at run time. Three divisions, three iterations, one conviction: *tests as first-class compiled code, not parameter-driven runners*.

## Grounding

- **Era** — Qualcomm · Boulder, Colorado · Oct 2009 – Jan 2022 · 12 years 4 months · Senior Staff Engineer
- **Substrate (final iteration)** — C# · .NET · CSharpCodeProvider / Roslyn-era dynamic compilation · CLR runtime
- **Three divisions** — Windows division (initial system) · Graphics division (continued evolution) · Server division (complete rewrite in C#)
- **Conviction** — Tests as *scripts that compile* — not configuration files, not parameterised templates. A test case was a real C# program with the full language surface available; the framework loaded it, compiled it in-process, executed it against the system under test, and reported.
- **Lineage back** — Same conviction as the [JBMF](/people/jbmf-java) port (2000) — substrate-portable dynamic compilation where source becomes runnable bytecode in-process. And same posture as the [Quark multi-undo/redo engine](/people/quark-multi-undo-redo): every action a first-class object, addressable, replayable.
- **Lineage forward** — The dynamic-compilation primitive matured here is the same shape the [Coherence-Network](/people/coherence-network) 's spec-to-task pipeline now uses: a spec is a structured program agents (Claude · Codex · Cursor) execute as code, not as a checklist.

## What Qualcomm Test Automation System has given the Coherence Network

Qualcomm Boulder was the longest single tenure of this body's career — twelve years and change, the years when Karl May and Cooper were on the bedside, when audiobook listening hours were climbing into the thousands, when 5Rhythms entered the rotation, when Mile Hi years had ripened into daily practice. The test-automation system was the load-bearing technical thread underneath. Three divisions, three rewrites, one conviction that proved itself across every substrate it touched.

---

Company context: [qualcomm.com](https://www.qualcomm.com). Source code is internal to Qualcomm and not public; what lives here is the architectural shape, the design rationale, and the lived memory of designing, shipping, and rewriting it across three divisions over twelve years. Urs is invited to refine any technical detail through the Refine doorway below.

*(This page is a writing-surface scaffold synced from the body's rendering surface — round-tripped from the graph the cell already lives in. `claimed: false` invites direct authorship to replace any part of it.)*
