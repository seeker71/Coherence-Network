---
idea_id: agent-cli
status: active
source:
  - file: form/form-stdlib/rag-key.fk
    symbols: [str-bytes, rk-text-key]
  - file: form/form-stdlib/rag-freshness.fk
    symbols: [rf-heal-set, rf-orphans, rf-fresh?, rf-stale?]
  - file: form/form-stdlib/rag-adaptive-k.fk
    symbols: [rak-k, rak-knee-loop]
  - file: form/form-stdlib/rag-heal.fk
    symbols: [rh-file-key, rh-fresh?, rh-cell-stale?]
  - file: form/form-stdlib/rag-retrieve.fk
    symbols: [rag-topk, rag-dist]
  - file: scripts/form_cli_rag.py
    symbols: [content_key, freshness, heal, retrieve]
  - file: scripts/substrate_post_merge_hook.sh
    symbols: [rag heal step]
requirements:
  - "The content key is a Form recipe (adler32 over source bytes), four-way + fkwu — not a host hash, not mtime"
  - "Freshness is decided by a four-way Form recipe over (id key) pairs — missing, drifted, orphaned"
  - "Retrieval depth is a four-way Form recipe (knee-cut k), not a fixed k=5"
  - "The heal loop runs as a Form recipe on the kernel via host-io (rag-heal.fk), zero Python in that lane"
  - "Self-heal re-embeds only the delta (missing + drifted) and composts orphans; no full rebuild unless the index is absent"
  - "ask heals the stale delta before retrieving, so a fresh file is answerable without a manual index step"
  - "the post-merge hook heals the index beside substrate ingest"
done_when:
  - "rag-key band crosses four-way (Go/Rust/TS/fkwu) via form/validate.sh → 7"
  - "rag-freshness band crosses four-way → 63"
  - "rag-adaptive-k band crosses four-way → 15"
  - "rag-heal keys a real file and senses fresh-vs-drift on the kernel with no Python (Go leg → 7)"
  - "form-cli ask \"what is form shell?\" retrieves shell-grammar.fk / fsh-main.fk after a heal"
  - 'file_exists("form/form-stdlib/rag-key.fk")'
  - 'file_exists("form/form-stdlib/rag-heal.fk")'
  - 'file_exists("form/form-stdlib/tests/rag-freshness-band.fk")'
  - 'file_exists("form/form-stdlib/tests/rag-adaptive-k-band.fk")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/rag-key.fk form-stdlib/tests/rag-key-band.fk && ./validate.sh form-stdlib/rag-freshness.fk form-stdlib/tests/rag-freshness-band.fk && ./validate.sh form-stdlib/rag-adaptive-k.fk form-stdlib/tests/rag-adaptive-k-band.fk"
constraints:
  - "the key, freshness, adaptive-k, and ranking are Form recipes (four-way + fkwu); the heal loop is Form on the kernel (host-io, Go-kernel + fkwu-native-exe)"
  - "Python (form_cli_rag.py) is the RETIRING bootstrap bridge for the default serving path; its content_key/freshness/rak_k/rag_l1 are labeled mirrors of the canonical Form recipes"
  - "content key is content-addressed (adler32 of source bytes), never mtime"
  - "no new parallel store — the index remains one jsonl file until it rides the substrate natively"
  - "host-io is non-deterministic, outside the four-way output floor by the kernel's own design — the heal lane is single-runtime, the embedder is a local model-door crossing"
---

> **Parent idea**: [agent-cli](../ideas/agent-cli.md)
> **North star**: [`form-cli-north-star.form`](../docs/coherence-substrate/form-cli-north-star.form) — `rag-retrieve.fk` is the memory organ; this gives it freshness.
> **Source**: [`rag-retrieve.fk`](../form/form-stdlib/rag-retrieve.fk) | [`form_cli_rag.py`](../scripts/form_cli_rag.py) | [`substrate_post_merge_hook.sh`](../scripts/substrate_post_merge_hook.sh)

# Spec: form-cli self-healing memory

## Purpose

The form-cli's memory organ (`rag-retrieve.fk` over a local embedding index) could
recall the body but had no sense of when the index drifted from the body. A frozen
index made the local lane answer "not grounded" for content that was present on disk
but absent from the cache, escalating to a rented mind for an answer the body already
held. This makes the index a proper **water** layer: derived from the body, healed by
content-addressed freshness, expanding to absorb new tissue on its own.

## Requirements

- [ ] **R1 — Form content key**: the freshness key is a Form recipe — `rag-key.fk`'s
  `rk-text-key` = adler32 over the byte list, four-way + fkwu (band → 7). Every index
  entry stores it alongside `(id, kind, snippet, vec)`. No host hash, no mtime.
- [ ] **R2 — Form freshness decision**: `rag-freshness.fk` computes, over two `(id key)`
  lists (body, index): the **heal-set** (ids missing from the index or whose key
  drifted), the **orphans** (index ids whose source is gone), and **fresh?** (heal-set
  and orphans both empty). Pure list/string arithmetic — four-way.
- [ ] **R3 — delta heal**: the carrier re-embeds only the heal-set and drops orphans;
  a full embed runs only when the index file is absent.
- [ ] **R4 — lazy heal on ask**: `ask` senses freshness and heals the stale delta before
  retrieving, so a just-written file is answerable with no manual `index` step.
- [ ] **R5 — adaptive depth**: `rag-adaptive-k.fk` chooses retrieval depth by the
  distance knee within `[k_min, k_max]`, replacing the fixed `k=5`.
- [ ] **R6 — merge-time heal**: `substrate_post_merge_hook.sh` heals the index beside the
  substrate ingest so a merge keeps the cache current without a manual step.
