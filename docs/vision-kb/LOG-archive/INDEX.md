# LOG Archive

Monthly archives of `docs/vision-kb/LOG.md`. The working log holds the most recent ~30 days; older entries rotate here when the working file's size makes parallel breaths fight at its top.

| Month | File | Entries | Range |
|-------|------|---------|-------|
| 2026-05 | [`2026-05.md`](./2026-05.md) | ~71 | 2026-05-05 → 2026-05-23 |
| 2026-04 | [`2026-04.md`](./2026-04.md) | 36 | 2026-04-13 → 2026-04-29 |

## Rotation rhythm

When the working `LOG.md` grows past ~1500 lines or ~30 days of entries, the older half moves into a month-stamped file here. The split is by entry-day boundary; the working log keeps the recent burst (the entries the next breath is most likely to reference).

## Why this shape

The change-log served two functions: human navigation ("what landed recently?") and durable record. As the body's tempo accelerated, the working file grew past 3600 lines / 430KB / 163 entries, and concurrent breaths started competing for the same lines at the top. Splitting by month preserves the newest-at-top human-readable rhythm in a smaller working file, lets git history carry the complete record, and gives future cells a natural place to look ("the archive lives next to the log").

Scripts that consume vision-kb content already exclude `LOG.md` from substrate ingest (`scripts/coh_substrate.py`); the same exclusion now covers `LOG-archive/`.
