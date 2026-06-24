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
  - "Eight resource classes expose `bnii-interface` rows linked to `resource-port` shapes via port slugs (ten protocols including `host:file` and `http:request`)"
  - "macos-arm64, android-arm64, and windows-arm64 each bind all ten protocol classes to hos-implementation rows"
  - "Interface resolution and proof run on fkwu only — no Go kernel emission on this path"
  - "Local sovereignty knowledge index maps structural query slugs to body paths for form-first retrieval"
done_when:
  - "form-native-resource-interfaces-band.fk verdict 32767 at validate.sh (go/rust/ts/fkwu)"
  - "fnri-dispatch rows map all ten protocols to host-io op families without Go registerNative"
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
1. - [x] Ten resource classes expose `bnii-interface` rows linked to `resource-port` shapes via port slugs (includes `host:file`, `http:request`).
2. - [x] `macos-arm64`, `android-arm64`, and `windows-arm64` each bind all ten protocols to `hos-impl-for` rows.
3. - [x] `fnri-knowledge-cells` maps structural slugs to body paths for local retrieval.

### fkwu runtime and dispatch
4. - [x] `fnri-dispatch` maps each protocol to host-io op families without Go `registerNative`.
5. - [x] `fnri-runtime` = `"fkwu"` and `fnri-no-go-emission?` = 1 in proof band.
6. - [x] fkwu fourth-arm flatten crosses for the combined prelude chain (multi-line `; preludes:` fix in fourth-arm.sh).

## Files to Create/Modify

- `form/form-stdlib/form-native-resource-interfaces.fk` — class catalog, dispatch rows, knowledge index, resolve API.
- `form/form-stdlib/tests/form-native-resource-interfaces-band.fk` — proof band (verdict 32767).
- `form/form-stdlib/resource-port.fk` — `afferent-pixel` port shape.
- `docs/coherence-substrate/hati-os-targets.form` — lineage + honest fkwu gap.
- `docs/coherence-substrate/host-kernel.form` — native-interfaces lineage edge.
- `specs/form-native-resource-interfaces.md` — this spec.

## Acceptance Criteria

- `cd form && ./validate.sh … form-native-resource-interfaces-band.fk` returns **32767** with four-way agreement (band under `form/form-stdlib/tests/`).
- `fnri-runtime` = `"fkwu"` and `fnri-no-go-emission?` = 1 in the band proof.
- All ten `fnri-dispatch-for` rows resolve; process carrier = `filesystem`; http carrier = `http-socket`.

## Verification

```bash
cd form && ./validate.sh … form-native-resource-interfaces-band.fk
cd form && ./validate.sh … form-cli-band.fk   # 4095 incl. fnri witness + receipt
./scripts/verify_fnri_platform_receipt.sh
./scripts/verify_fnri_metal_standin_receipt.sh
./scripts/verify_fsh_fnri_bootstrap.sh
bash scripts/verify_fnri_windows_standalone.sh
bash scripts/verify_fnri_android_receipt.sh
./scripts/regen_form_cli_bootstrap.sh   # maintainer: regen bootstrap when preludes change
cd form && ./build-form-cli.sh
printf 'fnri witness\n' | form/form-cli   # → 32767
```

## Out of Scope

- Platform dispatch witnesses under `standard-receipt.form` (mac/windows/android observed rows).
- Windows amd64/x86_64 as primary sovereignty targets (rows stay in `hati-os-targets.fk`).
- Native audio/video/gpu carrier implementations beyond filesystem stand-in ops.

Stand-in proof bands (`fnri-audio-standin`, `fnri-video-standin`, `fnri-gpu-standin`) prove dispatch + byte/JIT-door wiring honestly — not native CoreAudio/Metal capture.

## Risks

- fkwu pre-flattened table returns 0 for this prelude chain until fourth-arm flatten is repaired.
- Dispatch rows name `filesystem`, `host-kernel`, or `http-socket` carriers aligned with form-fs and host-kernel-carrier.

## Known Gaps

- **Closed on mac (honest floor)**: catalog **32767**, dispatch **1023**, host-io **15**, metal stand-ins **15** each, **form-cli-band 4095** (fnri witness + know + receipt) — all four-way; runtime via `form/form-cli` binary; receipts via `verify_fnri_*` scripts (thin `form-cli-run.sh` carriers only).
- **North star (named, not hidden)**: native metal device witnesses (CoreAudio capture, ScreenCaptureKit frame, Metal/CUDA dispatch) with per-platform device traces — stand-ins are explicitly filesystem/host-kernel wiring, not metal proof.

## North star

Each class lowers to fkwu host-io dispatch with platform witnesses on mac, windows, and android under the standard receipt (`c-bootstrap`, toolchain-free, `observed` per platform).
