---
idea_id: idea-realization-engine
status: active
source:
  - file: form/form-stdlib/form-native-resource-interfaces.fk
    symbols: [fnri-classes, fnri-resolve, fnri-knowledge-cells, fnri-runtime]
  - file: form/form-stdlib/resource-port.fk
    symbols: [afferent-pixel, port, act, sense]
  - file: form/form-stdlib/hati-os-targets.fk
    symbols: [hos-implementations, hos-impl-for]
  - file: form/form-stdlib/bml-native-interface-package-import.fk
    symbols: [bnii-interface]
requirements:
  - "Every host resource family (process, usage, audio, video, sensor, gpu, dsp, mlx) exposes a generic bnii-interface class linked to resource-port shapes"
  - "macos-arm64, android-arm64, and windows-arm64 each bind all eight protocol classes to hos-implementation rows"
  - "Interface resolution and proof run on fkwu only — no Go kernel emission on this path"
  - "Local sovereignty knowledge index maps structural query slugs to body paths for form-first retrieval"
done_when:
  - "form-native-resource-interfaces-band.fk verdict 8191 at validate.sh (go/rust/ts)"
  - "fnri-dispatch rows map all eight protocols to host-io op families without Go registerNative"
  - "fnri-knowledge-cells lists host-kernel, standard-receipt, and form-first-reasoning paths"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/resource-port.fk form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk form-stdlib/form-native-resource-interfaces.fk form-stdlib/tests/form-native-resource-interfaces-band.fk"
constraints:
  - "No Go registerNative or Go table emission for interface catalog or knowledge lookup"
  - "Platform rows beyond mac/android/windows-arm64 stay in hati-os-targets.fk without duplicating impl strings"
  - "Standard receipt platform rows (c-bootstrap form-cli mac/windows/android) remain pending until witnessed"
---

# Spec: Form-native resource interfaces — class-based host resources on fkwu

## Purpose

Agents and cells need **class-based** host resource interfaces — port shapes, BML interface metadata, and per-OS implementation rows — resolved on **fkwu** metadata, with **body paths** for structural lookup so orientation does not depend on a rented frontier mind.

## Requirements

### Class catalog and bindings
1. - [x] Eight resource classes expose `bnii-interface` rows linked to `resource-port` shapes via port slugs.
2. - [x] `macos-arm64`, `android-arm64`, and `windows-arm64` each bind all eight protocols to `hos-impl-for` rows.
3. - [x] `fnri-knowledge-cells` maps structural slugs to body paths for local retrieval.

### fkwu runtime and dispatch
4. - [x] `fnri-dispatch` maps each protocol to host-io op families without Go `registerNative`.
5. - [x] `fnri-runtime` = `"fkwu"` and `fnri-no-go-emission?` = 1 in proof band.
6. - [ ] fkwu fourth-arm flatten crosses for the combined prelude chain (currently 3-kernel only).

## Files to Create/Modify

- `form/form-stdlib/form-native-resource-interfaces.fk` — class catalog, dispatch rows, knowledge index, resolve API.
- `form/form-stdlib/tests/form-native-resource-interfaces-band.fk` — proof band (verdict 8191).
- `form/form-stdlib/resource-port.fk` — `afferent-pixel` port shape.
- `docs/coherence-substrate/hati-os-targets.form` — lineage + honest fkwu gap.
- `docs/coherence-substrate/host-kernel.form` — native-interfaces lineage edge.
- `specs/form-native-resource-interfaces.md` — this spec.

## Acceptance Criteria

- `cd form && ./validate.sh … form-native-resource-interfaces-band.fk` returns **8191** with go/rust/ts agreement (band under `form/form-stdlib/tests/`).
- `fnri-runtime` = `"fkwu"` and `fnri-no-go-emission?` = 1 in the band proof.
- All eight `fnri-dispatch-for` rows resolve; process carrier = `filesystem`.

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/resource-port.fk \
  form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk \
  form-stdlib/form-native-resource-interfaces.fk \
  form-stdlib/tests/form-native-resource-interfaces-band.fk
python3 scripts/validate_commit_evidence.py \
  --file docs/system_audit/commit_evidence_2026-06-24_form_native_resource_interfaces.json
```

## Out of Scope

- Platform dispatch witnesses under `standard-receipt.form` (mac/windows/android observed rows).
- Windows amd64/x86_64 as primary sovereignty targets (rows stay in `hati-os-targets.fk`).
- Native audio/video/gpu carrier implementations beyond filesystem stand-in ops.

## Risks

- fkwu pre-flattened table returns 0 for this prelude chain until fourth-arm flatten is repaired.
- Dispatch rows name pending carriers (`host-audio-pending`, …) until platform witnesses land.

## Known Gaps

- **fkwu fourth-arm**: combined prelude flatten executes as 0 on fkwu while go/rust/ts return 8191 — follow-up: root-cause fourth-arm table for `form-native-resource-interfaces` prelude chain.
- **Standard receipt**: c-bootstrap form-cli platform rows remain `pending` — follow-up: platform witnesses per `standard-receipt.form`.
- **Host-io witnesses**: per-class mac/windows/android observed traces — follow-up: dispatch witness bands after flatten gap closes.
- None beyond the above for catalog/metadata scope.

## North star

Each class lowers to fkwu host-io dispatch with platform witnesses on mac, windows, and android under the standard receipt (`c-bootstrap`, toolchain-free, `observed` per platform).
