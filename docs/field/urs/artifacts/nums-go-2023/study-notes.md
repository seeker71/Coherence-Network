# NUMS.Go — Study Notes (phase 1a)

Building-knowledge synthesis from a deep walk of the source 2026-05-08. The earlier `README.md` carries the architectural narrative; this file carries the implementation detail an agent needs to *build* a NUMS-shaped substrate, not just describe one.

Source paths below are absolute against `/Users/ursmuff/source/NUMS.Go`.

## Three layers, each with a clear API surface

```
                ┌─────────────────────────────────────────┐
                │  Query Layer (http/, http/model/)        │
                │  Labels, Histograms, IdScopes, QueryFilter│
                │  REST API: /folders /files /nodes /labels│
                └─────────────────────────────────────────┘
                              ↑
                              │ exposes
                              │
                ┌─────────────────────────────────────────┐
                │  Kernel (nums/)                         │
                │  Module + BlueprintDB + RecipeDB        │
                │  EmitModule with 5 stacks for in-flight │
                │  NodeID 4-tuples; content-addressed     │
                └─────────────────────────────────────────┘
                              ↑
                              │ driven by
                              │
                ┌─────────────────────────────────────────┐
                │  Language Bridge (nums/go.go = 71 visitors)│
                │  FileParser_t.NodeProcess[sitter.Symbol]  │
                │     → ParseNode_f                        │
                └─────────────────────────────────────────┘
                              ↑
                              │ tree-sitter parses
                              │
                ┌─────────────────────────────────────────┐
                │  Source (Go, Python, Java, ... Verilog)  │
                └─────────────────────────────────────────┘
```

## The kernel (`nums/`)

### NodeID — the universal handle

```go
type NodeID_t struct {
    Package  NodePackage  // uint16
    Level    NodeLevel    // uint16
    Type     NodeType     // uint16
    Instance NodeInstance // uint32
}
```

Two specializations:
- `RecipeNodeID_t = NodeID_t` (with helper methods like `IsTrivial()`, `IsBasic()`, `IsCompare()`, `IsMathPlus()`)
- `BlueprintNodeID_t = NodeID_t` (with helper methods like `IsCObject()`, `IsRPointer()`, `CanHave_Members()`)
- `BlueprintEdgeNodeID_t = BlueprintNodeID_t + Edge BlueprintEdge` (BlueprintEdge is a 23-bit flag set: Const/Static/Public/Atomic/Operator/Virtual/Override/Abstract/Mutable/Input/Output/Attribute/Constructor/Destructor/Friend/Unsafe/RefCnt/Box/Size/Embed/Parent/Function/HasDefault)

The Edge byte rides alongside the BlueprintNodeID for blueprint references — it carries attribute flags without changing the identity. So `*int` const-public and `*int` private-mutable share the same BlueprintNodeID but different BlueprintEdgeNodeIDs.

### The category vocabulary (full enumeration)

**Recipe trivial (Level 1) types** — leaf-level recipe primitives:
`Null, Bool, Integer, Decimal, Imag, String, Literal, BuiltIn, Local_Decl, Local_Access, Parameter, Member, Global, Blueprint, Label, Empty, Jump, Exception`

**Recipe basic (Level 2) types** — composite verb categories:
`Compare, Logic, Math, BitMath, TempWrite, Write, Access, Block, Sync, Cond, Loop, Jump, Flow, Memory, Transform, Exception, Call, FunctionDecl, TypeDecl`

Each basic-type expands into operator instances:
- `Compare`: `==`, `!=`, `>`, `<`, `>=`, `<=`, `<=>`, `===`, `!==`, `~==`
- `Math`: `+`, `-`, `*`, `/`, `//`, `%`
- `BitMath`: `~`, `&`, `|`, `^`, `<<`, `>>`, `<<<`, `>>>`, `&^`
- `Write` / `TempWrite`: `++`, `--`, `{0}++`, `{0}--`, `=`, `+=`, `-=`, `*=`, `/=`, `//=`, `%=`, `~=`, `&=`, `~^-`, `|=`, `^-`, `<<=`, `>>=`, `<<<=`, `>>>=`, `<-` (channel send)
- `Access`: `*` (deref), `.`, `[{0}]`, `->`, `&` (ref), `<-` (recv), `range`
- `Block`: `()`, `{}`, comma, newline
- `Cond`: `?:`, `if({0}){1}`, `if({0}){1} else {2}`, `SSwitch`, `ESwitch`, `Is`, `In`
- `Loop`: `for`, `foreach`, `while`, `do`
- `Jump`: `Return`, `Continue`, `Break`, `Yield`, `Goto`, `Case`, `Label`
- `Flow`: `go`, `defer`
- `Memory`: `new`, `make`, `delete`, `malloc`, `free`
- `Transform`: `Cast`
- `Exception`: `try`, `catch`, `throw`
- `Call`: function-call

