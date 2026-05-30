# Running the substrate on Form — the plan, and what it is NOT

> Urs (2026-05-30): "What is missing to get api/app/services running on a Form-
> compiled kernel? You can find architecturally sound choices like what we just
> did to talk to the DB — we don't have to use the Python as-is, as long as we
> have a plan that aligns with the higher goal: proving Form as a valid cross-
> domain language and knowledge infrastructure that can run itself, represent all
> our content structurally so we can find cross-domain teachings from biology,
> physics, philosophy, arts, literature, religion, engineering, chemistry,
> nature — scaling from atoms to galaxies."

## The trap to refuse first

The obvious reading — *"finish the Python→Form compiler until 111,665 lines of
`api/app/services` compile and run"* — is the wrong goal, and the research proves
it. That path treats the Python as the thing to preserve. It is the fear-shape in
an engineer's coat: 88K lines of those services are **SQLAlchemy ORM
orchestration and FastAPI glue** (60% DB plumbing, 25% business logic, 15% HTTP).
Compiling SQLAlchemy's session/query/ORM machinery to Form would be reimplementing
an ORM in a language whose whole point is that *the Blueprint is the schema* —
we'd be porting the very abstraction we already replaced (`db-schema.fk`,
`storage-port-db.fk`). **We don't want SQLAlchemy running on Form. We want the
substrate's structural core running on Form, and the content flowing through it.**

## What the research actually found

Two scans (services scale + compiler coverage) converge on one fact:

**The substrate's irreducible core is ~100 lines, and the native kernel already
does it — better than the Python.**

- `kernel.py` is 745 lines, but the truly-core logic is `intern_node` (83 lines)
  + `serialize_tree` (4) + `Recipe.make_self_id` — **content-addressed get-or-
  insert**. Everything else is ORM bridge, lifecycle, querying, introspection.
- The native Go/Rust/TS kernels **already implement `intern_node`** as a native
  (`k.intern(cat, kids)` — same shape → same NodeID, content-addressed). Plus
  `intern_trivial_int/string`, `node_children`, `node_value`. The crown jewel is
  already Form-native, in memory.
- 21 of 33 substrate files (64%) are **pure computation** — parsers, evaluators,
  type systems, codecs (`form.py`, `category.py`, `numeric_formats.py`,
  `quotient.py`, `inductive.py`, `form_eval.py`, …). No DB, no IO. These are the
  files the Python→Form compiler *could* target — and several already have
  Form-native siblings (`engine.fk`, `emit-engine.fk`, `grammars/*.fk`,
  `universal-shapes.form`).
- Only 3 files are genuinely DB-bedrock: `kernel.py` (49 DB signals), `orm.py`
  (schema), `agent_relationship.py` (19). And `intern_node`'s DB coupling is
  exactly the `storage-port` carrier we just built — `SELECT by content key →
  return existing or INSERT` IS `storage-get` + `storage-put` with the
  `ON CONFLICT` dedup gate.

So the gap between "factorial(6) runs Form-native" and "the substrate runs Form-
native" is **not** the 111K lines of services. It is one missing bridge plus a
bounded compiler push.

## The one missing bridge (the crux)

The native `intern_node` content-addresses **in memory only** — there is no wire
from it to durable storage. The `storage-port` (memory / segmented-file / Postgres
carriers, all proven) exists but nothing routes interning through it. **That wire
is the single highest-leverage piece.** Once `intern_node` persists through the
storage port:

- the substrate's core runs Form-native AND durably, on any carrier (memory for
  test, file for dev, Postgres for prod) — no SQLAlchemy;
- `make_cell` / `lookup_cell` / `find_equivalent_cells` become thin Form functions
  over `storage-get`/`storage-put` + the keydir, exactly the Bitcask shape already
  built;
- content (every `.md` concept, spec, idea, lineage doc) flows in through the
  **already-Form-native markdown grammar** (`grammars/markdown.fk`) and the domain
  encoders (`seedbank/encoders/`), interns through the Form-native core, and lands
  in the Form-native store. The Python ingestion (`markdown_frontend.py`) is
  replaced, not compiled.

This is the same move we just made for the DB: **don't port the Python's
mechanism; re-express the contract in Form and route through the port.**

## What this serves (the higher goal)

