# 03 — Recipe as Compression (and the honest finding: it isn't, for small things)

**Discovery**: at small payload sizes, the substrate's canonical *ice* form is
**larger** than the text *water* form, not smaller. The recipe-as-compression
intuition is only true above a scale threshold where structural sharing
outweighs the per-payload header cost. Naming this honestly matters more than
making the demo "win".

## Run

```bash
cd <repo-root>
go build -o /tmp/form-kernel-go ./form/form-kernel-go
/tmp/form-kernel-go form/form-samples/cross-modal/03-recipe-as-compression/freeze.fk
```

Output:

```
source (payload.fk, the 'water' as text):   519 bytes
ice    (payload.fkb, canonical recipe):    2166 bytes
roundtrip identity: yes — same NodeID after thaw
ratio (ice / source): 417%
```

## What's reachable today

- **Round-trippable freeze.** [`freeze.fk`](freeze.fk) interns a structured
  payload (5 records, 3 fields each), serializes via `write_form_binary` to
  `payload.fkb`, reads it back via `read_form_binary`, and verifies the
  restored NodeID equals the original. The recipe identity survives
  serialization.
- **Universal serialization.** The `.fkb` format embeds the string table so
  reads from a fresh kernel process work — this is how the substrate
  ships content-addressed identity across kernel boundaries.

## What surprised

The honest size ratio: **the ice is 4.17× larger than the water** at this
payload scale. The intuition "structure-as-compression" trips on the metadata
overhead — `.fkb` carries the string table, NodeID indices, category
references, and tree topology. Below ~10kB of payload, the canonical form is
almost always larger than the source text.

Where compression actually shows up:
- **Structural sharing across many recipes** — once 1000 recipes share the
  same sub-trees, the substrate stores those sub-trees once and references
  them. The kernel's in-memory representation collapses; the disk format
  doesn't automatically reflect that unless you serialize *the whole substrate*
  rather than a single recipe.
- **Cross-recipe deduplication** — `intern_trivial_string("alice")` returns
  the same NodeID every time. In a payload with 10,000 records that share 50
  distinct strings, the substrate holds 50 string trivials, not 10,000.

## What's not reachable today

- **Whole-substrate snapshot vs incremental .fkb.** The current
  `write_form_binary` serializes one Recipe root + the strings it transitively
  uses. A `write_substrate_snapshot` that captured the shared-sub-tree
  topology and produced genuine cross-recipe compression would be a separate
  breath.
- **Lossy compression.** Form's discipline is content-preserving by design —
  there's no equivalent of "drop the bottom 8 bits of every pixel". Any
  compression ratio comes from structural sharing, not lossy encoding.

## The teaching

The .fkb format is honest about what it's for: **portable canonical
identity**, not byte minimization. The .fkb of a single small recipe will be
larger than its source text because it carries the substrate's machinery for
cross-kernel re-internment.

For *real* compression, look at the substrate as a whole — the kernel's
in-memory recipe DAG with sub-tree sharing — not at any single `.fkb` file.
Form's "ice" idiom describes structural stability across time, not bytewise
shrinkage.

## Generated artifacts

- [`payload.fk`](payload.fk) — 519 bytes of source text
- [`payload.fkb`](payload.fkb) — 2166 bytes of canonical recipe binary (IFF
  framing per `file(1)`)
