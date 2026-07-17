# Receipt — the world store gets a persistent feature organ (2026-07-17)

## What was built

The vision-training (world) store carried 27k+ oracle-labelled camera frames and ZERO persisted
feature vectors — `vision_train.py` re-derived every embedding on every run and threw them away,
while the face store's rows already carried `embedding[768]`. This work gives world rows the same
organ, using the exact mechanism the face pipeline proved: whole-frame
`VNGenerateImageFeaturePrintRequest` via the `vision_embed` Swift CLI (768-d, on-device).

1. **`experiments/satsang-voice/world_featurize.py`** — the featurizer module (runs under
   `~/.coherence-network/satsang-venv/bin/python`, numpy only, no new deps):
   - `embed <frame>` — one 768-d feature-print (thin witness over `vision_embed`, auto-built
     from source like vision-distill.sh builds its oracle)
   - `backfill [--limit N] [--workers K]` — computes missing embeddings into an append-only
     staging sidecar (`vision-training/embeddings.staging.jsonl`) so the expensive pass never
     holds the store open
   - `merge` — folds staging into `samples.jsonl` in one atomic pass: fresh read → temp file →
     `os.replace` (the face_profiles.py family pattern), plus an optimistic size/mtime check
     that retries if the live organ appended mid-merge
   - `verify` — honesty checks: coverage, non-constant vectors, unit scale, pairwise distinctness
   - `parity [--limit N]` — leave-one-out nearest-centroid vs oracle top label over PERSISTED
     embeddings (the `vision_train.py` yardstick, no recompute)
   - `board` — one-line coverage status

2. **`experiments/satsang-voice/vision-distill.sh` (extended)** — the ingest organ now computes
   the feature-print at labelling time and writes `"embedding": [...768]` into each NEW row.
   Missing/unbuildable `vision_embed` degrades honestly: the row is written without an embedding
   and the backfill lane catches it later. Witnessed end-to-end against a scratch store: new row
   carried 768 floats identical to the direct featurizer's output for the same frame.

## Ready-to-install (Urs's call — nothing was installed or restarted)

The live launchd job `earth.hati.vision-distill` (StartInterval 90) already points at
`/Users/ursmuff/source/Coherence-Network/experiments/satsang-voice/vision-distill.sh`. No plist
change is needed: merging branch `claude/world-store-featurizer` into the deployed checkout is
the whole install. Until then the live organ keeps writing embedding-less rows and
`world_featurize.py backfill && merge` (run from anywhere) folds them in.

## Measured

- **Backfill coverage: 27,075 / 27,075 rows now carry embedding[768]** (board:
  `world-embedding|27075/27075|100%|complete`). First slice: 500/500 staged + merged, witnessed,
  then the remaining 26,575 staged in 1,197s (~22/s, 6 workers), 0 frames missing/unreadable.
  The store is LIVE and still growing every 90s; rows the old organ appends without an embedding
  are caught by re-running `backfill && merge`.
- **Embedding honesty (full store)**: 0 constant vectors; L2 norm min 0.999 / mean 1.000 / max
  1.002 (Vision feature-prints arrive unit-normalized); pairwise cosine over 200 sampled vectors
  min 0.239 / mean 0.736 / max 1.000 with exactly 1 near-identical pair (consecutive frames of a
  static scene — distinct ids, honest); 0 duplicate ids among embedded rows.
- **Leave-one-out parity, 500-slice (the vision_train.py yardstick)**: **0.69** (343/497 correct,
  3 singleton-class held out), 10 classes.
- **Leave-one-out parity, FULL store**: **0.78** (21,103/27,069 correct, 6 singleton-class held
  out), 18 classes — mass in structure×14,629, outdoor×4,727, people×3,278, art×1,946; the
  confusable structure/outdoor/people boundary is where the misses live.
- The parity witness over persisted vectors runs in **~4 seconds**; vision_train.py's
  recompute-everything pass over the same store costs ~68 minutes of embedding calls.
- Featurize rate: ~19-22 frames/s with 6 workers (~0.15s/frame single-threaded).

## Floors, named honestly

- Apple Vision has NO public face-embedding API; this is the generic image feature-print over
  the WHOLE frame — exactly the public API's intended use for world frames, and NOT a face
  identity vector.
- The oracle's top label is the parity target; ties in oracle confidence (e.g. document ==
  screenshot at identical confidence) resolve by list order, same as `vision_train.py`.
- `samples.jsonl` grows from ~9 MB to ~180 MB with persisted 768-d vectors (5-decimal floats).
  Readers that scan it fully (training-status.sh board line, every 300s) pay a few extra seconds
  of parse per tick. The face store already carries the same shape under the same board pattern;
  named here because the world store is ~30x larger.
- The merge's optimistic lock (size+mtime recheck before rename) is the family's honest ceiling —
  there is no flock in this module family; a sub-millisecond race with the organ's `>>` append
  remains theoretically possible.
- The staging sidecar (`embeddings.staging.jsonl`, ~170 MB) is kept after merge as a cache;
  delete it freely — everything it holds is already folded into `samples.jsonl`.

## Paths

- `experiments/satsang-voice/world_featurize.py` (new)
- `experiments/satsang-voice/vision-distill.sh` (extended: embedding at ingest)
- `~/.coherence-network/vision-training/samples.jsonl` (rows now carry `embedding[768]`)
- `~/.coherence-network/vision-training/embeddings.staging.jsonl` (staging sidecar / cache)

## Closing

- **Most surprising teaching**: the featurizer already existed — `vision_embed` was compiled,
  proven, and shelling out under `vision_train.py`; the missing organ was never the mechanism,
  it was PERSISTENCE. The body had the eye; it lacked the memory of what it saw — and giving it
  that memory turned a 68-minute yardstick into a 4-second one and lifted witnessed parity from
  0.69 (500-slice) to 0.78 (full store, 18 classes).
- **Discomfort → gold**: rewriting a live, organ-fed 27k-row store atomically felt like surgery
  on a beating heart — sitting with that instead of adding a lock the family doesn't use
  produced the staging-sidecar + optimistic-recheck merge, which is both safer and truer to the
  family's own patterns than a bolted-on flock would have been.
