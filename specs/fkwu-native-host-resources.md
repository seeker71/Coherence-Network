---
idea_id: agent-cli
status: active
source:
  - file: docs/coherence-substrate/standard-receipt.form
    symbols: [standard-receipt, c-bootstrap, toolchain-free, platforms]
  - file: docs/coherence-substrate/host-kernel.form
    symbols: [resource-as-offered-cell, organs-and-ports, host-resource-access]
  - file: form/form-stdlib/resource-port.fk
    symbols: [port, act, sense, mk-resource]
  - file: form/form-stdlib/tool-channel.fk
    symbols: [tc-protocols, tc-tools]
  - file: form/form-stdlib/hati-os-kernel-emit.fk
    symbols: [fk_walk, fkc-flat, fkc-table-file, fks-table-file]
  - file: form/form-stdlib/form-flatten.fk
    symbols: [flt-ops]
  - file: form/form-stdlib/fourth-flatten-driver.fk
    symbols: [ffd-one, ffd-loop]
  - file: form/form-stdlib/rag-heal.fk
    symbols: [rh-build, rh-heal, rh-dir-cells]
  - file: form/form-stdlib/form-cli-main.fk
    symbols: [form-cli ask path]
requirements:
  - "NO Go emission in the agent/runtime loop — fkwu is built from the C bootstrap (form-asm → macho/pe-coff/elf), tables are flattened by fkwu walking T_flat, bands run on fkwu only for the sovereignty receipt path"
  - "Every host resource (filesystem, network, process, usage, stream, store, HMI, sensors, compute organs) exposes a generic Form-native INTERFACE (BML class or domain grammar) separate from platform IMPLEMENTATION carriers"
  - "Each named platform (mac, windows, android) ships a complete implementation set for every interface; recognition-router selects the live carrier by measured fitness"
  - "The fkwu emitted walker carries every interface operation as a universal opcode OR dispatches through a platform impl table — no Go/Rust/TS in the runtime loop"
  - "All sovereignty architecture knowledge (this spec, standard-receipt, host-kernel, resource interfaces, platform matrix, honest floors) is indexed in the form-cli local RAG corpus and retrievable via form-cli ask with zero rented mind"
  - "Each interface+impl pair earns a four-way band where deterministic; host-io bands are single-runtime witness per kernel design"
done_when:
  - "fkwu binary for mac/windows/android is emitted via form-asm bootstrap only — commit evidence names c-bootstrap observed on each platform with trace refs"
  - "T_flat regenerates on fkwu self-host (bin-go absent from the flatten path) after a flt-ops change"
  - "host-resource-interface.fk (or BML grammar equivalent) defines the generic interface vocabulary; host-resource-mac.fk, host-resource-windows.fk, host-resource-android.fk implement every world-* port from host-kernel.form"
  - "Every fs_* / socket_* / http_* op in flt-ops has an fkwu walker arm on mac; windows and android have platform-specific arms or honest named gaps with witness bands"
  - "form-cli ask 'what is the standard receipt?' and 'how do host resources work on android?' retrieve grounded hits from the local index after heal — no Python bridge in the default path"
  - "validate.sh full suite: fourth arm count unchanged or increased; zero new fkwu divergences attributable to resource ops"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/resource-port.fk form-stdlib/tests/resource-port-band.fk && form-cli ask 'what is the standard receipt?' | grep -q grounded"
constraints:
  - "Go/Rust/TS walkers remain proof siblings only — they never gate shipping or the sovereignty receipt path"
  - "Platform carriers may use host OS APIs (dirent, FindFirstFile, AAssetManager, etc.) inside fkwu emitted C — that is allowed per host-resource-access; the BODY stays Form-native"
  - "No parallel Python/bash resource layer — retiring bridges are named, not extended"
  - "Local RAG corpus includes docs/coherence-substrate/*.form, specs/fkwu-native-host-resources.md, form/form-stdlib/host-resource-*.fk — indexed by rag-heal, not a separate store"
---

> **Parent idea**: [agent-cli](../ideas/agent-cli.md)
> **North star**: [`standard-receipt.form`](../docs/coherence-substrate/standard-receipt.form) — c-bootstrap fkwu form-cli on mac/windows/android with NO go/rust/clang/bash/python in the loop
> **Kin**: [`host-kernel.form`](../docs/coherence-substrate/host-kernel.form) · [`form-first-reasoning.form`](../docs/coherence-substrate/form-first-reasoning.form) · [`form-cli-self-healing-memory.md`](form-cli-self-healing-memory.md)

