# BMF bootstrap floor — minimum closure vs releasable tissue

What the BMF/BML source-compile **actually reaches**, measured over the pinned,
self-contained bootstrap `.fkb` (the 8 source-compile preludes bundled into one
artifact, #2587). The instrument is [`form/form-stdlib/reachability.fk`](../../form/form-stdlib/reachability.fk)
— a Form-native transitive-closure walk, sibling to `name-check.fk`. Regenerate
this manifest any time with `scripts/bmf_bootstrap_audit.sh --names`.

## Tiers (snapshot 2026-06-08)

| tier | count | meaning |
|------|-------|---------|
| **FLOOR** | 146 | reached from the compile entry (`fsc-compile-section-recipe`) — the **minimum to compile any BMF/BML section**: parse (`g-parse` + the grammar) + emit (`fsc-rec-*` + ontology category mapping). Covers both the high-level and BMF paths. |
| **STORE** | 91 | reached from setup/runtime entries but not the compile entry — the ontology load (incl. the json parser, reached as a higher-order callback) + the runtime the emitted recipe needs. **FLOOR + STORE = 237 = must-store** for a working, self-contained bootstrap. |
| **RELEASABLE** | 265 | reached from **no** entry — candidate old bootstrap tissue to compost. |
| total | 502 | every defn the bootstrap currently bundles. |

## A real gap this audit caught (and the walk now handles)

The first run marked the entire `json-*` parser RELEASABLE — but the ontology loader
*uses* it (33 refs) to parse `form-ontology.json` on a cold cache. The walk had missed
it: `parse-json` is passed to `read_with_cache` as a **higher-order callback**, invoked
via that function's param, so collecting only the callee stranded `parse-json` (and all
of json-*) as falsely-releasable. Verification (a grep of the loader) caught it before
any release; the walk was then fixed to seed reachability from an executed form's *full*
reference set, including higher-order arguments. That moved 26 defns RELEASABLE→STORE
(291→265). **This is why the caveat below is load-bearing, not ceremony.**

**Caveat — the honest bound.** The walk is *static*. It now follows higher-order
arguments, but a function STORED in a variable and called later is still missed. So the
265 are **candidates**: verify dynamic/indirect references per-defn before composting.
(Example still to confirm: `json-value` is RELEASABLE — parse-json doesn't use that
accessor — but confirm no other indirect caller before dropping it.)

## Toward the north-star compiler

