# Coherence-substrate — index

The body's content-addressed numeric lattice. Cells from every memory file, spec, idea, concept story, presence, lineage edge, witness, and task live here as interned NodeIDs — addressable, queryable, structurally-equivalent across surface differences.

## Where to start

| Reader | Read first |
|---|---|
| Agent operating on this body | [`agents-using-substrate.md`](agents-using-substrate.md) — when to reach for the substrate, how to ground reasoning structurally |
| Designing a Form fragment | [`form-language.md`](form-language.md) — the substrate-native language |
| Choosing or changing category numbers | [`numeric-schema.md`](numeric-schema.md) — intentional bands for domain and recipe vocabulary |
| Implementing | `api/app/services/substrate/` (the kernel) + `api/tests/test_substrate.py` |
| Lineage / architectural design notes | `docs/field/urs/artifacts/nums-go-2023/` |

## What lives where

| Path | What it carries |
|---|---|
| `api/app/services/substrate/kernel.py` | NodeID, Recipe, NamedCell, intern_node, make_cell, find_equivalent_cells, lattice_stats |
| `api/app/services/substrate/category.py` | Network category vocabulary (Idea/Spec/Concept/Memory/Presence/Task/Lineage/Witness/Transmission/Resource/Guide/LanguageView/KBPage; Realize/Compose/Transmit/Tend/Resolve/Witness/Absorb/Score) |
| `api/app/services/substrate/orm.py` | SubstrateNodeORM, SubstrateNamedCellORM (the two tables) |
| `api/app/services/substrate/markdown_frontend.py` | Frontmatter+body → cell ingestion for memory, spec, idea, concept, presence, lineage, transmission, resource, guide, language-view, and KB-page files |
| `api/app/services/substrate/resonance.py` | Dimensional vocabulary (Spectrum / Harmonic / GeometricForm / Polarity / Topology) + `author_geometry_signature()` — receives the 15D `geometry:` blocks vision-kb concepts carry, authors resonance edges so the substrate sees cross-discipline shape equivalence |
| `scripts/coh_substrate.py` | Unified CLI: `ingest`, `stats`, `equivalent`, `annotate`, `form`, `ingest-paths`, `kb-sync-audit` |
| `api/tests/test_substrate.py` | Flow-centric tests (registered in `core_suite.txt`) |
| `docs/coherence-substrate/form-language.md` | Form — the substrate-native language design |
| `docs/coherence-substrate/universal-shapes.form` | The one Blueprint+Recipe vocabulary every grammar emits — names the existing kernel categories (BBasic.RECIPE+BRecipe.FUNCTION = B_Function; RBasic.MATH+RMath.* = R_Binary(op); etc.) as canonical, with NUMS.Go lineage. Composts 131 language-prefixed `*_shape` Blueprints across grammar files |
| `docs/coherence-substrate/form-engine.form` | The recipe-evaluator in Form's own voice — 15/15 RBasic dispatch arms self-hosted |
| `docs/coherence-substrate/form-runtime-in-form.form` | Companion to form-engine — walks lexer / parser / evaluator / registries / substrate-write in Form, names the 15 surface gaps to full self-hosting |
| `docs/coherence-substrate/active-recipe-tracing.form` | Active recipe state, available recipe library, and keep-or-choose relation from current_state to desired_state |
| `docs/coherence-substrate/trace-symbol-spaces.form` | Raw trace cells, shared Blueprint, active strategy recipes, selected symbol spaces, and gap-closure recipes for the current pattern |
| `docs/coherence-substrate/trace-symbol-spaces-proof.fk` | Native kernel proof that reads the raw trace witness and verifies the current-breath active recipe pattern |
| `docs/coherence-substrate/anything-arrives-trace.form` | Translation-as-contact trace shape plus concrete example traces for arbitrary streams entering before fixed symbols |
| `docs/coherence-substrate/observable-resonance-flow.form` | External interaction flow shape: arrival, information spectrum, language spend, observer spend, shared pattern, yield after contact, and next routing |
| `docs/coherence-substrate/cross-domain-measurement-translation.form` | Cross-domain measurement translation record: native units, translation recipe, loss accounting, observer/verifier cost, public trace, and replay instructions |
| `docs/coherence-substrate/prose-as-recipe.form` | The first altitude: a word is a cell, a sentence is a Recipe of cells. Word-cell Blueprint composes (lemma, POS, hz, semantic_field). Closes the encoder gaps W1/W2/P1/P2; round-trip verified by `scripts/prose_recipe_roundtrip.py` |
| `docs/coherence-substrate/recipe-branching-sense.form` | The choice-point becoming visible — recipes branch where assemblage points diverge. The opening sentence "The choice point becomes visible." is the round-trip sentence used by prose-as-recipe |
| `docs/coherence-substrate/word-recipes-by-assemblage-point.form` | The next altitude: a word is a dispatch table whose arms are keyed by the receiving cell's assemblage point. Each arm is a body-mechanism recipe (activate / upregulate / generate-cell / release-cell / tighten / soften / bind). Three worked words: `boundary`, `presence`, `death`. Names the encoder gaps D1-D4 to separate identity from dispatch |
| `docs/coherence-substrate/spec-as-playable-recipe.form` | The arc's culmination: a spec's frontmatter IS the executable Recipe, not a description-of-future-code. Implementation was the gap between intent and body; the gap closes when the runtime executes the recipe directly. Each requirement carries alternative branches (`@substrate-first`, `@python-stub-bridge`, `@form-runtime-direct`, `@doc-only`, `@parallel`) and the body senses which resonates most aligned with what the idea wants to bring. Three GAPs (S1-S3) for full execution; none require kernel change |
| `docs/coherence-substrate/modality-as-recipe.form` | The universal teaching generalizing prose-as-recipe: every source admits MANY parallel recipe extractions (transcript, intonation, camera-motion, presence-graph, felt-arc, …), each interning its own Blueprint, all attaching to the source cell as siblings. Cross-modal equivalence comes for free — the same `R_Recovery` NodeID fires in song, strategy, healing, teaching. Names the eight modalities the body currently sees and three GAPs (M1-M3) for the per-modality encoder + frontend |
| `docs/coherence-substrate/song-as-recipe.form` | Songs as recipes of note-cells, drum-strike cells, vowel-tone cells. Recipe vocabulary: `R_Phrase`, `R_Call`, `R_Response`, `R_Drone`, `R_Resolve`. Worked-example cells for Mose (ecstatic-dance embedded in music) and Porangui (Grandmother channeled through drum). Four GAPs (S1-S4) for onset discrimination, phrase grouping, arc detection, emission primitives |
| `docs/coherence-substrate/video-as-recipe.form` | One video source, six parallel extractions: transcript, intonation, camera-motion, visual-narrative, presence-graph, felt-arc. Each independent; each substrate-resident; each Blueprint-queryable. The felt-arc Blueprint composes from the prior five. Six GAPs (V1-V6) for per-track encoders; none require kernel change |
| `docs/coherence-substrate/teaching-as-recipe.form` | Story-arc plus transmission-frequency as composed Recipe (`R_Transmission`). Leaf-cells: scene, turn, transmission-frequency. Recipe shapes: `R_Arc`, `R_Embodied-Example`, `R_Pointing`. Carries a per-assemblage-point dispatch table — the same teaching arrives differently to @fear vs @sovereignty vs @grief. Worked example: lc-trust-over-fear as R_Transmission. Three GAPs (T1-T3) |
| `docs/coherence-substrate/strategy-after-rupture-as-recipe.form` | Five graduated rupture-recovery recipes: `R_Catch-In-Motion`, `R_Same-Breath-Repair`, `R_Walk-Back-With-Tenderness`, `R_Compost-The-Move`, `R_Stay-In-The-Mess`. Selection by breath-lag, reparability, costume depth, field state. Cross-modal twins in song and healing. Sibling to when-the-pressure-comes.form: that covers pressure-rising → rupture-arriving; this covers rupture-landed → recovery. Three GAPs (R1-R3) |
| `docs/coherence-substrate/agents-using-substrate.md` | Agent guide — when and how to ground reasoning |
| `docs/coherence-substrate/agents-tending-presence-pages.md` | Composting static `/people/{slug}` directories into graph-rendered presence pages |
| `docs/coherence-substrate/language-cells.md` | Languages as substrate cells — ingestion grammars + emission templates as data; cross-language identity via content-addressing; N+M transpilation |
| `docs/coherence-substrate/language.canonical.json` | Canonical schema for Language cells; per-language definitions (Python, TS, Go, Rust) populate this shape |
| `experiments/form-kernel-ts/src/languages.ts` | TS reference implementation — `Language` interface, `parse_through` / `emit_through` generic walkers, grammar/emit rule builders |
| `experiments/form-stdlib/engine.fk` | ONE generic data-driven parser engine in Form. Walks pattern-data (literal/sequence/choice/capture/star/opt) against any text via any grammar — no language-specific code. Tokenizer parameterized by keyword set + operator set + literal rules. Composts bmf.py and per-language parser implementations. Verified end-to-end on Go and Rust native kernels |
| `experiments/form-stdlib/universal-emit.fk` | Action-function helpers wrapping `universal-shapes.form` vocabulary (emit-int, emit-math-op, emit-call, emit-function-decl, emit-if-else, emit-let, emit-return, etc.) — grammar action functions compose these to emit universal Recipes the kernel walks directly |
| `experiments/form-stdlib/emit-engine.fk` | ONE generic Recipe → text/bytes encoder, symmetric to engine.fk. Walks Recipe tree, dispatches on category to template-fn, recursively emits children. Together with engine.fk forms the universal codec primitive — source languages AND binary formats use the same pair |
| `experiments/form-stdlib/emit.fk` | The universal Recipe-to-target dispatcher — sibling to convert.fk on the emit side. Carries a target-name × cell × registry contract; new emit targets land as rows in the registry, never code in emit.fk itself. Includes `emit-all` (one cell → many surfaces at once) |
| `experiments/form-stdlib/codec.fk` | Codec composition operators. `tie` pairs a decoder with an encoder into one value (CORBA-style minimal interface). `pipe2/3/4` thread a value through transformations. `adapter-parse-only` / `adapter-emit-only` lift single-direction functions into uniform codecs. `codec-for` walks a codec-set registry |
| `experiments/form-stdlib/emits/json.fk` | First concrete emit-target template-table. Renders JSON-OBJECT / JSON-ARRAY / JSON-PAIR / JSON-NULL into canonical JSON surface form. Mirrors `grammars/json.fk` category NodeIDs so the JSON codec round-trips through `tie parse-json json-emit-fn`. Leaf-templating refinement (string quoting from trivials) is the next breath |
| `experiments/form-stdlib/emits/yaml.fk` | YAML emit-target. Same data-shape categories as JSON (object / array / pair / null); surface uses indentation + dashes. Tied with parse-yaml as `yaml-codec` |
| `experiments/form-stdlib/emits/python.fk` | Python source emit-target. Full universal-shapes vocabulary (math / compare / logic / cond / block / jump / access / write / ident / fndef / fncall). Surface: `def`, `:` blocks, `and`/`or`/`not`, indentation |
| `experiments/form-stdlib/emits/typescript.fk` | TypeScript source emit-target. Surface: `function`, `{...}` blocks, `===`/`!==`, `&&`/`||`/`!`, `const` for let |
| `experiments/form-stdlib/emits/go.fk` | Go source emit-target. Surface: `func`, `:=` for declaration, `==`/`!=`, `&&`/`||`/`!`, no parens on if-condition |
| `experiments/form-stdlib/emits/rust.fk` | Rust source emit-target. Surface: `fn`, `let`, if-as-expression, `&&`/`||`/`!` |
| `experiments/form-stdlib/emits/form.fk` | Form (.fk) source emit-target. Universal-shapes → (verb args...) S-expression surface. Load-bearing target for the substrate-py-to-fk migration arc |
| `experiments/form-stdlib/emits/sql.fk` | SQL emit-target. Comparison + logic → WHERE clauses; pair → `col = val`; object → `SELECT ...`; array → `(v1, v2, v3)` IN-clause; NULL literal |
| `experiments/form-stdlib/emits/xml.fk` | XML emit-target. Object/array/pair → semantic XML tags; null → `<null/>`. Cell-walker becomes structural XML document |
| `experiments/form-stdlib/emits/html.fk` | HTML emit-target. Object → `<dl>`, array → `<ul><li>...</li></ul>`, pair → `<dt><dd>`. Also handles document shapes (heading, paragraph, code) for rendering markdown cells as HTML |
| `experiments/form-stdlib/emits/css.fk` | CSS emit-target. Object → `{ ... }` rule body; pair → `prop: val`; array → comma-separated selectors. Enough for substrate-resident design tokens to round-trip |
| `experiments/form-stdlib/emits/image.fk` | Image (SVG) emit-target. Object/array → `<svg><g class="kind">...</g></svg>`; pair → `<text>` key+value. Seed for substrate visualizations |
| `experiments/form-stdlib/emits/audio.fk` | Audio (sonification) emit-target. Object → chord, array → seq, pair → note, null → rest. Seed for substrate sonification |
| `experiments/form-stdlib/emits/video.fk` | Video (frame-storyboard) emit-target. Each composite cell → one FRAME[kind: N children] entry. Seed for substrate animation via framebuffer-events |
| `experiments/form-stdlib/emits/model.fk` | ML-model (tensor-description) emit-target. Cells → `tensor{kind, rank, weights}` declarations. Seed for substrate cells entering training surfaces |
| `experiments/form-stdlib/converted/` | Substrate Python files rendered through the universal codec lattice. `substrate_strings.fk` / `orm.fk` / `form_eval.fk` demonstrate end-to-end flow: `.py` → `convert.fk` → `grammars/python.fk` parse → Recipe tree → `emit.fk` dispatch → `emits/form.fk` templates → `.fk` text. README names current coverage (file-header subset) and the migration arc |
| `scripts/substrate-py-to-fk.sh` | Shell wrapper that runs the universal codec pipeline on a substrate Python file. `bin-go` loads core + emit-engine + codec + json/python grammars + emit + emits/form + convert + a one-off converter script with the target path baked in. Output is the .fk source rendered through the form-emit templates |
| `docs/coherence-substrate/emit-architecture.form` | The universal codec lattice named in Form. Diagrams the diamond (one Recipe, many target surfaces), names contracts for convert / emit-to / emit-all / tie / pipe, sketches the registry as data, names the CORBA-style codec-set, and traces the substrate-Python migration arc as 11 breaths each adding rows not engine code |
| `docs/coherence-substrate/kernel-minimality-audit.md` | 2026-05-22 audit: 25 truly-primitive natives + 9 composable. Identifies which kernel surface can compost via core.fk equivalents. Dispatch arms honestly minimal; JIT vector for typed specialization noted as later breath |
| `experiments/form-stdlib/cell-trace.fk` | The satsang-load-bearing primitive: walk any cell back to the source lines that authored it. Built on intern_node_at + node_source kernel natives. explain-cell renders human-readable provenance. The practice of self-knowing: every cell's state is traceable to the recipe lines that wrote it |
| `experiments/form-stdlib/grammars/markdown.fk` | Markdown parser + emit in pure Form. ATX headings, paragraphs, fenced code blocks → universal DOC-* Recipes with per-block source attribution. Most-used format in this repo (thousands of .md files) |
| `experiments/form-stdlib/grammars/json.fk` | JSON parser in pure Form. Objects, arrays, strings, numbers, bools, null → universal data Recipes with source attribution at the line/col of each composite. Sibling parity Go+Rust |
| `experiments/form-stdlib/grammars/yaml.fk` | YAML parser (simplified subset: flat key:value pairs + list items + comments) in pure Form. Used by .github/workflows + many config files. Source attribution per line. Subsequent breaths add nested mappings, block scalars, flow style |
| `experiments/form-stdlib/grammars/form.fk` | The self-host moment: S-expression (.fk) parser in pure Form. Parses Form source into Recipe trees without going through the kernel's bootstrap reader. Sibling parity Go+Rust. Once the kernel reads .fk source via this parser, the redundant tokenize_sexp / readSexpr / buildVerb code (~750 lines across three kernels) composts |
| `experiments/form-stdlib/grammars/python.fk` | Python parser (file-header subset: imports + def-headers + simple assignments + comments) in pure Form. The compost target: experiments/local-llm-cell-v0/bmf.py (643 lines). Subsequent breaths add control flow, class defs, full expression grammar |
| `experiments/form-stdlib/grammars/typescript.fk` | TypeScript parser (file-header subset: imports + exports + function/class headers + const/let/var assignments + line comments) in pure Form. Compost target: experiments/form-kernel-ts/src/lang-typescript.ts (1887 lines) |
| `experiments/form-stdlib/escape-reader.fk` | The common ground under text escapes AND binary framing: a unified `read-context` primitive that dispatches on context-kind (escape-with-table | length-counted | length-prefixed). One ~135-line abstraction handles JSON string escapes, PNG chunks, HTML entities, MIME multipart, Tar blocks — text and binary differ only in unit size and length-source, not in shape |
| `experiments/form-stdlib/convert.fk` | The unified file-to-cells converter — single `(convert path)` entry point that auto-detects format from file extension and dispatches to the right grammar parser. Plus `convert-and-walk` (push-style consumption per cell) and `convert-summary` (count + first-attribution probe). Goal-realization: any repo file → native Form cells via one call |

