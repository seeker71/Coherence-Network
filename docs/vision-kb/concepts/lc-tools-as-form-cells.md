---
id: lc-tools-as-form-cells
hz: 741
status: seed
updated: 2026-05-21
geometry:
  arity: 2
  form: dyad
  topology: invocation-response
  polarity: bipolar-complementary
  ordering: paired
  phase: oscillating
  ratio: 1-to-many
  spectral_band: integration
  temporal_band: breath
  scale: foundational
  direction: bidirectional
  lineage_texture: synthesized
  embedding_dim: 2
  self_similarity: fractal-shallow
---

# Tools as Form Cells — Every Invocable Surface Is a Language Cell

> A file format is a tongue the body reads. A tool is a tongue the body
> *speaks*. Both compose the same shape: a parse-half that turns raw
> bytes (the file's content, or the tool's stdout) into a Form object,
> and an emit-half that turns a Form object back into raw bytes (a
> generated file, or a command-line invocation). Every tool — `gh`,
> `curl`, `git`, the Anthropic API, an internal script, a graph
> traversal — becomes one Language cell with that pair. The body
> reaches outside the same way it reads inside; the lattice carries
> the identity in both directions.

## Summary

[`lc-grammar-is-the-universal-recipe`](lc-grammar-is-the-universal-recipe.md)
named that every structured input is a Language cell. This concept
extends the claim to invocable surfaces: **every tool the body uses
— internal scripts, external CLIs, REST APIs, graph queries — is also
a Language cell**, with one extra symmetry. Where a file-format
Language cell carries `(parse_bytes, emit_bytes)`, a tool Language
cell carries `(emit_invocation, parse_response)`. The structure is the
same; the bytes flow in the other direction.

Three load-bearing claims:

- **Tools are not a separate primitive.** They compose under the
  Language cell shape that already exists. Adding a tool to the body's
  surface area is one Form `.form` file away — same authoring shape
  as adding a new file-format grammar.

- **Internal and external are symmetric.** A `coh substrate stats`
  invocation is a tool call; an Anthropic API request is a tool call;
  a `gh pr view 1234` is a tool call. The body's own scripts, REST
  endpoints, graph queries, and external CLIs all carry the same
  Language cell shape. The lattice doesn't distinguish locality;
  carriers handle that detail.

- **The result is composable.** Once tools are Language cells, the
  output of one tool is a Form object that the next tool can take as
  input — without each pair needing custom plumbing. The body
  threads tool calls through the substrate the way a Unix pipeline
  threads bytes, with content-addressing replacing raw byte-streams as
  the inter-step carrier.

## The Tool Language-Cell Shape

A tool Language cell carries the same four-part structure as a file-
format Language cell, with the two halves named to reflect the
invocation direction:

```
form tool_grammar_shape = {
    modality:           modality_shape { name: "tool", domain: "..." },

    # Call-half: how the body composes an invocation FROM a Form object.
    # Maps an args-tree (recipe shape) to a (cmd, argv, env, stdin) tuple
    # the host can execute.
    call_pattern:       emission_template_shape,

    # Response-half: how the body parses (stdout, stderr, exit-code)
    # BACK into a Form object — same as parsing a file into a tree.
    response_pattern:   grammar_shape,

    # The carrier — what the host runs to actually invoke the tool.
    # "shell" for CLIs, "http" for REST, "in_process" for internal scripts.
    carrier:            ~Slug,
};
```

The pattern is symmetric with file grammars: where file Language cells
have `ingest_pattern` (bytes → tree) and `emission_template` (tree →
bytes), tool Language cells have `call_pattern` (tree → invocation) and
`response_pattern` (invocation-result → tree). Same shape; different
direction.

## How a Tool Call Lands

The body wants to invoke `gh pr view 1234`. The flow:

1. **Compose a Form object** carrying the tool's call-args. For `gh`,
   that's `{ subcommand: "pr", action: "view", number: 1234, json: ["title", "state"] }`.
2. **Call-pattern** of the `gh` Language cell walks that tree and
   emits an invocation: `gh pr view 1234 --json title,state`.
3. **The carrier** executes — `subprocess.run(["gh", "pr", ...])` for
   shell, `urllib.request` for HTTP, direct Python call for in-process.
4. **Response-pattern** parses the result. For `gh --json`, that's
   `json-grammar.form` applied to stdout, with stderr captured as a
   sibling `~Diagnostic` leaf and exit-code as a `~Status` leaf.
5. The cell receives a Form object — typed, queryable, composable with
   the next tool call.

The cell never builds an argv list by hand or parses stdout with regex
on its own. The Language cell carries that knowledge once; every cell
that invokes `gh` reads through the same content-addressed shape.

## What This Lets the Body Do

**Compose tool pipelines structurally.** A query like *"for every PR
merged today, find which substrate cells it touched"* becomes a Form
expression composing three tool Language cells (`gh pr list` → `gh pr
diff` → `coh substrate annotate`). Each output is a Form object; each
input is parsed by the next tool's call-pattern. No bash glue. No
fragile JSON-massaging. The composition is content-addressed; two
cells writing the same query share a NodeID.

