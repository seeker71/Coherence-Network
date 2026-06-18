# Form-CLI fourth-kernel surface — the cornerstone baseline

The 4th-kernel form-cli is the body's self-evolving spine: it senses its own
gaps, drafts recipes with a LOCAL oracle, proves them four-way (Go/Rust/TS +
the emitted `fkwu` walker), and loads each as native tissue for the next
iteration. This doc is the living inventory + north-star alignment of that
surface across twelve families, and the open rework plan that keeps it supple.
The floor source for four-way coverage stays `form/fourth-arm-bands.txt`; this
doc names purpose, grammar altitude, axiom relationships, and what is still
climbing toward the native ideal.

**Standing alignment:** 73/100 at first full audit (2026-06-18) — the body's *ideas* are north-star; *proof and altitude* lag, concentrated in the grammar/compiler/host-OS spine. The lift is the cornerstone investment.

## Landed in this baseline

The first cornerstone investment closed the most-pointed-at overnight gaps:

- **The principled BMF cursor crosses the fourth arm** — bmf-core (the cursor + data-driven matcher, verdict 600) and bmf-grammar (the recursive grammar engine: rule references, recursion, operator precedence, paren nesting, separator-lists + splice*, verdict 300) are **four-way proven incl. fkwu, 0 divergent**. One data-driven matcher, grammars-as-data, parsing-produces-recipes, no-sediment backtracking — the strongest north-star realization in the audit — is now provable on the fourth kernel. The string cursor (char_at/ord/substring) rides the shim string stones (tags 24..29); the parse emits universal recipes through the content-addressed intern arm (intern_node tag 47, bp tag 45, trivial interns tags 43/46, make_nodeid tag 91); `intern_node_at` rides the fourth-shim image of the carried intern — its returned NodeID is exactly `intern_node(cat, kids)`, the source attribution feeding only the framebuffer side-map the verdict never reads. This converts the whole BMF/dialect surface (bmf-core, bmf-grammar, bmf-to-fk, http-parse, the evals) toward provable.
- **Buffer model generalized** — the four frozen `ll-*` leaves (baked registers/offsets) lifted to one parameterized family `ll-alloc(n)/ll-store(rt,off)/ll-load(rt,off)/ll-free(n)` + composed `ll-buf` round-trip, **four-way proven incl. fkwu**; the frozen leaves composted (git keeps their close-next provenance).
- **The G1 lever advances toward G7 (self-host)** — `form-lower` now lowers `(str_eq a b)` to a native arm64 null-terminated byte-compare loop (`form-lower-streq` four-way, primitive `fa-cmp-r`) — the first string op native, the string half of the one lever. With `ll-buffer` (stack memory) that leaves host-io syscalls (`ll-readfile`) and the multi-arg calling convention (`ll-callconv`) as the remaining lever pieces; once they land, G3 compiles any recipe native and G7 self-hosts. The roadmap rung-status is now **manifest-derived** — `form_cli_roadmap.sh` reads each rung's proving band from `fourth-arm-bands.txt` and flags any drift, so the floor cannot claim what it has not proven.
- **Conviction codes named** — `lc-wrong/lc-bloated/lc-healthy/lc-better` replace bare 0/1/2/3.
- **Floor honesty** — 17 recipe headers retuned from understated "three-way" to their true four-way floor (each verified against a manifest row); a stray duplicate manifest composted.
- **Carrier fixes un-stranded** — close-gap drafts via the ollama HTTP API (clean text) with iterative kernel-feedback retry; close-next no longer resurrects composted leaves.

The rework plan below keeps the remaining (mostly spine) items open and honest.

## Families, best → worst alignment

1. storage + ports — 88 (14/14 four-way, cleanest carrier-last; one misaligned cache.fk)
2. native asm/lower/4th-arm (the lever) — 86 (11/11 four-way, most north-star-coherent; altitude-only gaps + flt-bp-node placeholder)
3. learning — 82 (39/42 four-way; systematic stale headers, one unnamed 3-kernel claim)
4. protocol + offer — 82 (5/8 four-way, honest floor, axiom-5 disciplined; altitude + DRY)
5. form-cli core + overnight cornerstones — 82 (17/19 four-way; raw-recipe altitude, frozen ll-* leaves, unwired ask-route)
6. substrate — 74 (5/8 four-way; stale claims, cache trust split, no BML lift)
7. choice + backtrack — 72 (8/9 four-way; flat tuples, two tag conventions, one proof-theater row)
8. channel — 68 (13/23 four-way; form-os-channel now Form over storage-port; inert catalogs, flat rows)
9. http + net — 84 (5/8 four-way: kernel-http + http-render + http-parse + http-request + http-server cross; one duplicate engine (http-serve) to compost, http-adapter compat tissue, http-socket host-io)
10. host-os + IO + tool-channel — 62 (8/11 four-way; the host-OS kernel carriers are 3-kernel-only with the exact op named in-file, carrier drift remains)
11. BMF grammar engine — 58 (4/19 four-way; the principled cursor (bmf-core/bmf-grammar) crosses; 3+ parallel engines + stale claims remain)
12. BML + source-compiler — 58 (5/13 four-way; two BML front-ends, Go-only compiler tissue, output-not-compiler proof)
## Inventory + per-family review

# Cornerstone Audit — form-cli 4th-kernel surface (12 families, 196 files)

Overall alignment: **73/100**. Strong ideas; proof and grammar-altitude lag on the grammar/compiler/host-OS spine.