- [ ] **R7 — Form heal on the kernel**: `rag-heal.fk` keys a file through the kernel's
  host-io (`rh-file-key` = `host-read` → `rk-text-key`) and senses fresh-vs-drift
  (`rh-cell-stale?` over `rf-stale?`) — the heal lane in Form, run on the kernel, no
  Python. Host-io is non-deterministic, so this is Go-kernel + fkwu-native-exe witnessed,
  outside the four-way output floor by the kernel's own design.

## Data Model

```yaml
RagEntry:
  id: string          # repo-relative path (or path#chunk once chunked)
  kind: string        # recipe | spec | concept | substrate | local
  key: string         # content hash of source bytes — the freshness coordinate
  snippet: string     # embedded text (purpose-line + structural signature)
  vec: list[int]      # quantized embedding (0..1000)
```

## Files to Create/Modify

- `form/form-stdlib/rag-key.fk` — Form content key (adler32 over bytes), BML (new)
- `form/form-stdlib/tests/rag-key-band.fk` — four-way band → 7 (new)
- `form/form-stdlib/rag-freshness.fk` — freshness delta recipe (new)
- `form/form-stdlib/tests/rag-freshness-band.fk` — four-way band → 63 (new)
- `form/form-stdlib/rag-adaptive-k.fk` — knee-cut depth recipe (new)
- `form/form-stdlib/tests/rag-adaptive-k-band.fk` — four-way band → 15 (new)
- `form/form-stdlib/rag-heal.fk` — host-io heal lane on the kernel, no Python (new)
- `scripts/form_cli_rag.py` — RETIRING bridge: content_key mirrors `rk-text-key`
  (adler32), delta heal, adaptive-k retrieve, fuller snippet, lazy heal on `ask` (modify)
- `scripts/substrate_post_merge_hook.sh` — rag heal step (modify)
- `form/fourth-arm-bands.txt` — register rag-key/rag-freshness/rag-adaptive-k bands (modify)

## Acceptance Tests

- `form/validate.sh form-stdlib/rag-freshness.fk form-stdlib/tests/rag-freshness-band.fk` → 63, four-way
- `form/validate.sh form-stdlib/rag-adaptive-k.fk form-stdlib/tests/rag-adaptive-k-band.fk` → 15, four-way
- `form-cli ask "what is form shell?"` cites `shell-grammar.fk` / `fsh-main.fk`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/rag-key.fk form-stdlib/tests/rag-key-band.fk   # -> 7, fourth arm four-way, 0 divergent
cd form && ./validate.sh form-stdlib/rag-freshness.fk form-stdlib/tests/rag-freshness-band.fk   # -> 63, four-way
cd form && ./validate.sh form-stdlib/rag-adaptive-k.fk form-stdlib/tests/rag-adaptive-k-band.fk # -> 15, four-way
python3 scripts/validate_spec_quality.py --file specs/form-cli-self-healing-memory.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_20260624_form_native_rag_memory.json
```

## North Star and Honest Floor

The destination is the whole loop on fkwu in Form — no Python/Go/TS/Rust/shell in the
runtime path, ending in the standard receipt (c-bootstrap fkwu form-cli observed on
mac/windows/android, toolchain-free). This step lands the **logic** there and opens the
host-io lane:

- **Crossed (four-way + fkwu):** the content key (`rag-key.fk` → 7), freshness delta
  (`rag-freshness.fk` → 63), retrieval depth (`rag-adaptive-k.fk` → 15), ranking
  (`rag-retrieve.fk` → 31). The decisions are Form, proven on all four kernels.
- **Kernel-run, no Python (Go-kernel + fkwu-native-exe):** the heal lane (`rag-heal.fk`)
  keys a real file via host-io and senses drift — witnessed Go leg → 7. host-io is
  single-runtime and non-deterministic, outside the four-way output floor by design.
- **Still bridge / named gaps:** the default serving path runs through the Python bridge
  while the native lane lands; the embedder is a local model-door crossing (ledgered by
  `form-cli-membrane.fk`); enumerating brand-new files needs a directory-list host-io op
  the kernel does not yet carry (drift + orphan heal are already full Form over
  host-read); the platform receipt (mac/windows/android, c-bootstrap, toolchain-free) is
  **pending**, not observed.

## Out of Scope (next breaths on the same path)

- A Form jsonl/index codec + the embed/write loop in `rag-heal.fk`, retiring the Python
  serving path entirely.
- A directory-list host-io op (or a committed body manifest read via `host-read`) so the
  native lane absorbs brand-new files without `find`/`ls`.
- Making index entries first-class substrate cells (one engine, no parallel jsonl).

## Risks and Assumptions

- The Python `content_key` is a mirror of `rk-text-key` (zlib.adler32 == the recipe's
  algorithm); the kernel recipe is the proof. ASCII-exact with the Form file key.
- Lazy heal adds embedding latency on the first `ask` after the body changes. Mitigated
  by delta-only heal (typically a handful of files) and the merge-time heal keeping the
  steady state fresh.

## Known Gaps

- Follow-up task: a Form jsonl/index codec + embed/write loop in `rag-heal.fk` to retire
  the Python serving path (`ask`/`search`) entirely.
- Follow-up task: a directory-list host-io op (or a committed body manifest read via
  `host-read`) so the native lane absorbs brand-new files; drift + orphan heal are already
  full Form, so this gap is only the new-file enumeration.
- Follow-up task: lift the embedder (ollama model-door crossing) toward a Form recipe.
- Follow-up task: earn the standard receipt (c-bootstrap fkwu form-cli observed on
  mac/windows/android, toolchain-free) — pending, not observed.
