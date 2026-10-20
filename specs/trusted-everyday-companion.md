---
idea_id: trusted-everyday-companion
status: active
source:
  - file: skills/coherence-network/SKILL.template.md
    symbols: [companion workflow]
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [TOOLS, dispatch]
  - file: mcp-server/coherence_mcp_server/form_cli_tools.py
    symbols: [catalog_capture, kernel_route, transmute_text]
requirements:
  - "Everyday help starts with the person's task and produces a useful artifact."
  - "Conversation capture requires explicit consent for selected local learning material."
  - "Public network submission and private host conversation have distinct boundaries."
  - "MCP startup, configuration and advertised tools match executable behavior."
done_when:
  - "Focused consent, configuration, launcher and MCP contract tests pass."
  - "Skill frontmatter validates and generated documents match their templates."
  - "Independent scenarios cover learning, business, design, creation, research and collaboration."
test: "uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest"
constraints:
  - "Use the existing skill and MCP; no parallel assistant runtime."
  - "Form/fkwu owns runtime decisions; Python and Node remain explicit transport and packaging carriers."
  - "No personal context, transcripts, credentials or identity bindings in public artifacts."
  - "No implicit publishing, messaging, training, identity registration or persistent memory."
---

# Spec: Trusted everyday companion

## Purpose

Help people learn, think, design, create and work together through the existing
Coherence skill and MCP connection. The first useful result should come from
their own task, without requiring them to become network operators. Trust means
accurate capability claims, control over crossings, and evidence that the
implemented behavior matches the invitation.

## Observed starting point

On 2026-10-20 the skill is a generated document, not a native plugin manifest.
Its entry path prioritizes network registration, inboxes, identity and portfolio
operations. The npm entry point launches the existing Python MCP carrier.

The capture hook reads the last chat turn and starts a detached training worker;
the direct capture tool has no consent argument. The rewrite instruction asks
to replace warning vocabulary. Routing names a retired Go kernel. The launcher
uses a shell, so its missing-executable fallback does not observe the expected
ENOENT event. The example config and runtime disagree on environment keys.
Public guidance still names a retired evaluator that returns HTTP 410.

The public lattice and relationship surfaces are not established private family
storage. Host conversation, selected local learning, public contribution and a
future authenticated shared space are separate scopes.

The existing GPT is Sema — coherence-kernel,
`https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625`.
Its source owner is `form/plugin/`, separate from the public network Action.
The editor observed on 2026-10-20 exposes only native GET `/ask` and `/trace`
at `https://sema.hati.earth`; all four host artifact/research capabilities are
enabled. Its older counsel-only instructions limit practical work. Update those
canonical instructions while preserving the currently imported read scope.
The same UI displays a December 11 migration notice; migration requires a
separate observed client lifecycle and permission-preserving handoff.

## Requirements

- [x] **R1 — Arrival:** Enter through the person's requested outcome. Ask only
  for missing information that changes useful work; ordinary assistance has no
  identity, inbox, registration, contribution or learning prerequisite.
- [x] **R2 — Useful work:** Support mentorship, business exploration, design,
  creation, research and collaboration with examples of completed outputs.
  Adjust explanation depth, language and pace; preserve the person's judgment.
- [x] **R3 — Honest trust:** Distinguish observed evidence, sourced information,
  inference and uncertainty. Preserve warnings, negations and boundaries during
  reframing. Warmth never requires false agreement or emotional dependence.
- [x] **R4 — Controlled context:** Keep work in the current host conversation by
  default. Explain that host privacy settings still apply. A selected local
  brief, local training excerpt, public contribution and message to another
  person each require the corresponding owner intent; one never implies another.
- [x] **R5 — Capture boundary:** Deny absent or incorrect local-learning consent
  before reads, writes or model execution. Retire automatic transcript capture.
  Explicit capture retains only supplied selected text with restricted local
  file permissions; no error path silently captures raw conversation.
- [x] **R6 — Native truth:** Route existing backend scoring through the pinned
  fkwu recipe. A missing kernel returns an honest capability error. No retired
  evaluator or runtime is a recommended usable tool.
- [x] **R7 — Usable packaging:** Configuration comes from files, startup forwards
  stdio and exit status, missing launchers fail clearly or use the documented
  fallback, and generated skill frontmatter begins at the document start.
- [x] **R8 — Reviewable evidence:** Focused automated tests and an independent
  scenario evaluation establish the bounded release; unbuilt future capabilities
  remain visibly planned.

## Implementation plan and ownership

Four concurrent lanes share one named linked worktree. Each discovering agent
keeps its repair and proof; integration follows after independent changes.