## storage + ports — 88
| file | grammar | aligned? | rework |
|---|---|---|---|
| storage-port | Form-recipe | yes | optional: carrier as record cell w/ Blueprint |
| storage-port-file | Form-recipe | yes | none |
| storage-port-db | Form-recipe | yes | SQL→query recipes when grammar lands (Rust-only by design) |
| cell-log-store | Form-recipe | yes | lift int↔str/contains/escape to shared codec |
| resource-port | Form-recipe | yes | none (cleanest axiom-3 file) |
| auth-port | Form-recipe | yes | wire into live mutation front-door |
| graph-node-port | Form-recipe | yes | newline-envelope/index → SEQUENCE recipe |
| application-graph-node-port | Form-recipe | yes | dedup esc/quote helpers; SQL→recipes |
| audit-log | Form-recipe | yes | optional: thread AUDIT-ENTRY Blueprint onto data |
| **cache** | Form-recipe | **NO** | **re-ground on content-hash (not mtime); add band** |
| cache-phase | Form-recipe | yes | none (the model cache.fk should match) |
| model-roster-report | Form-recipe | yes | optional shared min/max-select-by-field |
| oracle-catalog | Form-recipe | yes | optional rows→record cells |
| training-catalog | Form-recipe | yes | keep rows composed |

## native asm/lower/4th-arm (the lever) — 86
| file | grammar | aligned? | rework |
|---|---|---|---|
| form-asm | Form-recipe | yes | lift high-bit ops into generic packer |
| form-lower | Form-recipe | yes | instruction-selection as table; derive source-map from it |
| form-macho | Form-recipe | yes | derive cmdsize/offset from field layout |
| form-elf | Form-recipe | yes | true 8-byte u64 before large-object band |
| form-elf-exec | Form-recipe | yes | reuse form-asm/form-elf encoders (drop private copies) |
| form-flatten | Form-recipe | yes | **generate flt-bp-node from shared BP table (placeholder)** |
| jit-lower | Form-recipe | yes | generate jit-shape-table from op registry |
| jit-tensor-emit | Form-recipe | yes | str_concat ladders → emit/template grammar |
| fourth-shim | Form-recipe | yes | generate from core.fk vs hand-twin |
| fourth-union | Form-recipe | yes | none urgent (quine constraint justifies low-level) |
| capability-form-asm | Form-recipe | yes | wire sample counts to generated fitness ledger |

## learning — 82
| file | grammar | aligned? | rework |
|---|---|---|---|
| io-match / champion-challenger / nearest-shape / predictor-train / active-inference / classifier-eval / self-grounding-classifier / sequence-predictor / predictor-sampling / learning-arc / learning-trend / metabolic-learning / co-learning(-stream) / trust-weighted-colearning / colearning-retire / learned-primitive | Form-recipe | yes | **stale 'three-way' header → four-way (15 files)** |
| **learning-style-space** | Form-recipe | **NO** | **diagnose higher-order-fns-in-data; cross or name op** |
| **embedding-as-recipe** | Form-recipe | **NO** | add in-file '3-kernel — node/substrate' note |
| autodiff-gradient | Form-recipe | yes | add missing Proven-by (four-way) line |
| **oracle-distillation-learning** | mixed | **NO** | gates over real corpus, not fixture magic numbers |
| oracle-distill-corpus | doc-or-data | yes | none (the measured-data exemplar) |
| oracle-flywheel / oracle-ensure / oracle-catalog / geometric-learning / translation-learn / native-training-receipt / real-mesh-training-* / tensor-autodiff-verifier / code-tool-learning / text-summary-learning / + others | Form-recipe | yes | core-lift scan; add Proven-by lines |

## protocol + offer — 82
| file | grammar | aligned? | rework |
|---|---|---|---|
| afferent-offer | Form-recipe | yes | register once node/substrate carrier crosses fkwu |
| offer-lane | Form-recipe | yes | share axiom-5 ack vocabulary; lift to BML |
| offers-in-flight | Form-recipe | yes | same node/substrate carrier dependency |
| form-agent-protocol | Form-recipe | yes | part kinds → typed-token cells; bind JSON grammar |
| form-cli-membrane | Form-recipe | yes | surface strings → typed-token enum |
| **channel-protocol-choice-floor** | doc-or-data | **NO** | derive status from manifest; compost validation log |
| protocol-beliefs | mixed | yes | lift inline C string into shared emit grammar |
| sovereign-boundary-protocol | BML-high | yes | name 3-kernel in header; value-lane the tags to cross now |

## form-cli core + overnight cornerstones — 82
| file | grammar | aligned? | rework |
|---|---|---|---|
| form-cli-router | Form-recipe | yes | **make python ask-route call fcr-route (sole router)** |
| form-cli-loop | Form-recipe | yes | unify fcl-confidence w/ router axis |
| form-cli-predict/score/judge/review-gap | Form-recipe | yes | single-walk majority helper (covers+covers idiom) |
| form-cli-model | doc-or-data | yes | band diffing trainer output vs data cell |
| form-cli-sample | Form-recipe | yes | prelude membrane vocab (drop copied surfaces) |
| form-cli-gaps / oracle-ensure | Form-recipe | yes | single-source teacher-state strings |
| form-cli-guide | Form-recipe | yes | tool-name map → data cell |
| form-native-run | mixed | yes | JSON parse → grammar; honest host-io 3-kernel |
| lowering-conviction | Form-recipe | yes | name verdict codes as constants |
| roadmap | doc-or-data | yes | **derive status from evidence, not hand-asserted** |
| **ll-alloc16 / ll-store-w8 / ll-load-w9 / ll-free16** | Form-recipe | yes* | **generalize ll-alloc(n)/ll-store(rt,off); compose ll-buffer** |

