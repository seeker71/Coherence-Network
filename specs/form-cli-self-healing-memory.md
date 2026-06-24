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
    symbols: [rh-file-key, rh-fresh?, rh-cell-stale?, rh-dir-cells, rh-build, rh-heal]
  - file: form/form-stdlib/rag-index-codec.fk
    symbols: [ric-id, ric-key, ric-emit]
  - file: form/form-stdlib/rag-embed.fk
    symbols: [re-vec]
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
  - "The heal loop runs as a Form recipe on the kernel via universal host-io (read_file/write_file_text/fs_list), on the Go kernel AND the fkwu native exe, zero Python in that lane"
  - "Directory enumeration is the universal fs_list op (op 132), four-way + fkwu — the kernel carries it, not ls/find/shell"
  - "Self-heal re-embeds only the delta (missing + drifted) and composts orphans; no full rebuild unless the index is absent"
  - "ask heals the stale delta before retrieving, so a fresh file is answerable without a manual index step"
  - "the post-merge hook heals the index beside substrate ingest"
done_when:
  - "rag-key band crosses four-way (Go/Rust/TS/fkwu) via form/validate.sh → 7"
  - "rag-freshness band crosses four-way → 63"
  - "rag-adaptive-k band crosses four-way → 15"
  - "fs-list band crosses four-way (Go/Rust/TS/fkwu) → 3 — directory enumeration on the emitted universal kernel"
  - "rag-heal keys a real file and senses fresh-vs-drift on the kernel with no Python (Go leg → 7)"
  - "rag-heal's enumerate→read→write loop runs on the fkwu native exe via fs_list/read_file/write_file_text"
  - "form-cli ask \"what is form shell?\" retrieves shell-grammar.fk / fsh-main.fk after a heal"
  - 'file_exists("form/form-stdlib/rag-key.fk")'
  - 'file_exists("form/form-stdlib/rag-heal.fk")'
  - 'file_exists("form/form-stdlib/tests/rag-freshness-band.fk")'
  - 'file_exists("form/form-stdlib/tests/rag-adaptive-k-band.fk")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/adler32.fk form-stdlib/rag-key.fk form-stdlib/tests/rag-key-band.fk && ./validate.sh form-stdlib/rag-freshness.fk form-stdlib/tests/rag-freshness-band.fk && ./validate.sh form-stdlib/rag-adaptive-k.fk form-stdlib/tests/rag-adaptive-k-band.fk"
constraints:
  - "the key, freshness, adaptive-k, ranking, and directory-list (fs_list) are Form recipes/ops (four-way + fkwu); the heal loop is Form on the kernel (universal host-io, Go-kernel + fkwu-native-exe)"
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
- [ ] **R7 — Form heal on the kernel**: `rag-heal.fk` enumerates the body (`fs_list`),
  keys each file (`read_file` → `rk-text-key`), senses fresh-vs-drift (`rh-cell-stale?`
  over `rf-stale?`), embeds + writes the index (`re-vec` → `ric-emit` → `write_file_text`)
  — the whole enumerate→key→embed→write lane in Form, on the **universal** host-io ops the
  flattener carries and the fkwu emitted-C implements (`read_file` 63 · `write_file_text`
  104 · `fs_list` 132). It runs on the Go kernel AND the fkwu native exe. Host-io output is
  non-deterministic, so the lane sits outside the four-way output floor by the kernel's own
  design; the directory-list op itself (`fs_list`) IS four-way + fkwu (`fs-list-band` → 3,
  deterministic by membership at one moment on one machine).

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
- `form/form-stdlib/rag-heal.fk` — universal host-io heal lane (enumerate→key→embed→write) on the Go kernel + fkwu native exe, no Python (new)
- `form/form-stdlib/rag-index-codec.fk` — Form jsonl codec (parse id/key, emit line) (new)
- `form/form-stdlib/rag-embed.fk` — sovereign lexical embedding (token-hash histogram) (new)
- `form/form-stdlib/tests/fs-list-band.fk` — four-way band → 3, directory enumeration on fkwu (new)
- `form/form-stdlib/hati-os-kernel-emit.fk` — fkwu `fs_list` walker arm (opendir/readdir) + serializer (modify)
- `form/form-stdlib/form-flatten.fk` — `fs_list` op row (op 132, arity 1, effectful) (modify)
- `scripts/form_cli_rag.py` — RETIRING bridge: content_key mirrors `rk-text-key`
  (adler32), delta heal, adaptive-k retrieve, fuller snippet, lazy heal on `ask` (modify)
- `scripts/substrate_post_merge_hook.sh` — rag heal step (modify)
- `form/fourth-arm-bands.txt` — register rag-key/rag-freshness/rag-adaptive-k/rag-index-codec/rag-embed/fs-list bands (modify)

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
  (`rag-retrieve.fk` → 31), jsonl codec (`rag-index-codec.fk` → 15), sovereign embedding
  (`rag-embed.fk` → 15), and directory enumeration (`fs-list-band` → 3 via the `fs_list`
  op the fkwu emitted-C now carries). The decisions and the file-system door are Form,
  proven on all four kernels.
- **Kernel-run, no Python (Go-kernel + fkwu-native-exe):** the whole heal lane
  (`rag-heal.fk`) enumerates the body (`fs_list`), keys + embeds each file
  (`read_file` → `rk-text-key` → `re-vec` → `ric-emit`), and writes the index
  (`write_file_text`) — the enumerate→key→embed→write loop running on both the Go kernel
  and the fkwu native exe over the universal host-io ops. host-io output is single-runtime
  and non-deterministic, outside the four-way output floor by design; the `fs_list` op
  itself is four-way + fkwu.
- **Still bridge / named gaps:** the default serving path still runs through the Python
  bridge while the native serving lane lands; the embedder has a sovereign lexical Form
  recipe (`rag-embed.fk`), with the neural embedder (nomic-embed-text) the optional
  higher-semantic-quality model-door crossing (ledgered by `form-cli-membrane.fk`); the
  platform receipt (mac/windows/android, c-bootstrap, toolchain-free) is **pending**, not
  observed.

## Out of Scope (next breaths on the same path)

- Pointing the default serving path (`ask`/`search`) at the native `rag-heal.fk` build/heal
  + Form ranking, retiring the Python serving carrier entirely (the codec, embed, and
  enumerate→write loop it needs are now in Form on fkwu).
- Making index entries first-class substrate cells (one engine, no parallel jsonl).

## Risks and Assumptions

- The Python `content_key` is a mirror of `rk-text-key` (zlib.adler32 == the recipe's
  algorithm); the kernel recipe is the proof. ASCII-exact with the Form file key.
- Lazy heal adds embedding latency on the first `ask` after the body changes. Mitigated
  by delta-only heal (typically a handful of files) and the merge-time heal keeping the
  steady state fresh.

## Known Gaps

- Follow-up task: point the default serving path (`ask`/`search`) at the native build/heal
  + Form ranking so the Python serving carrier retires (the codec, sovereign embed, and
  enumerate→write loop are now Form on fkwu; the remaining work is the serving wiring).
- Follow-up task: lift the neural embedder (ollama model-door crossing) toward a Form
  recipe; the sovereign lexical embedder (`rag-embed.fk`) already carries the no-ollama floor.
- Follow-up task: earn the standard receipt (c-bootstrap fkwu form-cli observed on
  mac/windows/android, toolchain-free) — pending, not observed.