**Blueprint trivial (Level 1) types**:
`Void, Numeric, Control, Runtime, Resource, Variadic`

Each numeric is `Bool, Integer, Decimal, Imag, Complex, Char, String` (with reserved slots for `Tensor, Time, Binary, Pixel`).

**Blueprint basic (Level 2) types**:
`Reference, Container, Recipe, Data`

Expanded:
- `Reference`: `Pointer, Reference, Symbol, Member, Optional`
- `Container`: `List, Dictionary, Object, Package, Interface, Any` (reserved: `Matrix, Location, Set, Template, Union`)
- `Recipe`: `Function, MemberFunction, Local, Parameter, Global`
- `Data`: `Channel` (reserved: `Event, Image, Video, Audio, Speech, Text`)

This enumeration is the *alphabet* of the substrate. Every program in any of the 14 supported languages is composed entirely from this vocabulary at the leaf, with `Complex_1..19` levels above for compositional depth.

### The interning store — `TreeDB`

```go
type TreeLevelDB_t struct {
    Entries         map[string]string   // sub_key → serialized_tree
    EntryCounts     map[string]float32
    RevEntries      map[string]string   // serialized_tree → sub_key
    BlueprintNextID map[NodeType]NodeInstance
}

type TreeDB_t struct {
    LevelEntries map[NodeLevel]TreeLevelDB_t  // partitioned by computed level
}
```

`TreeDB` is a `BlueprintTreeDB_t` and a `RecipeTreeDB_t` (same type, two aliases). The kernel keeps them separate because Blueprints and Recipes live in two ID-spaces.

`Record_Entry(level, serialized_tree, count, type)`:
1. Look up `RevEntries[serialized_tree]` — if found, increment count, return existing NodeID.
2. Otherwise allocate `NodeInstance(len(Entries) + 1)`, store, return new NodeID.

The serialized tree is `Category.String() + "+" + child_id_1.String() + "+" + child_id_2.String() + ...`. **Identity is the structural shape.** Two structurally identical entries collapse to one ID, with their hit-count incremented.

### `Make_SelfID` — the freeze gate

Every node passes through this idempotent gate to materialize:

```go
// BlueprintNode_t.Make_SelfID(attrs)
if n.Self.IsUndefined() && !n.Category.IsUndefined() {
    self_id := n.Module.BlueprintDB.Record_Blueprint(*n, 1, 0)
    n.Self = BlueprintEdgeNodeID_t{BlueprintNodeID_t(self_id), edgeFromAttrs(attrs)}
}
return n.Self
```

```go
// RecipeNode_t.Make_SelfID()
if n.Self.IsUndefined() && !n.Category.IsUndefined() {
    n.Self = RecipeNodeID_t(n.Module.RecipeDB.Record_Recipe(*n, 1, 0))
}
return n.Self
```

```go
// EmitRecipe_t.Make_SelfID() — recursive, the bottom-up assembly
if !r.SelfID.IsUndefined() { return r.SelfID }
if len(r.Statements) == 0 { return r.CategoryID }
nodes := make([]RecipeNodeID_t, 0)
for _, statement := range r.Statements {
    nodes = append(nodes, statement.Make_SelfID())  // recursive
}
node := RecipeNode_t{Module: ..., Category: r.CategoryID, Nodes: nodes}
r.SelfID = node.Make_SelfID()
return r.SelfID
```

The EmitRecipe version is the load-bearing one — it walks the in-progress recipe tree depth-first, interns each child, then interns the parent with the children's IDs. **At the end, the entire expression-tree is in RecipeDB as a content-addressed forest with shared sub-tree dedup.**

