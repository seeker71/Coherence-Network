---
idea_id: agent-cli
status: active
source:
  - file: form/form-stdlib/rag-index-codec.fk
    symbols: [ric-node-id, ric-grounding-ready?, ric-emit-grounded]
  - file: form/form-stdlib/rag-retrieve.fk
    symbols: [rag-admitted?, rag-overlap, rag-best-overlap]
  - file: form/form-stdlib/rag-ask.fk
    symbols: [ra-select-hit, ra-grounded-at, ra-output-answer-binds-hit?]
  - file: form/form-stdlib/form-cli-staged-trace.fk
    symbols: [fcast-persistence-bound?, fcast-certificate-valid-at?, fcast-trace-hit-at]
  - file: form/form-stdlib/form-cli-ask-gate.fk
    symbols: [fca-ask-trace-row]
  - file: form/form-stdlib/form-freq-check.fk
    symbols: [fc-check, fc-semantic-reading, fc-certified-form-reading]
  - file: bin/form-cli
    symbols: [ask_native_local]
  - file: scripts/form_cli_rag.py
    symbols: [semantic_embed, retrieve, verify_grounding, verify_frequency_certificate]
  - file: scripts/form_first_offline_setup.sh
    symbols: [offline body bootstrap]
  - file: scripts/coh_substrate.py
    symbols: [substrate bootstrap command]
  - file: api/tests/test_form_cli_grounding_runtime.py
    symbols: [grounding runtime acceptance]
requirements:
  - "A grounded answer carries a real substrate NodeID that resolves to the cited cell; a path or prefix alone never counts"
  - "Fresh setup populates the local substrate and its derived retrieval index or fails visibly; zero-cell success is forbidden"
  - "The retrieval cache stores node_id and source_path separately, is schema-versioned, and retrieves paraphrases through native ranking"
  - "Default form-cli ask uses one kernel result whose path, grounding, frequency, and sufficiency signals are computed independently"
  - "OBSERVED is emitted only when all four executable signals pass; unknown frequency stays explicit and can never be promoted by a shell constant"
  - "Persistent witness observations, including deployment state, consume the working grounding plane rather than defining a special-case proof path"
done_when:
  - "A fresh temporary home bootstraps to cells_total > 0 and every indexed grounded entry contains a resolvable @p.l.t.i NodeID"
  - "Exact and paraphrased questions return the intended body cell while stale, unresolved, tampered, and path-only entries remain ungrounded or insufficient"
  - "The default ask carrier renders the kernel's independently-derived trust result and has no hardcoded grounded, frequency, sufficiency, or OBSERVED values"
  - "A persisted live observation is queryable by NodeID and a stale or mismatched deployment observation cannot pass sufficiency"
  - "Focused kernel bands, consumer tests, spec gate, worktree guard, CI, deployment, and a public native ask all pass"
test: "cd form && for band in form-stdlib/tests/rag-embed-band.fk form-stdlib/tests/rag-index-codec-band.fk form-stdlib/tests/rag-retrieve-band.fk form-stdlib/tests/rag-ask-grounded-band.fk form-stdlib/tests/rag-heal-grounding-band.fk form-stdlib/tests/form-freq-check-band.fk form-stdlib/tests/trust-row-band.fk form-stdlib/tests/form-cli-sufficiency-band.fk form-stdlib/tests/form-cli-ask-band.fk form-stdlib/tests/form-cli-staged-trace-band.fk form-stdlib/tests/form-cli-band.fk; do ./validate.sh \"$band\" || exit; done && cd .. && api/.venv/bin/pytest -q api/tests/test_form_cli_grounding_runtime.py"
constraints:
  - "Working behavior lands before evidence records; evidence records document executed proof and never supply trust booleans"
  - "Form owns identity, ranking, trust decisions, and observation composition; host code only carries filesystem, model, network, time, and persistence boundaries"
  - "No deployment-keyword shortcut, source-path grounding, exact-query fixture, hardcoded trust signal, or self-authored observed flag"
  - "Reusable kernel changes land in coherence-kernel first and reach Coherence Network only through the form submodule gitlink"
