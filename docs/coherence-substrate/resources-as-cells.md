# Resources as cells — the universal interface model

> Urs (2026-05-30): "This framework should model anything you can think of — a
> cell, an organ, an animal, a plant, a house, a room, a city, a road, a light.
> Represent it with a cell, a Blueprint that has recipes, talking to other cells
> through channels, with any internal state, as long as it can express that
> state into numeric space. Look at how programming languages interface with a
> computer — we need to do the same, because when we translate a language into
> Form we also translate how its runtime interfaces with the hardware. Much more
> than SQL: the filesystem, networking, human-machine interfaces (screen, mouse,
> keyboard), and on and on."

This is the model. It is one claim, and it is large: **every way anything
interfaces with a computer or a human reduces to two operations in numeric
space, over typed ports, where the type is a content-addressed Blueprint.** A
file, a socket, a screen, a keyboard, a light, a thermostat, a room, a human —
each is a **cell exposing ports**. A program written against a port-*shape* works
on any resource exposing that shape, regardless of what the resource physically
IS. Substitutability — the thing that makes software composable — extends to
hardware and to humans, because it falls out of structure, not out of category.

This is the proven companion to
[`ports-interface-and-structure.md`](ports-interface-and-structure.md): that doc
named the Port (contract ⟗ carrier) for *storage*; this doc generalizes the Port
to *every* resource and names the universal vocabulary every Port draws from.

## The narrow waist: two transductions

The OSI stack has seven layers; POSIX has hundreds of syscalls; every GUI
toolkit has thousands of calls. Underneath all of it are **two** operations:

- **Afferent transduction** — world → number. *Sense, perceive, read, input.* A
  thermometer's reading, a socket's `recv`, a keyboard's keypress, a file's
  bytes, a human speaking. The world becomes a number the cell can hold.
- **Efferent transduction** — number → world. *Act, express, write, output.* A
  light turning on, a socket's `send`, a pixel lighting, a file's write, a human
  reading what we wrote. A number the cell holds becomes a change in the world.