## substrate — 74
| file | grammar | aligned? | rework |
|---|---|---|---|
| substrate-core | Form-recipe | yes | stale 'three-way'→four-way; lift sc-int-str |
| concept-corpus | mixed | **NO** | split pure-parse from host read; name 3-kernel |
| persistence | Form-recipe | **NO** | resolve overlap w/ substrate-core; name host-io gap |
| recipe-equivalence-gate | Form-recipe | yes | broaden band coverage past thin fkc 3 |
| recipe-gen | Form-recipe | **NO** | source primitives from substrate cells; name 3-kernel |
| substrate-phase | Form-recipe | yes | give own four-way manifest row |
| cache-phase | Form-recipe | yes | none |
| memory-phases | Form-recipe | yes | stale 'three-way'→four-way |

## choice + backtrack — 72
| file | grammar | aligned? | rework |
|---|---|---|---|
| choice-receipt | Form-recipe | yes | lift record family to BML typed records (keystone) |
| branch-choice-order | Form-recipe | yes | tagged record vs 7-tuple |
| choice-receipt-learning | Form-recipe | yes | rides neighbors' lift |
| choice-outcome-learning | Form-recipe | yes | unify tag convention; drop 999999 sentinel |
| bml-route-choice-runtime | mixed | yes | escalation order from registry; drop magic 90/96 |
| recipe-choice-runtime | Form-recipe | yes | generic kind-tag dispatch vs 2-way fork |
| channel-protocol-choice-floor | doc-or-data | yes | derive status; compost validation log |
| **form-control-backtracking-ml** | doc-or-data | **NO** | bind names to bands or downgrade (proof-theater row) |
| **bmf-choice-receipts** | Form-recipe | **NO** | name 3-kernel BMF/node op family in-file |

## channel — 68
| file | grammar | aligned? | rework |
|---|---|---|---|
| channel | Form-recipe | yes | split relational cells from transport; name host-io |
| channel-interface | Form-recipe | yes | modes → typed-token enum (strongest file) |
| channel-flow / channel-loopback | Form-recipe/mixed | yes | tagged composites vs positional lists |
| **channel-protocol-choice-floor** | doc-or-data | **NO** | derive status; compost frozen validation log |
| channel-query / -json | Form-recipe | yes | fix fingerprint docstring; finish json-to-response |
| channels-registry / guidance-channel / iching / zodiac / ifs / celestial-pole / cjk | Form-recipe | yes | none — template sub-family |
| gematria / sanskrit / shamballa / shamballa-light | Form-recipe | yes | keep four-way claim on decoder, channel layer 3-kernel |
| form-os-channel | Form-recipe | yes | channel logic (schema, four verbs, offer/ack lifecycle) is Form over storage-port, four-way; sqlite persistence is an honest host-io carrier whose C is generated from the schema recipe |
| speech-kernel-channel / llm-feature-channel-floor / tool-channel | doc-or-data/mixed | yes/some | prose→doc; rows→typed composites |
| **tool-channel-grammar** | mixed | **NO** | diagnose silent manifest absence; make phrases real |

## http + net — 62
| file | grammar | aligned? | rework |
|---|---|---|---|
| kernel-http | BML-high | yes | tag ints → named Blueprint NodeIDs (the spine) |
| http-render | BML-high | yes | four-way (http-render-band 63), data-driven status/MIME table |
| http-server | BML-high | yes | four-way (http-server-band 1023), one value vocabulary end to end |
| http-request | BML-high | yes | four-way (http-request-band 63), lifts lexer parts to kh-request |
| http-adapter | BML-high | **NO** | track alist-bridge as closing recipe (compat tissue) |
| http-parse | BML-high | yes | four-way (http-parse-band 11): emits kh-header parts as values, no node detour |
| http-socket | BML-high | yes | name socket host-io 3-kernel in evidence |
| **http-serve** | mixed | **NO** | **compost (superseded engine); move fanout to kh-serve** |

## host-os + IO + tool-channel — 62
| file | grammar | aligned? | rework |
|---|---|---|---|
| host-kernel-cell | Form-recipe | yes | 3-kernel only named in-file (walk_recipe + write/read_form_binary); crosses when those ops join fkwu |
| kernel-satsang | Form-recipe | yes | 3-kernel only named in-file (walk_recipe + node projections + form-binary); lift to BML tagged constructors |
| kernel-core-self/-image | mixed | yes | 3-kernel only named in-file (BML source-scan + walk_recipe/native_blueprint + form-binary); promote proof→band when source-scan crosses |
| kernel-image-proposal | Form-recipe | yes | proposal is a tagged value over kernel-http vocabulary, serialized once by the http-render response carrier; asserted on structure (kh-tagged?/kh-field-value-or/children), four-way |
| kernel-http | BML-high | yes | carry socket-lifecycle parity to four-way |
| tool-channel | Form-recipe | yes | lift to BML section grammar |
| tool-channel-grammar | Form-recipe | yes | four-way registered (fks 255) |
| resource-port | Form-recipe | yes | route act/sense through indirect carrier dispatch |
| value-execution | Form-recipe | yes | optional BML tagged shape |
| capability-form-asm | Form-recipe | yes | extend per-op coverage |
| bml-capability-ledger | BML-high | yes | four-way registered (fks 255); drive status from manifest (sense, not declare) |

