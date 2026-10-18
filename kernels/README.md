# Form kernel floor

`fkwu` is the sole live Form kernel. Its c-bootstrap lives at
[`form/runtime/fkwu-uni.c`](../form/runtime/fkwu-uni.c); its standard library,
BML compiler, page JIT, application cells, and native build gates live under
[`form/form/`](../form/form/).

The former Rust, Go, TypeScript, and Python kernels established bootstrap and
historical validation evidence. They are not runtime choices, fallbacks,
deployment services, or recurring validation targets. Current work does not
add to those carriers or route around an fkwu/JIT gap through them.

## Writing and running software

- Author behavior in BML or a domain grammar, with direct Form recipes where
  that is the highest available grammar.
- Realize source on fkwu and let the page JIT own hot compatible functions.
- Treat every missing JIT shape as work in the JIT itself.
- Use `form-cli ask` for the native reasoning/read door and `fsh-main.fk` for
  Form-native shell composition.
- Keep the compatibility API only for application routes whose HTTP,
  persistence, or startup ownership has not yet moved into the native host.

The current application catalog is
[`form/form/apps/coherence-network/api.bml`](../form/form/apps/coherence-network/api.bml).
The exact current floor, released surfaces, and remaining native-host work are
recorded in
[`docs/system_audit/form_kernel_floor_2026-10-18.md`](../docs/system_audit/form_kernel_floor_2026-10-18.md).

## Validation boundary

Routine sibling-kernel comparison is retired. A change to `fkwu` receives the
smallest focused fkwu/JIT proof that exercises that change. Application and
documentation changes receive only their own focused contract checks. No
broad kernel suite runs merely because the submodule is present.

The other files in this directory are historical design and migration memory.
Where their wording conflicts with this page or the live fkwu source, this
fkwu-only floor and observed runtime behavior are authoritative.