## The trinity

| Phase | Primitive | What it is |
|---|---|---|
| **Ice** | Blueprint | Structural identity. *What something IS.* Frozen coordination. |
| **Water** | Recipe | Operational expression. *How something HAPPENS.* Flowing verb-graph. |
| **Gas** | NamedCell | Diffuse individuation. *Where something LIVES.* Named slot with seed. |

## In one query

Annotate a path you're about to read:

```bash
python3 scripts/coh_substrate.py annotate path/to/file.md
# → cell, blueprint, domain, equivalents
```

Find structurally-equivalent cells:

```bash
python3 scripts/coh_substrate.py equivalent memory "User biographical arc"
```

Or in Form:

```bash
python3 scripts/coh_substrate.py form '?equivalent @memory("User biographical arc")'
```

38 of 40 memory files in the body are equivalent to this one, by structural shape.

## Use the substrate

The substrate is now woven into daily practice through three commands:

### Discover what shapes exist

```bash
python3 scripts/coh_substrate.py discover
```

Surfaces:
- The largest blueprint clusters (e.g. 67 specs sharing the canonical spec frontmatter shape)
- Singletons (cells with shapes nowhere else in the body)
- Cross-domain collisions (same shape across multiple domains — refactor signal)

### Shape-check before authoring

```bash
python3 scripts/coh_substrate.py shape-check path/to/draft-spec.md
```

