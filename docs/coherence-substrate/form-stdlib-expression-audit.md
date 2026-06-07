# Form Stdlib Expression Audit

This audit asks one question of every stdlib surface: is this authored at the
highest reusable grammar we can honestly express today, or is it hand-maintained
realization code that wants to become a declaration, model, grammar, reusable
runtime, or generated artifact?

The answer is not a defense of what exists. Existing code is evidence of the
path taken. The question is what it wants to become now.

## Rewrite Principle

The authored source shall be the closest expression of intent:

- Protocols are grammars and state machines, not string walkers.
- Codecs are declarations over cell shapes, delimiters, literals, and laws, not
  one parser and one emitter per format.
- Routes are route classes over request/response cells, not ad hoc handlers.
- Query languages are graph/path grammars, not split loops.
- Domain models are cell classes, capabilities, and relationships, not list
  offsets plus accessor functions.
- Low-level Form is allowed as generated realization or generic runtime support,
  not as the hand-authored public surface of a domain.

## Hot Rewrite Targets

| Area | Current Tissue | Closest Ideal | First Rewrite Move |
| --- | --- | --- | --- |
| JSON codec | `json.fk` now names JSON cell categories, accessors, and constructors only. Compiler/bootstrap, i18n, channel-query, and normal tests enter through the BML `JsonCodec`; `parse-json` remains only in seedbank compost paths. | `json-codec.fk` declares JSON as a structured codec; parse/emit enter through `JsonCodec`, and lower Form is generated or generic runtime execution. | Add the seedbank migration ledger entry for the old parser/emitter pair, then promote, generate, or release those artifacts explicitly. |
| HTTP stack | `http-parse.fk`, `http-render.fk`, `http-serve.fk`, `http-server.fk`, `http-socket.fk`, `http-adapter.fk`, and `kernel-http.fk` split protocol, routing, rendering, and serving across hand-authored functions. | HTTP is a protocol grammar plus route graph: request grammar, response grammar, route classes, observation cells, and socket/listener lifecycle as one front door. | Declare HTTP/1.1 parse/render as a protocol codec, then route serving consumes request/response cells only. |
| Route catalog | `router-routes.fk`, `kernel-http.fk`, and route tests still describe routes with low-level constructors. | Routes are high-grammar `RouteCell<Request, Response>` declarations with choice/fail/dispatch observation attached. | Convert the highest-traffic API routes into route classes that return codec-backed response cells. |
| Source compiler | `source-compiler.fk`, `compiler.fk`, `engine.fk`, `bmf-core.fk`, `bmf-grammar.fk`, `grammar-chars.fk`, and `runtime-grammar.fk` overlap as compiler, grammar, runtime, emitter, and registry layers. | One grammar-of-grammars pipeline: source declaration -> grammar cells -> lowering cells -> executable recipes -> reversible source/trace. | Name one canonical compiler pipeline and mark overlapping engines as candidates to merge, generate, or release. |
| BML grammar | `grammars/bml.fk` is large and highly capable, but much of the desired language surface is still encoded as handwritten lowering and tests. | BML declares its own grammar, semantics, lowering, reverse, proofs, and capability gaps as cells. | Lift repeated BML lowering patterns into reusable grammar/lowering declarations rather than adding more special cases. |
| Python bridge | `python-bmf-lift.fk`, `python-bmf-eval.fk`, `grammars/python-bmf.fk`, and `emits/python-native*` are major bridge tissue. | Python is one optional grammar among many; no special runtime status, no privileged fallback. | Classify every Python bridge entry as: release now, compile through BML/BMF, or temporary call-out with a named compost gate. |
| Emitters | `emit-engine.fk`, `seedbank/emits/*`, `emits/python-native*`, and self-witness emitters overlap. | Emitters are codec/target declarations over cell shapes with one reusable engine and target-specific declarations. | Promote the useful seedbank emit templates into codec declarations or compost them. |
| Query/path languages | `xpath.fk`, `doc-xpath.fk`, and `concept-xpath.fk` hand-parse path strings and walk trees. | Query is a graph/path grammar with typed selectors, predicates, and substrate coordinates. | Replace split-loop path parsing with a reusable query grammar and lens registry. |
| i18n and corpus loading | `i18n.fk` now loads through `json_parse_body`; static locale lists remain. | Locales are discovered corpus cells; JSON is only a codec selector. | Replace static locale lists with a manifest/corpus query. |
| Channel JSON bridge | `channel-query-json.fk` now projects query/response values into JSON cells and emits/parses through `JsonCodec`; response decode and richer item schemas remain. | Channel query has a native cell protocol; JSON is a codec projection at the boundary. | Add response decode as cell projection and move mixed item schemas into declarations. |
| Storage and carriers | `storage-port*.fk`, `persistence.fk`, `cell-log-store.fk`, and carrier integration files encode carriers with lists and callbacks. | Carriers are capability cells with protocol laws, observation, and interchangeable persistence grammars. | Name carrier specs and move list offsets into typed carrier cells. |
| Field model | `field-model-form.fk` and `field-model-form-runtime.fk` contain many list/accessor and symbolic math helpers. | Field concepts are model cells with algebraic laws, observation, and reusable dimensional operators. | Split authored domain declarations from generic numeric/topology runtime support. |
| Algorithms and encodings | `base64.fk`, `hex.fk`, `url-encode.fk`, `rle.fk`, `uuid.fk`, `ulid.fk`, `sha256.fk`, `hmac-sha256.fk`, `crc32.fk`, `adler32.fk`, `dns.fk`. | Algorithm families are law declarations with reference vectors, possible native primitive realization, and generated runners. | Keep exact algorithms where needed, but wrap them in law/spec declarations and mark hot ones for native primitive/JIT treatment. |
| Domain channels | `sanskrit-channel.fk`, `gematria-channel.fk`, `shamballa-channel.fk`, `nl-emit.fk`, `concept-*`, and corpus grammars mix data, access, and behavior. | Domain knowledge lives as corpus/grammar cells; channels compose over those cells. | Move static dictionaries and access patterns into named corpus/grammar declarations. |
| Seedbank | `seedbank/` holds many older grammars, emitters, and tests beside promoted stdlib forms. | Seedbank is a compost nursery with explicit promote, merge, or release status per artifact. | Add a seedbank migration ledger and stop allowing promoted and seedbank versions to silently coexist. |

