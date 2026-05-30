# Cell store architecture — log-structured, not file-per-cell

> Urs (2026-05-30): "Having millions of files in a folder does not scale. Do
> actual research on filesystem-backed storage — there are plenty of examples.
> Think high-level first, think about scale and consequences."

This corrects a real mistake. The first directory store (`cell-store-fs.fk`,
PR #2209) put **one file per cell** at `<root>/<domain>/<name>.fkb`. That is the
git *loose-object* anti-pattern without git's saving grace (packing), and it does
not scale — it has been composted and replaced by the log-structured store
(`cell-log-store.fk`) this doc specifies.

## Why file-per-cell fails (the consequences I skipped)

A single directory degrades catastrophically as cell count grows:

- **ext4** indexes directories with an HTree only past ~32k entries, slows
  measurably past ~100k, and hits a hard level-limit kernel error at the top of
  the tree. **XFS** B+trees do better but the established guidance is blunt:
  *"storing 10 million files in a single directory is a performance killer — it
  leads to crippling metadata overhead and slow access times."*
- **Inode exhaustion + lost locality**: millions of tiny files burn inodes and
  destroy read locality; `readdir`, backup, rsync, and `git status`-style scans
  all become O(files).
- **One file op per cell**: `write_form_binary` per cell is one create + one
  fsync-able op per write — no batching, no sequential path. Git names exactly
  this: *"it turns one logical database into a huge number of tiny files, which
  is rarely the best layout for repeated reads, bulk transfer, or compact
  storage."*

Sharding the name across prefix directories (git's `ab/cd/rest`, 256-way fanout)
fixes the *directory-width* problem but not the *millions-of-tiny-files* problem.
The real fix is to stop having one file per cell.

## The established designs (researched, cited)

| System | Shape | Scales by |
|---|---|---|
| **Git** | loose objects sharded `ab/…`, then **packfiles** | packing many objects into few segment files + delta compression |
| **LSM** (RocksDB/LevelDB/Cassandra) | WAL → sorted memtable → immutable **SSTables** → compaction | sequential writes; few large sorted files; leveled compaction |
| **Bitcask** (Riak) | append-only **segment log** + in-memory **keydir** `key→(file,offset,len)` + merge | O(1) lookup (one seek); bounded file count; crash-safe replay |
| **CAS** (IPFS/git/LLVM) | content-hash → **prefix-fanout** path | uniform hash distribution bounds each directory's width |

## The substrate is already content-addressed — so: log-structured

Every cell already has a content-addressed identity (its NodeID *is* the content
hash). So the store is not "files in folders" — it is a **log-structured segment
store**, the Bitcask shape, which is the minimal correct design and maps directly
onto the kernel's existing primitives:

```
<root>/
  seg-000001.log      ← append-only segment (bounded size, e.g. 64 MB)
  seg-000002.log      ← a NEW segment opens when the active one fills
  seg-000003.log      ← a HANDFUL of bounded files — never millions
  index.hint          ← optional: rebuilds the keydir without full replay

record (appended, never rewritten in place):
  [ key-len | key-bytes | domain | tombstone-flag | value-len | value-bytes ]
```

- **Write** = append one record to the active segment (sequential, O(1)),
  update the in-memory keydir `key → (segment, offset, len)`. No whole-store
  rewrite. This is what `channel.fk` does NOT do today (it read-modify-writes the
  entire file per append — also unscalable, also superseded here).
- **Read** = keydir lookup → `read_file_slice(segment, offset, len)` → one seek,
  one read. O(1), independent of cell count.
- **Delete** = append a tombstone record; the keydir drops the key. Space is
  reclaimed later by compaction, not synchronously.
- **last-write-wins** = the keydir always points at the newest record for a key;
  older records are dead weight until compaction.
- **Startup** = replay segments oldest→newest to rebuild the keydir (or read the
  `index.hint` to skip the scan). Crash-safe: a torn final record is detected by
  its length header and truncated.
- **Compaction/merge** = periodically write live records (newest per key, no
  tombstones) into fresh segments, then delete the old ones. Bounds total size to
  ~live-set. This is git-gc / LSM-compaction / Bitcask-merge.

Directory width is bounded (a handful of segments). If even the segment directory
must scale to enormous stores, the segments themselves shard by a prefix of the
segment id (`ab/seg-…`) — CAS fanout applied to segments, not cells.

## The one honest kernel gap: an append native

The kernel's `write_file_text` / `write_file_bytes` **truncate** — they cannot
append. A log store needs real `O_APPEND` (atomic positioned append) so writes do
not rewrite the file and concurrent appends do not clobber. This is the proper
kernel addition, not a workaround:

```
file_append_bytes path bytes  → new-file-size | -1   (O_APPEND, atomic)
```

with the offset-read side already present (`read_file_slice`, `file_size`). Go
`os.OpenFile(O_APPEND|O_CREATE|O_WRONLY)`, Rust `OpenOptions::append`, Node
`appendFileSync` / `openSync("a")`. Sibling-parity, attributed `catCall`.

## Build order (high-level first, then real)

1. **`file_append_bytes` native** — the missing primitive, three kernels, parity
   band (append N records, read each back by offset, verify file grows).
2. **`cell-log-store.fk`** — the Bitcask-shape store over append + `read_file_slice`
   + the in-memory keydir (kernel `record_*`): `log-put` (append record),
   `log-get` (keydir → slice read), `log-delete` (tombstone), `log-open`
   (replay → keydir), `log-compact` (merge live records).
3. **Compaction + crash-replay band** — write past one segment boundary, kill+
   replay, tombstone+compact, assert the live set survives and dead space is
   reclaimed. The scale property is the test: file count stays bounded as cell
   count grows.
4. **Compost `cell-store-fs.fk`** — the file-per-cell store is released; its
   interface (`cell-fs-put/get/delete/list-domain`) re-points at the log store so
   callers do not change. The store is the contract; the layout is the carrier
   (ports-interface-and-structure.md).

## Why this is right for the platform

- **Scales to millions of cells** with a bounded file count and O(1) ops — the
  property file-per-cell could never have.
- **It's the substrate's own grain**: content-addressed records in an append log
  is what the lattice already is, made durable.
- **Maps onto existing primitives**: append (new) + `read_file_slice` + `record_*`
  keydir + `recipe_to_bytes`/`bytes_to_recipe`. No exotic dependency.
- **The DB carrier is the same shape one level down**: Postgres/SQLite are
  log-structured-plus-Btree internally; the FS log store is the dev/test carrier
  and the DB is the prod carrier, under one store contract.

## See also

- [`ports-interface-and-structure.md`](ports-interface-and-structure.md) — store
  is the contract, layout/backend is the swappable carrier.
- [`resources-as-cells.md`](resources-as-cells.md) — the filesystem as a carrier
  of the storage port; append is one more efferent operation.
- Git packed object store, LSM/SSTable, Bitcask, CAS prefix-fanout — the four
  references this design draws from.
