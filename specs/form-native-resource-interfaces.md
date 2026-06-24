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

Agents and cells need **class-based** host resource interfaces — port shapes, BML interface metadata, and per-OS implementation rows — resolved entirely on **fkwu**, with **body paths** for structural lookup so orientation does not depend on a rented frontier mind.

## Floor

- Eight resource classes wired to `resource-port.fk` + `bnii-interface` + `hos-impl-for`
- Three primary targets: `macos-arm64`, `android-arm64`, `windows-arm64`
- Runtime carrier: `fkwu`; `fnri-no-go-emission?` = 1
- Knowledge index: eight structural slugs including `standard-receipt` and `form-first-reasoning`

## North star

Each class lowers to fkwu host-io dispatch with platform witnesses on mac, windows, and android under the standard receipt (`c-bootstrap`, toolchain-free, `observed` per platform).
