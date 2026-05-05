// /one-sheet — structural metadata only.
//
// All user-facing strings (chrome + 23 word teachings × 3 voices) live in
// web/messages/{lang}.json under the `oneSheet` key, served via
// createTranslator(locale) at render time. The structural shape of each
// section — its stable id, optional visual, and outbound cross-links —
// lives in `_locales/types.ts` (SECTIONS).
//
// To add a 24th section: append a SectionMeta to SECTIONS in types.ts AND
// add a `sections.{newId}` entry to every messages/{lang}.json under the
// oneSheet block.

export { SECTIONS, type SectionMeta, type CrossLink } from "./_locales/types";