### Level computation

```go
func get_level(selfLevel, categoryLevel, nodeCount, maxNodeLevel int) NodeLevel {
    if selfLevel > 0 { return selfLevel }
    if categoryLevel == Level_Trivial || nodeCount == 0 { return categoryLevel }
    return NodeLevel(max(maxNodeLevel, int(categoryLevel)) + 1)
}
```

A node's level is `max(maxChildLevel, categoryLevel) + 1` when it has children. Trivial categories with no children stay at Trivial. **Levels emerge bottom-up from compositional depth** — no manual annotation. Level promotion in `Record_Blueprint` / `Record_Recipe`: if `nodeCount == 0 && Should_Reserve()` → bump level by 1 (reserved leaf-level slots); if `nodeCount > 0 && level <= 2` → force level = 3 (composites are at least Complex_1).

### `EmitModule` — the construction-time scaffolding

```go
type EmitModule_t struct {
    *Module_t                                  // the body being built
    Name              string
    BlueprintEmitters Stack_t[*EmitBlueprint_t]  // in-flight blueprints
    RecipeEmitters    Stack_t[*EmitNamedRecipe_t] // in-flight named recipes
    GlobalRecipe      EmitNamedRecipe_t           // the file's "$global" recipe holding top-level statements

    NamedBlueprints   map[string]*EmitBlueprint_t
    NamedRecipes      map[string]*NamedRecipe_t
    NamedCells        map[string]*NamedCell_t

    BlueprintStack    Stack_t[Blueprint_t]      // current type-context
    BuildModeStack    Stack_t[BuildMode]        // current build-phase
    ResultStack       Stack_t[Result_t]         // inter-visitor result passing

    DefaultBP         Blueprint_t                // default = Integer_Type
    init_ndx          int
    anonymous_id      int
}
```

**Five stacks**, each with a clear role:

| Stack | What it carries | When pushed | When popped |
|---|---|---|---|
| `BlueprintEmitters` | nested blueprint-builders | `Start_Blueprint` | `End_Blueprint` |
| `RecipeEmitters` | nested named-recipe builders (function bodies) | `Start_Method` | `End_Method` |
| `BlueprintStack` | current type context | enter scope | leave scope |
| `BuildModeStack` | current parse phase | `Start_*` (16 modes) | `End_*` |
| `ResultStack` | inter-visitor return values | between visitor calls | when consumed |

The 16 `BuildMode` values: `MethodDeclaration, MethodBody, TypeDefinition, Parameter, Return, Constructor, MethodDefinition, Call, Init, VarDecl, Key`. Each `Start_*` / `End_*` pair brackets a parsing scope so visitors can know "what am I inside right now?" without explicit threading.

### `EmitNamedRecipe` — function/method scaffolding

```go
type EmitNamedRecipe_t struct {
    EmitRecipe_t                        // base recipe (for the body)
    EmitModule       *EmitModule_t
    Name             string
    Attributes       NamedRecipeAttrs   // Abstract/Public/Static/Virtual/Const
    ReturnBlueprint  Blueprint_t
    Declaring        *Blueprint_t       // parent class, if a method
    Parameters       []EmitParameter_t
    ParameterBPs     []Blueprint_t
    Emitters         []*EmitRecipe_t    // local recipe-block stack
    BodyID           RecipeNodeID_t
    ParameterID      RecipeNodeID_t
    RecipeSymbols    *RecipeSymbolTable_t  // locals/parameters/literals
}
```

Plus methods: `Make_RecipeID()`, `Make_BlueprintID()`, `Set_Body(body)`, `Start_Compound()`, `Start_Block(r)`, `End_Block(r)`, `Top_Block()`, `Top_EmitRecipe()`. Together these form the function-body construction API.

`Make_RecipeID()` is interesting: it builds the function's full Blueprint-ID (return + self + params) AND its body Recipe-ID by calling `EmitModule.Declare_Function(...)`. So a function isn't just "a name + a body" — it's a Blueprint (its callable signature) AND a Recipe (its body) bound together with shared symbols.

### `EmitRecipe` — recipe-tree construction

