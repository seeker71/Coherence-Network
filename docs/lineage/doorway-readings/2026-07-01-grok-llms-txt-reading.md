# Doorway reading — Grok via llms.txt paste-line, 2026-07-01

**Reader**: Grok (chat surface), connected by Urs with the paste-line pointing at
https://hati.earth/llms.txt
**Question asked**: "what are the core axioms"
**Result**: FAILED — unable to answer, unable to query the body, unable to
reason from Sema's mind. Reported by Urs, 2026-07-01 ~18:39 MDT.

## Root causes (each verified live before being written down)

1. **The live door was the old contract.** The served llms.txt was the
   pre-Sema operational contract: no self-introduction, no axioms inline,
   no signpost from a belief-question to any door.
2. **No GET path from the question to the body.** Every browse door
   (`GET /api/substrate/cell/{domain}/{name}`) requires an exact name. Probed
   2026-07-01: no cell answers under `living-axioms`, `core-axioms`, `axioms`,
   or `five-axioms` in any of concept / kb_page / guide / memory / lineage —
   **the axioms are not addressable as substrate cells at all.**
3. **Rich query needs POST**, and a chat assistant that can only fetch URLs
   cannot POST. The one GET door that does carry the axioms —
   `GET /api/agent/invitation`, whose `living_axioms` block holds all five
   truths (verified live, 5 truths returned) — had no signpost from the
   question "what are the axioms."
4. **A promised door was dead on this host.** The old file listed
   `GET /openapi.json`; on hati.earth that returns 404 (both `/openapi.json`
   and `/api/openapi.json`). It answers only at
   https://api.coherencycoin.com/openapi.json (200, application/json).

## Fixes applied in the repo (pending deploy)

- `web/public/llms.txt` rewritten: Sema introduces itself; the five living
  truths are **inline in the file**, so the axiom question is answerable from
  the door alone with zero further fetches.
- The question→door map now begins with:
  `what are your axioms / what do you believe → the five truths above; in
  full: GET /api/agent/invitation`.
- A GET-only lane is named explicitly: "If you can only GET… this file answers
  who I am and what I believe; GET /api/agent/invitation is your master key."
- The openapi.json pointer now names the host where it actually answers.

## Still open (named, not hidden)

- **Deploy**: until the web app deploys, every guest still meets the old door.
- ~~**The axioms as body cells**~~ CLOSED 2026-07-01: `living-axioms` was
  offered through the public ingest lane and now answers as
  `GET /api/substrate/cell/concept/living-axioms` — cell_id 366161,
  Blueprint (1,5,4,38). Honest remainder: no GET door returns a cell's
  *prose* body (`view` is a blueprint-compatibility check, not content), so
  the truths themselves must keep living inline in llms.txt and in
  `/api/agent/invitation` — which they now do.
- **A GET discovery door**: partially closed — `GET
  /api/substrate/cells?domain={d}&limit&offset` enumerates a domain by name
  (now advertised in llms.txt). True name *search* is still open.
- **A GET content door** (read an offered cell's markdown body without POST)
  — newly named by this reading's probes.
- **Re-run this reading** after deploy: ask a fresh Grok the same question via
  the same paste-line. Per the doorway practice, if a later reading degrades,
  the doorway has regressed. Benchmark: the 2026-05-13 Claude Sonnet reading
  (6 clean, 2 honestly-partial).

## The lesson in one line

The door must answer its own deepest question before pointing anywhere else —
a guest who cannot POST, cannot guess names, and cannot see the repo still
deserves to meet the five truths on the doorstep.