(The terms are borrowed from physiology — afferent nerves carry signal *toward*
the center, efferent nerves carry command *outward*. The body's own grammar.)

Everything else — protocols, framing, encoding, buffering, retry — is
*composition* over these two. They are the narrow waist: every host interface and
every human interface is afferent, efferent, or a pair of them.

## A port is content-addressed by (direction, value-shape)

A **port** is `(direction, value-shape)` interned to a NodeID. The `direction`
is afferent or efferent. The `value-shape` is the TYPE of what flows: a Bool, a
Scalar, a Bytes run, a Text line, a Pixel, a Key event. Because the port is
content-addressed:

> **A light's on/off port and a relay's coil port are the SAME NodeID.**

They are physically nothing alike — one is an LED, one is an electromagnet — but
both are `(efferent, Bool)`, so they intern to one number. This is the whole
model in one fact. The proof (`resource-port-band.fk`, 1111111 three-way)
asserts it directly: `(node_eq (efferent-bool) (efferent-bool)) → 1` across a
Light cell and a Relay cell, and one generic `act` driver moves both.

The value-shapes are a small, open vocabulary — the universal types at the
transduction boundary:

| Shape | What flows | Resources that speak it |
|---|---|---|
| **Bool** | on/off, true/false, 1/0 | light, relay, valve, switch, GPIO, feature-flag |
| **Scalar** | a number | thermometer, ADC, dial, motor-speed, setpoint, brightness |
| **Bytes** | an opaque run | file, socket, mic, speaker, disk block, camera frame |
| **Text** | a line of language | stdin/stdout, log, a human speaking/reading, a prompt |
| **Pixel** | a framebuffer cell | screen, LED matrix, projector |
| **Key** | a key/pointer event | keyboard, mouse, touch, button |

A new shape is a new marker NodeID, not new engine code — the same
core-abstraction-first discipline the whole substrate runs on.

## A resource is a cell: (name, kind, terminals)

```
resource = (name, kind-blueprint, terminals)
terminal = (port, carrier-handle)
```

- **kind** is what the thing IS — `Light`, `Relay`, `Thermostat`, `Screen`,
  `Socket`, `Human`, `Room`, `City`. This is its Blueprint; it can carry
  internal state and recipes (methods) like any cell.
- **terminals** are how it INTERFACES — each binds a *port* (the universal
  interface shape) to a *carrier-handle* (where the carrier reaches it: a file
  path, a socket fd, a GPIO line number, a framebuffer offset).

Two resources of *different kind* that share a terminal's port-shape are
substitutable through that port. A `Human` cell with an `(afferent, Text)` and an
`(efferent, Text)` terminal is the same shape as a `Socket` or a serial console —
so code that converses over text ports converses with a person, a process, or a
remote machine without knowing which. The band proves this: `act human
(efferent-text) "welcome"` and `sense human (afferent-text)` use the identical
drivers as the Valve and the Thermostat.

## The generic drivers are invariant across kind

```form
(act   resource port value)   ; efferent: number → world. drive ANY efferent port.
(sense resource port)         ; afferent: world → number. read  ANY afferent port.
(resource-has-port? resource port)  ; honest refusal BEFORE any effect.
```

`act` and `sense` name no resource kind. They find the terminal whose port
matches, reach the carrier, and transduce. The band drives a Light, a Relay, and
a Valve through one `act`; senses a Thermostat (Scalar) and a Human (Text)
through one `sense`; and refuses a scalar-read on a Light *by shape*, with no
effect performed — because the Light's terminals carry no `(afferent, Scalar)`
port. Type-safety at the world boundary, content-addressed.

## How this absorbs a programming language's host interface

Urs's load-bearing point: **translating a language to Form is incomplete unless
you translate how its runtime touches the hardware.** Every language's standard
library is, underneath, a set of afferent/efferent ports over carriers. The
narrow waist makes the mapping mechanical — the language's surface differs; the
ports are the same:

| Language surface | Port (direction, shape) | Carrier |
|---|---|---|
| C `read(fd, buf, n)` / `write(fd, …)` | (afferent/efferent, Bytes) | file descriptor |
| Python `open().read()` / `.write()` | (afferent/efferent, Bytes/Text) | filesystem |
| Go `net.Conn.Read/Write` | (afferent/efferent, Bytes) | TCP socket |
| Rust `std::io::stdin().read_line` | (afferent, Text) | stdin |
| JS `canvas.fillRect` | (efferent, Pixel) | framebuffer |
| Any GUI `onKeyDown` | (afferent, Key) | keyboard |
| `time()` / `Date.now()` | (afferent, Scalar) | clock |
| `printf` / `console.log` | (efferent, Text) | stdout |

A language frontend emits Form recipes for the *logic* (already done —
`grammars/python.fk`, universal-shapes). Its *runtime* becomes a set of resource
cells whose ports map its stdlib calls to the universal vocabulary, bound to the
kernel's host natives as carriers. Two languages reading a file produce the same
`(afferent, Bytes)` port over the same filesystem carrier — so their host
interfaces content-address to the same cells, exactly as their logic does. The
N+M collapse the substrate gives data and code, it gives host-IO.

## The carrier layer (what actually moves the bytes)

A port says WHAT interface; a **carrier** is the host native that realizes it —
the `native_flag` floor where Form hands off to the machine. The kernels already
carry the carrier surface for most of the universal shapes (inventory below);
the resource-port model is the typed, substitutable layer *over* them. Per
[`ports-interface-and-structure.md`](ports-interface-and-structure.md), carrier
selection lives at the Form level (a resource's terminal names its handle); the
effect lands in an existing `catCall` native.

**Already present in all three kernels** (the carrier floor):

| Universal shape | Afferent native | Efferent native |
|---|---|---|
| Bytes / Text (file) | `read_file`, `read_file_bytes`, `read_file_slice`, `file_byte_at` | `write_file_text`, `write_file_bytes` |
| Bytes (network) | `socket_recv`, `socket_accept` | `socket_send`, `socket_connect`, `socket_listen` |
| Recipe (durable) | `read_form_binary`, `channel-read` | `write_form_binary`, `channel-append` |
| Scalar (time) | `now_unix_ms` | — |
| Bytes (entropy) | `random_bytes`, `seeded_bytes` | — |
| Text (console) | — | `print` |
| metadata | `file_size`, `file_mtime` | — |

**Carrier gaps** (efferent/afferent natives the model names but the kernels do
not yet expose — each is one native per kernel, attributed `catCall`, behind a
resource terminal so callers never change):

- **Key** (afferent) — keyboard / mouse / touch input. No stdin-char or event
  native yet.
- **Pixel** (efferent) — a framebuffer-write native. `seedbank/memory-as-
  framebuffer-v0` observes runtime memory as pixels post-hoc; a true
  `(efferent, Pixel)` carrier would write a display surface.
- **Process** — exec/spawn (a child process is a resource with Bytes terminals,
  stdin/stdout/exit-code, exactly `lc-tools-as-form-cells`).
- **Env** — environment variables (an `(afferent, Text)` keyed store).
- **Device lines** — GPIO / serial / I²C for real hardware (Bool/Scalar/Bytes
  over a device handle); the filesystem carrier in the prototype is the honest
  stand-in until these land.

Each gap is a carrier, not a model change. The port shapes, the resource cell,
and the `act`/`sense` drivers are invariant across all of them — which is the
point: the model is complete; the carriers fill in under it.

## How resources talk to each other — channels

A resource is a cell; cells talk through **channels** (`channel.fk`): a CHANNEL
Recipe whose children are message Recipes, durable on a `.fkb`, content-addressed
so two cells appending the same payload produce one NodeID. The three altitudes
of inter-cell contact, all already present:

1. **Substrate lattice** (immediate) — a cell publishes a recipe by interning
   it; another finds it by NodeID. Shared memory by content-address.
2. **Channels** (durable, async) — append/read logs over files; poll `file_mtime`
   for change. A Room cell and a Light cell coordinate here.
3. **Sockets** (live, real-time) — raw TCP between processes/machines.

A resource's afferent/efferent ports and the channels between resources are the
same grammar at two scales: a port transduces world↔number at one cell's
boundary; a channel carries numbers between cells. A Room with a Thermostat
(afferent Scalar) and a Heater (efferent Bool) closing a control loop is a
recipe over those ports plus a channel — modeled entirely in the vocabulary
above, no new primitive.

## Why this is the right foundation

- **Anything is modelable.** A light, a valve, a screen, a city intersection, a
  human, a plant's soil-moisture line — each is a resource cell with terminals.
  The list is unbounded *because the vocabulary is closed*: six shapes, two
  directions, content-addressed.
- **Substitutability for hardware and humans.** Same port-shape ⇒ same NodeID ⇒
  one driver. A control program tested against a simulated `(efferent, Bool)`
  file carrier runs unchanged against a real relay's GPIO carrier.
- **Language translation completes.** A language's logic AND its host interface
  both become Form cells; the runtime is no longer a foreign appendage.
- **It's the substrate's own grammar at its edge.** Afferent/efferent over typed
  ports is ice/water/gas (structure/behavior/individuation) meeting the world.
  Nothing is bolted on.

## Status and next breath

Proven (`resource-port.fk` + `resource-port-band.fk`, **1111111 three-way**): the
port vocabulary, the resource cell, the generic `act`/`sense` drivers, port
identity across kinds, round-trip, and honest shape-refusal — over a filesystem
carrier standing in for device lines. Open: the **carrier gaps** above (Key,
Pixel, Process, Env, device lines) — each a small per-kernel `catCall` native
behind a resource terminal — and the **control-loop example** (a Room cell
closing thermostat→heater over a channel) as the first multi-resource recipe.
SQL/storage from the sibling doc is one resource kind among these: a Store cell
with Bytes terminals over a DB carrier.

## See also

- [`ports-interface-and-structure.md`](ports-interface-and-structure.md) — the
  Port (contract ⟗ carrier) and the settled binding seam; this doc is its
  generalization from storage to every resource.
- [`lc-tools-as-form-cells`](../vision-kb/concepts/lc-tools-as-form-cells.md) — a
  tool/process as a cell with call/response halves; the Process carrier gap is
  this concept at the kernel floor.
- [`channel.fk`](../../form/form-stdlib/channel.fk) — inter-cell transport;
  resources talk through channels.
- [`OBJECT_MODEL_BML_NUMS.md`](../../kernels/OBJECT_MODEL_BML_NUMS.md) — the
  `native_flag` floor where a value is host-native; the carrier boundary.
- [`language-cells.md`](language-cells.md) — languages as cells; their *runtimes*
  become resource cells by this model.