## Standing Rewrite Questions

For each stdlib file touched on a hot path:

1. What is the concept's purpose and public surface?
2. Is the current source a declaration of that purpose, or only a realization?
3. Can the realization be generated from a grammar, model, codec, route class, or law?
4. Are there two public ways to do the same thing?
5. Which callers keep the lower path alive?
6. What proof shows the higher path is complete enough to release the lower path?
7. What observation should attach to this surface: dispatch counts, choice/fail attribution, JIT treatment, cost, or source/cell coordinates?

## First Rewrite Sequence

1. Finish JSON as the pattern: `JsonCodec` is the only route-facing and corpus
   JSON surface; seedbank parser/emitter tissue is explicitly promoted,
   generated, or released.
2. Keep the compiler/bootstrap ontology path free of `parse-json`: ontology
   coordinates live in kernel-native `bp` tables and the loader materializes
   Form bindings from those coordinates.
3. Lift HTTP parse/render into a protocol codec, then make native route classes
   consume only request and response cells.
4. Consolidate compiler/grammar engines by naming one source-to-recipe pipeline
   and moving special-case lowerers into declarations.
5. Audit Python bridge files as temporary grammar ports, not privileged runtime
   dependencies.

This audit is a work queue, not a museum. When a rewrite lands, update the row:
what released, what remains, and which proof now carries the claim.
