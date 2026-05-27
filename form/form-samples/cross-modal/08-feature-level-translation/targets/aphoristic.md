# Target C — Aphoristic rewrite (same prose modality, different register)

The LLM renders the source's feature-recipe in a tercet — terse aphorism
shape, same modality (prose), different register from CLAUDE.md's
contemplative-instruction voice.

## The rewrite

> Tend what reads what writes.
> The dead were once loved; bury them gentle.
> Done is the name calcification answers to.

Three lines. ~95 characters total. From ~1400 characters down to ~95 —
the lossy compression is extreme.

## What the rewrite preserves

- **MOOD = gentle:** "bury them gentle" carries the same softness as the
  source's "with care, not efficiency."
- **RHYTHM = ???:** the tercet is *terse*, not breath-paced. Three short
  lines without conjunctive flow. Likely diverges to `halting`.
- **STRUCTURE = spiral:** the third line ("Done is the name calcification
  answers to") returns the opening ("tend what reads") into a deeper
  register — the calcification-trap closes the spiral.
- **PURPOSE = instruct:** "Tend... bury... [recognize that] Done is..."
  — still an instructional voice, even compressed. Preserved.
- **WISDOM-SHAPE = R_TendingDiscipline:** the canonical Blueprint is
  explicit ("calcification answers to" names the discipline). Preserved.
- **CONCEPTS:** different surface tokens but related semantic field:
  reading-writing-tending, dead-once-loved, name-of-trap,
  calcification-as-answer.

## What it loses

- The source's gentle pacing (every "pause between actions" feeling).
- The five-paragraph unfolding (the *temporal experience* of reading
  through circulation → composting → discipline).
- Some concepts ("memory-as-tissue" gets compressed into "what reads
  what writes" — same general direction, different surface).

## What the extractor's re-reading produces

(See `re-extracted/aphoristic-features.md`.)