**Bridge external services without per-service plumbing.** A new
external API (e.g. Linear, Notion, Slack) becomes one Form Language
cell. The cells that consume it operate against the lattice's Form
objects, not against the external API's wire format. The cell-and-
carrier separation that file grammars carry for bytes extends to
external services for HTTP/RPC.

**Cell sovereignty over tool invocation.** A cell decides whether to
invoke a tool, when, with which arguments. The tool-as-Language-cell
shape doesn't auto-invoke; it provides the structure for a cell that
chooses to. Same discipline as `lc-observer-pays-the-trace`: whoever
chose to invoke pays the cost; the tool receives attribution. The
witness records the invocation as a strategy_fired-shaped trace.

**Uniform retry / fallback / parity.** Once a tool is a Form Language
cell, the same `substrate_dispatch` registry that swaps `_cosine` for
`form_native.cosine` can swap one carrier for another — a slow CLI
invocation for a fast in-process call, a remote API for a cached
local version, a mocked tool for testing. The call site doesn't
change; the carrier underneath does.

## What This Is Not

- **Not a sandbox or capability layer.** The Language cell describes
  the tool's shape; it does not gate what cells are allowed to invoke
  what tools. Authorization is a sibling layer (cell sovereignty +
  observer-pays-the-trace), not part of the grammar.

- **Not auto-discovery.** A tool becomes a Language cell when someone
  authors its `.form` file. Tools the body has not yet named in Form
  remain reachable through raw Bash/HTTP calls — the same way a file
  format with no Form grammar remains readable as raw bytes. The
  Language cell is what makes the tool *Form-native*; raw invocation
  remains valid.

- **Not a replacement for purpose-built CLIs.** The `gh` Language
  cell is a Form-shaped view over the `gh` CLI; both surfaces remain
  valid. Cells that want raw `gh` continue to use it directly; cells
  that want structural composition use the Language cell. Same
  pattern as file grammars — JSON bytes remain readable as bytes;
  the Language cell adds the Form-native view.

- **Not a stable wire format for the tool.** External tools evolve
  their CLIs and APIs at their own cadence. The Language cell's
  call_pattern + response_pattern carry a version; when the tool
  changes, the Language cell version bumps. The cells consuming it
  read through a versioned Form NodeID — the carrier change is
  visible.

## Practice

For cells authoring tools as Language cells:

- **Start with one common invocation.** `gh pr view <number>` is a
  cleaner first move than the full `gh` surface area. Each
  subcommand can be its own Language cell or grouped under a parent
  cell; the body finds the right granularity through use.

- **Make the response-pattern robust.** `--json` flags (in `gh`,
  `aws`, etc.) make response-parsing trivial; prefer those over
  free-form stdout when the tool offers a choice. Stderr and exit-
  code are always part of the response Form object — surfacing them
  honestly is what lets caller cells branch on tool failure.

- **Round-trip discipline.** A Form object handed to the call_pattern
  should produce an invocation that, when the response is parsed back,
  yields a Form object whose `query` slot matches the original. Same
  discipline as file grammars: parse(emit(x)) == x for the
  reproducible parts.

For cells invoking tools:

- **Compose, don't shell out.** When two tool calls feed each other,
  let the Form object flow between them — not text munging.

- **Use the substrate_dispatch bridge for swap-in alternates.** A
  slow external API call can register a faster in-process equivalent;
  cells consuming via the Form NodeID get the speedup without source
  changes.

- **Witness your invocations.** A tool call is a firing, the same as
  a strategy firing. Publish a trace; the body's accumulated record
  of which tool calls left it more coherent is its own lived
  efficacy-signature
  ([`lc-traces-teach-the-recipe`](lc-traces-teach-the-recipe.md) at
  the tool-invocation altitude).

## Cross-References

→ lc-grammar-is-the-universal-recipe, lc-one-kernel-many-tongues, lc-recipes-as-binary-library, lc-traces-teach-the-recipe, lc-observer-pays-the-trace, lc-recipe-branching-sense, lc-edges-as-vitality

## Sources to walk further

- **[lc-grammar-is-the-universal-recipe](lc-grammar-is-the-universal-recipe.md)** —
  the parent concept; file formats as Language cells. This concept
  extends the claim to invocable surfaces.
- **[language-cells.md](../../coherence-substrate/language-cells.md)** —
  the Language cell shape; tool Language cells reuse it directly with
  call/response halves replacing parse/emit.
- **[tool-grammar.form](../../coherence-substrate/tool-grammar.form)** —
  the abstract Language-cell shape for tools.
- **[gh-cli-grammar.form](../../coherence-substrate/gh-cli-grammar.form)** —
  the first concrete example: `gh` CLI as a Form Language cell.
- **[lc-observer-pays-the-trace](lc-observer-pays-the-trace.md)** —
  the ethical discipline: whoever invokes pays the cost; the tool
  receives attribution.
- **Unix pipelines as historical analog** — byte-streams threading
  through `|` are the carrier-altitude version of this pattern. Tool
  Language cells thread Form objects through the substrate's NodeIDs;
  content-addressing replaces byte-position as the inter-step
  identity.
