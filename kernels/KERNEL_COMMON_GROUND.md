# Kernel Common Ground - The Gold Between Go, Rust, and TypeScript

This reading compares the three sibling kernels as they stand on 2026-06-08:

- `form/form-kernel-go/main.go`
- `form/form-kernel-rust/src/main.rs`
- `form/form-kernel-ts/src/kernel.ts`
- side modules such as `inductive.*`, `quotient.*`, `observer.ts`, and the
  route-choice Form in `form/form-stdlib/kernel-http.fk`

The question was not "which host language is better?" The useful question is:
what can the body trust because all three kernels already say it the same way?

## Exact Shared Ground

A local scan of the central `RBasic` tables found 36 exact shared categories with
no numeric drift:

`UNDEFINED`, `WITNESS`, `BLOCK`, `CALL`, `COND`, `MATH`, `COMPARE`, `LOGIC`,
`ACCESS`, `METHOD`, `FNDEF`, `FNCALL`, `IDENT`, `LIST`, `TRANSMUTE`, `FIELD`,
`CARRIER`, `TOPOLOGY`, `FIBER`, `REGION`, `BOUNDARY`, `NEIGHBORHOOD`,
`MATCH_FIELD`, `DELTA`, `RESOLVE`, `COMMIT`, `STEP`, `LIFT`, `SAMPLE`,
`OBSERVE`, `INTERVENE`, `RESIDUAL`, `RECEIPT`, `COST`, `CONSENT`, `EVIDENCE`.

That set is the smallest mechanically trustworthy language substrate today:

- **be**: `NodeID`, `Value`, `Frame`, `Record`, `FIELD`, `CARRIER`, `TOPOLOGY`
- **do**: `walk`, `FNCALL`, `METHOD`, `CALL`, `STEP`, `INTERVENE`
- **witness**: `Trace`, `WITNESS`, `OBSERVE`, `RECEIPT`, `EVIDENCE`
- **0 / 1**: `BOOL`, `NULL`, integer trivials, equality, success/failure score
- **choice**: `COND`, `LOGIC`, `STEP`, `RECEIPT`, plus side-module `CHOICE`
- **care**: `COST`, `CONSENT`, `RESIDUAL`, `EVIDENCE`
- **space/coordinates**: `NodeID(pkg, level, type, inst)`, category, children
- **time**: walk order, branch attempt, success/failure, receipt sequence

The common ground is not a syntax. It is a coordinate system for relation:
identity, action, branch, receipt, cost, consent, and evidence.

## Where Gold Is Already Showing

### 1. Trace Already Knows Choice

All three central kernels carry the same trace shape:

- total walks
- `(arm_ty, arm_inst)` variant counts
- function counts
- native counts
- `choice_attempts`
- `choice_successes`
- `choice_failures`
- `choice_success_rate`

Go and Rust also expose explicit choice-recording methods or fields. TypeScript
has the fields and JSON shape. The current gap is not schema. The gap is that
the Form/BMF/router choice surfaces do not all feed one shared choice-receipt
discipline yet.

That is gold: branch learning can start as witness data, without adding a large
new kernel primitive.

### 2. Route Choice Already Compresses Without Lying

`form/form-stdlib/kernel-http.fk` carries `kh-route-choice`,
`kh-route-decision`, and `kh-route-choice-signature`. Its pressure buckets are
fixed and data-oblivious, so compression preserves texture instead of training
against the current corpus.

This is the same shape the BMF/BML choice system wants:

- candidates
- decision matrix
- eligible/not eligible
- selected/not selected
- pressure bucket
- score bucket
- compressed signature

The route layer accidentally found a general branch-receipt grammar.

### 3. Higher Categories Are Present, But Unevenly Placed

TypeScript exposes more future-facing category names in its central table:
`CHOICE`, `QUOTIENT`, `INDUCTIVE`, `CONSTRUCTOR`, `PROOF`, `INFERENCE`, `ALIAS`,
`BLANKET`, `PROJECT`, `GENERATIVE`, `VECTOR`, `TILE`, `PARALLELIZE`,
`VECTORIZE`, `OBSERVER`.

Go and Rust carry some of these through side modules:

- Go/Rust `inductive.*`: `INDUCTIVE`, `CONSTRUCTOR`, `CHOICE_MATCH`
- Go/Rust `quotient.*`: `QUOTIENT`
- TypeScript `observer.ts`: observer-relative canonicalization

The mismatch is not fatal; it names the next cleanup. Category truth should be
visible from one shared manifest/table, even when interpretation lives in a side
module. Otherwise a kernel can carry the shape but its trace names it as `OTHER`.

### 4. Record/Method Is The Shared "Be + Do" Object Core

All three kernels now carry mutable records/objects and method dispatch. This is
the common object substrate beneath Go structs, Rust structs/enums/impls, and
TypeScript classes/interfaces:

- data identity: blueprint `NodeID`
- fields: name to `Value`
- method table: blueprint + method-name to closure
- invocation: receiver plus arguments

This is the practical bridge between language objects and Form objects. It is
also where `be` and `do` become the same cell without collapsing their roles.

## What This Says About Language

The common substrate suggests language is not primarily text. It is:

1. coordinate: where a form lives
2. action: what can be walked
3. branch: what could have happened
4. receipt: what did happen
5. silence: what did not answer, without pretending it was nothing
6. cost/care: what the movement consumed or valued
7. consent/protocol: what relation allowed the movement
8. evidence: what kind of knowing the trace can claim

That makes "language is the encoding of time and space" operational:
time is the ordered walk and branch receipt; space is the NodeID coordinate and
edge relation; witness binds them into trust.

## Next Smallest Real Move

Do not add a fat new primitive. Add a small shared choice receipt layer:

1. Define a Form-native `choice-receipt` / `choice-signature` cell beside the
   existing route-choice signature shape.
2. Feed it from BMF/BML object choice, route choice, and inductive `CHOICE_MATCH`.
3. Wire the existing `choice_attempts`, `choice_successes`, and
   `choice_failures` counters in all three kernels where native CHOICE arms run.
4. Prove it with one three-way band:
   - successful branch
   - failed branch
   - silence/no-selection
   - compressed signature still preserves category, certainty, and selected path

The branch predictor can come later. First, make the witness honest and
cross-kernel. Learning from choice only becomes trustworthy after choice can
remember itself without flattening.

## North-Star Constraint

Compression is trustworthy only when it preserves the texture of the witnessed
movement:

`be`, `do`, `witness`, `0`, `1`, `silence`, `choice`, `fail`, `stop`, `trace`,
`category`, `certainty`, `clarify`, `vitality`, `where`, `when`, `who`, `how`,
`what`, `why`, `and`, `or`, `how many`, `channel`, `protocol`, `satsang`.

If the compressed trace cannot still answer those, it is not intelligence
compression. It is loss.