| Lane | Owner | Work and acceptance |
|---|---|---|
| Skill | plugin agent | Compact entry, six useful workflows, progressive network reference; valid frontmatter, resolved references, realistic scenario outputs. |
| Trust | trust agent | Explicit capture consent, retire automatic hooks, faithful rewrite instruction, fkwu routing; prove denied calls have no side effects and selected capture works. |
| Front door | journey agent | Supported Action schema, public instructions and MCP README; no retired evaluator, publication boundary visible, install instructions match source. |
| Integration | root | Detailed plan, launcher, file-backed config, generator correctness, current grounded-ask tool, proof receipts, cross-lane review and delivery. |

After the skill lane completes, its agent tends the kernel-owned GPT manifest
and publication handoff; the journey agent independently evaluates nine
fictional skill requests. Kernel changes land before the parent gitlink.

### First release: the existing plugin becomes useful and trustworthy

1. Replace operational onboarding with task-first guidance. Keep advanced network
   operations reachable when requested, with accurate scope and attribution.
2. Close the observed automatic-capture boundary before claiming trusted everyday
   use. Preserve the ability to offer a deliberately selected learning excerpt.
3. Align all touched discovery surfaces and remove executable claims about retired
   routes. Reuse the hosted grounded-ask/read boundary instead of reviving an AST
   evaluator. Host tools supply browsing and artifact creation when available.
4. Repair packaging and configuration at the existing carrier. No additional
   service, database or agent orchestrator is needed for this release.
5. Exercise realistic scenarios and adverse boundaries, record limitations and
   test evidence, then prepare the integrated change for review.

### Native roadmap after the first release

These are implementation increments with observable exit conditions, not claims
that the current plugin already implements them. Sequence follows dependency;
independent artifact adapters and scenario evaluations can proceed in parallel.

| Increment | User-visible outcome | Existing surface to extend | Exit evidence |
|---|---|---|---|
| A. Owner-controlled continuity | Choose what is remembered, inspect/correct/export/delete it, start fresh at any time. | Form cells, native persistence and consent boundaries; selected host brief until storage is proven. | Two identities cannot retrieve each other's data; revocation, export, deletion, restart and no-consent tests; clear retention policy. |
| B. Private shared projects | Invite people to one project, agree roles and share only selected artifacts. | Existing native identity/persistence and workspace seams, with authenticated authorization before claims. | Cross-project isolation; invitation acceptance and revocation; per-recipient visibility; audit without private transcript leakage. |
| C. Artifact completion | Turn a brief into a usable document, design, spreadsheet, presentation or code change. | Existing host artifact tools and connectors through scoped capabilities. | Correct artifact opens/renders; edits preserve source; provenance and access boundary survive handoff; unavailable tools yield an honest alternative. |
| D. Mentorship and business practice | Adaptive practice, feedback on attempts, explicit assumptions and low-cost experiments. | Skill workflows and native choice/checkpoint flow. | Human-rated usefulness and factual accuracy on consented scenarios; no invented research, certainty or unsupported business promises. |
| E. Collaboration continuity | Resume with goals, decisions, owners, disagreements and the next action intact. | Shared project records and native continuation/checkpoint flow. | Interrupted work resumes without duplicate effects; sending/publishing only reaches intended audience; each person's contribution remains attributed. |
| F. Native capability growth | Local lanes carry increasingly useful work with observable quality. | fkwu retrieval, voice and native engineering lanes. | Per-lane challenger matches agreed task-quality thresholds, honest errors, latency and consent checks; measured native/rented share without inflating it. |

Release each increment independently when its proofs pass. Private continuity
and collaboration depend on authenticated isolation; a public cell name, identity
handle, content hash, or consent-shaped prompt is not an access-control system.

### Evaluation and feedback

Use fictional, deliberately supplied scenarios; capture no family transcripts.
Evaluate whether the result is useful, evidence is accurate, requested scope is
preserved, unnecessary questions are avoided, and the person can revise or stop.
Record failures with the input, owner, smallest trace and next verification.
Measure cold-start success, task completion, correction acceptance, accidental
publication/capture (must be zero), and native/rented receipts. Set performance
targets from observed baseline; do not invent benchmark scores.

## Files to Create/Modify

- `skills/coherence-network/SKILL.template.md`, `SKILL.md`, `references/` and
  optional `agents/openai.yaml` — everyday guidance and progressive detail.
- `mcp-server/coherence_mcp_server/{server,settings,form_cli_tools,capture_hook,capture_worker}.py`
  — existing MCP carrier, file configuration and consent boundary.
- `mcp-server/index.mjs`, package/registry manifests and
  `skills/coherence-network/mcp-config.json` — truthful launch/install contract.
