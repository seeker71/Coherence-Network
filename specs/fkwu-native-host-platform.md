---
id: fkwu-native-host-platform
title: fkwu Native Host Platform
status: active
parent_idea: idea-realization-engine
source:
  - file: docs/coherence-substrate/fkwu-native-host-platform.form
    symbols: [fkwu-native-host-platform]
  - file: form/form/form-stdlib/bml/fkwu-platform-host.bml
    symbols: [HostPlatformRegistry]
requirements:
  - "fkwu is the sole host resource runtime"
  - "BML classes name resource contracts and platform implementations"
  - "JIT gaps are repaired in the page JIT rather than routed through lowering or sibling kernels"
  - "Configuration and credentials remain file-backed"
done_when:
  - "the requested resource executes through its fkwu/BML contract"
  - "the exact platform implementation returns an observed receipt"
  - "the smallest focused fkwu/JIT check passes"
test: "run only the focused fkwu/JIT observation named by the changed resource"
constraints:
  - "no sibling-kernel runtime, fallback, or routine parity suite"
  - "no new Python or Go implementation of Form behavior"
  - "no lowering detour for a JIT gap"
---

# fkwu Native Host Platform

## Purpose

Give BML programs direct, bounded access to filesystem, process, network,
socket, clock, entropy, memory, accelerator, and persistence resources through
fkwu. The platform contract is authored in BML; the c-bootstrap exposes only
the native operations needed to meet that contract.

## Requirements

- [ ] Resource behavior is named by a BML interface/class or existing Form port.
- [ ] macOS, Windows, Android, and Linux implementations bind through the same
  contract where the platform provides the resource.
- [ ] Hot compatible functions run through the fkwu page JIT.
- [ ] A missing page/op/value/calling shape is implemented in the JIT itself.
- [ ] Host code does not become a second semantic implementation.
- [ ] Application configuration is read from the file-backed configuration
  hierarchy.

## Verification

Validation follows the changed resource. Run one focused fkwu/JIT observation
that exercises its contract and receipt. Do not run sibling kernels or a broad
kernel suite merely because this spec changed.

## See also

- `docs/coherence-substrate/form-language.md`
- `docs/system_audit/form_kernel_floor_2026-10-18.md`
- `form/form/form-stdlib/bml/jit-page.bml`
- `form/form/form-stdlib/bml/host-kernel-interface.bml`