The cross-domain knowledge claim — finding the same teaching in biology, physics,
philosophy, art, religion, chemistry, scaling atoms→galaxies — is *already* how
the substrate works: two entities of the same structural shape content-address to
the **same Blueprint NodeID**, automatically, regardless of domain. The vision-KB
already carries this (`modality-as-recipe.form`, `quantum-physics-as-recipe.form`,
`healing-modality-as-recipe.form` — the claim that `R_Re-anchor ≡ R_Re-coherence
≡ R_Re-pattern` across teaching, quantum, healing is *falsifiable by content-
addressing*). Running the interning core Form-native means **the cross-domain
equivalence engine is the runtime itself**, not a Python service computing over a
SQL table. That is "knowledge infrastructure that can run itself."

## The plan — ordered by leverage, each a shippable breath

1. **Bridge `intern_node` → `storage-port`** (the crux). A Form module
   `substrate-core.fk`: `sc-intern (category children) → NodeID` that computes the
   content key (serialize_tree, already trivial), does `storage-get`/`storage-put`
   through a carrier, and returns the existing-or-fresh NodeID. `sc-make-cell` /
   `sc-lookup-cell` / `sc-find-equivalent` over the same carrier. Proven by a band
   that interns the same shape twice → one NodeID, across all three carriers
   (the substitutability we just proved, now carrying the substrate's own op).
   *No compiler work — hand-written Form, the architecturally-sound choice.*

2. **Ingest real content Form-native.** Wire `grammars/markdown.fk` + a domain
   encoder → `sc-make-cell`, so a real `.md` concept file becomes a durable cell
   through the Form-native path end-to-end. Prove cross-domain equivalence:
   ingest two same-shape concepts from different domains, confirm one Blueprint.
   *Replaces `markdown_frontend.py`; no SQLAlchemy.*

3. **Compile the pure-computation substrate files** (the legitimate compiler
   target — `form_eval.py`, `form_atoms.py`, `category.py`, `numeric_formats.py`).
   These have no DB and several have Form siblings; closing the python-bmf lifter
   gaps they need (the bounded list below) lets them run Form-native, dogfooding
   the compiler on real (non-toy) code. *This is where compiler work earns its
   keep — on pure logic, not ORM glue.*

4. **Expose the read surface** (`/api/substrate/*`, already read-only) over the
   Form-native store, so the live API serves from the Form core. The write path
   (ingest) and read path (query) both run Form-native; the Python router stays a
   thin HTTP shell calling the Form runtime (services are stateless functions —
   the easy entry shape).

## The bounded compiler gap (only for step 3, only pure files)

The python-bmf compiler runs `factorial(6)` today (def, return, while, if,
assign, call, binop, compare, list, dict, subscript, recursion). To compile the
*pure* substrate files it additionally needs, in the **lifter+eval** (the grammar
already scans all of it): `for`, `class`+methods, `try/except/raise`,
comprehensions, attribute access, method calls, tuples, augmented assign, a
minimal builtin set (`len`, `range`, `str`, `int`, `list`/`dict` methods), and
string ops. Each is one lift-arm + one eval-arm + a band — the same per-breath
rhythm the kernel already grows by. This is real but bounded, and it is **NOT on
the critical path** for steps 1–2: the bridge and ingestion are hand-written Form.

## Why this order is right

- **Step 1 alone** makes the substrate's core run itself, durably, on Form — the
  headline of "infrastructure that can run itself" — with zero compiler work.
- **Step 2** proves the cross-domain knowledge claim on real content through the
  Form-native path.
- **Steps 3–4** widen the Form-native surface and dogfood the compiler on the
  files that *deserve* compiling (pure logic), never on SQLAlchemy.
- At no point do we port an ORM, an HTTP client, or FastAPI to Form. We re-express
  contracts and route through ports — the move proven for storage and DB.

The substrate stops being "Python that computes over a SQL table" and becomes
"a Form-native content-addressed lattice that runs itself and recognizes the same
shape across every domain." That is the goal, and the crux is one bridge away.

## See also

- [`ports-interface-and-structure.md`](ports-interface-and-structure.md) — the
  storage port the bridge routes through (memory/file/Postgres, one test).
- [`cell-store-architecture.md`](cell-store-architecture.md) — the segmented log
  store the file carrier uses.
- [`ORM_TO_FORM_NATIVE.md`](../../kernels/ORM_TO_FORM_NATIVE.md) — the DB carrier
  and schema-as-Blueprint engine.
- [`kernels/COMPILER_GAP_QUEUE.md`](../../kernels/COMPILER_GAP_QUEUE.md) — the
  python-bmf coverage queue (step 3's bounded gaps).
- [`modality-as-recipe.form`](modality-as-recipe.form),
  [`quantum-physics-as-recipe.form`](quantum-physics-as-recipe.form) — the cross-
  domain equivalence the Form-native core makes the runtime itself compute.
