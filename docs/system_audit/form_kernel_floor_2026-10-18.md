# Form kernel floor — 2026-10-18

This reading is anchored to parent commit `2f2dbcf400e28d1b91413c8ba3531b1e3e66698b`
and coherence-kernel `b1f757be83801a75340273cae0f31a5162d30ded`. The parent was
already aligned with `origin/main`; the submodule was updated from the previous pin
through coherence-kernel PR 595.

## Executable floor

- The production recipe authority is the C-bootstrapped `fkwu`. Go, Rust, and
  TypeScript remain proof siblings; they are not additional production authorities.
- Grammar → recipes/cells → realization → reads is executable. BML/source compilation,
  native file/HTTP/persistence carriers, the native form-cli router, grounded RAG, and
  the sufficiency gate are present.
- `form-cli ask` is the single native lookup door. `ask+` now preserves the same staged
  native decision and crosses to a named remote command only after
  `decision:escalate`. Native and rented trust rows remain separate, and the canonical
  ask ledger records both crossings. The native stage is deadline-bound as well as the
  remote stage: the default allows 180 seconds for grounding and 30 seconds for the
  oracle, while an explicit `--timeout` constrains both.
- The loader band passes at verdict 4095 with one fourth-arm band, one passing band,
  and zero divergence.
- The model lane has tokenization, tensor mapping, sampling, Metal and autoregressive
  building blocks. Full answer generation from real hidden-state logits over complete
  model tensors remains unobserved. `ll-heap`, arbitrary recipe compilation through
  grammar-as-recipe, and a self-hosted form-cli remain open floor work.

## Repository body reading

The arrival wellness reading observed:

- 1,753 of 1,753 sources grounded into 8,235 cells.
- 7,485 structured cells, 32 flat cells, and 718 cells without a CTOR.
- 189 specs, 18 ideas, and 196 concepts indexed.
- 121 of 172 non-draft specs connected through the graph chain (70%).
- 217 native primitives: 184 in-band, 33 carrier-declared, 18 sibling gaps, and
  138 primitive names represented in bands.
- Seven bootstrap files / 3,471 lines remain; three of those files / 1,614 lines are
  Python-dependent. The wider compatibility substrate under `api/app/services/substrate`
  is 16 modules / 9,040 lines, while all four catalogued static-to-dynamic successors
  are live.
- The API catalog has 852 routes. Twenty-two are kernel-served (2.6%), 105 have a
  native-capable handler, and 830 remain on the Python compatibility carrier. At the
  reading boundary no public route was owned kernel-first, so shipped native capability
  is materially ahead of public native authority.

## Effects of recent features

- The bounded pulse projection keeps continuous web and monitor reads away from deep
  health proof.
- Deployment observation binds public, loopback, container, image, source, and native
  carrier evidence into persisted WITNESS cells.
- Hati grocery totals now carry one deadline through membership, database, graph, and
  native policy work, with finite process-tree cleanup.
- Retiring sibling kernel-router containers simplified production authority to one
  `fkwu`-carrying API service. It also made the compatibility API event loop a public
  availability boundary until more traffic moves to native route ownership.

## Observed tightness and repair

At arrival, the public web answered while all public API paths returned 404. The API
container was alive but unhealthy at approximately one full CPU core. A live Python
stack sample placed the active frame in `latest_deployment_observation`:

`health → latest_deployment_observation → _decode_row → ctor_field_lookup → lookup_node`

The deep health path decoded every witness field by walking the complete CTOR again.
That produced O(fields²) synchronous database reads on the sole event loop. Even
`/api/ping` then missed its five-second liveness window, and Traefik withdrew the
unhealthy service.

The repair makes whole-CTOR projection set-based: one CTOR read, one binding read, and
one string-leaf read regardless of field count. Current-deployment witness lookup now
filters before decoding and streams candidates. Health derives freshness from the
already verified payload instead of verifying the same WITNESS twice. Deep health is a
FastAPI worker endpoint, leaving the event loop free for `/api/ping` and other async
traffic. The documented worktree guard also enters the repository's prepared API
runtime when the host Python is bare, so the gate itself remains directly runnable.

## Remaining named work

- Close the 13 missing source paths across six specs and 20 unresolved symbols across
  five specs; add proof for four specs and reconcile five done/inactive specs whose
  claimed tests are absent.
- Close the 32 surfaced Form gaps: 18 ideas without a Form spec, six specs without
  validation, and eight capability gaps. Thirty-one are locally closable; the remote
  model lane needs its staging boundary.
- Promote observed high-traffic API families from native-capable handlers to public
  kernel-first ownership, preserving the deployment observer control plane on the API.
- Complete `ll-heap`, general grammar-as-recipe compilation, form-cli self-hosting, and
  full real-model hidden-state-to-answer generation.
- Re-run wellness after production release proof so deployment and CI circulation are
  measured from the restored public body.

## Trust trace

The structural floor query was native and grounded at `@1.1.9.104`, sourced from
`docs/coherence-substrate/fourth-kernel-wall-groups.form`, but the sufficiency gate
returned `decision:escalate`. The counts above come from repository-native wellness,
roadmap, synthesis, gap, test, Git, and runtime probes. Diagnosis and synthesis beyond
those receipts used the rented OpenAI GPT-5 reasoning lane.