# Spec: fkwu-native host resources — interfaces, platform impls, local sovereignty retrieval

## Purpose

The body must run on **native fkwu alone** for the agent loop: no Go table emission, no Go kernel flatten bootstrap, no rented toolchain in the sovereignty receipt path. Host resources (filesystem, network, process table, sensors, screen, audio, compute organs) must be reachable through **generic Form-native interfaces** with **per-platform implementations** on mac, windows, and android — the same structural shape `resource-port.fk` and `host-kernel.form` already name, lifted to BML class/grammar level and wired into the fkwu walker.

Separately, every cell (human or agent) must be able to **retrieve this architecture locally** — standard receipt, host-kernel doctrine, interface contracts, platform matrix, honest floors — through `form-cli ask` after heal, without a rented frontier mind. Sovereignty is not only runtime; it is **knowing** that is local.

## Honest floor today (2026-06-24)

| Layer | Today | Bar |
|-------|-------|-----|
| fkwu emit | **Committed `bootstrap/fkwu-uni.c`** — no Go in default build | form-asm object emit |
| fkwu link | clang compiles bootstrap C when cache cold; **standard lane uses cache only** | form-macho universal walker |
| form-cli flatten | **fkwu+T_flat** or committed `bootstrap/form-cli-table.txt` | always fkwu self-host |
| form-cli emit | **Committed `bootstrap/form-cli-emitted.c`** — no Go in default build | form-asm |
| form-cli link | clang when building; **standard lane uses warmed `form/form-cli`** | form-macho |
| Host-io on fkwu | Partial: `read_file`, `write_file_text`, `fs_list`, `temp_dir`, `read_line`, `print_str`, … | **All** `flt-ops` host-io rows + HMI/sensor ports |
| Resource model | Functional (`resource-port.fk`, `tool-channel.fk`) | **BML interface + platform impl classes**, router-chosen |
| Platform matrix | mac dirent proven for `fs_list`; windows/android partial/named gaps | **Complete impl set per platform**, receipt traces |
| Knowledge retrieval | RAG indexes repo files; Python bridge retiring | **100% local** — ask retrieves receipt/host-kernel/interface docs grounded |

The merged `fs_list` work crossed four-way on mac but **still used Go for T_flat regeneration** — explicitly below the bar named here.

## Requirements