---

# Spec: Form CLI Grounded Observation Plane — the body resolves, judges, and witnesses its own answers

## Purpose

`form-cli ask` currently has the vocabulary of grounding without a complete working
grounding path: its cache identifies source paths, its live lookup favors exact text,
and host wrappers can manufacture trust fields. This change makes grounding and
observation executable properties of the general answer path. Deployment becomes one
ordinary observed subject after the mechanism works, not a special receipt that hides
the missing core.

## Requirements

- [ ] **R1 — NodeID identity:** Each retrieval entry separates immutable `node_id`
  from mutable `source_path`. The grounding gate parses and resolves the NodeID against
  the substrate before setting `grounded=yes`.
- [ ] **R2 — body comes home:** Offline setup ingests the repository body, builds the
  derived retrieval projection, validates non-zero counts and resolvability, and exits
  non-zero on failure. It is safe and idempotent in a fresh home.
- [ ] **R3 — semantic native retrieval:** The live native ask path uses the existing
  Form embedding/ranking recipes for paraphrases. Exact substring search may be a fast
  candidate source, never the only retrieval rule.
- [ ] **R4 — one independent trust result:** Answer path, grounding, frequency, and
  sufficiency are distinct inputs to one Form result. A miss records a native attempt
  but never claims the body answered.
- [ ] **R5 — honest frequency:** A calibrated semantic signature may pass the general
  frequency head. A deterministic body renderer may pass only with a content-bound,
  independently validated certification. Missing evidence is `unknown`, never an
  implicit `no` or a hardcoded `yes`.
- [ ] **R6 — observation:** `OBSERVED` remains the all-four composite. Evidence-level
  observations are also first-class WITNESS cells, so a live fact can be observed and
  grounded even when arbitrary generated prose still has unknown frequency.
- [ ] **R7 — persistent consumers:** Post-deployment verification persists expected
  and actual SHA, route result, source hashes, observer, observed time, and expiry as
  composed witness cells. Health exposes the current receipt NodeID, and ask retrieves
  it through the same general lattice/index path.
- [ ] **R8 — no-shortcuts proof:** Tests mutate every trust input independently and
  cover unresolved IDs, stale evidence, mismatched SHAs, blocked reports inside green
  jobs, paraphrased questions, and fresh-home operation.

## Data Model

```yaml
RagEntry:
  schema: nodeid-rag-v1
  node_id: "@package.level.type.instance" # stable NamedCell REF
  content_node_id: "@package.level.type.instance" # current immutable CTOR
  source_path: string
  kind: string
  content_key: string
  embedding_kind: form-semantic-v2
  snippet: string
  vector: [first_hash, second_hash, ...] # unique adjacent pairs per semantic feature

AskTrust:
  answer_path: native | oracle | miss
  grounding: resolved NodeID | unresolved
  frequency: yes | no | unknown
  sufficiency: yes | no
  observed: boolean

DeploymentWitness:
  schema: deployment-witness-v1
  node_id: "@1.1.9.<cell_id>"
  content_node_id: NodeID
  expected_sha: git_sha
  actual_sha: git_sha
  health_route: /api/health
  health_status: integer
  health_result: string
  kernel_runtime: inline | subprocess
  health_body_json: canonical_json
  health_body_sha256: sha256
  observer: deploy-host-local-http-probe
  observed_at: utc_timestamp
  observed_epoch: integer
  expires_at: utc_timestamp
  expires_epoch: integer
  result: success
```

## Files to Create/Modify

- `form/form-stdlib/rag-embed.fk`, `rag-index-codec.fk`, `rag-retrieve.fk`, and
  `rag-ask.fk` — canonical semantic-v2 retrieval, strict index admission, and
  answer binding supplied only by the `coherence-kernel` submodule.
- `form/form-stdlib/form-cli-staged-trace.fk`, `form-cli-ask-gate.fk`,
  `form-freq-check.fk`, and `trust-row.fk` — independent native trust signals
  and the all-four observation gate.
