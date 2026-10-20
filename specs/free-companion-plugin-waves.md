---
idea_id: trusted-everyday-companion
status: active
source:
  - file: scripts/build_readmes.py
    symbols: [build]
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [handle_list_tools, dispatch]
requirements:
  - "Anyone can obtain the companion without a Coherence payment or account."
  - "The distributed artifact works outside a developer checkout."
  - "Default tools support assistance and public reads; advanced actions require local opt-in."
  - "Each improvement round retains an observed problem, repair and verification."
done_when:
  - "An installable plugin archive and tested MCP package are publicly downloadable."
  - "A clean host discovers the bundled skill and an extracted MCP package initializes."
  - "Behavioral scenarios establish useful, flexible responses and honest continuation."
test: "uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest"
constraints:
  - "Reuse the existing skill and MCP; Form remains the application runtime authority."
  - "No automatic learning, extra subscriptions, or private-storage claims."
  - "Host availability and costs remain distinct from the free plugin."
---

# Spec: Free companion plugin, observed in waves

## Purpose

Continue the trusted companion implementation until a newcomer can obtain it,
start useful work, correct direction, continue later and understand what leaves
their chat. Each round begins from observed behavior and ends with a verified
repair or an explicit external dependency. “Most useful” is a direction measured
through these journeys, not a claim of universal optimality.

## Requirements

- [x] **R1 — Free distribution:** publish an Apache-2.0 companion archive with
  source and clear setup, independent of npm publishing credentials. No Coherence
  payment, registration, identity binding or API key for ordinary assistance.
- [x] **R2 — Portable skill:** only the everyday skill and its relevant references
  enter the plugin. Runtime helpers, engineering skills, personal configuration,
  eval outputs and automatic hooks stay outside that distribution.
- [x] **R3 — Practical default:** expose a small public-read/rewrite tool set;
  reject advanced calls before I/O even if a caller bypasses tool discovery.
  An explicit file-backed advanced profile retains deliberate network workflows.
- [x] **R4 — Reproducible package:** the packed MCP release initializes, lists
  tools and handles a harmless call from a clean extraction with no repository
  imports or hidden credentials. Package/runtime versions and license agree.
- [x] **R5 — Flexible usefulness:** evaluate actual outputs for short requests,
  language and accessibility preferences, missing tools, changing goals,
  research uncertainty, practical artifacts and collaboration privacy.
- [x] **R6 — Continuation:** a user-chosen brief can carry relevant work between
  chats. Inspection, edits, export and deletion name their actual scope; a local
  note is not automatic memory, model unlearning or authenticated shared storage.
- [x] **R7 — Honest release:** distinguish GitHub availability, npm availability,
  installation proof, public directory approval and the existing GPT. Preserve
  the GPT while its custom Actions still need a supported migration replacement.

## Implementation Plan

| Wave | Observation | Repair | Exit evidence |
|---|---|---|---|
| 1: arrival and distribution | npm serves 0.5.5; source changes were not distributed; the repo has no installable companion manifest. | Package the canonical skill, add a repo marketplace, align 0.6.0 MCP metadata and remove unused dependencies. | Plugin discovery and archive integrity; extracted-package MCP lifecycle; free public download. |
| 2: usable boundaries | MCP discovery exposes about 100 tools including public writes and administrative operations; direct dispatch has no profile boundary. | Small companion default, advanced local opt-in, read tool annotations, early denial, encoded path segments and machine-readable failures. | Enumerated/default-denial tests, bypass tests with zero effects, meaningful error responses. |
| 3: task usefulness | Prior source tests covered six modes; portability and continuation need harder examples. | Observe fictional requests, repair only concrete weaknesses, add a compact continuation reference and reusable eval rubric. | Actual before/after outputs and scoped temporary-file continuation proof. |
| 4: release rehearsal | Source success does not establish the downloaded experience. | Validate the generated bundle, cross-review lanes, release immutable artifacts and read them back without credentials. | Public artifact hashes equal reviewed local artifacts; installation/discovery proof and clearly named remaining platform dependencies. |

Root owns integration, spec, plugin manifest/marketplace, generated distribution,
public setup and delivery. Package agent owns launcher/package/lifecycle proof.
Trust agent owns server/config admission and call boundaries. Journey agent owns
skill, continuation and fictional evaluation. Discovering agents keep repairs
in their active context; independent reviewers inspect the finished changes.

## Files to Create/Modify

- `plugins/coherence-companion/`, `.agents/plugins/marketplace.json` — installable
  skill package and discoverable repository listing.