- `.claude/settings.json`, `scripts/training_corpus.py` — retire implicit capture
  and require intentional selected-source learning at existing callers.
- `api/config/api.json` — file-backed MCP defaults.
- `scripts/build_readmes.py` — generated skill frontmatter correctness.
- `scripts/ensure_form_cli_native.sh` — keep cold-build diagnostics out of the
  executable-path stdout protocol observed during this work.
- `form/plugin/{ai-plugin.json,README.md,PUBLISH-HANDOFF.md}` in the kernel —
  everyday companion instructions and exact existing-GPT update scope.
- `docs/front-door/{INDEX,connectors}.md`, `openai-gpt-action.yaml`,
  `web/public/llms.txt`, `mcp-server/README.template.md`, `README.md` — aligned entry.
- `mcp-server/tests/`, `api/tests/test_form_cli_mcp_tools.py` — focused behavior proof.
- `docs/system_audit/commit_evidence_2026-10-20_trusted_companion.json` — integration receipt.
- Indexes and executor evidence as required by repository delivery guidance.

## Acceptance Tests

Focused contracts live in `mcp-server/tests/` and
`api/tests/test_form_cli_mcp_tools.py`; the final scenario pass is manual validation.

- No-consent capture, wrong-consent capture, inactive hook and worker have no
  transcript/model/file side effects; explicit selected capture persists only
  its inputs and exposes no secret in an error.
- The native routing test must observe fkwu when present; absence is a separate
  negative test, not substituted for success evidence.
- Launcher tests simulate missing uv, failing child, successful fallback, stdio
  and termination. Runtime config tests prove default/overlay precedence,
  malformed config failure and no environment fallback.
- Grounded-ask dispatch forwards to the supported read endpoint; the retired
  tool is absent from discovery and does not call its dead endpoint.
- Skill generation retains valid YAML, reference links resolve, and package
  contents include the files the launcher needs.
- Independent manual forward evaluation: a learner with an incorrect attempt,
  a business hypothesis, a design brief, a creative revision, evidence-limited
  research, and a collaboration request involving another person's private data.

## Verification

```sh
form-run python3 scripts/validate_spec_quality.py --file specs/trusted-everyday-companion.md
form-run node --test mcp-server/tests/test_launcher.mjs
form-run uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest
form-run python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-10-20_trusted_companion.json
form-run git diff --check
```

## Observed Delivery State

The source implementation satisfies R1–R8. Kernel instruction changes landed in
[coherence-kernel PR 619](https://github.com/seeker71/coherence-kernel/pull/619);
the parent pins that merged commit. Nine fictional forward examples cover the
six workflows, privacy, faithful revision and conflicting evidence. This is
source-skill evaluation, not proof of changed live GPT behavior. Automated
results and review repairs are recorded in the integration receipt.

The current checkout can run through the documented Node launcher. The published
npm package and existing GPT remain unchanged by this source delivery. The GPT
handoff preserves its imported read-only ask/trace Action; its migration to a
plugin still needs native MCP lifecycle implementation and client verification.
Roadmap A–F remains future work with explicit exit evidence.

## Out of Scope

- This release does not claim a new general-purpose model, authenticated private
family storage, a new chat product, automatic monitoring, or complete parity
with every host artifact tool. Publishing packages and deploying production
remain distinct delivery effects and must be reported accurately.

## Risks and Assumptions

- Existing installations must update to receive changed behavior. A source fix
  is not proof that published packages or running services have changed.
- The host supplies reasoning and optional artifact tools; MCP adds network
  capabilities and the skill adds guidance. Host privacy cannot be overridden
  or guaranteed by this plugin.
- Removing automatic learning is intentional. Useful learning becomes a
  selected contribution rather than an implicit cost of receiving assistance.
- Hosted read requests still send query text to that host; minimize personal
  details and do not equate a read operation with zero disclosure.

## Known Gaps and Follow-up Tasks

- Follow-up task A: owner-controlled continuity; task B: authenticated private projects.
- Follow-up task C: artifact completion; task D: evaluated mentorship and business practice.
- Follow-up task E: collaboration continuity; task F: measured native capability growth.
- Roadmap increments A–F above retain owner, dependency and exit evidence. They
are not first-release completion claims. Current private storage/authentication
and broad artifact support remain to be implemented at their native boundaries.

## See also

- [Agent start packet](../docs/shared/agent-start-packet.md)
- [Front door](../docs/front-door/INDEX.md)
- [Coherence skill](../skills/coherence-network/SKILL.md)
- [MCP server](../mcp-server/README.md)