## BMF grammar engine — 58
| file | grammar | aligned? | rework |
|---|---|---|---|
| bmf-core / bmf-grammar | Form-recipe | yes | **four-way incl. fkwu** (the central lift, crossed — cursor + recursive grammar engine on the fourth arm) |
| bmf-mini | Form-recipe | yes | carries the grammar-swap bands; header names the crossed cursor |
| bmf-to-fk | Form-recipe | yes | 3-op ladder → data-driven op table |
| **bmf-choice-receipts** | Form-recipe | **NO** | re-root off engine.fk; magic scores → measured/open |
| dynamic-grammar-carrier | Form-recipe | yes | fold onto real pattern algebra once cursor crosses |
| **form-ontology-loader** | mixed | **NO** | generate ~250-name list from kernel bp generator |
| form-parse | Form-recipe | yes | retire for bmf-grammar OR shared op table |
| **grammar-chars** | Form-recipe | **NO** | converge onto bmf-grammar g-match (3rd engine) |
| http-parse / midi-bmf | Form-recipe | yes | express as grammar-as-data (hand-written now) |
| line-grammar | Form-recipe | yes | drop locally-redefined core primitives |
| runtime-grammar | BML-high | **NO** | push file IO to carrier; re-root off engine.fk |
| **tool-channel-grammar** | Form-recipe | **NO** | make phrases real grammar or rename to -decls |
| prolog/python/typescript-bmf-eval, python/typescript-bmf-lift | Form-recipe | yes | data-table dispatch; share interpreter core; track 4-way |

## BML + source-compiler — 58
| file | grammar | aligned? | rework |
|---|---|---|---|
| bml.fk | BML-high | yes | make sole front-end; add executing four-way band |
| **source-compiler** | mixed | **NO** | **delete ~500-line hand scanner; drive bml.fk+engine.fk** |
| bml-source | mixed | yes | move hand-parsers onto grammar |
| bml-route-choice-runtime / -native-mutable-locals / -native-source-control / -native-interface-package-import / translation-engine | Form-recipe | yes | four-way floors; wire bml.fk to drive them |
| **engine.fk** | Form-recipe | **NO** | add owning four-way band; route bml.fk through it |
| **emit-engine** | Form-recipe | **NO** | wire a caller + round-trip band, or compost (inert) |
| **compiler** | mixed | **NO** | compost descriptive picture/future-lang rows |
| **compiler-lens** | BML-high | **NO** | attach to real surface w/ band, or fold accessors |
| bml-capability-ledger | BML-high | yes | recognize as doc-or-data; point claims at manifest |


## North-star alignment — where the surface holds the line and where it drifts

WHERE THE SURFACE HOLDS THE LINE. The body genuinely embodies its north star in identifiable cornerstones. (1) Content-addressing is EXECUTED, not asserted: gematria/sanskrit/shamballa channels run node_eq class membership and recursive derivation; resource-port interns ports so (direction,value-shape) identity = substitutability; offers-in-flight makes the offer NodeID the concurrency primitive with no host-ported registry. (2) One-engine-cases-as-data is real where it matters: guidance-channel + channels-registry (one resolver, systems as rows), storage-port (backend-as-data, one substitutability test over memory/file/db), learning-style-space and geometric-learning (styles/biases as data), kernel-http's data-oblivious quantizer router. (3) Oracle-as-teacher is codified verbatim: lowering-conviction (semantic-equivalence the only hard gate, byte-identity only for encoders, smaller-than-oracle is a WIN), capability-form-asm (native MATCHES clang by execution exit-code then retires it). (4) Carrier-last holds in the strong families: oracle-ensure (brain-Form/hands-host-io), tool-channel (plans, never executes), the native-asm .sh files are named carriers only. (5) The lever works: Form-recipe tree -> arm64/ELF/Mach-O bytes with zero clang, proven four-way including fkwu; ll-* leaves were self-authored by close-next via local oracle with zero remote tokens.

WHERE IT DRIFTS. (a) HIGHEST-GRAMMAR GAP is pervasive — almost the entire surface sits at raw Form-recipe (defn/if/list) when BML/domain-grammar is the highest available; structural-composition (typed records, TypedTokenRef, SEQUENCE) is met almost nowhere, so flat positional nth-tuples and string-eq tags are the body-wide norm. Only kernel-http, bml.fk, sovereign-boundary-protocol, and a few BML-authored ledgers reach the top tier. (b) CARRIER-AS-BODY: resource-port hardwires file IO inside drivers it promises are swappable — the remaining cell where the host call lives inside the swap point. (form-os-channel and kernel-image-proposal are Form recipes over their carriers — four-way, structure-asserted, with host emission generated from the recipe.) (c) HARDCODED SPECIAL-CASES / PLACEHOLDERS: the ll-* leaves are frozen single-instruction wrappers (sp=31, imm=16 baked) not a memory model; flt-bp-node is a 31-arm hand-keyed NodeID table; form-ontology-loader hand-lists ~250 coordinates; tool-channel-grammar holds parse-phrases as inert doc-strings. (d) PROOF-THEATER: form-control-backtracking-ml's four-way row proves only 'return strings'; oracle-distillation fixtures carry invented magic numbers; channel-query's fingerprint docstring describes an unrun sha256-fold; roadmap.fk asserts 'done' with no evidence link; the BML compiler's COMPILED OUTPUT crossing four-way is presented as the COMPILER crossing (it runs Go-only). (e) FOUR-WAY HOLES on the most load-bearing cells: the host-OS kernel carriers (host-kernel-cell/kernel-satsang) are walled off fkwu on walk_recipe + the .fkb form-binary pair, and were SILENTLY absent — the precise shape CLAUDE.md forbids. (The principled BMF cursor crosses — bmf-core/bmf-grammar four-way incl. fkwu, intern_node_at lifted via the fourth-shim's content-addressed image.) (f) PARALLEL PATHS: two BML front-ends, 3+ grammar cursor engines, two HTTP servers, two cache trust axioms. The honest verdict: the body's IDEAS are north-star; its PROOF and ALTITUDE lag the ideas, and the lag is concentrated in the grammar/compiler/host-OS spine — the very cornerstones that should be strongest.
## Floor — what the manifest and headers owe reality