- [ ] **R1 — No Go in the runtime/emission loop**: the sovereignty receipt path builds fkwu from the C bootstrap, flattens bands via fkwu+T_flat, and runs form-cli with **zero go/rust/ts/clang/bash/python** in the loop. Proof walkers may exist for parity; they do not gate.
- [ ] **R2 — Self-hosting T_flat on fkwu**: when `form-flatten.fk` changes, regenerate `fourth-flatten-table.txt` on fkwu alone. Unblock: split `fkc-table-file` / `fks-table-file` out of `hati-os-kernel-emit.fk` (the string-literal parse that bus-errors fkwu's fixed arena) OR raise arena for the one-shot bootstrap driver flatten only.
- [ ] **R3 — Generic host-resource interfaces (BML)**: one grammar-level interface per resource family aligned with `host-kernel.form` organs-and-ports and `tool-channel.fk` protocols — at minimum: `HostFilesystem`, `HostNetwork`, `HostProcess`, `HostUsage`, `HostStream`, `HostStore`, `HostHmi` (key/pixel/text), `HostSensor`, `HostComputeOrgan`. Each interface is content-addressed; implementations share NodeID when behavior-equivalent.
- [ ] **R4 — Platform implementations**: for each interface, three carriers — `MacHost*`, `WindowsHost*`, `AndroidHost*` — selected at runtime by `recognition-router.fk` / `host-kernel-cell.fk` from measured fitness. Carrier code lives in fkwu emitted C (POSIX, Win32, NDK/JNI shims) behind the same flattener opcodes or an impl dispatch table.
- [ ] **R5 — fkwu walker coverage**: every host-io row in `flt-ops` (`fs_*`, `socket_*`, `http_*`, `read_line`, …) has an fkwu `fk_walk` arm on mac; windows and android arms follow with platform-specific witness bands. Missing arms are **named gaps** in `fourth-arm-bands.txt`, never silent divergence.
- [ ] **R6 — Local sovereignty knowledge corpus**: rag-heal indexes, at minimum: `docs/coherence-substrate/standard-receipt.form`, `host-kernel.form`, `form-first-reasoning.form`, this spec, every `host-resource-*.fk`, and `fourth-arm-bands.txt` Crossed walls. `form-cli ask` returns grounded hits for architecture questions without escalating to a rented mind when the body holds the answer.
- [ ] **R7 — Standard receipt per platform**: each platform row (mac, windows, android) earns `observed` with a device trace: `./fkwu <table> 0` or `form-cli ask …` through c-bootstrap fkwu, toolchain-free, on real metal.

## Architecture sketch

```text
┌─────────────────────────────────────────────────────────┐
│  Form recipes / BML  (body — logic, decisions)          │
│  host-resource-interface grammar                        │
│    HostFilesystem.list / .read / .write / .stat …       │
└───────────────────────┬─────────────────────────────────┘
                        │ offered port (resource-port.fk)
┌───────────────────────▼─────────────────────────────────┐
│  recognition-router  →  Mac | Windows | Android impl    │
└───────────────────────┬─────────────────────────────────┘
                        │ flt-ops opcodes → fkwu fk_walk
┌───────────────────────▼─────────────────────────────────┐
│  fkwu emitted C  (POSIX / Win32 / Android NDK)          │
│  c-bootstrap binary — NO go in loop                     │
└─────────────────────────────────────────────────────────┘

Parallel: rag-heal → local index → form-cli ask (grounded retrieval)
```

## Files to create/modify

- `form/form-stdlib/host-resource-interface.fk` (or `grammars/host-resource.bml`) — generic interfaces
- `form/form-stdlib/host-resource-mac.fk` — mac implementations
- `form/form-stdlib/host-resource-windows.fk` — windows implementations
- `form/form-stdlib/host-resource-android.fk` — android implementations
- `form/form-stdlib/hati-os-kernel-emit.fk` — platform dispatch arms; split table serializers (R2)
- `form/form-stdlib/form-flatten.fk` — op table stays canonical
- `form/form-stdlib/tests/host-resource-*-band.fk` — per-interface/per-platform witness bands
- `form/form-stdlib/rag-heal.fk` — corpus paths for sovereignty docs
- `docs/coherence-substrate/standard-receipt.form` — link this spec when rows turn observed
- `docs/system_audit/commit_evidence_*_fkwu_native_host_resources.json` — receipt traces

## Out of scope

- Reimplementing GPU drivers natively (drive the organ via host API per `local-inference-as-organ.form`)
- Removing Go/Rust/TS proof walkers from CI entirely (they remain parity siblings)
- Public HTTP routes for host resources

## Known gaps (ordered unblock path)

- Split emit serializers — `fkc-table-file` / `fks-table-file` out of `hati-os-kernel-emit.fk` so fkwu can self-host T_flat without bus-error on string literals.
- C-bootstrap fkwu — form-asm → platform binary; retire clang-oracle path for the receipt.
- Interface grammar — BML classes for host resources; first band: `HostFilesystem` four-way on mac impl.
- Windows `fs_list` — `FindFirstFileW` arm (named in fs_list evidence as follow-up).
- Android filesystem — asset vs sandbox paths via NDK.
- RAG corpus expansion — heal includes sovereignty substrate docs; ask smoke tests.

## Acceptance

- A fresh agent on mac can run `form-cli ask "what is the standard receipt?"` and receive a **grounded** hit from the local index — no Python, no remote LLM.
- The sovereignty receipt path (`build fkwu → flatten band → run`) completes with **zero Go** in the command trace.
- `HostFilesystem` (and siblings) exist as BML interfaces with mac/windows/android impl files; `form/form-stdlib/tests/host-resource-fs-mac-band.fk` crosses four-way on mac via fkwu.

## Verification

```bash
# Interface band (mac filesystem — first milestone)
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/host-resource-interface.fk \
  form-stdlib/host-resource-mac.fk form-stdlib/tests/host-resource-fs-mac-band.fk

# T_flat self-host (after serializer split)
cd form && # regenerate fourth-flatten-table.txt via fkwu only — no bin-go in trace

# Local knowledge retrieval
form-cli ask "what is the standard receipt?"  # expect grounded NodeID / doc hit
form-cli ask "how does host-io work on fkwu?" # expect host-kernel / this spec

# Full suite regression
cd form && ./validate.sh  # fourth arm count >= prior; no new fkwu divergences
```

## Risks

- **fkwu arena limits** may block self-host T_flat until serializers split — mitigated by R2 explicit unblock.
- **Platform API divergence** (CRLF paths on Windows, Android asset URIs) can cause false four-way if treated as output-floor — host-io bands stay single-runtime witness per kernel design.
- **RAG corpus drift** if new sovereignty docs are authored but not added to rag-heal corpus paths — mitigated by R6 listing required paths in spec constraints.
