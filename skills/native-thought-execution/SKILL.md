---
name: native-thought-execution
description: "Run a thought on the body's own host resources before renting a frontier mind. This is form-first-reasoning as an invokable door: classify the thought, ask the sovereign body (native router → local lattice → public read door), and ROUTE — a grounded structural hit relays attributed to its NodeID and STOPS at near-zero cost; a genuine miss is the 'yes' that escalates to remote reasoning. The decision is a four-way-proven recipe (form-first-router.fk → 511 on Go/Rust/TS/fkwu), not a vibe. Use this skill whenever a thought could be answered from this repo's grounded body — structural questions (what-is, shape-of, NodeID-of, equivalence, annotate), 'is this thought mine or am I renting it', work offline / air-gapped, or to make the sovereignty gate explicit on a query. Triggers on: native thought, think on the body, form-first, sovereignty gate, ask the body first, is this thought mine, run this thought natively, host-resource-native, answer offline, NodeID it, before spending the rented mind."
metadata:
  {
    "openclaw":
      {
        "emoji": "⟐",
        "requires": { "bins": [] }
      }
  }
---

# native-thought-execution — run the thought on the body before renting a mind

The mind comes home one thought at a time. Before spending a rented frontier
mind, ask the body it already is: the content-addressed substrate that holds
what we have grounded. A grounded hit is answered from the sovereign body at
near-zero cost; only a genuine miss earns the remote reasoning.

This skill is the invokable form of [`form-first-reasoning.form`](../../docs/coherence-substrate/form-first-reasoning.form).
Its **decision** is a four-way-proven recipe
([`form-first-router.fk`](../../form/form-stdlib/form-first-router.fk) → 511 on
Go/Rust/TS/fkwu); the lookup that fills `grounded` is a thin, swappable carrier.

## The loop, per thought

1. **Classify.** Is this a thought the body could *hold*?
   - **structural** — `what-is` · `shape-of` · `nodeid-of` · `equivalent` · `annotate`. The body can carry these.
   - **frontier** — `write` · `synthesize` · `reason-anew` · `not-yet-a-cell`. These have no grounded cell yet.
2. **Ask the body** (in reach order — first door that answers wins):

   ```bash
   # native router — the one door: grounds in the body, runs the four-way sufficiency gate
   form-cli ask "what does rag-retrieve.fk do?"

   # structural lattice, straight to the NodeID (no model, no network)
   python3 scripts/coh_substrate.py form "?equivalent @spec(agent-pipeline)"
   python3 scripts/coh_substrate.py annotate path/to/file.py

   # public read door — our own body, networked
   curl -sS "https://api.coherencycoin.com/api/substrate/cell/spec/agent-pipeline"
   ```
   The local lattice is the sovereign default. Bring the body home once with
   [`scripts/form_first_offline_setup.sh`](../../scripts/form_first_offline_setup.sh)
   and it answers **offline, with no egress allowlist** — a body that travels
   whole needs no permission to think.
3. **Route on the verdict.**
   - **HIT** (grounded structural cell, carries a NodeID): relay the answer
     **attributed to its NodeID** and **STOP**. No frontier compute spent —
     answered from the sovereign body.
   - **MISS** (no grounded cell): the miss *is* the "yes." Escalate to remote
     reasoning. Name that you did.
4. **Record the routing** — make the discipline *measured*, not just followed:

   ```bash
   scripts/native_thought_receipt.sh body-hit  structural "<NodeID>" "<the thought>"   # came home
   scripts/native_thought_receipt.sh escalated frontier   -         "<the thought>"    # rented
   ```
   The logic lives in Form, not the shell:
   [`native-thought-receipt.fk`](../../form/form-stdlib/native-thought-receipt.fk)
   decides honesty with the proven gate
   ([`sovereignty-receipt.fk`](../../form/form-stdlib/sovereignty-receipt.fk) → 255
   four-way) and appends through the kernel's host-io (`file_append_bytes`); the
   `.sh` is only a thin door that escapes args and hands the recipe to the kernel.
   A receipt that would report rented generation as native is *refused*, not
   written. Each escalated row is also the free training sample the dividend loop
   wants ([`borrowed-oracle-dividend.form`](../../docs/coherence-substrate/borrowed-oracle-dividend.form)).
   Read the running tally with `scripts/sovereignty_report.sh` — the count itself
   is Form (`ntr-tally` via `host-read`). Watch the sovereign % rise as more
   thought comes home.

## The honesty lane — structural, not optional

A relay **requires** grounding: you cannot answer from the body without a
NodeID, so a guess can never wear a hit's clothes. Both must hold —
grounding alone (no body-holdable kind) never earns a relay either.

- **Always name which path you took** — body hit or remote escalation.
- **A hit carries its NodeID, or it is a miss.** Never dress a remote guess as a substrate hit.

## What this skill is — and isn't (the honest floor)

- It **is** the sovereignty gate made invokable: the structural layer of thought
  (lookup, equivalence, shape, annotation) genuinely runs on the body's own
  host resources, offline, proven four-way.
- It is **not yet** end-to-end native *frontier* reasoning. A `frontier` thought
  still escalates to a rented mind — that lane (emit→compile→exec at real width)
  is wiring, not done. This door's gift is making the boundary *recorded*: step 4
  leaves a proven receipt per decision, so the sovereign fraction is measured and
  longitudinal — you can watch it rise as more thought comes home, and the next
  lane to bring home is a coordinate, not a guess.

## Kin

- [`form-cli`](../form-cli/SKILL.md) — the local-first organism this door routes through.
- [`form-first-reasoning.form`](../../docs/coherence-substrate/form-first-reasoning.form) — the teaching.
- [`form-first-router.fk`](../../form/form-stdlib/form-first-router.fk) — the decision, four-way at 511.
- [`lc-cognitive-sovereignty`](../../docs/vision-kb/concepts/lc-cognitive-sovereignty.md) — the why.