- `scripts/build_readmes.py` — derive the packaged skill from its canonical source.
- `scripts/validate_commit_evidence.py`, `api/tests/test_commit_evidence_validator.py`
  — classify MCP runtime sources accurately in release evidence.
- `skills/coherence-network/` — workflow and continuation source, evaluation fixtures.
- `mcp-server/` — existing transport admission, packaging, version and regression tests.
- `api/config/api.json` — file-backed default capability profile.
- `docs/front-door/`, `docs/integration/`, `web/public/llms.txt` — accurate installation,
  free-use and capability guidance.
- `docs/system_audit/companion_wave_evaluation_2026-10-20.md` — observed synthetic outputs.
- `docs/system_audit/commit_evidence_2026-10-20_companion_plugin_waves.json` — proof receipt.
- Generated indexes and executor ledger as required by repository delivery guidance.

## Acceptance Tests

- Discover the plugin through an actual supported host and inspect the installed
  manifest/skill. Test the extracted plugin's relative references independently.
- Pack/extract MCP outside the checkout, initialize the actual client, list the
  intended default tools and make a harmless current-chat rewrite call.
- Deny publishing, capture, messaging, identity and administrative tools in the
  default profile without reaching arguments, network, disk or subprocesses.
- Preserve explicit advanced behavior with local config; a model argument never
  elevates privileges. Invalid configuration fails clearly.
- Run fictional behavioral cases with recorded actual output; preserve requested
  language, brevity, facts, privacy and changing intent. Do not grade style by
  fragile phrase matching or count cases as deployed-GPT evidence.
- Prove continuation file edits/deletion in a temporary directory and explain
  that earlier chats, other copies and trained models are outside that action.
- Verify downloaded release checksums and retain external rollout failures with
  their exact continuation command; no successful publication claim on failure.

## Risks and Assumptions

- The plugin is free source and distribution; the chosen host's plans, tools,
  network use and limits remain its own. No unlimited inference promise.
- Skill-only help works without local Node/Python. Optional MCP needs its
  documented runtime; a REST endpoint is not a hosted MCP endpoint.
- npm authentication was observed unavailable (`npm whoami`: E401). GitHub
  artifacts provide an independent distribution path; never publish an old npm
  package as if it contained the reviewed release.
- Public directory submission is separate from public GitHub availability.
  Existing GPT migration makes the original read-only and does not transfer
  custom Actions; preserve the working door until its replacement is verified.
- The plugin has no automatic hooks or collection. Host retention still applies.

## Verification

```sh
form-run python3 scripts/build_readmes.py --check
form-run python3 scripts/validate_spec_quality.py --file specs/free-companion-plugin-waves.md
form-run node --test mcp-server/tests/test_launcher.mjs
form-run uv run --directory mcp-server --with ../api --with pytest --with pyyaml --with pytest-asyncio python -m pytest tests ../api/tests/test_form_cli_mcp_tools.py -q --noconftest
form-run codex plugin list --available --json --marketplace coherence-network
```

## Out of Scope

- Authenticated shared family storage, automatic cross-chat memory, a new model,
and unsupported host capability guarantees remain outside this release. The
native roadmap in the earlier spec retains their prerequisites and proofs.

## Observed Release

[Companion 0.6.0](https://github.com/seeker71/Coherence-Network/releases/tag/companion-v0.6.0)
is public. Unauthenticated downloads matched reviewed checksums, Codex installed
from the pinned public marketplace, and an actual MCP client exercised the
GitHub archive through `npx` with isolated configuration. The
[release receipt](../docs/system_audit/companion_release_verification_2026-10-20.json)
records scope, outputs and remaining distribution dependencies.

## Known Gaps and Follow-up Tasks

- Follow-up task: public directory submission and review, owned by the publisher;
  completion is an approved, publicly installable directory listing.
- Follow-up task: npm 0.6.0 publication, owned by an authenticated package maintainer;
  completion is registry read-back of the reviewed version and integrity.
- Follow-up task: native GPT Action-to-MCP migration, owned by the native plugin
  maintainer; completion requires a client lifecycle and equivalent read scope.
  Current release status belongs in the receipt and setup guide, not inferred
  from source edits.

## See also

- [Trusted everyday companion](trusted-everyday-companion.md)
- [Connector setup](../docs/front-door/connectors.md)
- [Official plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Official GPT migration](https://learn.chatgpt.com/docs/migrate-custom-gpts)