- `scripts/form_cli_rag.py`, `scripts/coh_substrate.py`, and
  `scripts/form_first_offline_setup.sh` — retiring filesystem/persistence
  carriers for complete corpus ingestion and live NodeID verification.
- `bin/form-cli` and `api/app/routers/substrate.py` — actual native wrapper and
  bounded public ask door.
- `api/app/services/deployment_observation.py`, `api/app/routers/health.py`,
  `deploy/hostinger/auto-deploy.sh`, and
  `scripts/verify_observed_deployment_ask.sh` — persisted deployment WITNESS,
  health exposure, deploy-time indexing, and exact end-to-end verification.
- `api/tests/test_form_cli_grounding_runtime.py` — cold, tamper, collision,
  concurrency, wrapper/native, and deployment-observation regressions.

## Acceptance Tests

- `api/tests/test_form_cli_grounding_runtime.py` proves a fresh-home bootstrap
  produces a non-empty substrate and a NodeID-backed index.
- `api/tests/test_form_cli_grounding_runtime.py` proves paraphrases resolve the
  same cell while unrelated real-corpus queries miss.
- `form/form-stdlib/tests/rag-ask-grounded-band.fk` and the consumer test prove
  syntactically valid but absent NodeIDs, path-only IDs, swapped answers, and
  stale CTORs do not ground.
- `form/form-stdlib/tests/form-cli-staged-trace-band.fk` independently mutates
  every trust input and proves `OBSERVED` requires all four.
- `api/tests/test_form_cli_grounding_runtime.py` proves blocked, mismatched,
  expired, unavailable-runtime, and tampered deployment reports cannot certify.
- `api/tests/test_form_cli_grounding_runtime.py` exercises the actual wrapper,
  c-bootstrapped native binary, persisted WITNESS, and public route end to end.

## Verification

```bash
cd form
for band in \
  form-stdlib/tests/rag-embed-band.fk \
  form-stdlib/tests/rag-index-codec-band.fk \
  form-stdlib/tests/rag-retrieve-band.fk \
  form-stdlib/tests/rag-ask-grounded-band.fk \
  form-stdlib/tests/rag-heal-grounding-band.fk \
  form-stdlib/tests/form-freq-check-band.fk \
  form-stdlib/tests/trust-row-band.fk \
  form-stdlib/tests/form-cli-sufficiency-band.fk \
  form-stdlib/tests/form-cli-ask-band.fk \
  form-stdlib/tests/form-cli-staged-trace-band.fk \
  form-stdlib/tests/form-cli-band.fk
do
  ./validate.sh "$band" || exit
done
cd ..
api/.venv/bin/pytest -q api/tests/test_form_cli_grounding_runtime.py
python3 scripts/validate_spec_quality.py --file specs/form-cli-grounded-observation-plane.md
```

## Out of Scope

- Claiming general semantic frequency for arbitrary generated prose before a
  calibrated native semantic head exists; those answers remain `unknown`.
- Replacing SQLite/PostgreSQL filesystem and persistence effects with Form code;
  the host carriers are explicit retiring bridges while identity, ranking, and
  trust decisions already execute in the kernel.
- Treating deployment receipts or documentation as proof without the executable
  native ask and public-route checks above.

## Gaps

- Follow-up task: calibrate and four-way prove the general prose-frequency
  challenger; until then, only an
  exact, fresh, content-bound deterministic WITNESS can currently yield
  `freq:yes`; ordinary grounded answers remain visibly partial.
- Follow-up task: add a native cross-process Windows ask lock. Windows currently
  provides in-process serialization but lacks the Unix
  cross-process `flock` carrier; multi-worker Windows deployment needs a native
  shared lock before it is supported.

## Risks and Assumptions

- Reindexing is required when the schema or embedding kind changes; mixed vector spaces
  are rejected rather than ranked together.
- NodeID identity proves content identity, not external truth. External truth additionally
  requires current independent observations and sufficiency checks.
- The general semantic frequency model may mature separately from deterministic body
  renderers. The interface keeps that gap visible without blocking grounded retrieval.