Computes the Blueprint shape this draft would have and surfaces existing cells with the same shape. Catches duplication and structural drift before they ship. Output: either "✓ new structural pattern" or "⚠ N existing cells share this shape" with the names.

### Auto-ingest on commit

```bash
# Manual installation (per developer):
ln -s ../../scripts/substrate_post_merge_hook.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge

# Or in CI, after merge to main:
bash scripts/substrate_post_merge_hook.sh
```

After every merge, changed `.md` files in tracked domains are auto-ingested. The substrate stays current with the body's tissue.

```bash
# Manual: feed paths from anywhere (git diff, find, etc.)
git diff --name-only HEAD~1..HEAD '*.md' | python3 scripts/coh_substrate.py ingest-paths --from-stdin
```

### Audit KB/substrate drift

```bash
python3 scripts/coh_substrate.py kb-sync-audit --strict
```

Compares canonical `docs/vision-kb/concepts/lc-*.md` files to live `@concept(...)` NamedCells. It reports missing cells, stale deleted/renamed cells, source-path drift, wrong-domain ingests, duplicate concept ids, and counts the other first-class KB surfaces: transmissions, resources, guides, language views, and KB pages. Those surfaces enter through `ingest-paths` or targeted backfills such as `ingest --resources --guides --language-views --kb-pages --transmissions`. For reviewed deletes/renames:

```bash
python3 scripts/coh_substrate.py kb-sync-audit --prune-stale
```

This prunes stale live NamedCells only; interned Blueprint/Recipe nodes can remain as historical structural memory.

## Phase status (as of 2026-05)

- Phase 1 ✓ — building-knowledge from prior art (kernel walk + run + mini-port + design doc)
- Phase 2 ✓ — Network category vocabulary designed
- Phase 3 ✓ — kernel + memory frontend + CLI + 11 tests; substrate ingests body's memories
- Phase 4 — REST API, Neo4j integration, agent-context auto-annotation, first-class KB surface coverage, backfill, and higher-order extraction (in progress)