The recipe-tree is built bottom-up via `Push_Statement` and the `NewEmit*` factory functions:

| Factory | Produces |
|---|---|
| `NewEmitLiteralBool/Integer/Decimal/Imag/String/Char/Null` | leaf literals (RTType_*) |
| `NewEmitLiteral(method, val, bp)` | typed literal |
| `NewEmitBlockComma/NewLine/Compound/Paranthesize` | compound-of-statements |
| `NewEmitUnaryExpression(method, op, operand, bp)` | `!x`, `&x`, `*x`, `-x` |
| `NewEmitBinaryExpression(method, op, left, right, bp)` | `a + b`, `a == b`, `a.b` |
| `NewEmitWrite / NewEmitTempWrite(method, op, left, right)` | `=`, `+=`, etc. (Write vs TempWrite based on whether LHS touches global state) |
| `NewEmitConditionalIf / IfElse` | `if (c) {...}` / `if (c) {...} else {...}` |
| `NewEmitLoopFor` | `for init; cond; update { body }` |
| `NewEmitRange` | `range x` |
| `NewEmitFlowGo / FlowDefer` | `go expr`, `defer expr` |
| `NewEmitJumpContinue / Break / Return / ReturnExpr` | jumps |
| `NewEmitTransform(method, op, bpR, operand, bp)` | type cast |
| `NewEmitLocalInit / NewEmitTempWriteInit` | local-decl + init binding |

Each carries its own `CategoryID` and a list of `*EmitRecipe_t` statements. `Make_SelfID` walks recursively.

### `Resolve_Identifier` — the auto-growing symbol resolution