The manifest (form/fourth-arm-bands.txt, ~335 four-way rows) is the floor source and is largely accurate — but several concrete updates are owed so the body's self-attestation matches reality:

HOST-OS BANDS RESOLVED: the host-OS surface bands cross four-way — tool-channel-grammar (fks 255) and bml-capability-ledger (fks 255), both int/string/list ops the same family four-way tool-channel rides. Their kernel carriers are 3-kernel-only with the exact op named in each file header: host-kernel-cell and kernel-satsang on walk_recipe (execute an interned recipe) + write_form_binary/read_form_binary (.fkb host-io image) + node_children/node_value projections; kernel-core-self and kernel-core-image add broad BML source-scan + native_blueprint. The flattener has no flt-ops row for these, so fkwu lowers each to its literal-0 fallback (a degraded value, not a wrong computed one) — unsupported op families, standing walls, kept out of the manifest until those ops join the fourth arm. kernel-image-proposal (fks 111111) and form-os-channel (fks 111111) cross four-way as Form recipes over their carriers. The http server value stack is registered four-way: http-render (63), http-parse (11), http-request (63), http-server (1023). ADD ROWS still owed: substrate-phase (its primitives already cross as cache-phase's prelude).

FIX STALE UNDERSTATEMENTS (headers say 'three-way' while the manifest proves four-way — retune to match the floor): substrate-core.fk, memory-phases.fk, and 15 learning files (active-inference, classifier-eval, co-learning-stream, learned-primitive, nearest-shape, predictor-train, self-grounding-classifier, sequence-predictor, colearning-retire, learning-arc, predictor-sampling, trust-weighted-colearning, champion-challenger, learning-trend, metabolic-learning — verified on disk). Add the missing '; Proven by: ... (four-way)' line to autodiff-gradient.fk.

NAME THE HONEST 3-KERNEL BOUNDARIES IN-FILE (real unsupported-op walls, currently silent): embedding-as-recipe (node/substrate ops), learning-style-space (diagnose the higher-order-functions-in-data shape — either cross or name the exact op; this is the one UNNAMED 3-kernel claim that is a correctness/honesty gate), the channel/sanskrit/gematria/shamballa transport wrappers (their DECODER grammars are four-way; only the channel layer is 3-kernel by node/host-io family — never let the channel inherit the grammar's verdict), bmf-choice-receipts, and storage-port-db (pg_* Rust-only by design — already named).

DOWNGRADE THE SEMANTICALLY-VACUOUS ROW: form-control-backtracking-ml's 65535 four-way row proves only 'return a list of strings crosses four kernels' — either bind each named primitive to its proving band (verified index) or move to a .form north-star cell.

STOP DUPLICATING THE FLOOR: channel-protocol-choice-floor.fk hand-mirrors ~18 sibling 'proven-four-way' verdicts as string literals that can silently drift — derive status from fourth-arm-bands.txt instead. The real BMF cursor front-end now crosses the fourth kernel (bands bmf-core, bmf-grammar) alongside the tokenwise fold — the principled grammar engine is provable on fkwu. The cornerstone host-OS inversion remains the standing four-way hole.
## Biggest cross-cutting gaps

- FOUR-WAY COVERAGE on the most load-bearing cells. The host-OS inversion's surface bands cross (kernel-image-proposal, tool-channel-grammar, bml-capability-ledger four-way registered); its kernel carriers (host-kernel-cell on kernel-satsang, kernel-core-self/image) are 3-kernel-only on the walk_recipe + .fkb form-binary + broad-source-scan walls, with the exact op family named in each header — no longer silently absent. The real BMF front end (bmf-core/bmf-grammar g-parse cursor) crosses the fourth arm: the char_at/ord cursor rides the shim string stones, the parse emits universal recipes through the content-addressed intern arm, and intern_node_at rides the shim image of intern_node (same returned NodeID, attribution feeds only the framebuffer the verdict never reads). The http server value stack (http-parse, http-request, http-render, http-server) crosses four-way: http-parse emits the request's parts as kh-header values directly, so http-request lifts them into kh-request with no substrate-node detour, and the whole flow walks one vocabulary.
- PARALLEL PATHS / TWO ENGINES. BML has two front-ends (the principled bml.fk grammar vs a ~500-line hand-rolled string scanner in source-compiler.fk that the build actually runs — Go-only). The grammar family has at least three cursor/matcher engines (bmf-core/bmf-grammar, form-parse, grammar-chars) plus engine.fk under bmf-choice-receipts/runtime-grammar, and per-language lifters re-implement precedence climbing bmf-grammar already carries as data. http + net carries a superseded second server engine (http-serve.fk) on life-support with three live bands. storage has two cache files (cache.fk vs cache-phase.fk) that DISAGREE on the trust axiom.
- GRAMMAR ALTITUDE GAP — almost nothing is at the highest available grammar. The learning family (42 files), choice+backtrack (9), substrate (8), storage+ports (14), native-asm (11), and form-cli-core (19) are ALL uniformly raw Form-recipe (defn/if/list) when BML/domain-grammar is available; the structural-composition discipline (typed records, NamedField, TypedTokenRef, SEQUENCE) is met almost nowhere — flat positional nth-tuples and stringly-typed tags are the family-wide norm.
- PROOF-THEATER AND STALE PROOF CLAIMS. form-control-backtracking-ml returns string-LISTS naming choose/fail/cut and carries a four-way row (65535) that proves only 'return strings crosses four kernels'. SYSTEMATIC stale headers: 15 learning files + substrate-core + memory-phases say 'three-way at validate.sh' while the manifest proves them four-way (understatement drift). channel-protocol-choice-floor hand-mirrors ~18 sibling 'proven-four-way' verdicts as drift-prone string literals and freezes a per-agent validation-round journey-log. channel-query's cq-query-fingerprint docstring promises a sha256-fold the body (return node_inst) never runs.
- CARRIER-AS-BODY DRIFT. resource-port hardwires write_file_text/read_file inside its drivers despite a header promising swappable carriers — the remaining cell where a host call lives inside what claims to be the swap point. (form-os-channel and kernel-image-proposal are Form recipes over their carriers: the channel logic crosses four-way over the storage-port memory carrier with sqlite as an honest host-io carrier whose C is generated from the schema recipe; the proposal is a tagged value serialized once by the kernel-http response carrier, asserted on structure.)
- HARDCODED PLACEHOLDERS / FROZEN INSTANCES on the overnight path. The ll-* memory leaves (alloc16/store-w8/load-w9/free16) are four frozen single-instruction wrappers with baked registers/offsets (sp=31, imm=16, w8/#8, w9/#12), not the composed ll-buffer memory model the roadmap itself names as open. form-flatten's flt-bp-node is a 31-arm hand-keyed literal NodeID table self-admitted as 'follow-on lift'. jit-tensor-emit assembles kernels as ~60-deep str_concat ladders. roadmap.fk asserts G0..G7 'done'/'open' with no link to evidence — it can claim done for something that regressed.
- DUPLICATED / UNWIRED VOCABULARY AND LOGIC. The four membrane surfaces are copied verbatim into form-cli-sample; teacher-state strings ('installed'/'source-pending'/'absent') are triplicated across gaps/oracle-ensure/oracle-catalog; int->string is re-rolled in 9+ stdlib files; SQL escape/contains helpers re-rolled across four storage carriers; a covers+covers double-walk majority idiom recurs across predict/score/judge/review-gap. The python `ask` route (form_cli.py:1025) does NOT call the four-axis fcr-route — a latent second router. trust/confidence notions exist twice in form-cli (router axis vs loop fcl-confidence) without one folding into the other.

## Open rework plan (the cornerstone investment)

### [HIGH] Generalize the frozen ll-* leaves to ll-alloc(n) / ll-store(rt,off) / ll-load(rt,off) / ll-free(n) and compose them into the ll-buffer memory model the roadmap names as open

- **Why:** OVERNIGHT CORNERSTONE. The four ll-* files (alloc16/store-w8/load-w9/free16) are frozen single-instruction wrappers with baked literals (sp=31, imm=16, w8/#8, w9/#12) — verified on disk: alloc16 () (fa-sub-x-imm 31 31 16). They are a valuable close-next provenance artifact (native authored a four-way recipe, zero remote tokens) but NOT a memory model: nothing enforces matched alloc/free pairing or offset-consistent slots, and the 'memory model' is implicit across four files. This is the single most-pointed-at overnight gap.
- **Action:** Replace each leaf with a parameterized recipe (ll-alloc(n)->fa-sub-x-imm 31 31 n; ll-store(rt,off)->fa-str-w rt 31 off; ll-load(rt,off); ll-free(n)). Then author the composed ll-buffer recipe (sp alloc + typed pointers + matched alloc/free + offset-consistent slots) and add its four-way band. Keep the original frozen leaves only if a provenance band needs the exact close-next instance.

### [HIGH] Wire the four-axis router and confidence/trust as the SOLE decision path; fold the duplicate confidence notion

- **Why:** OVERNIGHT CORNERSTONE / UNWIRED TRUST. form-cli-router carries the one fitness formula over sovereignty/trust/capability/confidence with weights-as-data — exactly right — but the python `ask` route (form_cli.py:1025) bypasses it with a coarse library-has-it-else-oracle door, and form-cli-loop's fcl-confidence is a second 0..100 confidence notion that never folds into the router's confidence axis. Trust/confidence is computed but not the actual gate at the live carrier.
- **Action:** Make the python `ask` route call fcr-route (or its native runner equivalent) so the four-axis formula is the only router; unify fcl-confidence with the router's confidence axis into one confidence primitive feeding both the gate and the fitness scalar.

### [DONE 2026-06-18] The 7 host-os bands each end four-way-registered or 3-kernel-only with the exact op named

- **What landed:** Each of host-kernel-cell, kernel-satsang, kernel-core-self, kernel-core-image, kernel-image-proposal, tool-channel-grammar, and bml-capability-ledger was probed on the fourth arm. THREE cross and are registered (kernel-image-proposal fks 11111, tool-channel-grammar fks 255, bml-capability-ledger fks 255) — int/string/list family, 0 divergent. FOUR are 3-kernel-only on a real unsupported op family, named in each header: host-kernel-cell and kernel-satsang on walk_recipe + write/read_form_binary (kernel-satsang also node_children/node_value over a fresh image); kernel-core-self and kernel-core-image on broad BML source-scan host-io + walk_recipe/native_blueprint + the form-binary pair. The carried node/substrate floor (intern_node, node_eq, node_category, intern_trivial_int/string, bp) crosses; the flattener has no flt-ops row for the walled ops, so fkwu answers a literal-0-degraded value (25, 193 under probe) — a standing wall, not a divergence. Commit evidence: docs/system_audit/commit_evidence_20260618_host_os_fourth_arm_bands.json.
- **Remaining toward the native ideal:** host-kernel-cell/kernel-satsang/kernel-core-self/image cross when walk_recipe, the interned-node projections, the broad source-scan, and the form-binary carrier join the fourth arm; the proof files use the *-proof.fk convention and become *-band.fk when their ops cross.

### [CROSSED] The real BMF cursor (bmf-core/bmf-grammar g-parse) is on the fourth arm

- **What crossed:** The strongest north-star realization in the audit — one data-driven matcher, grammars-as-data, parsing-produces-recipes, no-sediment backtracking — is four-way proven incl. fkwu (bands bmf-core verdict 600, bmf-grammar verdict 300, 0 divergent). The string cursor's char_at/ord/substring ride the shim string stones (tags 24..29); the parse emits universal recipes through the content-addressed intern arm (intern_node tag 47, bp tag 45, trivial interns tags 43/46, make_nodeid tag 91). bmf-grammar's `intern_node_at` rides a fourth-shim image: `(defn intern_node_at (cat kids file line col) (intern_node cat kids))` — the returned NodeID is exactly the content-addressed intern, and the file/line/col attribution feeds only the framebuffer side-map, observer-side metadata no band verdict reads. This converts the BMF/dialect surface (bmf-core, bmf-grammar, bmf-to-fk, http-parse, the evals) toward provable; bmf-mini carries the grammar-swap bands (jit-lower-bmf / fourth-union / language-packs-fourth).

### [HIGH] Re-ground cache.fk on content-hash trust and the roadmap on real evidence; honor lowering-conviction's gate distinction everywhere

- **Why:** OVERNIGHT CORNERSTONE. lowering-conviction.fk is the clearest north-star cell — it codifies oracle-as-teacher: semantic-equivalence is the only hard gate, byte-identity ONLY for the encoder where one right answer exists, smaller/faster than the oracle is a WIN. But cache.fk trusts MTIME while its sibling cache-phase.fk explicitly teaches mtime-trust is wrong and content-hash is right (two cache files in one family disagreeing on the trust axiom, and cache.fk is the unproven one). roadmap.fk asserts 'done'/'open' with no link to ground truth — it can claim done for something that regressed.
- **Action:** Re-ground cache-fresh? on input-hash equality (cache.fk:33-39) and add a four-way band; derive roadmap step status from manifest rows / band presence instead of hand-edited literals; name lowering-conviction's four verdict codes (wrong/bloated/healthy/better) as constants so callers stop comparing bare 0/1/2/3.

### [DONE] Un-invert carrier-as-body: form-os-channel and kernel-image-proposal are Form/BML recipes over existing carriers

- **Shape now:** form-os-channel is a Form recipe — the schema (three composed relation kinds), the four verbs (init/state/offer/validate), and the offer/acknowledge lifecycle (offer-lane's axiom-5 OFFERED→GROUNDED ack) run over the storage-port contract; the SAME logic crosses four-way over the memory carrier (form-os-channel fks 111111) while sqlite/file are honest host-io carriers, and the table DDL the sqlite carrier needs is generated from the schema recipe (foc-emit-create) so there is one source and no baked divergence string. kernel-image-proposal is a tagged value tree over kernel-http's vocabulary — candidate image / mutation gate / trust envelope as nested tagged cells over kh-field rows — serialized once by the http-render response carrier (kh-serve-response); every assertion reads structure (kh-tagged?, kh-field-value-or, accessor children, kh-response-status), four-way (kernel-image-proposal fks 111111).
- **Remaining carrier-as-body:** resource-port hardwires file IO inside its swappable drivers (its own item).

### [HIGH] Resolve oracle-ensure / oracle-distillation proof grounding: drive native-vs-oracle gates over REAL captured corpus, not fixtures

- **Why:** OVERNIGHT CORNERSTONE. oracle-ensure.fk is exemplary brain-Form/hands-host-io separation — keep its shape. But oracle-distillation-learning's odl-*-receipt fixtures (lines 226-295) are invented magic numbers (token 900/160, quality 88/84) and the 'native beats oracle' gate runs over them — proof-theater risk. oracle-distill-corpus.fk already holds MEASURED 949-turn held-out counts and is the right exemplar. form-cli-model is a hand-frozen data cell with no band proving it matches the trainer's current output.
- **Action:** Drive odl-native-wins?/odl-c-ready? over real io-match / native-training-receipt rows (the oracle-distill-corpus pattern), move prose floor/north-star lists out of executable code; add a band that diffs form_cli_train_predict.sh output against the form-cli-model data cell so a stale model is caught. Single-source teacher-state strings across oracle-ensure/gaps/oracle-catalog.

### [MED] Collapse the duplicate engines: one BML front-end, one cursor engine, one HTTP server

- **Why:** Parallel paths violate the one-engine north star in three families at once. BML: bml.fk grammar vs the ~500-line hand-rolled scanner in source-compiler.fk that the build actually runs (Go-only, so neither front-end is four-way-proven as executing tissue — the proof-theater is the COMPILED OUTPUT crossing four-way being presented as the compiler crossing). Grammar: 3+ cursor/matcher engines + engine.fk. http: a superseded http-serve.fk on life-support with three live bands.
- **Action:** Delete the source-compiler.fk fsc-compile-form-bml-* scanner and drive form-source-compile through bml.fk+engine.fk to one Recipe tree; converge form-parse + grammar-chars onto bmf-grammar g-match (add not/peek/cut/multi-match/eol as data tags); compost http-serve.fk after moving its unique http-fanout relay into kh-serve.

### [DONE] http-parse emits request parts as kh-header values directly (no substrate node detour) — server value stack four-way

- **What landed:** http-parse is re-authored in BML as the lexer: it walks the wire bytes into the request's PARTS (method, full path, kh-header list, body) as plain values, interning nothing. http-request lifts those parts into kh-request (path/query split, query → kh-field). The intern_node/node_category wall is gone from the value path, so the whole server stack walks one vocabulary. http-render-band, http-parse-band, http-request-band, and http-server-band are registered four-way (63 / 11 / 63 / 1023). http-serve (the superseded engine) reads the same lexer parts + kernel-http's kh-header-value-or, shedding its own duplicate ascii-lower/header-value-ci helpers, and stays three-kernel only for its socket host-io. The fourth-arm stem resolver now anchors to form-stdlib/tests/ so a same-named sample (cross-modal 34-http-parse) cannot collide with a manifest band.
- **Remaining in family:** compost http-serve (superseded engine), move its fan-out relay into kh-serve; track http-adapter's alist bridge as a closing compat recipe.

### [MED] Generate flt-bp-node and the form-ontology-loader name-list from the shared BP table; lift jit-tensor-emit string assembly to a template grammar

- **Why:** form-flatten's flt-bp-node is a 31-arm hand-keyed literal NodeID table — the native-asm family's ONLY true admitted placeholder, the one spot where fkwu's NodeID identity is hand-keyed not derived. form-ontology-loader hand-lists ~250 dialect-binding coordinates as a string mega-literal. jit-tensor-emit assembles model kernels as ~60-deep str_concat ladders (correct but inert carrier tissue).
- **Action:** Generate flt-bp-node and the form-ontology-loader dialect-binding list + engine-constant rows from the SAME generator that emits the kernel bp table (one source of truth); introduce a small emit/template grammar with named holes (el/ac/fname) for jit-tensor-emit kernel bodies.

### [MED] Resolve form-control-backtracking-ml proof-theater and the stale/duplicated proof claims across the body

- **Why:** form-control-backtracking-ml returns string-lists naming choose/fail/cut and carries a four-way row (65535) that proves nothing about backtracking — an unproven claim dressed as covered coverage. 15 learning files + substrate-core + memory-phases carry stale 'three-way' headers while proven four-way. channel-protocol-choice-floor hand-mirrors ~18 'proven-four-way' verdicts (drift) and freezes a journey-log. channel-query's fingerprint docstring overclaims.
- **Action:** Bind each named backtracking primitive to the band that proves it runs four-way (verified index) or move the prose to a .form north-star cell; sweep the 'three-way'->'four-way' headers; derive channel-protocol-choice-floor status from fourth-arm-bands.txt and compost its validation-round log; fix or rewrite cq-query-fingerprint.

### [LOW] Core-lift the duplicated low-level helpers and the covers+covers majority idiom into shared cells

- **Why:** int->string is re-rolled in 9+ stdlib files (the '0123456789' substring trick); SQL escape/quote/contains? re-rolled across cell-log-store/graph-node-port/application-graph-node-port/storage-port-db (headers admit it); a covers+covers double-walk majority idiom recurs across predict/score/judge/review-gap. This is the exact 'repeated low-level shape wants to become a reusable teaching' the core-lift north-star names.
- **Action:** Add one int->str and one parse-int/contains?/escape codec module to core.fk and prelude it from every carrier; add a single-walk majority?/ge2x helper and replace the covers+covers idiom everywhere.

### [LOW] Lift flat positional tuples + stringly-typed tags to typed composites family-wide, starting with choice-receipt

- **Why:** The structural-composition discipline (compose, never flat; TypedTokenRef capabilities) is met almost nowhere: flat nth-tuples and string-eq tags are the norm across learning, choice, channel, storage, protocol, host-os. choice-receipt.fk is the keystone every other choice file accessors-through; lifting it raises the family and turns documented content-addressing into enforced content-addressing. Two tag conventions (integer CR-TAG vs string literals) coexist inside the choice family.
- **Action:** Lift choice-receipt's record family (and branch-choice-order / choice-outcome-learning tuples) to BML typed records with integer Blueprint tags bound to user-blueprint-registry.md cell-refs; promote tc-tool/tc-protocol capabilities to TypedTokenRef so an unknown capability is unrepresentable; unify the choice family on one tag convention.