The minimum is small — ~146 recipes for parse + emit. That is the core to rewrite as the
streaming, cursor-based, recipe-emitting compiler: generic (data-driven over the grammar),
blazing fast, and leaning on the kernel's **content-addressing** so that multiple parse
branches are an order of magnitude cheaper — shared sub-recipes intern once, discarded
branches cost nothing (GC'd, never copied), overlapping branches memoize for free.
Releasing the 265 clears the field; the pinned bootstrap (#2587) lets the core be swapped
under a stable artifact without stdlib-drift.

## FLOOR — the minimum to compile any section (146)

  append bmf-unescape-str bmf-unescape-str-loop bml-grammar bp chain-incdec? cp-in-class? 
  cur-advance cur-eof? cur-peek cur-pos cur-slice cur-surface cur-win2 cursor-of cursor-str 
  fol-row5->nodeid fol-table-lookup fsc-bmf-section-recipe fsc-capture-fn 
  fsc-compile-section-recipe fsc-dialect-fn fsc-empty? fsc-find-char-from 
  fsc-find-string-from fsc-high-level-form-dialect? fsc-line-end fsc-line-next fsc-lit-fn 
  fsc-pattern-item-recipe fsc-pattern-items-recipes fsc-read-part-end fsc-read-quoted-end 
  fsc-rec-call fsc-rec-do fsc-rec-ident fsc-rec-let fsc-rec-list-of fsc-rec-string fsc-rev 
  fsc-rev-into fsc-rtrim-index fsc-rule-line-recipe fsc-rules-recipes-loop 
  fsc-skip-rule-line? fsc-skip-spaces fsc-space? fsc-sub fsc-trim fsc-word-char? 
  fsc-word-loop? fsc-word-start-char? fsc-word? g-build g-caps g-cur g-kids g-match 
  g-match-rule g-no g-ok g-ok? g-parse g-rule g-rule-find g-rules g-start g-val gc-empty 
  gc-get gc-put gen-scan gm-alt gm-args gm-args-loop gm-call-suffix gm-cap gm-chain 
  gm-chain-loop gm-char gm-cls gm-infix gm-infix-climb gm-infix-loop gm-lit gm-num 
  gm-num-frac gm-num-int gm-opt gm-q-scan gm-ref gm-rep gm-rep-loop gm-run gm-run-loop gm-sep 
  gm-sep-loop gm-seq gm-str gm-ternary grammar infix-peek-op is-alpha-cp is-digit-cp 
  is-ident-cont-cp is-ws-cp nil? nlist nlist-items nth p-cap p-chain p-char p-infix p-lit 
  p-num p-opt p-ref p-rep p-run p-sep p-str p-ternary r3-pat r3-tpl reverse-acc 
  reverse-acc-loop rok-cur rok-node rok? rule3 skip-block-comment skip-line-comment skip-ws 
  surf-kind surf-len surf-payload surface-string t-const t-const-bool t-const-int t-emit 
  t-splice t-splice-int t-splices unit 

## STORE — ontology load (incl. json via higher-order) + emitted-recipe runtime (91)

  cache-fresh? fol-3to5-loop fol-all-dialect-lets fol-all-dialect-lets-loop 
  fol-all-engine-defns fol-all-engine-defns-loop fol-append fol-build-row fol-build-rows 
  fol-build-rows-loop fol-cat fol-concat-acc fol-dialect-cat-let fol-dialect-cat-lets-loop 
  fol-dialect-lets fol-engine-entries-loop fol-engine-entry-body-factory 
  fol-engine-entry-body-string fol-engine-entry-defn fol-engine-family-defns fol-rec-call 
  fol-rec-fndef-0 fol-rec-let fol-rec-make-nodeid fol-user-alias-rows fol-user-rows-for 
  fol-user-rows-loop form-cat-node form-prim-node form-row-inst form-row-type 
  form-source-compile-file form-source-compile-loop form-source-compile-text 
  form-table-lookup fsc-compile-section fsc-last-char-index fsc-line-opens-block? fsc-q 
  fsc-quote-loop fsc-section-end fsc-section-end-depth fsc-source-dialect 
  fsc-source-emit-call fsc-source-emit-join fsc-source-emit-list fsc-source-emit-list-loop 
  fsc-source-emit-params fsc-source-emit-params-loop fsc-source-emit-recipe 
  fsc-source-primitive-name fsc-source-primitive-name-loop json-array-elements json-int-value 
  json-is-digit-cp json-is-digit-or-minus-cp json-mk-pair-r json-mk-tok json-next-token 
  json-object-get json-object-get-loop json-object-has-loop json-object-has? 
  json-object-pairs json-pair-key json-pair-pos json-pair-r json-pair-value json-parse-array 
  json-parse-array-elements json-parse-object json-parse-object-pairs json-parse-value 
  json-reverse-acc json-reverse-acc-loop json-scan-literal json-scan-number 
  json-scan-number-end json-scan-string json-scan-string-end-loop json-scan-string-end-pos 
  json-scan-string-loop json-skip-ws json-string-value json-substr json-tok-kind 
  json-tok-start json-tok-val json-token-end parse-json read_with_cache 

## RELEASABLE — candidate old bootstrap tissue (265) — verify indirect refs before composting

  apply-form-action-bmf-rule build-emit build-kids build-tpl caps-add caps-empty caps-get 
  cur-checkpoint cur-peek-char cur-restore cursor-file find-from find-loop 
  form-action-bmf-call form-action-bmf-call0 form-action-bmf-call1 form-action-bmf-call2 
  form-action-bmf-call3 form-action-bmf-call4 form-action-bmf-call5 form-action-bmf-def 
  form-action-bmf-do-roundtrip form-action-bmf-do-source form-action-bmf-find-rule 
  form-action-bmf-ident form-action-bmf-if form-action-bmf-int form-action-bmf-let 
  form-action-bmf-program form-action-bmf-proof-score form-action-bmf-roundtrip-program 
  form-action-bmf-rules form-action-bmf-string form-action-bmf-value form-prim-or-empty 
  fsc-action-args fsc-action-call-node fsc-action-cap fsc-action-do-node fsc-action-emit-call 
  fsc-action-emit-def fsc-action-emit-do fsc-action-emit-ident fsc-action-emit-if 
  fsc-action-emit-int fsc-action-emit-let fsc-action-emit-string fsc-action-expr 
  fsc-action-ident-node fsc-action-if-node fsc-action-int fsc-action-items 
  fsc-action-keyword? fsc-action-kw fsc-action-let-node fsc-action-name fsc-action-name-char? 
  fsc-action-name-kind fsc-action-op fsc-action-param-block fsc-action-param-nodes 
  fsc-action-params fsc-action-scan-int fsc-action-scan-int-loop fsc-action-scan-name 
  fsc-action-scan-name-loop fsc-action-scan-next fsc-action-scan-op fsc-action-scan-skip 
  fsc-action-scan-string fsc-action-scan-string-loop fsc-action-source-span 
  fsc-action-src-args fsc-action-src-expr fsc-action-src-int fsc-action-src-items 
  fsc-action-src-kw fsc-action-src-name fsc-action-src-op fsc-action-src-params 
  fsc-action-src-string fsc-action-string fsc-bmf-lower-node fsc-bmf-roundtrip-node-eq? 
  fsc-bmf-source-node-eq? fsc-capture-expr fsc-contains? fsc-digit? fsc-file-source-cursor 
  fsc-file-source-cursor-window fsc-find-char-from-len fsc-find-string-at-len? 
  fsc-find-string-at? fsc-find-string-from-len fsc-float-body? fsc-float-dot-loop? fsc-float? 
  fsc-int-loop? fsc-int? fsc-lens-roundtrip-anchor-eq? fsc-lens-roundtrip-node-eq? 
  fsc-list-append fsc-literal-expr fsc-prefix? fsc-rec-append-rev fsc-rec-false fsc-rec-fndef 
  fsc-rec-form-call fsc-rec-if3 fsc-rec-param-trivials fsc-rec-string-list 
  fsc-rec-string-list-items fsc-rec-true fsc-repo-binary-document 
  fsc-repo-binary-document-byte-count fsc-repo-binary-document-structure fsc-repo-corpus 
  fsc-repo-corpus-files fsc-repo-corpus-name fsc-repo-corpus-total-bytes fsc-repo-document 
  fsc-repo-document-kind fsc-repo-document-size fsc-repo-document-spans 
  fsc-repo-document-structure fsc-repo-empty-spans fsc-repo-field-int fsc-repo-field-key 
  fsc-repo-field-node fsc-repo-field-string fsc-repo-field-value fsc-repo-field-value-int 
  fsc-repo-field-value-string fsc-repo-file fsc-repo-file-byte-count fsc-repo-file-from-bytes 
  fsc-repo-file-from-text fsc-repo-file-kind fsc-repo-file-media-type fsc-repo-file-path 
  fsc-repo-file-sensed fsc-repo-meaning fsc-repo-meaning-decoder fsc-repo-meaning-fields 
  fsc-repo-text-document fsc-repo-text-document-line-count fsc-repo-text-document-lines 
  fsc-repo-text-document-structure fsc-repo-text-line fsc-repo-text-line-end 
  fsc-repo-text-line-end-col fsc-repo-text-line-end-line fsc-repo-text-line-length 
  fsc-repo-text-line-number fsc-repo-text-line-start fsc-repo-text-line-start-col 
  fsc-repo-text-lines fsc-repo-text-lines-loop fsc-rule-ref-expr fsc-scan-result 
  fsc-scan-result-cursor fsc-scan-result-object fsc-source-advance-n fsc-source-corpus 
  fsc-source-corpus-files fsc-source-corpus-name fsc-source-cursor fsc-source-cursor-advance 
  fsc-source-cursor-char fsc-source-cursor-col fsc-source-cursor-end? 
  fsc-source-cursor-file-prefix? fsc-source-cursor-file-window? fsc-source-cursor-file? 
  fsc-source-cursor-line fsc-source-cursor-next fsc-source-cursor-offset 
  fsc-source-cursor-prefix? fsc-source-cursor-range fsc-source-cursor-slice 
  fsc-source-cursor-source fsc-source-cursor-source-len fsc-source-cursor-window 
  fsc-source-cursor-window-contains? fsc-source-cursor-window-start 
  fsc-source-cursor-windowed fsc-source-cursor-with-len fsc-source-dialect-eof-kind 
  fsc-source-dialect-int-kind fsc-source-dialect-keyword-kind fsc-source-dialect-keywords 
  fsc-source-dialect-name-kind fsc-source-dialect-op-kind fsc-source-dialect-ops 
  fsc-source-dialect-string-kind fsc-source-file fsc-source-file-kind fsc-source-file-path 
  fsc-source-file-sections fsc-source-match-op fsc-source-name-char? fsc-source-name-kind 
  fsc-source-name-start-char? fsc-source-object fsc-source-scan-int fsc-source-scan-int-loop 
  fsc-source-scan-name fsc-source-scan-name-loop fsc-source-scan-next 
  fsc-source-scan-next-dialect fsc-source-scan-op fsc-source-scan-skip fsc-source-scan-string 
  fsc-source-scan-string-loop fsc-source-section-binary fsc-source-section-binary-node 
  fsc-source-section-dialect fsc-source-section-node-eq? fsc-source-section-rule-name 
  fsc-source-section-source fsc-source-window-size fsc-string-list-contains? 
  fsc-string-to-bytes fsc-string-to-bytes-len-loop fsc-strip-semi is-blank? json-array-length 
  json-count-line json-is-ws-cp json-object-keys json-object-keys-loop line-num line-text 
  lines-from-source lines-loop m-caps m-cur m-no m-ok m-ok? match-alt match-cap match-cls 
  match-lit match-opt match-pat match-run match-run-loop match-seq pick-min rule-of rule-pat 
  rule-tpl run-cur run-node run-ok? run-rule split-on split-on-loop starts-with-keyword? 
  starts-with? surface-file trim trim-leading-ws trim-trailing-ws 