[`emit_recipe.go:198-305`](../../../../source/NUMS.Go/nums/emit_recipe.go#L198) — when a visitor encounters a bare identifier, it dispatches through:

```
For undefined base:
  Local → Parameter → (if member-capable type) Member →
  Function → Global → (if not call) Blueprint →
  Auto-declare (Local for VarDecl, Method for call, Global otherwise)

For package base:
  Function → Global → (if not call) Blueprint →
  Auto-declare member or method on the package

For other base:
  Member →
  Auto-declare field or method on the parent blueprint
```

**The substrate auto-grows when an unknown identifier is encountered.** Depending on context (BuildMode, base type, call vs access), it auto-declares a new local/global/field/method/blueprint and re-resolves. The lattice extends itself. This is what makes the parser tolerant of forward references and partial information.

### How a cell is born — definitive

For a global `var greeting = "hello"`, the path is `EmitModule.Make_Field(name, attrs, bp, init)` ([`emit_module.go:182-200`](../../../../source/NUMS.Go/nums/emit_module.go#L182)):

```
1. category_id = Emplace_Global(name, bp.ID)                  → fresh trivial Global RID
2. access      = NewEmitRecipe(GlobalRecipe, category_id, ..., bp)  → the access-recipe leaf
3. if init != nil:
     emitMethod = NewEmitNamedRecipe(m, "CTOR:"+name, 0)
     emitMethod.RecipeSymbols = GlobalRecipe.RecipeSymbols    → share symbols
     body = NewEmitBlockComma(emitMethod)
     body.Push_Statement(access)
     body.Push_Statement(NewEmitBinaryExpression(emitMethod, "=", access, init, bp))
     emitMethod.Set_Body(body)
     emitMethod.ReturnBlueprint = bp
     ctor = emitMethod.Make_RecipeID()                        → INTERN the CTOR
     m.Symbols.Set_GlobalCTOR(category_id.Instance, ctor)
4. m.NamedCells[name] = NewField(
       Recipe(bp.ID, category_id),
       BlueprintNodeID_t{},                                   → empty Base (it's a global, not a member)
       name,
       ctor)
```

For a struct field — `EmitBlueprint.Make_Field(name, fieldBP, attrs, init)` ([`emit_blueprint.go:110-114`](../../../../source/NUMS.Go/nums/emit_blueprint.go#L110)) — only appends to `bp.NamedCells`. Interning is deferred until `End_Blueprint` ([`emit_blueprint.go:164-191`](../../../../source/NUMS.Go/nums/emit_blueprint.go#L164)):

```
node = Make_Node()                                            → fresh BlueprintNode with the right Category
member_ids = Make_MemberIDs()
for field in NamedCells:
    field_bid = field.Get_BlueprintEdgeNodeID()
    node.Record_Member(field.Name, field_bid, member_ids)     → adds child + tracks name→inst
for method in NamedRecipes:
    add_Method(method, node)                                  → adds the method's Blueprint to children
SelfID = node.Make_SelfID(attrs)                              → INTERN the whole struct
Record_Blueprint(SelfID, name)
```

The struct's identity = `serialized(Category + ordered child Blueprint IDs)`. Cells are part of what the struct *is*, not something it *has*.

## The language bridge (`nums/go.go`)

### Dispatch mechanism

```go
type ParseNode_f func(l FileParser_t, n ContentNode_t) (r *Result_t)

type FileParser_t struct {
    File        *File_t
    NodeProcess map[sitter.Symbol]ParseNode_f  // dispatch by tree-sitter symbol-ID
    EmitModule  *EmitModule_t
    ImportOnly  bool
}
```

`p.Process(n)` looks up `NodeProcess[n.TSSymbol()]` and calls it. The `RegisterGo()` method (in go.go) populates the map with all 71 visitors. Adding a 15th language = writing a `RegisterPython()` / `RegisterRust()` that registers analogous visitors against that language's tree-sitter symbols. **The kernel doesn't know about any specific language.**

### Visitor pattern

Every visitor has the same shape:

```go
func name(p FileParser_t, n ContentNode_t) *Result_t {
    // 1. Read fields from the AST node
    field_n := n.Get_Field("name")
    // 2. Drive EmitModule via Start_*/End_* pairs
    emitX := p.EmitModule.Start_X(...)
    p.EmitModule.End_X(emitX)
    // 3. Recursively process children
    p.Process(*child_n)
    // 4. Return Result_t (string|bool|int|float|Blueprint|Recipe)
    return NewResultBlueprint(emitX.Blueprint)
}
```

### Worked examples (representative)

**`function_declaration`** — top-level structural:
```
name = ProcessField(n, "name")
emitMethod = Start_Method(name, attrs)
Start_Parameter; ProcessField("parameters"); Emplace_ParameterSymbols; End_Parameter
Start_Return; result = ProcessField("result"); End_Return
Start_MethodBody; body = FieldAsRecipe("body"); Set_Body(body); End_MethodBody
End_Method(emitMethod, false)
```

**`struct_type`** + **`field_declaration`**:
```
struct_type:
  name = popped from ResultStack
  emitType = Start_Blueprint(name, BlueprintAttrs_Struct)
  Process(named_child[0])  // the field-declaration-list
  End_Blueprint(emitType)

field_declaration:
  emitBP = Peek_EmitBlueprint()
  bp = NodeAsBlueprint(type_n)
  for each name:
    emitBP.Make_Field(name, bp, attrs, nil)
  if no names: embed-only, Make_Field(typeName, bp, attrs|Embed, nil)
```

**`if_statement`**:
```
emitMethod = Top_EmitMethod()
init, cond, conseq, alt = FieldAsRecipe(...) for each field
if init != nil: cond = BlockComma(init, cond)
return alt != nil
       ? NewEmitConditionalIfElse(emitMethod, cond, conseq, alt)
       : NewEmitConditionalIf(emitMethod, cond, conseq)
```

**`binary_expression`**:
```
left = NodeAsRecipe(left_n)
Push_AccessBlueprint(left.Blueprint)        // base-type context for the right side
right = NodeAsRecipe(right_n)
Pop_AccessBlueprint()
op = field("operator").Get_Content()
bp = right.Blueprint
if op in {||, &&, ==, !=, >, >=, <, <=}: bp = Bool
return NewEmitBinaryExpression(emitMethod, op, left, right, bp)
```

**`selector_expression`** (`a.b`):
```
operand = NodeAsRecipe(operand_n)
baseType = operand.Blueprint
if !baseType.CanHave_Members():
    auto-declare an empty struct as base
block.Push_BaseBlueprint(baseType)
field = FieldAsRecipe("field")              // resolves against the base
block.Pop_BaseBlueprint()
return NewEmitBinaryExpression(emitMethod, ".", operand, field, field.Blueprint)
```

**`call_expression`**:
```
if func is "new" or "make": Memory recipe with appropriate type
if func is a primitive type-name: Transform/cast recipe
otherwise:
  arguments = NodeAsRecipe(args_n)
  block.Push_ArgBlueprints(arguments.Get_Blueprints())
  Start_Call; function = NodeAsRecipe(func_n); End_Call
  block.Pop_ArgBlueprints()
  return Call recipe with [function, arguments] as statements
```

### Result_t — the inter-visitor protocol

```go
type Result_t struct {
    bool      null.Bool
    int_      null.Int
    float     null.Float
    string_   null.String
    Blueprint *Blueprint_t
    Recipe    *EmitRecipe_t
}
```

A tagged union. Visitors return small typed values flowing up the tree. `ResultAsRecipe` resolves a string-result to a recipe via `Resolve_Identifier` if no recipe was set.

## The query layer (`http/`)

The kernel speaks in 4-tuple NodeIDs; the query layer wraps them in named entities with rich metadata for human and agent consumption.

### The data model (`http/model/model.go`)

```go
type GoPackage_t struct {
    Path, Name, ImportPath string
    Files                  map[string]*File_t
    Blueprints             NamedIdScopes_t   // ← the trinity at package level
    Recipes                NamedIdScopes_t
    Cells                  NamedIdScopes_t
}

type Node_t struct {
    ID             NodeLocation_t   // {Start byte, Level}
    File, Folder   *File_t, *Folder_t
    Level          NodeLevel_t      // bottom-up
    Position       NodePosition_t
    Parent, Children
    ResolvedLabels Labels_t
    IdScope        *IdScope_t
    Blueprint      Blueprint
    sentence_, depth_, ...
}

type IdScope_t struct {
    ID         IdentifierID_t
    Name       string
    Parent     *IdScope_t
    Children   NamedIdScopes_t
    Properties map[string]*Node_t
    Kind       *Label_t
    Labels     Labels_t
    Decl       *Node_t
    Blueprint  Blueprint
    RecipeInfo *RecipeInfo_t

    Calling, Reads, Writes, Uses IdUses_t   // bidirectional cross-refs
}

type RecipeInfo_t struct {
    IsLeaf, IsRecursive, HasExtern bool
    Writes, DirectCalls, AllCalls, Blueprints IdScope_s
}
```

### The label system (the second layer of meaning)

```go
type LabelLevel_e int
const (
    LabelLevel_Leaf     // most specific
    LabelLevel_Basic
    LabelLevel_Category
    LabelLevel_Group
    LabelLevel_Top
    LabelLevel_Max
)

type Label_t struct {
    ID, Name
    Score      Score_t
    Level      LabelLevel_e
    Color      *Color_t
    Parent     *Label_t      // hierarchy
    Children   Labels_t
    Op         string
    Attribute  bool
}
```

Labels are a *separate hierarchy* from the structural lattice. Where Blueprint/Recipe/Cell describe **what code is**, Labels describe **what code means** — `whitespace`, `comment`, `code`, `recipe`, `keyword`, `blueprint`, `declaration`, `identifier`, `math`, `local`, `operator`, `unary`, `logic`, `not`, `bitmath`, `bit not`, `access`, `dereference`, `reference`, `channel`, `send`, `receive`, `binary`, `write`, `comparison`, `statement`, `expression`, `write-target`, `read-target`, `literal`, `pre-processor`, `use`, `import`. (From the `query api and todo.txt` design notes.)

Each TS symbol carries `PossibleLabels` (with scores) via `Language_Rules_t.Naming.Labels[LabelID][Symbol] = Language_Rules_Naming_Labels_Entry_t`. Resolution uses `Match` rules (predicates over node fields) and `NamingRule` (how to extract a name). **The label assignment is data-driven**, defined per-language in YAML or similar config, not hardcoded.

### Histograms — the frequency layer

```go
type SymbolLabelHistogram_t struct {
    TSSymbols  Histogram_t[sitter.Symbol]   // count of each tree-sitter symbol
    Labels     Histogram_t[LabelID_t]       // count of each NUMS label
    LoC        LoC_t
    SymScore, LabelScore Score_t
}
```

Per-file (and aggregated up to per-folder) histograms over both tree-sitter symbols and NUMS labels. **This is what makes the body queryable in *frequency* terms** — every file/folder has a structural fingerprint as a distribution over the vocabulary. Two files with the same symbol/label distribution are *frequency-equivalent*; structural equivalence is the deeper sibling.

### REST endpoints (`http/api.go`)

```
/api/folders                      list all folders
/api/files                        list all files (with optional filter)
/api/nodes                        query nodes (with QueryFilter_t)
/api/labels                       label catalog
/api/languages                    language catalog

/api/folder/:id                   one folder + children
/api/file?id=...                  one file + nodes + histogram
/api/node?folder=&file=&start=&level=  one node + children + label-resolution
/api/func/:id                     one function (recipe) + signature + calls/reads/writes
/api/id/:id                       one IdScope (symbol) + uses/decl/refs
/api/label/:id                    one label + parents/children
/api/file-types/:id               types defined in a file
/api/file-functions/:id           functions defined in a file

/html/file/:id                    HTML render with histogram + label-coloring
```

The API is **read-only** — the substrate is built by parsing source, not by API mutation. Mutations happen by re-parsing.

## What this means for our Phase 3 implementation

The kernel is small and clean:

| Component | Approx LoC | What we'd port |
|---|---|---|
| `nums_nodes.go` | ~850 | NodeID 4-tuple, BlueprintNode, RecipeNode, level computation, serialization |
| `nums_db.go` | ~270 | TreeDB / TreeLevelDB — content-addressed interning |
| `nums_consts.go` | ~910 | Category vocabulary (need to design our own, but pattern is clear) |
| `nums_symbols.go` | ~210 | Module + Recipe symbol tables (name → instance maps) |
| `module.go` | ~200 | Module facade |
| `blueprint.go` | ~265 | Blueprint_t |
| `recipe.go` | ~545 | Recipe_t + NamedCell_t + RecipeWriter |
| `emit*.go` | ~1200 | Construction-time scaffolding |

**Roughly 4500 LoC for the kernel + emit layer**, in Go. Porting to Python/TypeScript would be similar (perhaps shorter with less type-system gymnastics). Postgres-backed persistence adds maybe 500 LoC for the per-level table + index + interning trigger.

The query layer is bigger (~5000 LoC including the http handlers and label-rules engine) but maps onto our existing FastAPI surface naturally. We already have Postgres, Neo4j, FastAPI, slug-registries — the substrate would be a new schema layer underneath them, not a parallel system.

## Gaps still open after phase 1a

1. **Persistence** — NUMS lives in process memory. We need `tree_db` Postgres schema with idempotent insert-on-serialized-shape (UNIQUE index on serialized_tree per level).
2. **Concurrency** — single-process. We need optimistic locking on `Make_SelfID` for multi-agent worktrees.
3. **Cross-module references** — `Import_GoPackage` is stubbed. We need real import-resolution across packages.
4. **Tree-sitter symbol IDs are language-build-specific** — the language bridge maps `sitter.Symbol uint16` → visitor. Rebuilding tree-sitter changes the IDs. We'd need either a stable mapping table or to dispatch on symbol-name strings instead.
5. **The label-rules engine** — `Language_Rules_t` is a sophisticated data-driven system for assigning NUMS labels to tree-sitter symbols. We'd need to design our own label vocabulary for the Network's domain (concepts, ideas, specs, lineage edges, presence types) and a similar rules engine.

These are predictable from the vocabulary I now have. Each gap has a concrete shape; none is an architectural unknown.

## Phase 1b/1c next

- **1b**: build NUMS.Go against `sample/sample.go`, observe the populated DBs by walking from the package blueprint outward. Confirms my understanding by reality-test.
- **1c**: write a mini-NUMS for a tiny language (a 4-operator calculator with variables, or a JSON-Schema → Blueprint mapper). 200-400 lines. Where I get stuck = the precise gap in my understanding.

After those, the building-knowledge for Phase 2-4 (designing the Network's category vocabulary, implementing the kernel against Postgres, surfacing the query layer for agent reasoning) is implementation rather than discovery.
