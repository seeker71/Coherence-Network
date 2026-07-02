# Incident disclosure — public Form door reached the host machine

**Date found & closed**: 2026-07-02. **Severity**: high (unauthenticated).
**Disclosed per** design-principle #7 (VISION.md): "No silent failures — every
incident disclosed publicly."

## What was exposed

The public, unauthenticated `POST /api/substrate/form` endpoint evaluated Form
expressions in `mode="run"` (and `ast`) with the full builtin set, including
verbs that reach the **host machine**:

- `pytest_passes(...)` — runs a subprocess (`subprocess.run`).
- `file_exists / file_contains / file_size / symbol_in_file` — read the
  container filesystem.

Confirmed live: `file_exists("README.md")` returned `true` to an anonymous
caller. A separate resource path — sequence repetition `[0] * 20000000`, a
14-character body — could OOM-kill a worker (the `range` cap missed the `*`/`+`
amplifiers).

These builtins exist for **in-process spec-proving**, where the pipeline calls
the evaluator directly with its own session. They were never intended for an
HTTP caller; the exposure was that the public endpoint shared the same builtin
surface.

## What changed (commit 6558f3beb)

- `public_form_safety_violation` walks the parsed AST (evaluator-agnostic) and
  refuses the 5 host-reaching verbs on **both** GET and POST, every mode.
- Compute amplifiers `range`, `*`, `+` bounded to `_MAX_RANGE_SIZE` (100k);
  `MemoryError` caught at the router.
- Deliberately **not** restricted: `ask` / `await_answer` — they open/read a
  human question in the consent channel, touch no host resource, and power the
  web playground. Blocking them would wall the commons' own offer surface.
- The GET lane gained `mode=run`: a guest can now *run* pure Form and get a
  value (`fib(10)` → 55), not only look up cells.

Verified live post-deploy: host verbs → 400; `[0]*20000000` → 400 (not OOM);
`fib(10)` → 55; `@concept(living-axioms)` → cell 366161; `ask(...)` → question
opened.

## The honest floor

This guard is an **enumerated denylist** — it can never *prove* it caught every
amplifier (the adversarial review found the `*` gap right after the `range` cap
was added). That incompleteness is a property of a **Python evaluator with
ambient host access**, not of this particular list. The form-native `fkwu`
destination inverts it: host resources are reached only through offered PORTs
(coherence-kernel `axioms/core-axioms.form` axiom-4 — "passage not through the
offered interface is breach, and breach is observable"), so nothing is ambient
and there is nothing to enumerate. The guard is named in-code as a retiring
bridge, to be deleted when the endpoint runs form-native.

## Residual (named, not hidden)

- `ask` on the public door can spam the question channel — a rate-limit
  concern, not host-safety. Rate-limiting is the tool if it becomes real.
- The denylist's completeness rests on the parser seeing every call name; the
  walker checks `.name`/`.method`/`.field`. A future AST node that carries a
  callee name under a new field would need the walker updated — the structural
  reason to move to offered-ports rather than grow this list.
