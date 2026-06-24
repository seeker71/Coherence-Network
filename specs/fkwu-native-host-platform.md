---
idea_id: form-kernel-runtime
status: active
source:
  - file: docs/coherence-substrate/fkwu-native-host-platform.form
    symbols: [fkwu-native-host-platform]
  - file: form/form-stdlib/bml/form-fs.bml
    symbols: [IFormFilesystem, FormFilesystem, Path, FileStat]
  - file: form/form-stdlib/form-fs.fk
    symbols: [fs-read-text, fs-write-text, fs-path-join, fs-stdlib-test]
  - file: form/form-stdlib/bml/fkwu-platform-host.bml
    symbols: [HostPlatformRegistry, IPlatformHostCarrier]
  - file: form/form-stdlib/bml/host-kernel-interface.bml
    symbols: [HostKernelInterface, HostResourceObservable]
  - file: form/form-stdlib/fkwu-platform-host-carrier.fk
    symbols: [host-platform-detect, host-platform-carrier]
  - file: form/form-stdlib/host-kernel-fkwu-native-emit.fk
    symbols: [hkne-gaps-decl-text, hkne-gaps-arms-text]
  - file: form/form-stdlib/form-flatten.fk
    symbols: [flt-native-registry]
  - file: docs/coherence-substrate/standard-receipt.form
    symbols: [standard-receipt]
requirements:
  - "fkwu host resource receipt path MUST NOT use form-kernel-go or form-kernel-rust to flatten bands or emit fkwu C"
  - "Generic BML class contracts name every host resource; Mac, Windows, and Android each bind an IPlatformResourceImpl carrier record"
  - "HTTP, SSE, filesystem, CPU, GPU, RAM, threads, clock, entropy map to resource-port shapes and host-kernel-interface organs/world-ports — no parallel API surfaces"
  - "fkwu runs all RUNS-status primitives via flatten tags + platform C arms or pure Form table rows"
  - "Architecture and how-to are substrate-ingestible at docs/coherence-substrate/fkwu-native-host-platform.form"
done_when:
  - "c-bootstrap flatten + emit produces fkwu and tables with zero go/rust/ts in the build script"
  - "host-kernel-gaps-close-band crosses four-way on fkwu without segfault (verdict 127)"
  - "platform carrier band proves Mac/Windows/Android dispatch shape on all siblings incl. fkwu"
  - "standard-receipt rows c-bootstrap toolchain-free mac windows android observed for host-metal band"
test: "cd form && bash scripts/fourth-arm-gate.sh host-kernel-gaps-close fkwu-platform-carrier && python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_<date>_fkwu_native_host_platform.json"
constraints:
  - "No new syscall tables in hand-written C beside platform emit slices driven from BML registry"
  - "Go/Rust/TS remain parity witnesses until receipt path retires them — not shipping compilers for host resources"
  - "Honest GAP and VIA_HOST status in BML when a platform lacks a carrier"
---

# Spec: fkwu native host platform — sovereign class-based resource interfaces

## Purpose

Ship the universal kernel (fkwu) as the **only** host resource runtime on the standard receipt path: **c-bootstrapped**, **toolchain-free at run**, **mac + windows + android observed**. Host duties (filesystem, network/HTTP/SSE, CPU/GPU/RAM, threads, clock, entropy, HMI) are **generic BML classes** with **per-platform implementations**, not Go-emitted C stubs or rented-toolchain flatten tables.

## Requirements

- **R1 — No Go emission on receipt path:** Retire `build-form-cli.sh` / `fourth-arm.sh` dependence on `form-kernel-go/bin-go` for flatten and `fkc-emit-universal` on the path that earns `standard-receipt.form`. Replace with c-bootstrap chain: `bootstrap-host` → `form-flatten` (recipe) → `form-asm` / `form-macho` / `form-pe-coff` / `form-elf` → fkwu.

- **R2 — Class-based platform binding:** `fkwu-platform-host.bml` defines `HostPlatformId`, `IPlatformHostCarrier`, and `IPlatformResourceImpl` templates. Each resource has `Mac*`, `Windows*`, `Android*` implementation classes. `HostPlatformRegistry` resolves `(platform, resource) → carrier record`.

- **R3 — Port-shaped APIs only:** New features use `resource-port.fk` shapes and `host-kernel-interface.bml` catalog entries. HTTP and SSE are **WorldNetwork** bytes ports; filesystem is **WorldFilesystem**; GPU is **OrganGpu** via host JIT door; RAM is **OrganRam** + `storage-port` memory carrier.

- **R4 — Full fkwu natives:** Every `RUNS` primitive in the contract has a `form-flatten.fk` tag and a platform C arm (or pure-Form table row). Gap natives 127–140 must four-way without segfault.

- **R5 — Local retrieval:** `docs/coherence-substrate/fkwu-native-host-platform.form` is the canonical architecture cell; agents read it via substrate ingest / `form-cli ask` before implementing host features.

## Resource map (implement new features here)

| Duty | BML catalog | Port shape | Form binding | fkwu tag family |
|------|-------------|------------|--------------|-----------------|
| FileSystem | `WorldFilesystem` | afferent/efferent bytes + text | `read_file`, `write_file`, storage-port file | 55–63, storage |
| HTTP | `WorldNetwork` | afferent/efferent bytes | `http_get`, `socket_*` | 120–126 |
| SSE | `WorldNetwork` (stream) | efferent bytes chunked | extend `http-client.fk` stream read | TBD stream tag |
| CPU | `OrganCpu` | (recipe) | `walk_recipe`, math natives | 128, 1–12 |
| GPU | `OrganGpu` | VIA_HOST | `hk-gpu-dispatch` → `jit_compile_value` | JIT dylib |
| RAM | `OrganRam` | storage KV | `hk-ram-*`, `volatile_cell_*` | 136–140 |
| Threads | `OsThreads` | NAMED → lift | pthread in fkwu main today | future tag |
| Clock | `OrganClock` | scalar | `now_unix_ms` | 135 |
| Entropy | `WorldEntropy` | bytes | `random_bytes`, `seeded_bytes` | 134, 117 |

## How to implement (agent checklist)

1. Read `docs/coherence-substrate/fkwu-native-host-platform.form` and `host-kernel-interface.bml`.
2. Add or extend BML class in `fkwu-platform-host.bml` with Mac/Windows/Android impl classes.
3. Wire `fkwu-platform-host-carrier.fk` dispatch from `host-platform-detect`.
4. Register native in `form-flatten.fk`; add platform C in emit slice (c-bootstrap path).
5. Add `tests/<name>-band.fk`; prove three-kernel, then four-way on fkwu.
6. Update `NativePrimitiveBinding` rows; run substrate ingest.

## See also

- `docs/coherence-substrate/standard-receipt.form`
- `docs/coherence-substrate/host-kernel.form`
- `docs/coherence-substrate/form-to-asm.form`
- `form/form-stdlib/bml/host-kernel-interface.bml`
- `specs/kernel-image-proposal-public-interface.md`
