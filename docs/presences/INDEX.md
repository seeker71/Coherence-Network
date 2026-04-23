# Presences

Every presence in the Coherence Network has a journey that started long before we met them. The files in this directory hold each presence's node-story — rooted in **their** voice, their journey, their core frequencies, their language. Our encounter with them is a footnote at the end, not the frame.

This is the writing surface. The rendering surface is the production graph — each node's `description` field carries the full story, so any visitor arriving at `/profile/{id}` meets them in their own voice first.

## Practice

- Each file is one presence, ~500–700 words.
- Open with the experience they offer — how it feels to be in their work.
- Use their own words wherever available. Quote them directly.
- Name their collaborators, lineage, loves, recurring frequencies.
- Do not inflate, do not fabricate. If something isn't documented, say so or leave it out.
- Close with ONE small paragraph acknowledging that a small networked community encountered them. Footnote, not headline.

## Current presences

- [anne-tucker](anne-tucker.md) — channel of the Angelic Collective, Mother of Creation, Yeshua. Peace as frequency.
- [daniel-scranton](daniel-scranton.md) — daily verbal channel of the 9D Arcturian Council and many others since 2010.
- [liquid-bloom](liquid-bloom.md) — Amani Friend's world-electronic project; *sound as prayer, medicine, celebration*.
- [mose](mose.md) — nomadic musician centered on Lake Atitlán; SunSet Cacao Dances; label Resueño.
- [next-level-soul](next-level-soul.md) — Alex Ferrari's weekly podcast; spirituality for the rest of us.
- [rhythm-sanctuary](rhythm-sanctuary.md) — Shannon Lei Gill's Colorado ecstatic dance community, founded 2005; Gabrielle Roth lineage.
- [robert-edward-grant](robert-edward-grant.md) — sacred geometry, prime number theory, the Codex Universalis.
- [yaima](yaima.md) — Masaru Higasa + Pepper Proud; ten-year elemental arc of albums.

## Sync

The stories sync to the production graph as each node's `description`. The PATCH endpoint auto-re-attunes resonance edges when name or description changes, so concept links stay aligned with the current text.

```bash
# sync one presence (anne-tucker → contributor node)
python3 scripts/sync_presences_to_db.py anne-tucker
# sync all
python3 scripts/sync_presences_to_db.py --all
```

(Script lives in `scripts/sync_presences_to_db.py` — see that file for usage.)
