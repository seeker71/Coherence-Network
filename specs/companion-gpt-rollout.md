---
idea_id: trusted-everyday-companion
status: active
requirements:
  - "Update the existing GPT with the reviewed companion instructions."
  - "Observe real hosted responses and refine concrete failures."
  - "Advance remaining distribution within available account access."
done_when:
  - "GPT publication is read back completely and its existing Action scope is preserved."
  - "Every public rollout claim has direct observation and remaining owner dependencies."
test: "python3 scripts/validate_spec_quality.py --file specs/companion-gpt-rollout.md"
constraints:
  - "Keep personal/account snapshots outside git."
  - "Preserve current GPT identity, Everyone visibility and imported ask/trace Action."
  - "Do not infer migration, private storage or directory approval from source readiness."
---

# Spec: Existing GPT and companion rollout

## Purpose

Make the already shared Sema ChatGPT link useful for everyday work without
installation. Continue the free companion release through observed improvement
waves, preserving the owner's existing public identity and actual tool scope.

## Requirements

- [x] R1: Preserve current settings privately, apply the canonical kernel model
  instructions, and read the full saved text back from the existing editor.
- [x] R2: Use clear description and four practical starters from a reviewable
  profile while preserving name, capabilities, sharing and read-only Action.
- [x] R3: Observe actual hosted mentorship, creative revision and collaboration
  with fictional input and actual artifacts. Name how each observation relates
  to the North Star. Repair concrete failures in the same context and repeat
  only the affected check; distinguish case evidence from broad reliability.
- [x] R4: Prepare and validate the missing directory metadata/assets as a new
  skills-only plugin version, keeping optional MCP separate.
- [x] R5: Inspect publishing access; publish/submit where authorized and available.
  Keep npm, directory, GPT, server and migration outcomes distinct.

## Implementation Plan

1. Read the actual GPT, instructions and imported Action; retain local recovery
   copies. Independently review source instructions and public native reads.
2. Publish the reviewed instructions and practical arrival profile; reopen and
   compare complete fields. Observe fresh fictional hosted journeys, including
   an ambiguous case; improve only where the output supplies evidence.
3. Prepare version0.6.1 directory metadata and existing brand assets. Inspect
   the submission portal and remaining npm access without reading credentials.
4. Record observed outcomes, merge source/profile/evidence, release the reviewed
   versioned bundle and verify downloads. Keep external account verification or
   required owner action as a concrete continuation.

## Files to Create/Modify

- `docs/integration/chatgpt-profile.json` and `chatgpt-setup.md`: live profile
  source, publication instructions and observed status.
- `plugins/coherence-companion/`, `scripts/build_readmes.py`, and focused bundle
  tests: directory metadata and canonical asset packaging.
- `docs/front-door/connectors.md`: easy existing-GPT entry and release guidance.
- `specs/companion-gpt-rollout.md`: the bounded rollout and observed waves.
- `docs/system_audit/`: minimal fictional results, publication evidence and ledger.

## Acceptance Tests

- Manual validation: fresh hosted conversations and complete saved-editor
  readback establish the GPT claims; see `docs/integration/companion-gpt-observations.md`.
- Exact instruction equality with `form/plugin/ai-plugin.json` after publication.
- Description/starters equal the profile; all four capabilities remain enabled.
- Imported Action remains unauthenticated `GET /ask` and `GET /trace` at its
  current native server. No whole-schema import or memory scope expansion.
- Actual hosted replies respect hint-first, requested language/brevity, useful
  artifacts, changed goals and honest persistence limits. Distinguish preview,
  published chat, source-only review and independent recipient access.
- Directory lengths/icon formats meet current official requirements and archive
  bytes match source; a public release is not directory approval.

## Verification

```sh
form-run python3 scripts/build_readmes.py --check
form-run python3 scripts/validate_spec_quality.py --file specs/companion-gpt-rollout.md
form-run python3 scripts/validate_commit_evidence.py --file <rollout-receipt>
```

Manual validation: live UI read-back and fictional conversations supply the GPT publication proof.
The previous MCP lifecycle proof is reused while its source remains unchanged.

## Risks and Assumptions

- GPT migration makes the original read-only and does not transfer custom Actions.
The existing UI currently announces a December11 migration deadline. Preserve
this working door while a separate replacement remains unproven. Native reads
return evidence, not complete generated answers or measured private retention.
The plugin remains free source; host access/costs and verified publisher identity
are separate. A skills-only directory listing cannot currently add MCP later.

## Out of Scope

- New private-memory services, an unverified native MCP replacement, changing
  account credentials and claims about access in another person's account remain
  outside this instruction/profile and skills-only distribution round.

## Known Gaps and Follow-up Tasks

- Completed this round: existing GPT publication and exact readback; three live
  waves and a checked teaching retry; source PR4116 and kernel PR620 merged;
  public version0.6.1 package downloaded and matched to the reviewed checksum.
  Recipients use their own host accounts; no publisher API credentials or
  funded inference service are offered.
- Follow-up task: complete npm account authentication before package publication;
  owner is the authenticated package maintainer, with registry integrity read-back.
- Follow-up task: directory upload remains behind publisher verification.
  Public GitHub sharing is already available; keep account/billing changes
  outside this rollout and resume only through a verification path the owner
  chooses. No directory submission or approval is claimed.
- Follow-up task: prove native Action-equivalent remote MCP lifecycle before any
  GPT migration; preserve private memory as a separately authenticated capability.

## See also

- [Prior companion waves](free-companion-plugin-waves.md)
- [Existing GPT setup](../docs/integration/chatgpt-setup.md)
- [Official migration behavior](https://learn.chatgpt.com/docs/migrate-custom-gpts)
- [Directory submission](https://developers.openai.com/plugins/deploy/submission)
