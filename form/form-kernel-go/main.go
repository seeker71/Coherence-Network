// form-kernel-go — vertical-slice host for Form-on-top.
//
// Executes Form recipe trees and binary artifacts. The CLI still carries a
// source-to-recipe adapter for current tests; the kernel path is the
// substrate, walker, host primitives, and binary artifact loader.
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — all 22 RBasic dispatch arms
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, I/O, conversion
//   • Binary loader      — Form artifact bytes → recipe tree
//
// Parsers and grammars belong in Form artifacts above this layer.
//
// Usage:  form-kernel-go <file.fk>
//         form-kernel-go --bench
//         form-kernel-go --expr "(add 2 3)"

package main

import (
	"encoding/json"
	"fmt"
	"form-kernel-go/core"
	"hash/fnv"
	"io"
	"math"
	"net"
	"os"
	"path/filepath"
	"runtime/debug"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"form-kernel-go/jitabi"
)

// --- core types extracted to package core (so JIT plugins can import them) ---
type NodeID = core.NodeID
type NameID = core.NameID
type ValueKind = core.ValueKind
type Value = core.Value
type Record = core.Record
type Closure = core.Closure
type Frame = core.Frame

const (
	VNull    = core.VNull
	VInt     = core.VInt
	VStr     = core.VStr
	VBool    = core.VBool
	VList    = core.VList
	VClosure = core.VClosure
	VNodeID  = core.VNodeID
	VFloat   = core.VFloat
	VRecord  = core.VRecord
)

var (
	NewFrame      = core.NewFrame
	NewCallFrame  = core.NewCallFrame
	formatFloatJS = core.FormatFloatJS
)

// --- Socket natives — L1 physical layer (TCP) ---------------------------
// Connection table. Handles are monotone ints; the kernel never reveals
// the underlying Listener/Conn to Form code — only the handle. -1 always
// means error (sibling parity with Rust/TS). socket_close on -1 is a
// no-op returning -1.
var (
	socketTableMu sync.Mutex
	socketHandles       = map[int64]interface{}{} // listener or conn
	socketNextHnd int64 = 0
)

func socketRegister(v interface{}) int64 {
	socketTableMu.Lock()
	defer socketTableMu.Unlock()
	socketNextHnd++
	h := socketNextHnd
	socketHandles[h] = v
	return h
}

func socketLookup(h int64) interface{} {
	socketTableMu.Lock()
	defer socketTableMu.Unlock()
	return socketHandles[h]
}

func socketDrop(h int64) {
	socketTableMu.Lock()
	defer socketTableMu.Unlock()
	delete(socketHandles, h)
}

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// NodeID — the 4-tuple identity. Registered substrate ids use pkg=1.
// Runtime-interned composites use pkg=0 so temporary recipe ids cannot collide
// with registered/basic categories across an execution context boundary.
// Trivials encode their value in `Inst`.

const (
	LevelTrivial uint32 = 1
	LevelBasic   uint32 = 2

	// RBasic — aligned with api/app/services/substrate/category.py
	RBasicUndefined uint32 = 0
	RBasicWitness   uint32 = 6 // substrate self-attestation
	RBasicBlock     uint32 = 9
	RBasicCall      uint32 = 10 // invoke external effect (I/O, tool)
	RBasicCond      uint32 = 11
	RBasicMath      uint32 = 12
	RBasicCompare   uint32 = 13
	RBasicLogic     uint32 = 14
	RBasicAccess    uint32 = 15 // read property / field
	RBasicMatch     uint32 = 19 // match/switch by substrate key
	RBasicChoice    uint32 = 20 // choose/fail/stop - speculative branching
	RBasicMethod    uint32 = 27 // transform on a cell-like value
	RBasicTransmute uint32 = 76 // present value through Blueprint without changing identity
	// Kernel-demo additions (extending RBasic for self-hosting needs)
	RBasicFnDef        uint32 = 31
	RBasicFnCall       uint32 = 32
	RBasicIdent        uint32 = 33
	RBasicList         uint32 = 34  // list-literal recipe
	RBasicField        uint32 = 88  // Field Model Form: distributed field value
	RBasicCarrier      uint32 = 89  // sequence / graph / mesh / attention carrier
	RBasicTopology     uint32 = 90  // adjacency and boundary declaration
	RBasicFiber        uint32 = 91  // value shape at each field location
	RBasicRegion       uint32 = 92  // named carrier subset
	RBasicBoundary     uint32 = 93  // membrane / constraint surface
	RBasicNeighborhood uint32 = 94  // local context relation
	RBasicMatchField   uint32 = 95  // region / subgraph / gradient match
	RBasicDelta        uint32 = 96  // snapshot-relative candidate mutation
	RBasicResolve      uint32 = 97  // conflict algebra over deltas
	RBasicCommit       uint32 = 98  // atomic logical-time commit
	RBasicStep         uint32 = 99  // freeze/match/choose/delta/commit
	RBasicLift         uint32 = 100 // data -> field
	RBasicSample       uint32 = 101 // point/region probe
	RBasicObserve      uint32 = 102 // projection + receipt
	RBasicIntervene    uint32 = 103 // consented perturbation
	RBasicResidual     uint32 = 104 // loss / budget remainder
	RBasicReceipt      uint32 = 105 // transparent execution record
	RBasicCost         uint32 = 106 // observer cost ledger
	RBasicConsent      uint32 = 107 // permission surface
	RBasicEvidence     uint32 = 108 // observed/inferred/simulated status

	TrivInt    uint32 = 1
	TrivString uint32 = 2
	TrivBool   uint32 = 3
	TrivNull   uint32 = 4
	// INT64 — signed integer whose magnitude exceeds the 32-bit inst slot.
	// Integer literals fit inline in TrivInt while |n| ≤ 2^31-1; once a
	// literal (hash, address, large counter) crosses the int32 ceiling the
	// inst carries an index into the kernel's `i64s` overflow table, exactly
	// as FLOAT64 does with `f64s`. Both TrivInt and TrivInt64 decode to the
	// same Value{VInt, int64}, so arithmetic stays a single uniform i64 path.
	// Slot 5 is aligned three-way — Rust, Go, and TS all carry INT64 = 5.
	TrivInt64 uint32 = 5
	// FLOAT32 — IEEE 754 32-bit value stored inline; the inst field carries
	// the IEEE bit pattern reinterpreted as u32. No overflow table needed.
	// Matches sibling TS kernel's Triv.FLOAT32 = 6.
	TrivFloat32 uint32 = 6
	// FLOAT64 — IEEE 754 64-bit value; 64 bits exceed the 32-bit inst slot,
	// so the inst carries an index into the kernel's `f64s` overflow table.
	// Canonicalization on intern: NaN bit patterns collapse to qNaN, -0.0
	// collapses to +0.0, ±Inf stay distinct (mirrors Rust + TS sibling
	// kernels). The trivial float type tags are aligned three-way — Rust,
	// Go, and TS all carry FLOAT32 = 6 and FLOAT64 = 7. Cross-kernel parity
	// also rides on .fk source, where the token shape (digits+dot vs digits)
	// names the type, and on the .fkb value-carrying float record.
	TrivFloat64 uint32 = 7
)

// RMath / RCompare / RLogic / RCond / RBlock instance constants
const (
	RMathPlus     uint32 = 1
	RMathMinus    uint32 = 2
	RMathMultiply uint32 = 3
	RMathDivide   uint32 = 4
	RMathModulo   uint32 = 5

	RCompareEq uint32 = 1
	RCompareNe uint32 = 2
	RCompareLt uint32 = 3
	RCompareLe uint32 = 4
	RCompareGt uint32 = 5
	RCompareGe uint32 = 6

	RLogicAnd uint32 = 1
	RLogicOr  uint32 = 2
	RLogicNot uint32 = 3

	RCondIfThen     uint32 = 1
	RCondIfThenElse uint32 = 2

	RBlockDo       uint32 = 1
	RBlockSequence uint32 = 2
	RBlockLet      uint32 = 3

	RMatchSwitch uint32 = 1

	RChoiceChoose uint32 = 1
	RChoiceFail   uint32 = 2
	RChoiceStop   uint32 = 3
)

// Recipe — composite storage. Trivials are NOT stored; their NodeID carries
// the value.
type Recipe struct {
	Category NodeID
	Children []NodeID
}

// NameID — interned identifier handle. The same uint32 used to encode a
// name trivial's NodeID instance is what every runtime name-lookup
// compares. String comparison happens once at parse time, never in the
// hot path.

// NativeEntry — a native's function plus the Form category it expresses.
// Carries Blueprint attribution into the kernel: when the walker dispatches
// through a native, the trace records the category alongside the FNCALL
// arm, so reasoning about which Form-shapes did the work reaches inside
// the host-language layer. UNDEFINED marks natives whose Form attribution
// hasn't been settled yet — honest, not omitted.
type NativeEntry struct {
	Name     NameID
	Category NodeID
	Fn       NativeFn
}

// armKey — (ty, inst) tuple key for trace dispatch counters. Storing the
// inst alongside ty surfaces typed-numeric distribution — MATH.PLUS_F64
// (inst=0x91) becomes distinguishable from MATH.PLUS_I32 (inst=0x01) in
// the report.
type armKey struct {
	Ty   uint32
	Inst uint32
}

// Trace — per-(arm, inst) dispatch counters. Held inside Kernel so the
// walker can record without threading an extra reference through every
// recursive call. Mirrors the Rust kernel's trace structure for sibling-
// kernel parity.
type Trace struct {
	TotalWalks      uint64
	ArmCounts       map[armKey]uint64 // (cat.Type, cat.Inst) → count
	FnCounts        map[string]uint64
	NativeCounts    map[string]uint64
	ChoiceAttempts  uint64
	ChoiceSuccesses uint64
	ChoiceFailures  uint64
	MatchLookups    uint64
	MatchHits       uint64
	MatchDefaults   uint64
	MatchMisses     uint64
}

func newTrace() *Trace {
	return &Trace{
		ArmCounts:    make(map[armKey]uint64),
		FnCounts:     make(map[string]uint64),
		NativeCounts: make(map[string]uint64),
	}
}

func (t *Trace) record(armTy uint32, armInst uint32) {
	t.TotalWalks++
	t.ArmCounts[armKey{Ty: armTy, Inst: armInst}]++
}

func (t *Trace) recordFn(name string) {
	t.FnCounts[name]++
}

func (t *Trace) recordNative(name string) {
	t.NativeCounts[name]++
}

// armName — label categories in the trace JSON. Walker arms + native
// Blueprint-attribution categories. Mirrors Rust kernel's Trace::arm_name.
func armName(armTy uint32) string {
	switch armTy {
	case RBasicBlock:
		return "BLOCK"
	case RBasicCond:
		return "COND"
	case RBasicMath:
		return "MATH"
	case RBasicCompare:
		return "COMPARE"
	case RBasicLogic:
		return "LOGIC"
	case RBasicMatch:
		return "MATCH"
	case RBasicIdent:
		return "IDENT"
	case RBasicFnDef:
		return "FNDEF"
	case RBasicFnCall:
		return "FNCALL"
	case RBasicList:
		return "LIST"
	case RBasicChoiceMatch:
		return "CHOICE_MATCH"
	case RBasicWitness:
		return "WITNESS"
	case RBasicCall:
		return "CALL"
	case RBasicAccess:
		return "ACCESS"
	case RBasicChoice:
		return "CHOICE"
	case RBasicMethod:
		return "METHOD"
	case RBasicTransmute:
		return "TRANSMUTE"
	case RBasicField:
		return "FIELD"
	case RBasicCarrier:
		return "CARRIER"
	case RBasicTopology:
		return "TOPOLOGY"
	case RBasicFiber:
		return "FIBER"
	case RBasicRegion:
		return "REGION"
	case RBasicBoundary:
		return "BOUNDARY"
	case RBasicNeighborhood:
		return "NEIGHBORHOOD"
	case RBasicMatchField:
		return "MATCH_FIELD"
	case RBasicDelta:
		return "DELTA"
	case RBasicResolve:
		return "RESOLVE"
	case RBasicCommit:
		return "COMMIT"
	case RBasicStep:
		return "STEP"
	case RBasicLift:
		return "LIFT"
	case RBasicSample:
		return "SAMPLE"
	case RBasicObserve:
		return "OBSERVE"
	case RBasicIntervene:
		return "INTERVENE"
	case RBasicResidual:
		return "RESIDUAL"
	case RBasicReceipt:
		return "RECEIPT"
	case RBasicCost:
		return "COST"
	case RBasicConsent:
		return "CONSENT"
	case RBasicEvidence:
		return "EVIDENCE"
	default:
		return "OTHER"
	}
}

// armVariantName — readable label for an (arm_ty, arm_inst) pair.
// Returns "MATH.PLUS", "COMPARE.LE", "BLOCK.LET", etc. For arms without
// a known inst encoding, returns just the bare arm name. Symmetric with
// the Rust/TS variant naming.
func armVariantName(armTy uint32, armInst uint32) string {
	base := armName(armTy)
	var variant string
	switch armTy {
	case RBasicMath:
		switch armInst {
		case RMathPlus:
			variant = "PLUS"
		case RMathMinus:
			variant = "MINUS"
		case RMathMultiply:
			variant = "MUL"
		case RMathDivide:
			variant = "DIV"
		case RMathModulo:
			variant = "MOD"
		}
	case RBasicCompare:
		switch armInst {
		case RCompareEq:
			variant = "EQ"
		case RCompareNe:
			variant = "NE"
		case RCompareLt:
			variant = "LT"
		case RCompareLe:
			variant = "LE"
		case RCompareGt:
			variant = "GT"
		case RCompareGe:
			variant = "GE"
		}
	case RBasicLogic:
		switch armInst {
		case RLogicAnd:
			variant = "AND"
		case RLogicOr:
			variant = "OR"
		case RLogicNot:
			variant = "NOT"
		}
	case RBasicCond:
		switch armInst {
		case RCondIfThen:
			variant = "IF"
		case RCondIfThenElse:
			variant = "IF_ELSE"
		}
	case RBasicBlock:
		switch armInst {
		case RBlockDo:
			variant = "DO"
		case RBlockSequence:
			variant = "SEQ"
		case RBlockLet:
			variant = "LET"
		}
	case RBasicMatch:
		switch armInst {
		case RMatchSwitch:
			variant = "SWITCH"
		}
	case RBasicChoice:
		switch armInst {
		case RChoiceChoose:
			variant = "CHOOSE"
		case RChoiceFail:
			variant = "FAIL"
		case RChoiceStop:
			variant = "STOP"
		}
	}
	if variant == "" {
		return base
	}
	return base + "." + variant
}

func (t *Trace) toJSON() map[string]interface{} {
	type variantRec struct {
		ArmTy      uint32 `json:"arm_ty"`
		ArmInst    uint32 `json:"arm_inst"`
		ArmName    string `json:"arm_name"`
		ArmVariant string `json:"arm_variant_name"`
		Count      uint64 `json:"count"`
	}
	type armRec struct {
		ArmTy   uint32 `json:"arm_ty"`
		ArmName string `json:"arm_name"`
		Count   uint64 `json:"count"`
	}
	type nameRec struct {
		Name  string `json:"name"`
		Count uint64 `json:"count"`
	}

	// Per-(ty, inst) records — preserves typed-numeric distribution.
	variants := make([]variantRec, 0, len(t.ArmCounts))
	for k, c := range t.ArmCounts {
		variants = append(variants, variantRec{
			ArmTy:      k.Ty,
			ArmInst:    k.Inst,
			ArmName:    armName(k.Ty),
			ArmVariant: armVariantName(k.Ty, k.Inst),
			Count:      c,
		})
	}
	sort.Slice(variants, func(i, j int) bool { return variants[i].Count > variants[j].Count })

	// Per-ty aggregate — kept for backward compatibility with consumers
	// that want the coarser shape.
	byTy := make(map[uint32]uint64)
	for k, c := range t.ArmCounts {
		byTy[k.Ty] += c
	}
	arms := make([]armRec, 0, len(byTy))
	for ty, c := range byTy {
		arms = append(arms, armRec{ArmTy: ty, ArmName: armName(ty), Count: c})
	}
	sort.Slice(arms, func(i, j int) bool { return arms[i].Count > arms[j].Count })

	functions := make([]nameRec, 0, len(t.FnCounts))
	for name, c := range t.FnCounts {
		functions = append(functions, nameRec{Name: name, Count: c})
	}
	sort.Slice(functions, func(i, j int) bool { return functions[i].Count > functions[j].Count })

	natives := make([]nameRec, 0, len(t.NativeCounts))
	for name, c := range t.NativeCounts {
		natives = append(natives, nameRec{Name: name, Count: c})
	}
	sort.Slice(natives, func(i, j int) bool { return natives[i].Count > natives[j].Count })

	rate := 0.0
	if t.ChoiceAttempts > 0 {
		rate = float64(t.ChoiceSuccesses) / float64(t.ChoiceAttempts)
	}
	return map[string]interface{}{
		"total_walks":         t.TotalWalks,
		"arms":                arms,     // aggregated by ty (backward-compatible)
		"variants":            variants, // full (ty, inst) granularity
		"functions":           functions,
		"natives":             natives,
		"choice_attempts":     t.ChoiceAttempts,
		"choice_successes":    t.ChoiceSuccesses,
		"choice_failures":     t.ChoiceFailures,
		"choice_success_rate": rate,
		"match_lookups":       t.MatchLookups,
		"match_hits":          t.MatchHits,
		"match_defaults":      t.MatchDefaults,
		"match_misses":        t.MatchMisses,
	}
}

// Kernel — the running substrate.
type Kernel struct {
	byHash map[uint64]NodeID
	byID   map[NodeID]Recipe
	strs   []string
	strIdx map[string]NameID
	next   uint32
	// Float64 overflow table — IEEE 754 values don't fit the 32-bit `inst`
	// field, so the FLOAT64 trivial NodeID carries an index into `f64s`.
	// `f64Idx` is keyed by the IEEE bit pattern after canonicalization
	// (NaN → qNaN, -0.0 → +0.0) so the same value parsed twice yields the
	// same NodeID. Mirrors Rust + TS sibling kernels.
	f64s       []float64
	f64Idx     map[uint64]uint32
	// Int64 overflow table — the sibling of `f64s` for integers wider than the
	// 32-bit inst slot. `i64Idx` is keyed by the value itself (integers are
	// already canonical) so the same literal interns to the same NodeID.
	i64s       []int64
	i64Idx     map[int64]uint32
	natives    map[NameID]NativeEntry
	envNatives map[NameID]EnvAwareNativeEntry
	// methods — the blueprint method table (BML/NUMS reference: methods live
	// on the blueprint/type, shared by all instances, name-dispatched). Keyed
	// by (blueprint, method-name) → the method's Closure.
	methods map[methodKey]*Closure
	// jitAliases: Form-function-name → native-name redirect. When a
	// function call's name is in this map, the walker substitutes the
	// aliased name before native lookup. Lets a Form recipe DEFINE an
	// algorithm as canonical truth; a `register_jit` call makes its
	// calls dispatch to a kernel-resident optimized native. Removing
	// the entry falls back to walking the Form recipe.
	jitAliases map[NameID]NameID
	// SourceAttr — NodeID → (file_name_id, line, col). Populated by
	// intern_node_at; read by node_source. The satsang-load-bearing
	// surface: every cell's state traceable to the source line that
	// authored it. The practice of self-knowing.
	sourceAttr map[NodeID]sourceLoc
	importSeq  uint32
	// walkCache — JIT-vector memoization for pure recipes. Keyed by
	// recipe NodeID. Real JIT replaces this with compiled native code;
	// the architectural slot is the same: same NodeID = same result.
	walkCache        map[NodeID]Value
	walkCacheHits    uint64
	walkCacheMisses  uint64
	activeRoots      []NodeID
	framebufferRoots []NodeID
	observeRuntime   bool
	observeSeq       uint32
	sourceCompileErr string
	// Optional tracing — nil for hot-path runs, set for trace subcommand.
	// Per lc-native-kernel-binary's "tracing and observation pattern."
	Trace *Trace
	// jitCompiledGo - body-NodeID-key -> host-native typed function pointers.
	// Populated by the recipe→Go-source+plugin.Open JIT path (see jit.go's
	// machinery wired into the `jit_compile` env-aware native). Read on every
	// FNCALL closure dispatch: when present, marshal Form values into the ABI
	// whose guard matches (i64, f64, or jitabi.Value), call generated Go, and
	// box the result. Same shape as TS kernel's k.jitCompiled, widened for
	// honest guard-miss observation.
	jitCompiledGo map[string]*GoJITCompiled
	// jitCompiledGoV — body-NodeID-key → Value-typed native function. The
	// general JIT path (jit_value.go): compiles ANY recipe to a plugin that
	// operates on core.Value and routes native / cross-function calls back
	// through a kernel-supplied dispatch. Read on FNCALL closure dispatch
	// before the int64 fast path; when present, runs the body native with no
	// walk-interpreter overhead. Falls back to walk when a shape can't lower.
	jitCompiledGoV  map[string]jitValueFn
	jitHits         map[NodeID]uint32
	jitFailed       map[NodeID]bool
	jitFailedReason map[NodeID]string
	jitDispatchHits map[NodeID]uint32
	switchTables    map[NodeID]*switchTable
}

type switchTable struct {
	cases       map[NodeID]NodeID
	dynamicArms []switchArm
	defaultBody NodeID
	hasDefault  bool
}

type switchArm struct {
	pattern NodeID
	body    NodeID
}

type sourceLoc struct {
	FileID NameID
	Line   uint32
	Col    uint32
}

func NewKernel() *Kernel {
	k := &Kernel{
		byHash:          make(map[uint64]NodeID),
		byID:            make(map[NodeID]Recipe),
		strIdx:          make(map[string]NameID),
		sourceAttr:      make(map[NodeID]sourceLoc),
		importSeq:       1,
		walkCache:       make(map[NodeID]Value),
		next:            1,
		f64Idx:          make(map[uint64]uint32),
		i64Idx:          make(map[int64]uint32),
		natives:         make(map[NameID]NativeEntry),
		envNatives:      make(map[NameID]EnvAwareNativeEntry),
		methods:         make(map[methodKey]*Closure),
		jitAliases:      make(map[NameID]NameID),
		jitCompiledGo:   make(map[string]*GoJITCompiled),
		jitCompiledGoV:  make(map[string]jitValueFn),
		jitHits:         make(map[NodeID]uint32),
		jitFailed:       make(map[NodeID]bool),
		jitFailedReason: make(map[NodeID]string),
		jitDispatchHits: make(map[NodeID]uint32),
		switchTables:    make(map[NodeID]*switchTable),
	}
	k.registerNatives()
	return k
}

func resolveKernelHostPath(path string) string {
	if path == "" || filepath.IsAbs(path) {
		return path
	}
	slashPath := filepath.ToSlash(path)
	if slashPath == "form-stdlib" || strings.HasPrefix(slashPath, "form-stdlib/") {
		root, err := findRepoRoot()
		if err == nil {
			return filepath.Join(root, "form", filepath.FromSlash(slashPath))
		}
	}
	return path
}

func sourceInventorySkipSet(v Value) map[string]bool {
	skip := map[string]bool{}
	if v.Kind != VList {
		return skip
	}
	for _, item := range v.List {
		if item.Kind == VStr && item.Str != "" {
			skip[item.Str] = true
		}
	}
	return skip
}

func countTextLines(path string) int64 {
	body, err := os.ReadFile(path)
	if err != nil {
		return -1
	}
	if len(body) == 0 {
		return 0
	}
	lines := int64(strings.Count(string(body), "\n"))
	if body[len(body)-1] != '\n' {
		lines++
	}
	return lines
}

func sourceInventoryRow(rel string, loc int64) Value {
	return Value{Kind: VList, List: []Value{
		{Kind: VStr, Str: rel},
		{Kind: VInt, Int: loc},
	}}
}

func (k *Kernel) nextImportScope() uint32 {
	scope := k.importSeq
	k.importSeq++
	return scope
}

func (k *Kernel) remapImportedLeaf(scope uint32, nid NodeID) NodeID {
	if nid.Pkg != 0 {
		return nid
	}
	return k.intern(catUndefined(), []NodeID{
		k.internTrivialInt(int64(scope)),
		k.internTrivialInt(int64(nid.Level)),
		k.internTrivialInt(int64(nid.Type)),
		k.internTrivialInt(int64(nid.Inst)),
	})
}

func hashRecipe(r Recipe) uint64 {
	h := fnv.New64a()
	fmt.Fprintf(h, "C|%d.%d.%d.%d", r.Category.Pkg, r.Category.Level, r.Category.Type, r.Category.Inst)
	for _, c := range r.Children {
		fmt.Fprintf(h, "|%d.%d.%d.%d", c.Pkg, c.Level, c.Type, c.Inst)
	}
	return h.Sum64()
}

// intern — content-addressed insertion. Same shape ⇒ same NodeID.
func (k *Kernel) intern(category NodeID, children []NodeID) NodeID {
	r := Recipe{Category: category, Children: children}
	h := hashRecipe(r)
	if nid, ok := k.byHash[h]; ok {
		return nid
	}
	nid := NodeID{Pkg: 0, Level: category.Level, Type: category.Type, Inst: k.next}
	k.next++
	k.byHash[h] = nid
	k.byID[nid] = r
	return nid
}

func (k *Kernel) internTrivialInt(n int64) NodeID {
	// Inline while the value fits the 32-bit inst slot; overflow into `i64s`
	// once it crosses the int32 ceiling (mirrors internTrivialFloat64). Both
	// paths decode back to Value{VInt, int64} in trivialValue, so callers and
	// arithmetic never see the storage split.
	if n >= math.MinInt32 && n <= math.MaxInt32 {
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivInt, Inst: uint32(int32(n))}
	}
	if idx, ok := k.i64Idx[n]; ok {
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivInt64, Inst: idx}
	}
	idx := uint32(len(k.i64s))
	k.i64s = append(k.i64s, n)
	k.i64Idx[n] = idx
	return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivInt64, Inst: idx}
}

// decodeInt64 — read back the value from the i64 overflow table.
func (k *Kernel) decodeInt64(inst uint32) int64 {
	if int(inst) >= len(k.i64s) {
		panic(fmt.Sprintf("decodeInt64: bad index %d", inst))
	}
	return k.i64s[inst]
}

// internTrivialFloat32 — IEEE 754 32-bit inline encoding. The float's bit
// pattern (cast through math.Float32bits) lives directly in the inst slot;
// no overflow table needed. Two f32 values with the same bit pattern share
// the same NodeID by construction. NaN bit patterns are NOT canonicalized
// here because f32 NaNs are uncommon at the substrate boundary; if needed,
// the caller (or a typed-numeric layer above) collapses them first.
// Sibling parity with TS kernel's internTrivialFloat32.
func (k *Kernel) internTrivialFloat32(f float32) NodeID {
	bits := math.Float32bits(f)
	return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivFloat32, Inst: bits}
}

// internTrivialFloat64 — content-addressed insertion into the f64 overflow
// table. The trivial NodeID carries the table index in `inst`. Canonicalization
// matches the Rust + TS sibling kernels so the same float value parsed twice
// produces the same NodeID:
//   - any NaN bit pattern collapses to qNaN (0x7ff8000000000000)
//   - -0.0 collapses to +0.0
//   - ±Inf keep distinct identity
func (k *Kernel) internTrivialFloat64(f float64) NodeID {
	var canonical float64
	switch {
	case math.IsNaN(f):
		canonical = math.Float64frombits(0x7ff8000000000000)
	case f == 0.0:
		// IEEE 754: -0.0 == +0.0 by value comparison; collapse both to +0.0
		// so the substrate doesn't carry a redundant duplicate entry.
		canonical = 0.0
	default:
		canonical = f
	}
	bits := math.Float64bits(canonical)
	if idx, ok := k.f64Idx[bits]; ok {
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivFloat64, Inst: idx}
	}
	idx := uint32(len(k.f64s))
	k.f64s = append(k.f64s, canonical)
	k.f64Idx[bits] = idx
	return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivFloat64, Inst: idx}
}

// decodeFloat32 — read back the IEEE bit pattern from the inst slot.
func (k *Kernel) decodeFloat32(inst uint32) float32 {
	return math.Float32frombits(inst)
}

// decodeFloat64 — read back the value from the overflow table.
func (k *Kernel) decodeFloat64(inst uint32) float64 {
	if int(inst) >= len(k.f64s) {
		panic(fmt.Sprintf("decodeFloat64: bad index %d", inst))
	}
	return k.f64s[inst]
}

func (k *Kernel) internString(s string) NodeID {
	if idx, ok := k.strIdx[s]; ok {
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivString, Inst: uint32(idx)}
	}
	idx := NameID(len(k.strs))
	k.strs = append(k.strs, s)
	k.strIdx[s] = idx
	return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivString, Inst: uint32(idx)}
}

// internName — fast path when the caller already holds the string and
// only needs the NameID (no NodeID wrapper).
func (k *Kernel) internName(s string) NameID {
	if idx, ok := k.strIdx[s]; ok {
		return idx
	}
	idx := NameID(len(k.strs))
	k.strs = append(k.strs, s)
	k.strIdx[s] = idx
	return idx
}

func (k *Kernel) observationActive() bool {
	return k.observeRuntime || k.Trace != nil
}

func (k *Kernel) observeFrame(file string, line uint32, col uint32, children ...NodeID) {
	if !k.observationActive() {
		return
	}
	k.observeSeq++
	kids := make([]NodeID, 0, len(children)+1)
	kids = append(kids, k.internTrivialInt(int64(k.observeSeq)))
	kids = append(kids, children...)
	nid := k.intern(catReceipt(), kids)
	fileID := k.internName(file)
	k.sourceAttr[nid] = sourceLoc{FileID: fileID, Line: line, Col: col}
	k.activeRoots = append(k.activeRoots, nid)
	k.framebufferRoots = append(k.framebufferRoots, nid)
}

func (k *Kernel) observeRecipeDispatch(cat NodeID) {
	k.observeFrame(
		"observe/go/recipe-dispatch",
		cat.Type,
		cat.Inst,
		k.internTrivialInt(int64(cat.Type)),
		k.internTrivialInt(int64(cat.Inst)),
	)
}

func (k *Kernel) observeNamedDispatch(file string, name NameID) {
	k.observeFrame(file, uint32(name), 1, k.internString(k.nameStr(name)))
}

func (k *Kernel) observeJIT(file string, body NodeID, line uint32, col uint32) {
	k.observeFrame(file, line, col, body)
}

func (k *Kernel) nodeDisplay(n NodeID) string {
	if n.Level != LevelTrivial {
		return nodeIDKey(n)
	}
	return k.trivialValue(n).String()
}

func (k *Kernel) framebufferSourceCounts() []map[string]interface{} {
	type key struct {
		file string
		line uint32
		col  uint32
	}
	counts := map[key]int{}
	for _, nid := range k.framebufferRoots {
		loc, ok := k.sourceAttr[nid]
		if !ok {
			continue
		}
		file := ""
		if int(loc.FileID) < len(k.strs) {
			file = k.strs[loc.FileID]
		}
		counts[key{file: file, line: loc.Line, col: loc.Col}]++
	}
	rows := make([]map[string]interface{}, 0, len(counts))
	for k, count := range counts {
		rows = append(rows, map[string]interface{}{
			"file":  k.file,
			"line":  k.line,
			"col":   k.col,
			"count": count,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		ci := rows[i]["count"].(int)
		cj := rows[j]["count"].(int)
		if ci != cj {
			return ci > cj
		}
		fi := rows[i]["file"].(string)
		fj := rows[j]["file"].(string)
		if fi != fj {
			return fi < fj
		}
		li := rows[i]["line"].(uint32)
		lj := rows[j]["line"].(uint32)
		if li != lj {
			return li < lj
		}
		return rows[i]["col"].(uint32) < rows[j]["col"].(uint32)
	})
	return rows
}

func (k *Kernel) framebufferEvents() []map[string]interface{} {
	rows := make([]map[string]interface{}, 0, len(k.framebufferRoots))
	for _, nid := range k.framebufferRoots {
		loc, ok := k.sourceAttr[nid]
		if !ok {
			continue
		}
		file := ""
		if int(loc.FileID) < len(k.strs) {
			file = k.strs[loc.FileID]
		}
		kids := k.children(nid)
		seq := int64(0)
		if len(kids) > 0 && kids[0].Level == LevelTrivial && kids[0].Type == TrivInt {
			seq = int64(int32(kids[0].Inst))
		}
		childRows := make([]string, 0, len(kids))
		childValues := make([]string, 0, len(kids))
		for _, child := range kids {
			childRows = append(childRows, nodeIDKey(child))
			childValues = append(childValues, k.nodeDisplay(child))
		}
		rows = append(rows, map[string]interface{}{
			"seq":          seq,
			"file":         file,
			"line":         loc.Line,
			"col":          loc.Col,
			"node":         nodeIDKey(nid),
			"children":     childRows,
			"child_values": childValues,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		si := rows[i]["seq"].(int64)
		sj := rows[j]["seq"].(int64)
		if si != sj {
			return si < sj
		}
		return rows[i]["node"].(string) < rows[j]["node"].(string)
	})
	return rows
}

func (k *Kernel) substrateMark() []Value {
	return []Value{
		{Kind: VInt, Int: int64(k.next)},
		{Kind: VInt, Int: int64(len(k.strs))},
		{Kind: VInt, Int: int64(len(k.byID))},
	}
}

func (k *Kernel) substrateCounts() []Value {
	return []Value{
		{Kind: VInt, Int: int64(len(k.byID))},
		{Kind: VInt, Int: int64(len(k.strs))},
	}
}

func (k *Kernel) substrateRelease(mark []Value) int64 {
	if len(mark) < 2 {
		return 0
	}
	nextMark := uint32(mark[0].Int)
	strMark := int(mark[1].Int)
	if nextMark == 0 || strMark < 0 || strMark > len(k.strs) {
		return 0
	}
	var released int64
	for nid, recipe := range k.byID {
		if nid.Pkg == 0 && nid.Inst >= nextMark {
			delete(k.byID, nid)
			delete(k.byHash, hashRecipe(recipe))
			delete(k.sourceAttr, nid)
			delete(k.walkCache, nid)
			delete(k.switchTables, nid)
			released++
		}
	}
	for i := strMark; i < len(k.strs); i++ {
		delete(k.strIdx, k.strs[i])
	}
	k.strs = k.strs[:strMark]
	k.next = nextMark
	k.walkCache = make(map[NodeID]Value)
	return released
}

func markStringNode(n NodeID, liveStrings map[NameID]bool) {
	if n.Pkg == 1 && n.Level == LevelTrivial && n.Type == TrivString {
		liveStrings[NameID(n.Inst)] = true
	}
}

func (k *Kernel) markNode(n NodeID, liveNodes map[NodeID]bool, liveStrings map[NameID]bool) {
	markStringNode(n, liveStrings)
	if n.Pkg != 0 || liveNodes[n] {
		return
	}
	r, ok := k.byID[n]
	if !ok {
		return
	}
	liveNodes[n] = true
	k.markNode(r.Category, liveNodes, liveStrings)
	for _, child := range r.Children {
		k.markNode(child, liveNodes, liveStrings)
	}
}

func (k *Kernel) markValue(v Value, liveNodes map[NodeID]bool, liveStrings map[NameID]bool, liveFrames map[*Frame]bool) {
	switch v.Kind {
	case VList:
		for _, item := range v.List {
			k.markValue(item, liveNodes, liveStrings, liveFrames)
		}
	case VClosure:
		if v.Cl != nil {
			liveStrings[v.Cl.Name] = true
			k.markNode(v.Cl.Body, liveNodes, liveStrings)
			k.markFrame(v.Cl.Env, liveNodes, liveStrings, liveFrames)
		}
	case VNodeID:
		k.markNode(v.Nid, liveNodes, liveStrings)
	}
}

func (k *Kernel) markFrame(frame *Frame, liveNodes map[NodeID]bool, liveStrings map[NameID]bool, liveFrames map[*Frame]bool) {
	for cur := frame; cur != nil; cur = cur.Parent {
		if liveFrames[cur] {
			return
		}
		liveFrames[cur] = true
		for _, binding := range cur.Bindings {
			liveStrings[binding.Name] = true
			k.markValue(binding.Val, liveNodes, liveStrings, liveFrames)
		}
	}
}

func (k *Kernel) substrateGC(roots []Value, stack *Frame) []Value {
	liveNodes := make(map[NodeID]bool)
	liveStrings := make(map[NameID]bool)
	liveFrames := make(map[*Frame]bool)
	for name := range k.natives {
		liveStrings[name] = true
	}
	for _, loc := range k.sourceAttr {
		liveStrings[loc.FileID] = true
	}
	for _, root := range k.activeRoots {
		k.markNode(root, liveNodes, liveStrings)
	}
	for _, root := range roots {
		k.markValue(root, liveNodes, liveStrings, liveFrames)
	}
	if stack != nil {
		k.markFrame(stack, liveNodes, liveStrings, liveFrames)
	}
	for changed := true; changed; {
		beforeNodes := len(liveNodes)
		beforeStrings := len(liveStrings)
		for nid, value := range k.walkCache {
			if liveNodes[nid] {
				k.markValue(value, liveNodes, liveStrings, liveFrames)
			}
		}
		changed = len(liveNodes) != beforeNodes || len(liveStrings) != beforeStrings
	}
	var freed int64
	for nid, recipe := range k.byID {
		if nid.Pkg == 0 && !liveNodes[nid] {
			delete(k.byID, nid)
			delete(k.byHash, hashRecipe(recipe))
			delete(k.sourceAttr, nid)
			delete(k.walkCache, nid)
			delete(k.switchTables, nid)
			freed++
		}
	}
	for nid := range k.walkCache {
		if !liveNodes[nid] {
			delete(k.walkCache, nid)
		}
	}
	pruned := 0
	if stack != nil {
		for len(k.strs) > 0 {
			idx := NameID(len(k.strs) - 1)
			if liveStrings[idx] {
				break
			}
			delete(k.strIdx, k.strs[idx])
			k.strs = k.strs[:len(k.strs)-1]
			pruned++
		}
	}
	return []Value{{Kind: VInt, Int: freed}, {Kind: VInt, Int: int64(pruned)}}
}

func (k *Kernel) category(n NodeID) NodeID {
	if n.Level == LevelTrivial {
		return n
	}
	if r, ok := k.byID[n]; ok {
		return r.Category
	}
	return n
}

func (k *Kernel) children(n NodeID) []NodeID {
	if r, ok := k.byID[n]; ok {
		return r.Children
	}
	return nil
}

// recipeAt — fold of category + children. The walker's hot path uses this
// to do ONE map lookup per composite step instead of two. For trivials,
// the caller already short-circuited on Level before calling.
func (k *Kernel) recipeAt(n NodeID) Recipe { return k.byID[n] }

func (k *Kernel) isParallelPure(n NodeID, seen map[NodeID]bool) bool {
	if n.Level == LevelTrivial {
		return true
	}
	if seen[n] {
		return true
	}
	seen[n] = true
	r, ok := k.byID[n]
	if !ok {
		return false
	}
	switch r.Category.Type {
	case RBasicMath, RBasicCompare, RBasicLogic, RBasicCond, RBasicList, RBasicMatch:
		for _, child := range r.Children {
			if !k.isParallelPure(child, seen) {
				return false
			}
		}
		return true
	default:
		return false
	}
}

func (k *Kernel) trivialValue(n NodeID) Value {
	if n.Level != LevelTrivial {
		panic(fmt.Sprintf("trivialValue: %v is composite", n))
	}
	switch n.Type {
	case TrivInt:
		return Value{Kind: VInt, Int: int64(int32(n.Inst))}
	case TrivInt64:
		return Value{Kind: VInt, Int: k.decodeInt64(n.Inst)}
	case TrivString:
		return Value{Kind: VStr, Str: k.strs[n.Inst]}
	case TrivBool:
		return Value{Kind: VBool, Bool: n.Inst != 0}
	case TrivNull:
		return Value{Kind: VNull}
	case TrivFloat32:
		return Value{Kind: VFloat, Float: float64(k.decodeFloat32(n.Inst))}
	case TrivFloat64:
		return Value{Kind: VFloat, Float: k.decodeFloat64(n.Inst)}
	}
	panic(fmt.Sprintf("trivialValue: unknown trivial type %d", n.Type))
}

// identID — the NameID this identifier resolves to. No string lookup, no
// comparison; the inst slot IS the NameID.
func (k *Kernel) identID(n NodeID) NameID {
	if n.Level == LevelTrivial && n.Type == TrivString {
		return NameID(n.Inst)
	}
	kids := k.children(n)
	if len(kids) == 1 && kids[0].Level == LevelTrivial && kids[0].Type == TrivString {
		return NameID(kids[0].Inst)
	}
	panic(fmt.Sprintf("identID: %v is not an identifier shape", n))
}

// nameStr — resolve a NameID back to its source-level string. Error
// messages and parse-time only; never in the walker's hot path.
func (k *Kernel) nameStr(id NameID) string { return k.strs[id] }

// ---------------------------------------------------------------------------
// Values — runtime tagged values
// ---------------------------------------------------------------------------

// Record — a mutable struct/object. Blueprint tags its type (class /
// method-table NodeID); Fields is an ordered name→value map.
func isDictValue(v Value) bool {
	return v.Kind == VList &&
		len(v.List) > 0 &&
		v.List[0].Kind == VStr &&
		v.List[0].Str == "__dict__"
}

func dictKeyEq(a, b Value) bool {
	if a.Kind == VStr && b.Kind == VStr {
		return a.Str == b.Str
	}
	if a.Kind == VInt && b.Kind == VInt {
		return a.Int == b.Int
	}
	return false
}

// Value — runtime tagged union. List and Closure carry pointers; the rest
// are inline. Kept as a flat struct so the walker's hot path is allocation-
// free for ints and bools.

func valueKindName(v Value) string {
	switch v.Kind {
	case VNull:
		return "null"
	case VInt:
		return "int"
	case VStr:
		return "string"
	case VBool:
		return "bool"
	case VList:
		return "list"
	case VClosure:
		return "closure"
	case VNodeID:
		return "node_id"
	case VFloat:
		return "float"
	case VRecord:
		return "record"
	default:
		return "unknown"
	}
}

type sourceNativeLexicon struct {
	keywords     map[string]bool
	properties   map[string]bool
	keywordKind  string
	propertyKind string
	nameKind     string
	intKind      string
	floatKind    string
	stringKind   string
	charKind     string
	opKind       string
	ops          []string
	lineComment  string
	blockOpen    string
	blockClose   string
}

func sourceNativeStr(value string) Value {
	return Value{Kind: VStr, Str: value}
}

func sourceNativeEmptyList() Value {
	return Value{Kind: VList, List: []Value{}}
}

func sourceNativeAtom(kind, value string) Value {
	return Value{Kind: VList, List: []Value{
		sourceNativeStr("cell"),
		sourceNativeStr(kind),
		sourceNativeStr(value),
		sourceNativeEmptyList(),
		Value{Kind: VNull},
	}}
}

func sourceNativeStringSet(v Value, field string) map[string]bool {
	if v.Kind != VList {
		panic(fmt.Sprintf("source_scan_file: %s must be list", field))
	}
	out := map[string]bool{}
	for _, item := range v.List {
		if item.Kind != VStr {
			panic(fmt.Sprintf("source_scan_file: %s item must be string", field))
		}
		out[item.Str] = true
	}
	return out
}

func sourceNativeStringList(v Value, field string) []string {
	if v.Kind != VList {
		panic(fmt.Sprintf("source_scan_file: %s must be list", field))
	}
	out := []string{}
	for _, item := range v.List {
		if item.Kind != VStr {
			panic(fmt.Sprintf("source_scan_file: %s item must be string", field))
		}
		out = append(out, item.Str)
	}
	return out
}

func sourceNativeField(xs []Value, idx int, field string) Value {
	if idx >= len(xs) {
		panic(fmt.Sprintf("source_scan_file: lexicon missing %s", field))
	}
	return xs[idx]
}

func sourceNativeFieldStr(xs []Value, idx int, field string) string {
	v := sourceNativeField(xs, idx, field)
	if v.Kind != VStr {
		panic(fmt.Sprintf("source_scan_file: lexicon %s must be string", field))
	}
	return v.Str
}

func sourceNativeLexiconFromValue(v Value) sourceNativeLexicon {
	if v.Kind != VList {
		panic("source_scan_file: lexicon must be a list")
	}
	xs := v.List
	if len(xs) < 15 || sourceNativeFieldStr(xs, 0, "tag") != "source-lexicon" {
		panic("source_scan_file: lexicon must be (source-lexicon ...)")
	}
	return sourceNativeLexicon{
		keywords:     sourceNativeStringSet(sourceNativeField(xs, 1, "keywords"), "keywords"),
		properties:   sourceNativeStringSet(sourceNativeField(xs, 2, "properties"), "properties"),
		keywordKind:  sourceNativeFieldStr(xs, 3, "keyword-kind"),
		propertyKind: sourceNativeFieldStr(xs, 4, "property-kind"),
		nameKind:     sourceNativeFieldStr(xs, 5, "name-kind"),
		intKind:      sourceNativeFieldStr(xs, 6, "int-kind"),
		floatKind:    sourceNativeFieldStr(xs, 7, "float-kind"),
		stringKind:   sourceNativeFieldStr(xs, 8, "string-kind"),
		charKind:     sourceNativeFieldStr(xs, 9, "char-kind"),
		opKind:       sourceNativeFieldStr(xs, 10, "op-kind"),
		ops:          sourceNativeStringList(sourceNativeField(xs, 11, "ops"), "ops"),
		lineComment:  sourceNativeFieldStr(xs, 12, "line-comment"),
		blockOpen:    sourceNativeFieldStr(xs, 13, "block-open"),
		blockClose:   sourceNativeFieldStr(xs, 14, "block-close"),
	}
}

func sourceNativeNameKind(lex sourceNativeLexicon, value string) string {
	if lex.keywords[value] {
		return lex.keywordKind
	}
	if lex.properties[value] {
		return lex.propertyKind
	}
	return lex.nameKind
}

func sourceNativeNameStart(b byte) bool {
	return (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || b == '_'
}

func sourceNativeNameChar(b byte) bool {
	return sourceNativeNameStart(b) || (b >= '0' && b <= '9')
}

func sourceNativeHexDigit(b byte) bool {
	return (b >= '0' && b <= '9') || (b >= 'a' && b <= 'f') || (b >= 'A' && b <= 'F')
}

func sourceNativeBinDigit(b byte) bool {
	return b == '0' || b == '1'
}

func sourceNativeDecodeEscape(b byte) byte {
	switch b {
	case '\\':
		return '\\'
	case '\'':
		return '\''
	case '"':
		return '"'
	case 'n':
		return '\n'
	case 't':
		return '\t'
	case 'r':
		return '\r'
	case '0':
		return 0
	default:
		return b
	}
}

func sourceNativeScanQuoted(src string, i int, quote byte) (string, int) {
	j := i + 1
	var b strings.Builder
	for j < len(src) {
		c := src[j]
		if c == '\\' && j+1 < len(src) {
			b.WriteByte(sourceNativeDecodeEscape(src[j+1]))
			j += 2
			continue
		}
		if c == quote {
			return b.String(), j + 1
		}
		b.WriteByte(c)
		j++
	}
	return b.String(), j
}

func sourceNativeSkip(src string, i int, lex sourceNativeLexicon) int {
	for i < len(src) {
		c := src[i]
		if c == ' ' || c == '\t' || c == '\n' || c == '\r' {
			i++
			continue
		}
		if lex.lineComment != "" && strings.HasPrefix(src[i:], lex.lineComment) {
			i += len(lex.lineComment)
			for i < len(src) && src[i] != '\n' {
				i++
			}
			continue
		}
		if lex.blockOpen != "" && lex.blockClose != "" && strings.HasPrefix(src[i:], lex.blockOpen) {
			end := strings.Index(src[i+len(lex.blockOpen):], lex.blockClose)
			if end < 0 {
				return len(src)
			}
			i = i + len(lex.blockOpen) + end + len(lex.blockClose)
			continue
		}
		break
	}
	return i
}

func sourceNativeScanText(src string, lex sourceNativeLexicon) Value {
	out := []Value{}
	for i := 0; i < len(src); {
		i = sourceNativeSkip(src, i, lex)
		if i >= len(src) {
			break
		}
		c := src[i]
		if c == '"' {
			value, next := sourceNativeScanQuoted(src, i, '"')
			out = append(out, sourceNativeAtom(lex.stringKind, value))
			i = next
			continue
		}
		if c == '\'' {
			value, next := sourceNativeScanQuoted(src, i, '\'')
			out = append(out, sourceNativeAtom(lex.charKind, value))
			i = next
			continue
		}
		if c >= '0' && c <= '9' {
			j := i + 1
			kind := lex.intKind
			if c == '0' && j < len(src) && (src[j] == 'x' || src[j] == 'X') {
				j++
				for j < len(src) && sourceNativeHexDigit(src[j]) {
					j++
				}
			} else if c == '0' && j < len(src) && (src[j] == 'b' || src[j] == 'B') {
				j++
				for j < len(src) && sourceNativeBinDigit(src[j]) {
					j++
				}
			} else {
				for j < len(src) && src[j] >= '0' && src[j] <= '9' {
					j++
				}
				if j < len(src) && src[j] == '.' && j+1 < len(src) && src[j+1] >= '0' && src[j+1] <= '9' {
					kind = lex.floatKind
					j++
					for j < len(src) && src[j] >= '0' && src[j] <= '9' {
						j++
					}
					if j < len(src) && (src[j] == 'e' || src[j] == 'E') {
						k := j + 1
						if k < len(src) && (src[k] == '+' || src[k] == '-') {
							k++
						}
						if k < len(src) && src[k] >= '0' && src[k] <= '9' {
							j = k + 1
							for j < len(src) && src[j] >= '0' && src[j] <= '9' {
								j++
							}
						}
					}
				}
			}
			out = append(out, sourceNativeAtom(kind, src[i:j]))
			i = j
			continue
		}
		if sourceNativeNameStart(c) {
			j := i + 1
			for j < len(src) && sourceNativeNameChar(src[j]) {
				j++
			}
			value := src[i:j]
			out = append(out, sourceNativeAtom(sourceNativeNameKind(lex, value), value))
			i = j
			continue
		}
		matched := ""
		for _, op := range lex.ops {
			if strings.HasPrefix(src[i:], op) {
				matched = op
				break
			}
		}
		if matched == "" {
			matched = string(c)
		}
		out = append(out, sourceNativeAtom(lex.opKind, matched))
		i += len(matched)
	}
	return Value{Kind: VList, List: out}
}

// asFloat — coerce a Value to float64 for IEEE 754 arithmetic. VFloat
// passes through; VInt and VBool widen by Go's standard conversion. Other
// kinds panic — float arithmetic on a string or list is a Form-author
// bug, not a kernel fallback. Mirrors Rust's Value::as_float.

// roundNdigitsDecimal — CPython `round(x, n)` for a finite double, n >= 0.
//
// CPython rounds the TRUE value of the double (a finite dyadic decimal) to n
// fractional digits half-to-even, then takes the nearest double. The naive
// f64 paths (floor(x*10^n+0.5)/10^n; banker's on the scaled f64) both diverge
// because the *10^n reintroduces representation error CPython's decimal path
// avoids. This rounds on the EXACT decimal expansion instead, obtained via
// strconv.FormatFloat('f', 1074): a finite double m*2^e2 (e2<0) equals
// m*5^(-e2)/10^(-e2), a decimal with exactly -e2 (<= 1074) fractional digits,
// so 1074 places is the exact terminating expansion for any double — no
// domain assumption, no pre-rounding at the round position. Verified bit-for-
// bit against CPython on 6.6M cases with ZERO divergences. Sibling-parity
// with the Rust kernel (format!("{:.1074}")) and TS kernel (BigInt
// mantissa*5^k, since JS toFixed caps at 100 places).
func roundNdigitsDecimal(x float64, n int64) float64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return x
	}
	neg := math.Signbit(x)
	ax := math.Abs(x)
	// Exact fixed-point decimal of |x|; 1074 fractional places is the full
	// terminating expansion for any double, so no rounding occurs at the tail.
	s := strconv.FormatFloat(ax, 'f', 1074, 64)
	dot := strings.IndexByte(s, '.')
	ipart := s[:dot]
	fpart := s[dot+1:]
	digits := []byte(ipart + fpart)
	point := int64(len(ipart))
	keep := point + n
	if keep < 0 {
		if neg {
			return math.Copysign(0, -1)
		}
		return 0
	}
	keepI := int(keep)
	if len(digits) < keepI {
		pad := make([]byte, keepI-len(digits))
		for i := range pad {
			pad[i] = '0'
		}
		digits = append(digits, pad...)
	}
	keptSlice := digits[:keepI]
	rest := digits[keepI:]
	var kept string
	if len(keptSlice) == 0 {
		kept = "0"
	} else {
		kept = string(keptSlice)
	}
	roundUp := false
	if len(rest) > 0 {
		first := rest[0]
		if first > '5' {
			roundUp = true
		} else if first < '5' {
			roundUp = false
		} else {
			tailNonzero := false
			for _, d := range rest[1:] {
				if d != '0' {
					tailNonzero = true
					break
				}
			}
			if tailNonzero {
				roundUp = true
			} else {
				lastKept := kept[len(kept)-1]
				roundUp = (lastKept-'0')%2 == 1
			}
		}
	}
	if roundUp {
		kept = addOneDecimal(kept)
	}
	dec := composeScaledDecimal(kept, int(n), neg)
	out, err := strconv.ParseFloat(dec, 64)
	if err != nil {
		out = 0
	}
	if out == 0 && neg {
		return math.Copysign(0, -1)
	}
	return out
}

// addOneDecimal — increment a non-negative decimal digit string by 1,
// propagating carry (may grow by one leading digit).
func addOneDecimal(s string) string {
	b := []byte(s)
	i := len(b)
	for {
		if i == 0 {
			b = append([]byte{'1'}, b...)
			break
		}
		i--
		if b[i] == '9' {
			b[i] = '0'
		} else {
			b[i]++
			break
		}
	}
	return string(b)
}

// composeScaledDecimal — render integer string `kept` scaled by 10^-n as a
// decimal literal with the given sign. n >= 0.
func composeScaledDecimal(kept string, n int, neg bool) string {
	var body string
	if n == 0 {
		body = kept
	} else {
		si := kept
		if len(si) <= n {
			pad := n - len(si) + 1
			si = strings.Repeat("0", pad) + si
		}
		split := len(si) - n
		body = si[:split] + "." + si[split:]
	}
	if neg {
		return "-" + body
	}
	return body
}

// formatFloatJS — render a float the way JavaScript's String(number) does,
// so the Go kernel's output is byte-identical to the TS kernel's. (The
// Rust kernel uses Python-style formatting which adds a trailing ".0" to
// integer-valued floats; that's a known divergence between Rust and TS.
// This Go kernel follows TS — the bootstrap reference — and a future
// breath will harmonize Rust's render to match.) Specials follow the JS
// surface: NaN → "NaN", +Inf → "Infinity", -Inf → "-Infinity".

type GoJITCompiled struct {
	I64   func([]int64) int64
	F64   func([]float64) float64
	Value func([]jitabi.Value) jitabi.Value
}

func valueToJIT(v Value) (jitabi.Value, bool) {
	switch v.Kind {
	case VNull:
		return jitabi.Null(), true
	case VInt:
		return jitabi.Int(v.Int), true
	case VFloat:
		return jitabi.Float(v.Float), true
	case VStr:
		return jitabi.Str(v.Str), true
	case VBool:
		return jitabi.Bool(v.Bool), true
	case VNodeID:
		return jitabi.Node(v.Nid.Pkg, v.Nid.Level, v.Nid.Type, v.Nid.Inst), true
	case VList:
		out := make([]jitabi.Value, 0, len(v.List))
		for _, child := range v.List {
			jv, ok := valueToJIT(child)
			if !ok {
				return jitabi.Null(), false
			}
			out = append(out, jv)
		}
		return jitabi.List(out...), true
	}
	return jitabi.Null(), false
}

func valueFromJIT(v jitabi.Value) Value {
	switch v.Kind {
	case jitabi.NullKind:
		return Value{Kind: VNull}
	case jitabi.IntKind:
		return Value{Kind: VInt, Int: v.Int}
	case jitabi.FloatKind:
		return Value{Kind: VFloat, Float: v.Float}
	case jitabi.StrKind:
		return Value{Kind: VStr, Str: v.Str}
	case jitabi.BoolKind:
		return Value{Kind: VBool, Bool: v.Bool}
	case jitabi.NodeKind:
		return Value{Kind: VNodeID, Nid: NodeID{Pkg: v.Node.Pkg, Level: v.Node.Level, Type: v.Node.Type, Inst: v.Node.Inst}}
	case jitabi.ListKind:
		out := make([]Value, 0, len(v.List))
		for _, child := range v.List {
			out = append(out, valueFromJIT(child))
		}
		return Value{Kind: VList, List: out}
	}
	return Value{Kind: VNull}
}

type choiceFailSignal struct{}
type choiceStopSignal struct{}

// methodKey — (blueprint, method-name) key for the blueprint method table.
type methodKey struct {
	blueprint NodeID
	name      NameID
}

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

// Frame — scope primitive. Bindings as a small ordered slice; the common
// case (function call with 1-3 args) beats a hash map at this size and
// keeps the data layout cache-friendly. Linear scan is the right shape
// for n < ~16.

// NewCallFrame — pre-sized for a function call with `arity` params.
// Avoids append-grow during parameter binding in the hot recursion path.

// ---------------------------------------------------------------------------
// Native functions — what Form-on-top reaches for at the leaves
// ---------------------------------------------------------------------------

type NativeFn func(k *Kernel, args []Value) Value

// EnvAwareNativeFn — natives that need access to the caller's env to do
// in-scope evaluation (e.g. walk_recipe_here, which walks a pre-built
// Recipe in the calling scope so its `let` bindings land in the caller's
// env, not a fresh one). Separate registry to avoid changing the existing
// NativeFn signature across ~60 sites.
type EnvAwareNativeFn func(k *Kernel, env *Frame, args []Value) Value

type EnvAwareNativeEntry struct {
	Name     NameID
	Category NodeID
	Fn       EnvAwareNativeFn
}

// registerNative — central registration point. The string name is
// interned once into a NameID; runtime dispatch is u32-keyed. Each
// native carries the Form category it expresses (Blueprint attribution).
func (k *Kernel) registerNative(name string, category NodeID, fn NativeFn) {
	id := k.internName(name)
	k.natives[id] = NativeEntry{Name: id, Category: category, Fn: fn}
}

func (k *Kernel) registerEnvNative(name string, category NodeID, fn EnvAwareNativeFn) {
	id := k.internName(name)
	k.envNatives[id] = EnvAwareNativeEntry{Name: id, Category: category, Fn: fn}
}

func (k *Kernel) registerNatives() {
	// Blueprint attribution discipline (mirrors Rust kernel):
	//   catCall      — invoke external effect (I/O, tool)
	//   catAccess    — read property / field
	//   catMethod    — transform on a cell-like value
	//   catCompare   — equality / ordering
	//   catListNat   — construct/destructure a List
	//   catWitness   — substrate self-attestation (intern, walk, lookup)
	//   catUndefined — honest "no Form category settled yet"

	k.registerNative("print", catCall(), func(_ *Kernel, args []Value) Value {
		for i, a := range args {
			if i > 0 {
				fmt.Print(" ")
			}
			fmt.Print(a.String())
		}
		fmt.Println()
		return Value{Kind: VNull}
	})
	// String ops
	k.registerNative("str_len", catAccess(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(len(args[0].Str))}
	})
	k.registerNative("substring", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		a := args[1].Int
		b := args[2].Int
		if a < 0 || b < a || b > int64(len(s)) {
			panic(fmt.Sprintf(
				"substring: bounds out of range start=%d end=%d len=%d",
				a,
				b,
				len(s),
			))
		}
		return Value{Kind: VStr, Str: s[a:b]}
	})
	k.registerNative("char_at", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		i := args[1].Int
		if i < 0 || i >= int64(len(s)) {
			panic(fmt.Sprintf("char_at: bounds out of range index=%d len=%d", i, len(s)))
		}
		return Value{Kind: VStr, Str: string(s[i])}
	})
	k.registerNative("str_concat", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: args[0].Str + args[1].Str}
	})
	k.registerNative("form_error", catWitness(), func(_ *Kernel, args []Value) Value {
		panic(args[0].Str)
	})
	k.registerNative("form-error", catWitness(), func(_ *Kernel, args []Value) Value {
		panic(args[0].Str)
	})
	k.registerNative("source_scan_file", catCall(), func(_ *Kernel, args []Value) Value {
		body, err := os.ReadFile(args[0].Str)
		if err != nil {
			panic(fmt.Sprintf("source_scan_file: %v", err))
		}
		return sourceNativeScanText(string(body), sourceNativeLexiconFromValue(args[1]))
	})
	// pow — integer exponentiation in native code (no Form recursion).
	// (pow base exp) → base**exp. Negative exponents return 0 (Python's
	// int**-n is a float; floats on this path are a later breath).
	k.registerNative("pow", catMethod(), func(_ *Kernel, args []Value) Value {
		base := args[0].Int
		exp := args[1].Int
		if exp < 0 {
			return Value{Kind: VInt, Int: 0}
		}
		result := int64(1)
		for i := int64(0); i < exp; i++ {
			result *= base
		}
		return Value{Kind: VInt, Int: result}
	})
	// --- struct/object primitive (BML reference, rung 2) -------------------
	// A Record is the kernel's first MUTABLE value: a struct/object with
	// identity. Every language's class/struct compiles onto these natives.
	// Blueprint NodeID tags the type; fields are a name→value map.
	//
	// record_new — (record_new blueprint k1 v1 k2 v2 ...) → Record.
	k.registerNative("record_new", catMethod(), func(k *Kernel, args []Value) Value {
		rec := &Record{Blueprint: args[0].Nid}
		i := 1
		for i+1 < len(args) {
			rec.Set(k.internName(args[i].Str), args[i+1])
			i += 2
		}
		return Value{Kind: VRecord, Rec: rec}
	})
	// record_get — (record_get rec "field") → value, or null if absent.
	k.registerNative("record_get", catAccess(), func(k *Kernel, args []Value) Value {
		v, _ := args[0].Rec.Get(k.internName(args[1].Str))
		return v
	})
	// record_set — (record_set rec "field" value) → the record (mutated in
	// place; shared identity means all holders see it). BML's `self.x = v`.
	k.registerNative("record_set", catMethod(), func(k *Kernel, args []Value) Value {
		args[0].Rec.Set(k.internName(args[1].Str), args[2])
		return args[0]
	})
	// record_has — (record_has rec "field") → bool.
	k.registerNative("record_has", catAccess(), func(k *Kernel, args []Value) Value {
		_, ok := args[0].Rec.Get(k.internName(args[1].Str))
		return Value{Kind: VBool, Bool: ok}
	})
	// record_blueprint — (record_blueprint rec) → the blueprint NodeID.
	k.registerNative("record_blueprint", catAccess(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: args[0].Rec.Blueprint}
	})
	// record_keys — (record_keys rec) → list of field-name strings, in
	// insertion order. Lets Form enumerate a record used as a hash map (e.g.
	// the keydir of cell-log-store.fk for compaction).
	k.registerNative("record_keys", catAccess(), func(k *Kernel, args []Value) Value {
		fields := args[0].Rec.Fields
		out := make([]Value, len(fields))
		for i, f := range fields {
			out[i] = Value{Kind: VStr, Str: k.strs[f.Name]}
		}
		return Value{Kind: VList, List: out}
	})
	// record? — (record? v) → bool type predicate.
	k.registerNative("record?", catAccess(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VBool, Bool: args[0].Kind == VRecord}
	})
	// --- methods on the blueprint (BML/NUMS reference, rung 2b) ----------
	// Methods live on the blueprint/type, shared by all records of that type,
	// name-dispatched. The keystone that makes a Record a real object.
	//
	// method_define — (method_define blueprint "name" closure) → blueprint.
	k.registerNative("method_define", catMethod(), func(k *Kernel, args []Value) Value {
		if args[2].Kind != VClosure {
			panic("method_define: third arg must be a closure")
		}
		k.methods[methodKey{args[0].Nid, k.internName(args[1].Str)}] = args[2].Cl
		return args[0]
	})
	// method_has — (method_has record-or-blueprint "name") → bool.
	k.registerNative("method_has", catAccess(), func(k *Kernel, args []Value) Value {
		var bp NodeID
		switch args[0].Kind {
		case VRecord:
			bp = args[0].Rec.Blueprint
		case VNodeID:
			bp = args[0].Nid
		default:
			return Value{Kind: VBool, Bool: false}
		}
		_, ok := k.methods[methodKey{bp, k.internName(args[1].Str)}]
		return Value{Kind: VBool, Bool: ok}
	})
	// method_invoke — (method_invoke record "name" arg1 arg2 ...) → value.
	// Dispatches by the record's blueprint; the method's FIRST param is the
	// receiver (Python `self` convention), remaining params bind to call args.
	k.registerNative("method_invoke", catMethod(), func(k *Kernel, args []Value) Value {
		if args[0].Kind != VRecord {
			panic("method_invoke: first arg must be a record")
		}
		rec := args[0].Rec
		key := methodKey{rec.Blueprint, k.internName(args[1].Str)}
		cl, ok := k.methods[key]
		if !ok {
			panic(fmt.Sprintf("method_invoke: no method '%s' on blueprint @%d.%d.%d.%d",
				args[1].Str, rec.Blueprint.Pkg, rec.Blueprint.Level,
				rec.Blueprint.Type, rec.Blueprint.Inst))
		}
		callArgs := args[2:]
		if len(cl.Params) == 0 {
			panic(fmt.Sprintf("method '%s' must declare a receiver param (self)", args[1].Str))
		}
		if len(callArgs) != len(cl.Params)-1 {
			panic(fmt.Sprintf("method '%s' wants %d args, got %d",
				args[1].Str, len(cl.Params)-1, len(callArgs)))
		}
		call := NewCallFrame(cl.Env, len(cl.Params))
		call.Bind(cl.Params[0], args[0]) // receiver
		for i, p := range cl.Params[1:] {
			call.Bind(p, callArgs[i])
		}
		return k.walk(cl.Body, call)
	})
	// str_find — Go-level substring search starting at index `from`.
	// Signature: (str_find s needle from) → int (index or -1). The whole
	// search runs in this Go loop (uses strings.Index after slicing); no
	// Form closure dispatch per byte, no Form recursion. This is what
	// `tokenizeSexp` does internally — exposed for Form scanners that
	// would otherwise blow the walker stack with per-character recursion.
	k.registerNative("str_find", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		needle := args[1].Str
		from := int(args[2].Int)
		if from < 0 {
			from = 0
		}
		if from > len(s) {
			return Value{Kind: VInt, Int: -1}
		}
		idx := strings.Index(s[from:], needle)
		if idx < 0 {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(from + idx)}
	})
	k.registerNative("str_line_at", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		idx := int(args[1].Int)
		if idx < 0 || idx > len(s) {
			return Value{Kind: VStr, Str: ""}
		}
		start := idx
		for start > 0 && s[start-1] != '\n' {
			start--
		}
		end := idx
		for end < len(s) && s[end] != '\n' {
			end++
		}
		if end > start && s[end-1] == '\r' {
			end--
		}
		return Value{Kind: VStr, Str: s[start:end]}
	})
	k.registerNative("str_ascii_prefix", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		end := 0
		for end < len(s) && s[end] < utf8.RuneSelf {
			end++
		}
		return Value{Kind: VStr, Str: s[:end]}
	})
	// scan_run — return the end-index where a contiguous run of bytes
	// matching `class_code` ends (exclusive). Generic per-byte loop in
	// Go avoids the walker dispatch a pure-Form recursion would pay
	// per character — closing the per-byte parser-throughput gap that
	// makes Form unviable as a universal runtime translator otherwise.
	// Class codes (sibling-parity across Go/Rust/TS):
	//   0  whitespace          space, tab, lf, cr
	//   1  ascii-digit         '0'-'9'
	//   2  ascii-alpha         'a'-'z', 'A'-'Z'
	//   3  identifier-char     alpha + digit + '_' + '-'
	//   4  non-quote-non-escape   anything except '"' and '\\'
	//   5  non-newline         anything except '\n'
	//   6  json-string-safe    byte >= 0x20 and not '"' or '\\'
	// Used by json.fk's skip-ws / scan-string / scan-number, BMF
	// tokenizers, CSV scanners, future YAML/TOML parsers — not
	// JSON-special. A new class adds one branch to a small switch.
	k.registerNative("scan_run", catAccess(), func(_ *Kernel, args []Value) Value {
		s := args[0].Str
		from := int(args[1].Int)
		class := int(args[2].Int)
		if from < 0 {
			from = 0
		}
		n := len(s)
		end := from
		switch class {
		case 0: // whitespace
			for end < n {
				c := s[end]
				if c != ' ' && c != '\t' && c != '\n' && c != '\r' {
					break
				}
				end++
			}
		case 1: // ascii digit
			for end < n && s[end] >= '0' && s[end] <= '9' {
				end++
			}
		case 2: // ascii alpha
			for end < n {
				c := s[end]
				if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
					break
				}
				end++
			}
		case 3: // identifier char
			for end < n {
				c := s[end]
				if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
					(c >= '0' && c <= '9') || c == '_' || c == '-') {
					break
				}
				end++
			}
		case 4: // non-quote-non-escape
			for end < n && s[end] != '"' && s[end] != '\\' {
				end++
			}
		case 5: // non-newline
			for end < n && s[end] != '\n' {
				end++
			}
		case 6: // json-string-safe
			for end < n && s[end] >= 0x20 && s[end] != '"' && s[end] != '\\' {
				end++
			}
		default:
			panic(fmt.Sprintf("scan_run: unknown class_code %d (valid: 0-6)", class))
		}
		return Value{Kind: VInt, Int: int64(end)}
	})
	// string_fold — Go-level streaming iteration over a string's bytes.
	// Signature: (string_fold s init step) where step is a closure of
	// (acc, char) → acc. Whole iteration in this Go for-loop; no Form-
	// level recursion. Lets the substrate process arbitrary-length input
	// streams without piling kernel stack frames — the universal-translator
	// stream property the goal's first sentence demands.
	k.registerNative("string_fold", catCall(), func(k *Kernel, args []Value) Value {
		s := args[0].Str
		acc := args[1]
		fnVal := args[2]
		if fnVal.Kind != VClosure {
			panic("string_fold: third arg must be a closure")
		}
		cl := fnVal.Cl
		if len(cl.Params) != 2 {
			panic(fmt.Sprintf("string_fold: step closure wants 2 params (acc char), got %d", len(cl.Params)))
		}
		for i := 0; i < len(s); i++ {
			call := NewCallFrame(cl.Env, len(cl.Params))
			call.Bind(cl.Params[0], acc)
			call.Bind(cl.Params[1], Value{Kind: VStr, Str: string(s[i])})
			acc = k.walk(cl.Body, call)
		}
		return acc
	})
	k.registerNative("str_eq", catCompare(RCompareEq), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VBool, Bool: args[0].Str == args[1].Str}
	})
	// int_to_str — value-to-string for trivial leaves. The historical
	// name reflects its first use (line numbers in cell-trace.fk); its
	// semantics is "render any trivial value as text" so emit-engine.fk
	// can pass node_value of any leaf type through it. Multi-target
	// emit (universal codec lattice — see emit.fk + emits/json.fk)
	// depends on this passthrough for strings and bools.
	k.registerNative("int_to_str", catMethod(), func(_ *Kernel, args []Value) Value {
		v := args[0]
		switch v.Kind {
		case VStr:
			return Value{Kind: VStr, Str: v.Str}
		case VBool:
			if v.Bool {
				return Value{Kind: VStr, Str: "true"}
			}
			return Value{Kind: VStr, Str: "false"}
		case VNull:
			return Value{Kind: VStr, Str: "null"}
		case VFloat:
			return Value{Kind: VStr, Str: formatFloatJS(v.Float)}
		}
		return Value{Kind: VStr, Str: strconv.FormatInt(v.Int, 10)}
	})
	k.registerNative("value_str", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: formValueString(args[0])}
	})
	k.registerNative("value_kind", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: valueKindName(args[0])}
	})
	k.registerNative("value-kind", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: valueKindName(args[0])}
	})
	k.registerNative("str_to_int", catMethod(), func(_ *Kernel, args []Value) Value {
		n, _ := strconv.ParseInt(args[0].Str, 10, 64)
		return Value{Kind: VInt, Int: n}
	})
	k.registerNative("str_to_float", catMethod(), func(_ *Kernel, args []Value) Value {
		f, _ := strconv.ParseFloat(args[0].Str, 64)
		return Value{Kind: VFloat, Float: f}
	})
	k.registerNative("ord", catAccess(), func(_ *Kernel, args []Value) Value {
		if len(args[0].Str) == 0 {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(args[0].Str[0])}
	})
	k.registerNative("byte_to_str", catAccess(), func(_ *Kernel, args []Value) Value {
		if args[0].Int < 0 || args[0].Int > 255 {
			return Value{Kind: VStr, Str: ""}
		}
		return Value{Kind: VStr, Str: string(byte(args[0].Int))}
	})
	// List ops
	k.registerNative("list", catListNat(), func(_ *Kernel, args []Value) Value {
		out := make([]Value, len(args))
		copy(out, args)
		return Value{Kind: VList, List: out}
	})
	k.registerNative("cons", catListNat(), func(_ *Kernel, args []Value) Value {
		out := make([]Value, 0, len(args[1].List)+1)
		out = append(out, args[0])
		out = append(out, args[1].List...)
		return Value{Kind: VList, List: out}
	})
	k.registerNative("head", catListNat(), func(_ *Kernel, args []Value) Value {
		if len(args[0].List) == 0 {
			return Value{Kind: VNull}
		}
		return args[0].List[0]
	})
	k.registerNative("tail", catListNat(), func(_ *Kernel, args []Value) Value {
		if len(args[0].List) == 0 {
			return Value{Kind: VList, List: []Value{}}
		}
		return Value{Kind: VList, List: args[0].List[1:]}
	})
	k.registerNative("len", catAccess(), func(_ *Kernel, args []Value) Value {
		switch args[0].Kind {
		case VList:
			if isDictValue(args[0]) {
				return Value{Kind: VInt, Int: int64((len(args[0].List) - 1) / 2)}
			}
			return Value{Kind: VInt, Int: int64(len(args[0].List))}
		case VStr:
			return Value{Kind: VInt, Int: int64(len(args[0].Str))}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("nth", catAccess(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind != VList {
			return Value{Kind: VNull}
		}
		i := args[1].Int
		if i < 0 || int(i) >= len(args[0].List) {
			return Value{Kind: VNull}
		}
		return args[0].List[i]
	})
	k.registerNative("empty", catListNat(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VList, List: []Value{}}
	})
	// _list_append — functional list extension: (_list_append xs x) → a NEW
	// list = xs ++ [x]. Sibling-parity with Rust + TS. The Python adapter
	// lowers the accumulator idiom `result.append(x)` to
	// (let result (_list_append result x)), rebinding the name to the grown
	// list each pass — what unblocks list-returning routes (softmax, vectors).
	// A non-list receiver yields a single-element list, matching an append
	// onto an empty accumulator.
	k.registerNative("_list_append", catListNat(), func(_ *Kernel, args []Value) Value {
		var xs []Value
		if args[0].Kind == VList {
			xs = append(xs, args[0].List...)
		}
		xs = append(xs, args[1])
		return Value{Kind: VList, List: xs}
	})
	k.registerNative("_dict_new", catListNat(), func(_ *Kernel, args []Value) Value {
		out := make([]Value, 0, len(args)+1)
		out = append(out, Value{Kind: VStr, Str: "__dict__"})
		out = append(out, args...)
		return Value{Kind: VList, List: out}
	})
	k.registerNative("_dict_get", catAccess(), func(_ *Kernel, args []Value) Value {
		if !isDictValue(args[0]) {
			return Value{Kind: VNull}
		}
		xs := args[0].List
		for i := 1; i+1 < len(xs); i += 2 {
			if dictKeyEq(xs[i], args[1]) {
				return xs[i+1]
			}
		}
		return Value{Kind: VNull}
	})
	k.registerNative("_dict_set", catMethod(), func(_ *Kernel, args []Value) Value {
		if !isDictValue(args[0]) {
			return args[0]
		}
		out := append([]Value{}, args[0].List...)
		for i := 1; i+1 < len(out); i += 2 {
			if dictKeyEq(out[i], args[1]) {
				out[i+1] = args[2]
				return Value{Kind: VList, List: out}
			}
		}
		out = append(out, args[1], args[2])
		return Value{Kind: VList, List: out}
	})
	k.registerNative("_dict_has", catCompare(RCompareEq), func(_ *Kernel, args []Value) Value {
		if !isDictValue(args[0]) {
			return Value{Kind: VBool, Bool: false}
		}
		xs := args[0].List
		for i := 1; i+1 < len(xs); i += 2 {
			if dictKeyEq(xs[i], args[1]) {
				return Value{Kind: VBool, Bool: true}
			}
		}
		return Value{Kind: VBool, Bool: false}
	})
	k.registerNative("_dict_keys", catAccess(), func(_ *Kernel, args []Value) Value {
		if !isDictValue(args[0]) {
			return Value{Kind: VList, List: []Value{}}
		}
		xs := args[0].List
		out := make([]Value, 0, (len(xs)-1)/2)
		for i := 1; i+1 < len(xs); i += 2 {
			out = append(out, xs[i])
		}
		return Value{Kind: VList, List: out}
	})
	k.registerNative("_dict_values", catAccess(), func(_ *Kernel, args []Value) Value {
		if !isDictValue(args[0]) {
			return Value{Kind: VList, List: []Value{}}
		}
		xs := args[0].List
		out := make([]Value, 0, (len(xs)-1)/2)
		for i := 1; i+1 < len(xs); i += 2 {
			out = append(out, xs[i+1])
		}
		return Value{Kind: VList, List: out}
	})
	k.registerNative("_get", catAccess(), func(k *Kernel, args []Value) Value {
		if len(args) < 2 {
			return Value{Kind: VNull}
		}
		if args[0].Kind == VRecord && args[1].Kind == VStr {
			v, _ := args[0].Rec.Get(k.internName(args[1].Str))
			return v
		}
		if isDictValue(args[0]) {
			xs := args[0].List
			for i := 1; i+1 < len(xs); i += 2 {
				if dictKeyEq(xs[i], args[1]) {
					return xs[i+1]
				}
			}
			return Value{Kind: VNull}
		}
		if args[0].Kind == VList && args[1].Kind == VStr {
			xs := args[0].List
			for i := 0; i+1 < len(xs); i += 2 {
				if xs[i].Kind == VStr && xs[i].Str == args[1].Str {
					return xs[i+1]
				}
			}
			panic(fmt.Sprintf("_get: no field '%s' on record", args[1].Str))
		}
		if args[0].Kind == VList {
			i := args[1].Int
			if i < 0 || int(i) >= len(args[0].List) {
				return Value{Kind: VNull}
			}
			return args[0].List[i]
		}
		if args[0].Kind == VStr {
			i := args[1].Int
			if i < 0 || int(i) >= len(args[0].Str) {
				return Value{Kind: VStr, Str: ""}
			}
			return Value{Kind: VStr, Str: string(args[0].Str[i])}
		}
		return Value{Kind: VNull}
	})
	k.registerNative("_iter", catListNat(), func(_ *Kernel, args []Value) Value {
		if len(args) == 0 {
			return Value{Kind: VList, List: []Value{}}
		}
		if isDictValue(args[0]) {
			xs := args[0].List
			out := make([]Value, 0, (len(xs)-1)/2)
			for i := 1; i+1 < len(xs); i += 2 {
				out = append(out, xs[i])
			}
			return Value{Kind: VList, List: out}
		}
		if args[0].Kind == VList {
			return args[0]
		}
		if args[0].Kind == VStr {
			out := make([]Value, 0, len(args[0].Str))
			for i := 0; i < len(args[0].Str); i++ {
				out = append(out, Value{Kind: VStr, Str: string(args[0].Str[i])})
			}
			return Value{Kind: VList, List: out}
		}
		return Value{Kind: VList, List: []Value{}}
	})
	k.registerNative("_in", catCompare(RCompareEq), func(_ *Kernel, args []Value) Value {
		if isDictValue(args[1]) {
			xs := args[1].List
			for i := 1; i+1 < len(xs); i += 2 {
				if dictKeyEq(xs[i], args[0]) {
					return Value{Kind: VBool, Bool: true}
				}
			}
			return Value{Kind: VBool, Bool: false}
		}
		if args[1].Kind == VList {
			for _, v := range args[1].List {
				if dictKeyEq(v, args[0]) || (v.Kind == VBool && args[0].Kind == VBool && v.Bool == args[0].Bool) {
					return Value{Kind: VBool, Bool: true}
				}
			}
			return Value{Kind: VBool, Bool: false}
		}
		if args[1].Kind == VStr && args[0].Kind == VStr {
			return Value{Kind: VBool, Bool: strings.Contains(args[1].Str, args[0].Str)}
		}
		return Value{Kind: VBool, Bool: false}
	})
	// Common Python builtins applied to lists. Sibling-parity with
	// Rust + TS kernels. Honest error messages on empty lists.
	k.registerNative("min", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) == 1 && args[0].Kind == VList {
			xs := args[0].List
			if len(xs) == 0 {
				panic("min: empty list")
			}
			best := xs[0].Int
			for i := 1; i < len(xs); i++ {
				if xs[i].Int < best {
					best = xs[i].Int
				}
			}
			return Value{Kind: VInt, Int: best}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	k.registerNative("max", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) == 1 && args[0].Kind == VList {
			xs := args[0].List
			if len(xs) == 0 {
				panic("max: empty list")
			}
			best := xs[0].Int
			for i := 1; i < len(xs); i++ {
				if xs[i].Int > best {
					best = xs[i].Int
				}
			}
			return Value{Kind: VInt, Int: best}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	// `sum` composted from the kernel native list 2026-05-22 —
	// core.fk's (defn sum (xs) (foldl plus 0 xs)) covers it via the
	// existing foldl + plus primitives. First of 9 composable natives
	// named in kernel-minimality-audit.md.
	k.registerNative("abs", catMethod(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind == VFloat {
			return Value{Kind: VFloat, Float: math.Abs(args[0].Float)}
		}
		n := args[0].Int
		if n < 0 {
			n = -n
		}
		return Value{Kind: VInt, Int: n}
	})
	// float→int conversions: bridge float compute to integer band verdicts /
	// quantization codes. floor/ceil/trunc are IEEE-unambiguous; round is
	// half-away-from-zero (math.Round) to match Rust f64::round and the TS
	// sign*round(abs) impl. An int argument passes through unchanged.
	k.registerNative("floor", catMethod(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind == VFloat {
			return Value{Kind: VInt, Int: int64(math.Floor(args[0].Float))}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	k.registerNative("ceil", catMethod(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind == VFloat {
			return Value{Kind: VInt, Int: int64(math.Ceil(args[0].Float))}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	k.registerNative("trunc", catMethod(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind == VFloat {
			return Value{Kind: VInt, Int: int64(math.Trunc(args[0].Float))}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	k.registerNative("round", catMethod(), func(_ *Kernel, args []Value) Value {
		if args[0].Kind == VFloat {
			return Value{Kind: VInt, Int: int64(math.Round(args[0].Float))}
		}
		return Value{Kind: VInt, Int: args[0].Int}
	})
	// Polymorphic `+` for Python: int+int=add, str+str=concat,
	// list+list=concat, with float promotion on numeric mixes.
	// Sibling-parity with Rust + TS kernels.
	k.registerNative("_plus", catMethod(), func(_ *Kernel, args []Value) Value {
		a, b := args[0], args[1]
		if a.Kind == VInt && b.Kind == VInt {
			return Value{Kind: VInt, Int: a.Int + b.Int}
		}
		// Float promotion — matches Python: int+float, float+int, float+float
		// all return float. Mirrors Rust's _plus dispatch.
		if (a.Kind == VFloat || a.Kind == VInt) && (b.Kind == VFloat || b.Kind == VInt) {
			if a.Kind == VFloat || b.Kind == VFloat {
				return Value{Kind: VFloat, Float: a.AsFloat() + b.AsFloat()}
			}
		}
		if a.Kind == VStr && b.Kind == VStr {
			return Value{Kind: VStr, Str: a.Str + b.Str}
		}
		if a.Kind == VStr && b.Kind == VInt {
			return Value{Kind: VStr, Str: a.Str + strconv.FormatInt(b.Int, 10)}
		}
		if a.Kind == VInt && b.Kind == VStr {
			return Value{Kind: VStr, Str: strconv.FormatInt(a.Int, 10) + b.Str}
		}
		if a.Kind == VStr && b.Kind == VFloat {
			return Value{Kind: VStr, Str: a.Str + formatFloatJS(b.Float)}
		}
		if a.Kind == VFloat && b.Kind == VStr {
			return Value{Kind: VStr, Str: formatFloatJS(a.Float) + b.Str}
		}
		if a.Kind == VList && b.Kind == VList {
			out := append([]Value{}, a.List...)
			out = append(out, b.List...)
			return Value{Kind: VList, List: out}
		}
		panic("_plus: unsupported operand types")
	})
	// range(n) / range(a,b) / range(a,b,s) — eager list of integers.
	// Matches CPython semantics for `for i in range(N):`.
	// Sibling-parity with the Rust + TS kernels.
	// `range` composted 2026-05-22 — core.fk has (defn range (start end) ...).
	// Sibling-parity with Rust kernel removal.

	// ── Python `math` module — a tight kernel-native shape ─────
	// The Python adapter rewrites `math.sqrt(x)` → `(math_sqrt x)`,
	// `math.pi` → `(math_pi)`, etc. at parse time, so imports compile
	// to nothing at runtime. Sibling-parity with the Rust + TS kernels;
	// the entries are tight (sqrt, pi, floor, ceil, pow) and follow
	// CPython's return-type convention: sqrt/pi/pow → float; floor/ceil
	// → int (CPython 3 behaviour).
	k.registerNative("math_sqrt", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: math.Sqrt(args[0].AsFloat())}
	})
	k.registerNative("math_acos", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: math.Acos(args[0].AsFloat())}
	})
	k.registerNative("math_pi", catMethod(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VFloat, Float: math.Pi}
	})
	k.registerNative("math_floor", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(math.Floor(args[0].AsFloat()))}
	})
	k.registerNative("math_ceil", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(math.Ceil(args[0].AsFloat()))}
	})
	k.registerNative("math_pow", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: math.Pow(args[0].AsFloat(), args[1].AsFloat())}
	})
	k.registerNative("math_log", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: math.Log(args[0].AsFloat())}
	})
	k.registerNative("math_exp", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: math.Exp(args[0].AsFloat())}
	})
	// round_ndigits(x, n) — CPython `round(x, n)` for floats, EXACTLY.
	// The Python adapter lowers `round(x, n)` → `(round_ndigits x n)`. Rounds
	// the exact decimal value of the double half-to-even at n fractional
	// places (n >= 0), matching CPython bit-for-bit. Sibling-parity with the
	// Rust + TS kernels. See roundNdigitsDecimal above.
	k.registerNative("round_ndigits", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VFloat, Float: roundNdigitsDecimal(args[0].AsFloat(), args[1].Int)}
	})

	// ── Float construction + introspection — sibling-parity with the
	// TS kernel's make_float32/make_float64 + f32/f64 transmute casts.
	// The Rust kernel doesn't currently expose these as natives (it
	// only parses float literals from .fk source); Go matches TS so
	// Form code that constructs floats explicitly has a verb to call.
	//
	// make_float64 — intern a float-valued substrate trivial. Takes an
	// int or float arg; returns a NodeID. Sibling to make_int* /
	// make_uint* — used when Form code wants to hold the substrate
	// identity rather than the value.
	k.registerNative("make_float32", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internTrivialFloat32(float32(args[0].AsFloat()))}
	})
	k.registerNative("make_float64", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internTrivialFloat64(args[0].AsFloat())}
	})

	// File I/O
	k.registerNative("read_file", catCall(), func(_ *Kernel, args []Value) Value {
		b, err := os.ReadFile(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VNull}
		}
		return Value{Kind: VStr, Str: string(b)}
	})
	// Byte-level host file read — returns a list of ints (0-255), one per byte.
	k.registerNative("read_file_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		b, err := os.ReadFile(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VNull}
		}
		out := make([]Value, len(b))
		for i, by := range b {
			out[i] = Value{Kind: VInt, Int: int64(by)}
		}
		return Value{Kind: VList, List: out}
	})
	// source_inventory(root, suffix, skip-dir-names) — generic source
	// inventory primitive. Returns rows of [relative-path, line-count].
	// Form owns classification and aggregation; the kernel only exposes
	// filesystem walking and text line counts as primitive observation.
	k.registerNative("source_inventory", catCall(), func(_ *Kernel, args []Value) Value {
		root := resolveKernelHostPath(args[0].Str)
		suffix := args[1].Str
		skip := sourceInventorySkipSet(args[2])
		rootAbs, err := filepath.Abs(root)
		if err != nil {
			return Value{Kind: VNull}
		}
		rows := []Value{}
		err = filepath.WalkDir(rootAbs, func(path string, d os.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			name := d.Name()
			if d.IsDir() {
				if skip[name] {
					return filepath.SkipDir
				}
				return nil
			}
			if suffix != "" && !strings.HasSuffix(name, suffix) {
				return nil
			}
			rel, err := filepath.Rel(rootAbs, path)
			if err != nil {
				return err
			}
			rows = append(rows, sourceInventoryRow(filepath.ToSlash(rel), countTextLines(path)))
			return nil
		})
		if err != nil {
			return Value{Kind: VNull}
		}
		return Value{Kind: VList, List: rows}
	})
	// random_bytes(n) — open the doorway. Reads n bytes from
	// /dev/urandom every call. Different per invocation, per kernel
	// process. lc-divergence-is-the-doorway: this native intentionally
	// violates sibling parity when invoked — the divergence is the
	// substrate's signal of live field-touch.
	k.registerNative("random_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		n := int(args[0].Int)
		if n <= 0 {
			return Value{Kind: VList, List: []Value{}}
		}
		f, err := os.Open("/dev/urandom")
		if err != nil {
			return Value{Kind: VNull}
		}
		defer f.Close()
		buf := make([]byte, n)
		if _, err := io.ReadFull(f, buf); err != nil {
			return Value{Kind: VNull}
		}
		out := make([]Value, n)
		for i, by := range buf {
			out[i] = Value{Kind: VInt, Int: int64(by)}
		}
		return Value{Kind: VList, List: out}
	})
	// ---- bitwise primitives -----------------------------------
	// True kernel primitives — cannot be expressed in pure Form
	// without exponential cost. Operate on 32-bit-unsigned semantics
	// so SHA-256-style recipes compose round functions consistently.
	k.registerNative("band", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: args[0].Int & args[1].Int}
	})
	k.registerNative("bor", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: args[0].Int | args[1].Int}
	})
	k.registerNative("bxor", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: args[0].Int ^ args[1].Int}
	})
	k.registerNative("bnot_u32", catMethod(), func(_ *Kernel, args []Value) Value {
		a := uint32(args[0].Int)
		return Value{Kind: VInt, Int: int64(^a)}
	})
	k.registerNative("shl_u32", catMethod(), func(_ *Kernel, args []Value) Value {
		a := uint32(args[0].Int)
		n := uint32(args[1].Int) & 31
		return Value{Kind: VInt, Int: int64(a << n)}
	})
	k.registerNative("shr_u32", catMethod(), func(_ *Kernel, args []Value) Value {
		a := uint32(args[0].Int)
		n := uint32(args[1].Int) & 31
		return Value{Kind: VInt, Int: int64(a >> n)}
	})
	k.registerNative("rotr_u32", catMethod(), func(_ *Kernel, args []Value) Value {
		a := uint32(args[0].Int)
		n := uint32(args[1].Int) & 31
		return Value{Kind: VInt, Int: int64((a >> n) | (a << (32 - n)))}
	})
	// add_u32: modular 32-bit addition — SHA-256's round constants
	// and message schedule both require this discipline.
	k.registerNative("add_u32", catMethod(), func(_ *Kernel, args []Value) Value {
		a := uint32(args[0].Int)
		b := uint32(args[1].Int)
		return Value{Kind: VInt, Int: int64(a + b)}
	})
	// sha256_bytes / bytes_sum / bytes_hash were temporarily added as
	// natives here but composted: those are composites, not primitives.
	// SHA-256 lives in form-stdlib/sha256.fk as a Form recipe over the
	// bitwise primitives above. The real JIT path (Form recipe → host
	// machine code via recipe-emitter+plugin.Open) is the next walk;
	// this kernel currently relies on recipe-walk for composite ops.
	// register_jit form-name-str native-name-str → 1 on bind, 0 if
	// native-name has no registered native (refuse silent miss).
	// Inserts (form-name → native-name) into k.jitAliases. After this,
	// every (form-name ...) call goes through the aliased native instead
	// of walking the Form definition. Form recipes are canonical truth;
	// register_jit is the opt-in that promotes a recipe to host-native
	// execution. Removing the entry restores the Form walk.
	k.registerNative("register_jit", catWitness(), func(k *Kernel, args []Value) Value {
		formName := args[0].Str
		nativeName := args[1].Str
		nativeID := k.internName(nativeName)
		_, hasN := k.natives[nativeID]
		_, hasE := k.envNatives[nativeID]
		if !hasN && !hasE {
			return Value{Kind: VInt, Int: 0}
		}
		formID := k.internName(formName)
		k.jitAliases[formID] = nativeID
		return Value{Kind: VInt, Int: 1}
	})
	// unregister_jit form-name-str → 1 if removed, 0 if no alias was
	// bound. Restores the Form-recipe walk path for that name.
	k.registerNative("unregister_jit", catWitness(), func(k *Kernel, args []Value) Value {
		formName := args[0].Str
		formID := k.internName(formName)
		if _, ok := k.jitAliases[formID]; ok {
			delete(k.jitAliases, formID)
			return Value{Kind: VInt, Int: 1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	// recipe_to_bytes nid → list-of-bytes (or null on error).
	//   Serializes a Recipe subtree to the .fkb wire format as a byte
	//   list — usable over any byte channel without a file detour.
	k.registerNative("recipe_to_bytes", catWitness(), func(k *Kernel, args []Value) Value {
		bytes := serializeArtifact(k, args[0].Nid)
		out := make([]Value, len(bytes))
		for i, b := range bytes {
			out[i] = Value{Kind: VInt, Int: int64(b)}
		}
		return Value{Kind: VList, List: out}
	})
	// bytes_to_recipe bytes-list → nid (or null on parse error).
	k.registerNative("bytes_to_recipe", catWitness(), func(k *Kernel, args []Value) Value {
		if args[0].Kind != VList {
			return Value{Kind: VNull}
		}
		bytes := make([]byte, len(args[0].List))
		for i, v := range args[0].List {
			bytes[i] = byte(v.Int)
		}
		root, err := deserializeArtifact(k, bytes)
		if err != nil {
			return Value{Kind: VNull}
		}
		return Value{Kind: VNodeID, Nid: root}
	})
	// jit_compile form-name-str → 1 if a host-JIT compile succeeded,
	//   0 if the compile fell back (toolchain missing, body uses ops the
	//   emitter can't lower, plugin.Open failed), -1 if the name isn't
	//   bound to a closure at all. Env-aware: needs the caller's env to
	//   resolve the named closure.
	//
	// The Go path: Form recipe body → generated Go source under /tmp/
	//   → `go build -buildmode=plugin -o plugin.so` (via os/exec)
	//   -> plugin.Open + plugin.Lookup("FnI64"/"FnF64") to load ABI symbols
	//   -> store typed artifact under bodyKey in k.jitCompiledGo
	//   -> FNCALL closure path checks ABI guards and dispatches when present.
	//
	// Same shape as TS kernel's compileNode+jitCompiled — same canonical
	// truth (the recipe) expressed through each host's available compiler.
	k.registerEnvNative("jit_compile", catWitness(), func(k *Kernel, env *Frame, args []Value) Value {
		if len(args) < 1 || args[0].Kind != VStr {
			return Value{Kind: VInt, Int: -1}
		}
		nameID := k.internName(args[0].Str)
		v, ok := env.Lookup(nameID)
		if !ok || v.Kind != VClosure {
			return Value{Kind: VInt, Int: -1}
		}
		cl := v.Cl
		bodyKey := nodeIDKey(cl.Body)
		// Already compiled? Reuse — the body NodeID is content-addressed,
		// so the same shape across calls always resolves to the same .so.
		if _, exists := k.jitCompiledGo[bodyKey]; exists {
			delete(k.jitHits, cl.Body)
			k.observeJIT("observe/go/jit/compile-hit", cl.Body, 1, 1)
			return Value{Kind: VInt, Int: 1}
		}
		fn, err := jitCompileClosureGo(k, cl)
		if err != nil {
			// Honest fallback — the recipe still walks. The body remains
			// canonical truth; the JIT path is just unavailable for this
			// shape today.
			k.jitFailed[cl.Body] = true
			k.jitFailedReason[cl.Body] = err.Error()
			k.observeJIT("observe/go/jit/compile-fail", cl.Body, 1, 1)
			return Value{Kind: VInt, Int: 0}
		}
		k.jitCompiledGo[bodyKey] = fn
		delete(k.jitHits, cl.Body)
		k.observeJIT("observe/go/jit/compile-success", cl.Body, 1, 1)
		return Value{Kind: VInt, Int: 1}
	})
	// jit_compile_value form-name-str → 1 if the Value-typed JIT compiled
	//   the named closure to a native plugin, 0 on honest fallback (source
	//   root unavailable, or a recipe shape the emitter can't lower yet),
	//   -1 if the name isn't bound to a closure. The general path: compiles
	//   ANY recipe (lists, strings, native calls, cross-function calls) to a
	//   plugin operating on core.Value, with calls routed through dispatch.
	//   The recipe stays canonical truth; this just runs it native.
	// jit_emit_c form-name-str → the recipe lowered to freestanding C
	//   source (jit_c.go int64 subset), or "" when the shape isn't in the
	//   subset / the name isn't a closure. The projection surface for
	//   cross-ISA assembly: scripts/jit_assembly_audit tooling feeds it to
	//   LLVM for aarch64/hexagon/amdgcn/nvptx and reads the instructions.
	k.registerEnvNative("jit_emit_c", catWitness(), func(k *Kernel, env *Frame, args []Value) Value {
		if len(args) < 1 || args[0].Kind != VStr {
			return Value{Kind: VStr, Str: ""}
		}
		nameID := k.internName(args[0].Str)
		v, ok := env.Lookup(nameID)
		if !ok || v.Kind != VClosure {
			return Value{Kind: VStr, Str: ""}
		}
		src, err := jitEmitCClosure(k, v.Cl)
		if err != nil {
			return Value{Kind: VStr, Str: ""}
		}
		return Value{Kind: VStr, Str: src}
	})
	k.registerEnvNative("jit_compile_value", catWitness(), func(k *Kernel, env *Frame, args []Value) Value {
		if len(args) < 1 || args[0].Kind != VStr {
			return Value{Kind: VInt, Int: -1}
		}
		nameID := k.internName(args[0].Str)
		v, ok := env.Lookup(nameID)
		if !ok || v.Kind != VClosure {
			return Value{Kind: VInt, Int: -1}
		}
		cl := v.Cl
		bodyKey := nodeIDKey(cl.Body)
		if _, exists := k.jitCompiledGoV[bodyKey]; exists {
			return Value{Kind: VInt, Int: 1}
		}
		fnv, err := jitCompileClosureValueGo(k, cl)
		if err != nil {
			return Value{Kind: VInt, Int: 0}
		}
		k.jitCompiledGoV[bodyKey] = fnv
		return Value{Kind: VInt, Int: 1}
	})
	// jit_aliased? form-name-str → 1 if a JIT alias is currently bound
	// for this name, else 0. Lets Form code introspect dispatch routing.
	k.registerNative("jit_aliased?", catCompare(RCompareEq), func(k *Kernel, args []Value) Value {
		formName := args[0].Str
		formID := k.internName(formName)
		if _, ok := k.jitAliases[formID]; ok {
			return Value{Kind: VInt, Int: 1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	// jit_compiled? form-name-str -> 1 if the named closure's body NodeID has
	// a loaded Go plugin artifact, else 0. This reports compile-state only:
	// dispatch still depends on the artifact ABI matching the call's runtime
	// argument values. The trace's `jit-go-dispatch` native is the proof that a
	// call actually crossed into generated Go.
	k.registerEnvNative("jit_compiled?", catCompare(RCompareEq), func(k *Kernel, env *Frame, args []Value) Value {
		if len(args) < 1 || args[0].Kind != VStr {
			return Value{Kind: VInt, Int: 0}
		}
		formID := k.internName(args[0].Str)
		v, ok := env.Lookup(formID)
		if !ok || v.Kind != VClosure {
			return Value{Kind: VInt, Int: 0}
		}
		bodyKey := nodeIDKey(v.Cl.Body)
		if jc, ok := k.jitCompiledGo[bodyKey]; ok && jc != nil && (jc.I64 != nil || jc.F64 != nil || jc.Value != nil) {
			return Value{Kind: VInt, Int: 1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	// jit-stats -> list(kind, body-nodeid, count, detail). This is the
	// observer-facing JIT state: warming counters, compiled artifacts,
	// dispatch hits, and failed bodies with their compiler reason.
	k.registerNative("jit-stats", catWitness(), func(k *Kernel, _ []Value) Value {
		type jitStatRow struct {
			kind   string
			body   string
			count  uint32
			detail string
		}
		rows := []jitStatRow{}
		for bodyKey := range k.jitCompiledGo {
			rows = append(rows, jitStatRow{kind: "compiled", body: bodyKey})
		}
		for body, count := range k.jitDispatchHits {
			rows = append(rows, jitStatRow{kind: "dispatch-hit", body: nodeIDKey(body), count: count})
		}
		for body, count := range k.jitHits {
			rows = append(rows, jitStatRow{kind: "warming", body: nodeIDKey(body), count: count})
		}
		for body, failed := range k.jitFailed {
			if !failed {
				continue
			}
			rows = append(rows, jitStatRow{
				kind:   "compile-failed",
				body:   nodeIDKey(body),
				count:  1,
				detail: k.jitFailedReason[body],
			})
		}
		sort.Slice(rows, func(i, j int) bool {
			if rows[i].kind != rows[j].kind {
				return rows[i].kind < rows[j].kind
			}
			return rows[i].body < rows[j].body
		})
		out := make([]Value, 0, len(rows))
		for _, row := range rows {
			out = append(out, Value{Kind: VList, List: []Value{
				{Kind: VStr, Str: row.kind},
				{Kind: VStr, Str: row.body},
				{Kind: VInt, Int: int64(row.count)},
				{Kind: VStr, Str: row.detail},
			}})
		}
		return Value{Kind: VList, List: out}
	})
	// seeded_bytes(seed, count) — deterministic LCG byte stream.
	// Same (seed, count) → byte-identical output across Go / Rust / TS.
	// glibc rand(): state = (state * 1103515245 + 12345) & 0x7FFFFFFF
	k.registerNative("seeded_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		seed := uint32(args[0].Int)
		count := int(args[1].Int)
		if count <= 0 {
			return Value{Kind: VList, List: []Value{}}
		}
		state := seed
		out := make([]Value, count)
		for i := 0; i < count; i++ {
			state = (state*1103515245 + 12345) & 0x7FFFFFFF
			out[i] = Value{Kind: VInt, Int: int64(state & 0xFF)}
		}
		return Value{Kind: VList, List: out}
	})
	// sum_bytes_list(list) — fast O(n) compiled sum.
	k.registerNative("sum_bytes_list", catCall(), func(_ *Kernel, args []Value) Value {
		var s int64 = 0
		if args[0].Kind == VList {
			for _, v := range args[0].List {
				s += v.Int
			}
		}
		return Value{Kind: VInt, Int: s}
	})
	// write_form_binary — emit a Recipe to .fkb on disk in the full
	// artifact format (string table + tree). Sibling to read_form_binary.
	// Use when source-compile output needs to cross kernel invocations:
	// serialize-recipe alone drops string indices, which break under
	// fresh string tables on load. This format embeds the strings.
	k.registerNative("write_form_binary", catCall(), func(k *Kernel, args []Value) Value {
		path := resolveKernelHostPath(args[0].Str)
		nid := args[1].Nid
		bytes := serializeArtifact(k, nid)
		if err := os.WriteFile(path, bytes, 0644); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(len(bytes))}
	})
	k.registerNative("read_form_binary", catCall(), func(k *Kernel, args []Value) Value {
		b, err := os.ReadFile(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VNull}
		}
		root, err := deserializeArtifact(k, b)
		if err != nil {
			return Value{Kind: VNull}
		}
		return Value{Kind: VNodeID, Nid: root}
	})
	k.registerNative("write_form_binary", catCall(), func(k *Kernel, args []Value) Value {
		bytes := serializeArtifact(k, args[1].Nid)
		if err := os.WriteFile(resolveKernelHostPath(args[0].Str), bytes, 0644); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(len(bytes))}
	})
	k.registerNative("file_size", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: info.Size()}
	})
	// file_mtime — modification time in unix seconds; -1 if file missing.
	// Used by Form-side cache layers (form-stdlib/cache.fk) to decide
	// when a .fkb projection of a source file is stale. Generic: any
	// "regenerate cache when source newer" pattern can compose this.
	k.registerNative("file_mtime", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: info.ModTime().Unix()}
	})
	k.registerNative("file_byte_at", catCall(), func(_ *Kernel, args []Value) Value {
		if args[1].Int < 0 {
			return Value{Kind: VInt, Int: -1}
		}
		f, err := os.Open(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		defer f.Close()
		buf := []byte{0}
		n, err := f.ReadAt(buf, args[1].Int)
		if err != nil || n == 0 {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(buf[0])}
	})
	k.registerNative("read_file_slice", catCall(), func(_ *Kernel, args []Value) Value {
		offset := args[1].Int
		length := args[2].Int
		if offset < 0 || length <= 0 {
			return Value{Kind: VStr, Str: ""}
		}
		f, err := os.Open(resolveKernelHostPath(args[0].Str))
		if err != nil {
			return Value{Kind: VStr, Str: ""}
		}
		defer f.Close()
		buf := make([]byte, length)
		n, _ := f.ReadAt(buf, offset)
		return Value{Kind: VStr, Str: string(buf[:n])}
	})

	// --- Filesystem CRUD natives — real directories + files ------------
	// Sibling parity across Go/Rust/TS. Paths are strings. Convention:
	// predicates return 1/0; mutations return 0 on success, -1 on error;
	// fs_list returns a VList of name-strings (entries of a directory),
	// or VNull on error. These compose into a real directory tree with
	// file CRUD, the foundation under the file carrier and the substrate
	// file store.
	// (fs_exists path)        → 1 | 0
	// (fs_is_dir path)        → 1 | 0
	// (fs_mkdir path)         → 0 | -1   (mkdir -p; existing dir is success)
	// (fs_rmdir path)         → 0 | -1   (recursive remove of a directory)
	// (fs_remove path)        → 0 | -1   (remove a single file)
	// (fs_rename old new)     → 0 | -1
	// (fs_list path)          → VList of entry-name strings | VNull
	k.registerNative("fs_exists", catCall(), func(_ *Kernel, args []Value) Value {
		if _, err := os.Stat(args[0].Str); err != nil {
			return Value{Kind: VInt, Int: 0}
		}
		return Value{Kind: VInt, Int: 1}
	})
	k.registerNative("fs_is_dir", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(args[0].Str)
		if err != nil || !info.IsDir() {
			return Value{Kind: VInt, Int: 0}
		}
		return Value{Kind: VInt, Int: 1}
	})
	k.registerNative("fs_mkdir", catCall(), func(_ *Kernel, args []Value) Value {
		if err := os.MkdirAll(args[0].Str, 0755); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("fs_rmdir", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(args[0].Str)
		if err != nil || !info.IsDir() {
			return Value{Kind: VInt, Int: -1}
		}
		if err := os.RemoveAll(args[0].Str); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("fs_remove", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(args[0].Str)
		if err != nil || info.IsDir() {
			return Value{Kind: VInt, Int: -1}
		}
		if err := os.Remove(args[0].Str); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("fs_rename", catCall(), func(_ *Kernel, args []Value) Value {
		if err := os.Rename(args[0].Str, args[1].Str); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: 0}
	})
	k.registerNative("fs_list", catCall(), func(_ *Kernel, args []Value) Value {
		entries, err := os.ReadDir(args[0].Str)
		if err != nil {
			return Value{Kind: VNull}
		}
		out := make([]Value, len(entries))
		for i, e := range entries {
			out[i] = Value{Kind: VStr, Str: e.Name()}
		}
		return Value{Kind: VList, List: out}
	})

	// --- Socket natives — L1 physical layer for inter-cell IO ----------
	// Sibling parity across Go/Rust/TS. Handle = int (≥ 0 success, -1
	// error). The connection table is package-level (socketHandles).
	// (socket_listen port)             → handle | -1
	// (socket_accept listener-handle)  → conn-handle | -1   (BLOCKS)
	// (socket_connect host port)       → conn-handle | -1
	// (socket_send conn bytes-string)  → bytes-sent | -1
	// (socket_recv conn max-bytes)     → received-string ("" on close)
	// (socket_close handle)            → 0 | -1
	k.registerNative("socket_listen", catCall(), func(_ *Kernel, args []Value) Value {
		port := args[0].Int
		ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: socketRegister(ln)}
	})
	// (socket_port listener-handle) → bound TCP port | -1. Lets a listener
	// opened on port 0 (ephemeral) report the OS-assigned port — the basis
	// of single-process loopback (listen 0 → port → connect → accept).
	k.registerNative("socket_port", catCall(), func(_ *Kernel, args []Value) Value {
		v := socketLookup(args[0].Int)
		ln, ok := v.(net.Listener)
		if !ok {
			return Value{Kind: VInt, Int: -1}
		}
		ta, ok := ln.Addr().(*net.TCPAddr)
		if !ok {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(ta.Port)}
	})
	k.registerNative("socket_accept", catCall(), func(_ *Kernel, args []Value) Value {
		v := socketLookup(args[0].Int)
		ln, ok := v.(net.Listener)
		if !ok {
			return Value{Kind: VInt, Int: -1}
		}
		c, err := ln.Accept()
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: socketRegister(c)}
	})
	k.registerNative("socket_connect", catCall(), func(_ *Kernel, args []Value) Value {
		host := args[0].Str
		port := args[1].Int
		c, err := net.Dial("tcp", fmt.Sprintf("%s:%d", host, port))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: socketRegister(c)}
	})
	k.registerNative("socket_send", catCall(), func(_ *Kernel, args []Value) Value {
		v := socketLookup(args[0].Int)
		c, ok := v.(net.Conn)
		if !ok {
			return Value{Kind: VInt, Int: -1}
		}
		n, err := c.Write([]byte(args[1].Str))
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(n)}
	})
	k.registerNative("socket_recv", catCall(), func(_ *Kernel, args []Value) Value {
		v := socketLookup(args[0].Int)
		c, ok := v.(net.Conn)
		if !ok {
			return Value{Kind: VStr, Str: ""}
		}
		max := args[1].Int
		if max <= 0 {
			return Value{Kind: VStr, Str: ""}
		}
		buf := make([]byte, max)
		n, err := c.Read(buf)
		if err != nil || n <= 0 {
			return Value{Kind: VStr, Str: ""}
		}
		return Value{Kind: VStr, Str: string(buf[:n])}
	})
	k.registerNative("socket_close", catCall(), func(_ *Kernel, args []Value) Value {
		h := args[0].Int
		if h < 0 {
			return Value{Kind: VInt, Int: -1}
		}
		v := socketLookup(h)
		if v == nil {
			return Value{Kind: VInt, Int: -1}
		}
		switch x := v.(type) {
		case net.Listener:
			x.Close()
		case net.Conn:
			x.Close()
		}
		socketDrop(h)
		return Value{Kind: VInt, Int: 0}
	})

	// --- Substrate write surface ----------------------------------------
	// All attributed as WITNESS — the substrate attesting to its own
	// structure. Form code holds NodeIDs as values (VNodeID) and uses
	// these natives to construct recipes.

	k.registerNative("make_nodeid", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: NodeID{
			Pkg:   uint32(args[0].Int),
			Level: uint32(args[1].Int),
			Type:  uint32(args[2].Int),
			Inst:  uint32(args[3].Int),
		}}
	})
	k.registerNative("bp", catWitness(), func(_ *Kernel, args []Value) Value {
		if c, ok := bpTable[args[0].Str]; ok {
			return Value{Kind: VNodeID, Nid: NodeID{Pkg: c[0], Level: c[1], Type: c[2], Inst: c[3]}}
		}
		// Fail loud — never invent a NodeID for an unknown name. The old silent
		// fallback to {1,2,0,0} collapsed EVERY unregistered name onto one
		// NodeID, so distinct blueprints collided invisibly (the bug that bit
		// the Shamballa channel twice). The substrate's promise is that identity
		// is bounded by what is registered; an unregistered name is a missing
		// registration, not a valid shape. Sibling parity: Rust panics, TS throws.
		panic(fmt.Sprintf("bp: unregistered blueprint name %q — register it: "+
			"python3 scripts/scan_form_blueprints.py register %s (bp tables then regenerate). "+
			"The substrate never invents a NodeID for an unknown name.", args[0].Str, args[0].Str))
	})
	k.registerNative("intern_trivial_int", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internTrivialInt(args[0].Int)}
	})
	k.registerNative("intern_trivial_string", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internString(args[0].Str)}
	})
	k.registerNative("intern_trivial_bool", catWitness(), func(_ *Kernel, args []Value) Value {
		inst := uint32(0)
		if truthy(args[0]) {
			inst = 1
		}
		return Value{Kind: VNodeID, Nid: NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivBool, Inst: inst}}
	})
	// intern_trivial_float — content-address an IEEE-754 f64 into the overflow
	// table and return its trivial NodeID. The string argument is the float's
	// source text (e.g. "0.5"); a parse failure lands on +0.0 so the witness is
	// total like str_to_int. Sibling of intern_trivial_int / intern_trivial_string;
	// exposes the existing internTrivialFloat64 to Form code so the python-bmf
	// float-literal lift can build a PY-BMF-FLOAT leaf.
	k.registerNative("intern_trivial_float", catWitness(), func(k *Kernel, args []Value) Value {
		f, _ := strconv.ParseFloat(args[0].Str, 64)
		return Value{Kind: VNodeID, Nid: k.internTrivialFloat64(f)}
	})

	// float_value — decode a TrivFloat* NodeID back to a VFloat so it can be
	// fed into math_sqrt, math_acos, arithmetic, etc. This is the small bridge
	// that lets host-interned live floats (via intern_trivial_float / make_float64)
	// be used directly in kernel-native numeric code (including the geometry projection
	// on external efficacy-probe vectors).
	k.registerNative("float_value", catMethod(), func(k *Kernel, args []Value) Value {
		if len(args) != 1 {
			panic("float_value expects 1 argument")
		}
		n := args[0]
		if n.Kind != VNodeID {
			panic("float_value expects a NodeID")
		}
		switch n.Nid.Type {
		case TrivFloat32:
			return Value{Kind: VFloat, Float: float64(k.decodeFloat32(n.Nid.Inst))}
		case TrivFloat64:
			return Value{Kind: VFloat, Float: k.decodeFloat64(n.Nid.Inst)}
		default:
			panic("float_value expects a float NodeID")
		}
	})

	// print_float — forces a clean numeric print of a VFloat or TrivFloat* value.
	// This is a small diagnostic + reporting helper so the kernel can "report"
	// actual numbers from geometry / numeric workloads on host-supplied data.
	k.registerNative("print_float", catMethod(), func(k *Kernel, args []Value) Value {
		if len(args) != 1 {
			panic("print_float expects 1 argument")
		}
		v := args[0]
		var f float64
		if v.Kind == VFloat {
			f = v.Float
		} else if v.Kind == VNodeID {
			if v.Nid.Type == TrivFloat32 {
				f = float64(k.decodeFloat32(v.Nid.Inst))
			} else if v.Nid.Type == TrivFloat64 {
				f = k.decodeFloat64(v.Nid.Inst)
			} else {
				panic("print_float expects a float value or float NodeID")
			}
		} else {
			panic("print_float expects a float value or float NodeID")
		}
		fmt.Printf("%.10g\n", f)
		return Value{Kind: VNull}
	})

	// dot_product and magnitude — the minimal vector primitives that make
	// the geometry projection (cosine + angle via math_acos) runnable on
	// live 8-band efficacy-probe vectors inside the kernel driver.
	// Follows the exact same registerNative + catMethod() pattern as
	// math_acos / print_float / float_value. Sibling parity target: Rust + TS kernels.
	// These close the "higher-order vector math (dot, mag, angle on lists) still tight"
	// item in the trace-symbol-spaces.form Part 6 tightness witness.
	k.registerNative("dot_product", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 2 {
			panic("dot_product expects 2 arguments")
		}
		a := args[0].List
		b := args[1].List
		if len(a) != len(b) {
			panic("dot_product requires equal length vectors")
		}
		var sum float64
		for i := range a {
			sum += a[i].AsFloat() * b[i].AsFloat()
		}
		return Value{Kind: VFloat, Float: sum}
	})

	k.registerNative("magnitude", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 1 {
			panic("magnitude expects 1 argument")
		}
		v := args[0].List
		var sum float64
		for i := range v {
			f := v[i].AsFloat()
			sum += f * f
		}
		return Value{Kind: VFloat, Float: math.Sqrt(sum)}
	})

	// vector_cosine and pair_angle — composite helpers that combine the
	// newly added dot_product + magnitude with math_acos for direct
	// geometry projection on live 8-band vectors in a single --expr call.
	// This is the kernel-native counterpart to the pair_cosine / pair_angle
	// recipes being added on the recipelib track. Placed immediately after
	// the vector primitives for locality.
	k.registerNative("vector_cosine", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 2 {
			panic("vector_cosine expects 2 arguments")
		}
		a := args[0].List
		b := args[1].List
		if len(a) != len(b) {
			panic("vector_cosine requires equal length vectors")
		}
		var dot float64
		var na float64
		var nb float64
		for i := range a {
			fa := a[i].AsFloat()
			fb := b[i].AsFloat()
			dot += fa * fb
			na += fa * fa
			nb += fb * fb
		}
		if na == 0 || nb == 0 {
			return Value{Kind: VFloat, Float: 0}
		}
		return Value{Kind: VFloat, Float: dot / (math.Sqrt(na) * math.Sqrt(nb))}
	})

	k.registerNative("pair_angle", catMethod(), func(k *Kernel, args []Value) Value {
		cosV := k.natives[k.internName("vector_cosine")].Fn(k, args)
		c := cosV.Float
		if c > 1.0 {
			c = 1.0
		}
		if c < -1.0 {
			c = -1.0
		}
		return Value{Kind: VFloat, Float: math.Acos(c)}
	})

	// dominant_band_delta — mirrors the recipelib helper for richer thruline
	// readout. Returns a two-element list [band_index, max_abs_delta] so the
	// kernel driver can surface the same band-tension information as the
	// Form-declared recipe path. Placed with the other geometry natives.
	k.registerNative("dominant_band_delta", catMethod(), func(_ *Kernel, args []Value) Value {
		if len(args) != 2 {
			panic("dominant_band_delta expects 2 arguments")
		}
		a := args[0].List
		b := args[1].List
		n := len(a)
		if len(b) < n {
			n = len(b)
		}
		if n == 0 {
			return Value{Kind: VList, List: []Value{
				{Kind: VFloat, Float: 0},
				{Kind: VFloat, Float: 0},
			}}
		}
		maxDelta := 0.0
		maxIdx := 0
		for i := 0; i < n; i++ {
			d := a[i].AsFloat() - b[i].AsFloat()
			if d < 0 {
				d = -d
			}
			if d > maxDelta {
				maxDelta = d
				maxIdx = i
			}
		}
		return Value{Kind: VList, List: []Value{
			{Kind: VFloat, Float: float64(maxIdx)},
			{Kind: VFloat, Float: maxDelta},
		}}
	})

	k.registerNative("intern_node", catWitness(), func(k *Kernel, args []Value) Value {
		cat := args[0].Nid
		kids := make([]NodeID, len(args[1].List))
		for i, c := range args[1].List {
			kids[i] = c.Nid
		}
		return Value{Kind: VNodeID, Nid: k.intern(cat, kids)}
	})
	fieldNode := func(nativeName string, categoryType uint32, categoryInst uint32) NativeFn {
		return func(k *Kernel, args []Value) Value {
			if len(args) != 1 || args[0].Kind != VList {
				panic(fmt.Sprintf("%s: expected one list of NodeIDs", nativeName))
			}
			kids := make([]NodeID, len(args[0].List))
			for i, c := range args[0].List {
				if c.Kind != VNodeID {
					panic(fmt.Sprintf("%s: children must be nodeids", nativeName))
				}
				kids[i] = c.Nid
			}
			return Value{
				Kind: VNodeID,
				Nid:  k.intern(NodeID{Pkg: 1, Level: LevelBasic, Type: categoryType, Inst: categoryInst}, kids),
			}
		}
	}
	fieldConstructors := []struct {
		name         string
		categoryType uint32
		categoryInst uint32
	}{
		{"field_blueprint", RBasicField, 1},
		{"field_cell", RBasicField, 2},
		{"field_carrier", RBasicCarrier, 1},
		{"field_topology", RBasicTopology, 1},
		{"field_fiber", RBasicFiber, 1},
		{"field_region", RBasicRegion, 1},
		{"field_boundary", RBasicBoundary, 1},
		{"field_neighborhood", RBasicNeighborhood, 1},
		{"field_match", RBasicMatchField, 1},
		{"field_delta", RBasicDelta, 1},
		{"field_resolve", RBasicResolve, 1},
		{"field_commit", RBasicCommit, 1},
		{"field_step", RBasicStep, 1},
		{"field_lift", RBasicLift, 1},
		{"field_sample", RBasicSample, 1},
		{"field_observe", RBasicObserve, 1},
		{"field_intervene", RBasicIntervene, 1},
		{"field_residual", RBasicResidual, 1},
		{"field_receipt", RBasicReceipt, 1},
		{"field_cost", RBasicCost, 1},
		{"field_consent", RBasicConsent, 1},
		{"field_evidence", RBasicEvidence, 1},
	}
	for _, c := range fieldConstructors {
		k.registerNative(c.name, catFieldPrimitive(c.categoryType), fieldNode(c.name, c.categoryType, c.categoryInst))
	}
	k.registerNative("substrate_mark", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VList, List: k.substrateMark()}
	})
	k.registerNative("substrate_counts", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VList, List: k.substrateCounts()}
	})
	k.registerNative("substrate_release", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: k.substrateRelease(args[0].List)}
	})
	k.registerNative("substrate_gc", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VList, List: k.substrateGC(args[0].List, nil)}
	})
	k.registerNative("node_category", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.category(args[0].Nid)}
	})
	k.registerNative("node_children", catWitness(), func(k *Kernel, args []Value) Value {
		kids := k.children(args[0].Nid)
		out := make([]Value, len(kids))
		for i, c := range kids {
			out[i] = Value{Kind: VNodeID, Nid: c}
		}
		return Value{Kind: VList, List: out}
	})
	k.registerNative("node_value", catWitness(), func(k *Kernel, args []Value) Value {
		return k.trivialValue(args[0].Nid)
	})
	k.registerNative("node_pkg", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(args[0].Nid.Pkg)}
	})
	k.registerNative("node_level", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(args[0].Nid.Level)}
	})
	k.registerNative("node_type", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(args[0].Nid.Type)}
	})
	k.registerNative("node_inst", catWitness(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VInt, Int: int64(args[0].Nid.Inst)}
	})
	// node_eq — compare two NodeIDs structurally. Sibling to Rust's node_eq.
	// Form code (emit-engine.fk lookup-template) uses this for category
	// dispatch — the kernel's `eq` (RCMP_EQ) coerces operands via as_int,
	// which panics on NodeIDs; node_eq closes that gap.
	k.registerNative("node_eq", catCompare(RCompareEq), func(k *Kernel, args []Value) Value {
		// Strict — sibling parity with Rust's `as_nid` and TS's `argNodeID`.
		// Both panic on non-NodeID args; Go's previous lenience (reading
		// `args[N].Nid` directly on a VStr returns the zero NodeID, making
		// two strings compare equal — a latent false positive) is the bug.
		if args[0].Kind != VNodeID || args[1].Kind != VNodeID {
			panic(fmt.Sprintf("node_eq: expected NodeID args, got %v and %v", args[0].Kind, args[1].Kind))
		}
		return Value{Kind: VBool, Bool: args[0].Nid == args[1].Nid}
	})
	// value_eq — polymorphic equality across all Value kinds. Returns
	// true when both args have the same kind AND compare equal within
	// that kind. Cross-kind returns false (str ≠ nodeid even if they
	// share text). Use this when a Form-side function holds tagged
	// values that may be either strings or NodeIDs (e.g. domain/lens
	// in bmf-symbol-context can be either typed-constant NodeIDs or
	// string literals). Avoids the str_eq/node_eq fork that previously
	// forced callers to know which type they held.
	k.registerNative("value_eq", catCompare(RCompareEq), func(k *Kernel, args []Value) Value {
		return Value{Kind: VBool, Bool: valueEqual(args[0], args[1])}
	})
	// intern_node_at — intern composite + record source attribution.
	// Engine.fk's parser actions call this so every emitted Recipe carries
	// (file, line, col) provenance. The satsang teaching: every cell's
	// state is traceable back to the recipe lines that authored it.
	// Args: (category, children, file_string, line_int, col_int)
	k.registerNative("intern_node_at", catWitness(), func(k *Kernel, args []Value) Value {
		cat := args[0].Nid
		kidsV := args[1].List
		kids := make([]NodeID, len(kidsV))
		for i, c := range kidsV {
			kids[i] = c.Nid
		}
		nid := k.intern(cat, kids)
		fileNid := k.internString(args[2].Str)
		fileID := NameID(fileNid.Inst)
		line := uint32(args[3].Int)
		col := uint32(args[4].Int)
		k.sourceAttr[nid] = sourceLoc{FileID: fileID, Line: line, Col: col}
		k.activeRoots = append(k.activeRoots, nid)
		k.framebufferRoots = append(k.framebufferRoots, nid)
		return Value{Kind: VNodeID, Nid: nid}
	})
	// node_source — read back a Recipe's source attribution.
	// Returns (list file_string line col) or empty list if none recorded.
	k.registerNative("node_source", catWitness(), func(k *Kernel, args []Value) Value {
		loc, ok := k.sourceAttr[args[0].Nid]
		if !ok {
			return Value{Kind: VList, List: []Value{}}
		}
		file := k.strs[loc.FileID]
		return Value{Kind: VList, List: []Value{
			{Kind: VStr, Str: file},
			{Kind: VInt, Int: int64(loc.Line)},
			{Kind: VInt, Int: int64(loc.Col)},
		}}
	})
	// framebuffer-events — return all NodeIDs with source attribution.
	// The source_attr side-map IS the framebuffer. Observer-side
	// tracing: emitter pays one hashmap insert per intern_node_at;
	// observer pays the cost of walking this list when it analyzes.
	k.registerNative("framebuffer-events", catWitness(), func(k *Kernel, _ []Value) Value {
		out := make([]Value, 0, len(k.framebufferRoots))
		for _, nid := range k.framebufferRoots {
			if _, ok := k.sourceAttr[nid]; !ok {
				continue
			}
			out = append(out, Value{Kind: VNodeID, Nid: nid})
		}
		return Value{Kind: VList, List: out}
	})
	// framebuffer-event-rows - ordered detail rows over the same framebuffer
	// facts as framebuffer-counts. Detail is useful before a route condenses;
	// counts are the compressed after-JIT view.
	k.registerNative("framebuffer-event-rows", catWitness(), func(k *Kernel, _ []Value) Value {
		rows := k.framebufferEvents()
		out := make([]Value, 0, len(rows))
		for _, row := range rows {
			childVals := []Value{}
			for _, child := range row["children"].([]string) {
				childVals = append(childVals, Value{Kind: VStr, Str: child})
			}
			childValueVals := []Value{}
			for _, child := range row["child_values"].([]string) {
				childValueVals = append(childValueVals, Value{Kind: VStr, Str: child})
			}
			out = append(out, Value{Kind: VList, List: []Value{
				{Kind: VInt, Int: row["seq"].(int64)},
				{Kind: VStr, Str: row["file"].(string)},
				{Kind: VInt, Int: int64(row["line"].(uint32))},
				{Kind: VInt, Int: int64(row["col"].(uint32))},
				{Kind: VStr, Str: row["node"].(string)},
				{Kind: VList, List: childVals},
				{Kind: VList, List: childValueVals},
			}})
		}
		return Value{Kind: VList, List: out}
	})
	// framebuffer-counts - observer-side aggregation over the framebuffer
	// plane. Rows are (file, line, col, count), so repeated recipe dispatch,
	// branch failure, and JIT events stay on the same surface as source
	// attribution instead of becoming a trace-only side channel.
	k.registerNative("framebuffer-counts", catWitness(), func(k *Kernel, _ []Value) Value {
		rows := k.framebufferSourceCounts()
		out := make([]Value, 0, len(rows))
		for _, row := range rows {
			out = append(out, Value{Kind: VList, List: []Value{
				{Kind: VStr, Str: row["file"].(string)},
				{Kind: VInt, Int: int64(row["line"].(uint32))},
				{Kind: VInt, Int: int64(row["col"].(uint32))},
				{Kind: VInt, Int: int64(row["count"].(int))},
			}})
		}
		return Value{Kind: VList, List: out}
	})
	k.registerNative("framebuffer-observe-start", catWitness(), func(k *Kernel, _ []Value) Value {
		k.observeRuntime = true
		return Value{Kind: VNull}
	})
	k.registerNative("framebuffer-observe-stop", catWitness(), func(k *Kernel, _ []Value) Value {
		k.observeRuntime = false
		return Value{Kind: VNull}
	})
	k.registerNative("framebuffer-observe-active?", catCompare(RCompareEq), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VBool, Bool: k.observationActive()}
	})
	// framebuffer-clear — reset the framebuffer for bounded windows.
	k.registerNative("framebuffer-clear", catWitness(), func(k *Kernel, _ []Value) Value {
		k.sourceAttr = make(map[NodeID]sourceLoc)
		k.observeSeq = 0
		k.framebufferRoots = nil
		return Value{Kind: VNull}
	})
	// serialize-recipe — walk a Recipe tree, emit a flat byte list as
	// Value::Int per byte. Format per node: 5 big-endian u32s
	// (pkg, level, ty, inst, children_count) + recursive children.
	// Trivials: children_count=0, NodeID encoded directly.
	// Composites: (pkg, level, ty, inst) is the CATEGORY; the composite
	// NodeID is reconstructed at deserialize via intern.
	k.registerNative("serialize-recipe", catWitness(), func(k *Kernel, args []Value) Value {
		bytes := []byte{}
		bytes = serializeNid(k, args[0].Nid, bytes)
		out := make([]Value, len(bytes))
		for i, b := range bytes {
			out[i] = Value{Kind: VInt, Int: int64(b)}
		}
		return Value{Kind: VList, List: out}
	})
	// deserialize-recipe — read byte list back into a Recipe tree.
	// Composites re-intern so the resulting NodeIDs match the original
	// identities by content-addressing.
	k.registerNative("deserialize-recipe", catWitness(), func(k *Kernel, args []Value) Value {
		bytes := make([]byte, len(args[0].List))
		for i, v := range args[0].List {
			bytes[i] = byte(v.Int)
		}
		nid, _ := deserializeNid(k, bytes, 0, k.nextImportScope())
		return Value{Kind: VNodeID, Nid: nid}
	})
	// write_file_bytes — sibling of read_file_bytes; writes a byte list.
	k.registerNative("write_file_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		bytes := make([]byte, len(args[1].List))
		for i, v := range args[1].List {
			bytes[i] = byte(v.Int)
		}
		err := os.WriteFile(args[0].Str, bytes, 0644)
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(len(bytes))}
	})
	// file_append_bytes path bytes-list → new-file-size | -1. Atomic O_APPEND
	// write — the missing primitive for a log-structured store. Unlike
	// write_file_bytes (which truncates), this seeks to end-of-file under the
	// kernel's append lock so concurrent appends do not clobber, then returns
	// the new total file size. Creates the file if absent. Foundation for
	// cell-log-store.fk (the Bitcask-shape store) — see
	// docs/coherence-substrate/cell-store-architecture.md.
	k.registerNative("file_append_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		bytes := make([]byte, len(args[1].List))
		for i, v := range args[1].List {
			bytes[i] = byte(v.Int)
		}
		f, err := os.OpenFile(args[0].Str, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		defer f.Close()
		if _, err := f.Write(bytes); err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		info, err := f.Stat()
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: info.Size()}
	})
	// write_file_text — host text output. Keeps text compilers from
	// materializing byte lists while byte codecs still use write_file_bytes.
	k.registerNative("write_file_text", catCall(), func(_ *Kernel, args []Value) Value {
		bytes := []byte(args[1].Str)
		err := os.WriteFile(args[0].Str, bytes, 0644)
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: int64(len(bytes))}
	})
	// walk-cached — JIT-vector memoization. Caller asserts purity.
	k.registerNative("walk-cached", catWitness(), func(k *Kernel, args []Value) Value {
		if v, ok := k.walkCache[args[0].Nid]; ok {
			k.walkCacheHits++
			return v
		}
		k.walkCacheMisses++
		env := NewFrame(nil)
		v := k.walk(args[0].Nid, env)
		k.walkCache[args[0].Nid] = v
		return v
	})
	k.registerNative("walk-cache-clear", catWitness(), func(k *Kernel, _ []Value) Value {
		k.walkCache = make(map[NodeID]Value)
		k.walkCacheHits = 0
		k.walkCacheMisses = 0
		return Value{Kind: VNull}
	})
	k.registerNative("walk-cache-size", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VInt, Int: int64(len(k.walkCache))}
	})
	k.registerNative("walk-cache-stats", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VList, List: []Value{
			{Kind: VInt, Int: int64(k.walkCacheHits)},
			{Kind: VInt, Int: int64(k.walkCacheMisses)},
			{Kind: VInt, Int: int64(len(k.walkCache))},
		}}
	})
	compileFormSource := func(k *Kernel, args []Value) Value {
		k.sourceCompileErr = ""
		label := "runtime:string/form"
		if len(args) > 1 && args[1].Kind == VStr && args[1].Str != "" {
			label = args[1].Str
		}
		root := readRootFromSource(k, args[0].Str)
		pinRuntimeCompiledRoot(k, root, label)
		return Value{Kind: VNodeID, Nid: root}
	}
	k.registerNative("compile_form_source", catWitness(), compileFormSource)
	k.registerNative("compile-form-source", catWitness(), compileFormSource)
	compileSourceSection := func(k *Kernel, args []Value) Value {
		k.sourceCompileErr = ""
		label := "runtime:string/source-section"
		if len(args) > 2 && args[2].Kind == VStr && args[2].Str != "" {
			label = args[2].Str
		}
		root, err := compileSourceSectionIntoKernel(k, args[0].Str, args[1].Str, label)
		if err != nil {
			k.sourceCompileErr = err.Error()
			return Value{Kind: VNull}
		}
		return Value{Kind: VNodeID, Nid: root}
	}
	k.registerNative("compile_source_section", catWitness(), compileSourceSection)
	k.registerNative("compile-source-section", catWitness(), compileSourceSection)
	compileSourceText := func(k *Kernel, args []Value) Value {
		k.sourceCompileErr = ""
		label := "runtime:string/source"
		if len(args) > 1 && args[1].Kind == VStr && args[1].Str != "" {
			label = args[1].Str
		}
		root, err := compileSourceTextIntoKernel(k, label, args[0].Str)
		if err != nil {
			k.sourceCompileErr = err.Error()
			return Value{Kind: VNull}
		}
		return Value{Kind: VNodeID, Nid: root}
	}
	k.registerNative("compile_source_text", catWitness(), compileSourceText)
	k.registerNative("compile-source-text", catWitness(), compileSourceText)
	k.registerNative("source_compile_last_error", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VStr, Str: k.sourceCompileErr}
	})
	k.registerNative("source-compile-last-error", catWitness(), func(k *Kernel, _ []Value) Value {
		return Value{Kind: VStr, Str: k.sourceCompileErr}
	})
	k.registerNative("walk_recipe", catWitness(), func(k *Kernel, args []Value) Value {
		env := NewFrame(nil)
		return k.walk(args[0].Nid, env)
	})
	// walk_recipe_here — walks a Recipe in the CALLER's env, so let-
	// bindings inside the Recipe land in the caller's scope. This is
	// how source-compiled output can produce Form definitions directly
	// from a Recipe tree without going through text round-trip: build
	// the Recipe via intern_node, serialize to .fkb, then load via
	//   (walk_recipe_here (deserialize-recipe (read_file_bytes "out.fkb")))
	// the lets propagate into the surrounding load chain's env.
	k.registerEnvNative("walk_recipe_here", catWitness(), func(k *Kernel, env *Frame, args []Value) Value {
		// Pin the recipe root as an active root so substrate_gc keeps the
		// definitions reachable. Closures bound here hold body NodeIDs that
		// aren't reachable from the source-parsed root, so without this pin
		// a subsequent substrate_gc would sweep them and leave the env
		// holding closures with deleted bodies.
		k.activeRoots = append(k.activeRoots, args[0].Nid)
		return k.walk(args[0].Nid, env)
	})
	walkParallel := func(k *Kernel, args []Value) Value {
		roots := make([]NodeID, len(args[0].List))
		for i, v := range args[0].List {
			roots[i] = v.Nid
		}
		workers := int(args[1].Int)
		if workers < 1 {
			workers = 1
		}
		if workers > len(roots) && len(roots) > 0 {
			workers = len(roots)
		}
		sequential := func() Value {
			out := make([]Value, len(roots))
			for i, root := range roots {
				out[i] = k.walk(root, NewFrame(nil))
			}
			return Value{Kind: VList, List: out}
		}
		if workers <= 1 || len(roots) <= 1 || k.Trace != nil {
			return sequential()
		}
		for _, root := range roots {
			if !k.isParallelPure(root, make(map[NodeID]bool)) {
				return sequential()
			}
		}
		out := make([]Value, len(roots))
		jobs := make(chan int)
		var wg sync.WaitGroup
		for w := 0; w < workers; w++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for idx := range jobs {
					out[idx] = k.walk(roots[idx], NewFrame(nil))
				}
			}()
		}
		for i := range roots {
			jobs <- i
		}
		close(jobs)
		wg.Wait()
		return Value{Kind: VList, List: out}
	}
	k.registerNative("walk_parallel", catWitness(), walkParallel)
	k.registerNative("walk-parallel", catWitness(), walkParallel)
	walkParallelCached := func(k *Kernel, args []Value) Value {
		roots := make([]NodeID, len(args[0].List))
		for i, v := range args[0].List {
			roots[i] = v.Nid
		}
		workers := int(args[1].Int)
		if workers < 1 {
			workers = 1
		}
		if workers > len(roots) && len(roots) > 0 {
			workers = len(roots)
		}
		sequential := func(cache bool) Value {
			out := make([]Value, len(roots))
			local := make(map[NodeID]Value)
			for i, root := range roots {
				if cache {
					if cached, ok := k.walkCache[root]; ok {
						k.walkCacheHits++
						out[i] = cached
						continue
					}
					if cached, ok := local[root]; ok {
						k.walkCacheHits++
						out[i] = cached
						continue
					}
					k.walkCacheMisses++
				}
				out[i] = k.walk(root, NewFrame(nil))
				if cache {
					k.walkCache[root] = out[i]
					local[root] = out[i]
				}
			}
			return Value{Kind: VList, List: out}
		}
		if len(roots) == 0 {
			return Value{Kind: VList, List: []Value{}}
		}
		for _, root := range roots {
			if !k.isParallelPure(root, make(map[NodeID]bool)) {
				return sequential(false)
			}
		}
		if workers <= 1 || len(roots) <= 1 || k.Trace != nil {
			return sequential(k.Trace == nil)
		}
		out := make([]Value, len(roots))
		jobs := make([]int, 0, len(roots))
		first := make(map[NodeID]int)
		fanout := make(map[int][]int)
		for i, root := range roots {
			if cached, ok := k.walkCache[root]; ok {
				k.walkCacheHits++
				out[i] = cached
			} else if primary, ok := first[root]; ok {
				k.walkCacheHits++
				fanout[primary] = append(fanout[primary], i)
			} else {
				k.walkCacheMisses++
				first[root] = i
				jobs = append(jobs, i)
			}
		}
		jobCh := make(chan int)
		var wg sync.WaitGroup
		for w := 0; w < workers; w++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for idx := range jobCh {
					root := roots[idx]
					out[idx] = k.walk(root, NewFrame(nil))
				}
			}()
		}
		for _, i := range jobs {
			jobCh <- i
		}
		close(jobCh)
		wg.Wait()
		for _, i := range jobs {
			k.walkCache[roots[i]] = out[i]
			for _, dup := range fanout[i] {
				out[dup] = out[i]
			}
		}
		return Value{Kind: VList, List: out}
	}
	k.registerNative("walk_parallel_cached", catWitness(), walkParallelCached)
	k.registerNative("walk-parallel-cached", catWitness(), walkParallelCached)

	// native_blueprint — read a native's Form category from inside Form.
	// Returns the category NodeID (level=2, ty=RBasic, inst=instance) or
	// VNull if the name isn't bound to a native.
	k.registerNative("native_blueprint", catWitness(), func(k *Kernel, args []Value) Value {
		idx, ok := k.strIdx[args[0].Str]
		if !ok {
			return Value{Kind: VNull}
		}
		ne, ok := k.natives[idx]
		if !ok {
			return Value{Kind: VNull}
		}
		return Value{Kind: VNodeID, Nid: ne.Category}
	})

	k.registerHostIONatives()

	// --- Debug / inspection -----------------------------------------------
	// `trace` — print-and-return. No Form category claimed; debug surface.
	k.registerNative("trace", catUndefined(), func(_ *Kernel, args []Value) Value {
		if len(args) >= 2 {
			fmt.Fprintf(os.Stderr, "[trace %s] %s\n", args[0].Str, args[1].String())
			return args[1]
		}
		fmt.Fprintf(os.Stderr, "[trace] %s\n", args[0].String())
		return args[0]
	})

	// `now_unix_ms` — current wall-clock as a millisecond unix timestamp.
	// External effect (reads the host clock) so it's catCall. Sibling
	// parity holds on shape, NOT on value: every kernel returns an int,
	// every kernel's int is > a recent past epoch — but the exact
	// milliseconds diverge between invocations. Bands check shape only.
	k.registerNative("now_unix_ms", catCall(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VInt, Int: time.Now().UnixMilli()}
	})
}

// Category constructors for native attribution live further down alongside
// catMath/catCompare/catBlock/etc. The reader-side helpers already cover
// catCompare(inst), catBlock(inst), etc.; the native-attribution helpers
// (catCall, catWitness, catAccess, catMethod, catListNat, catUndefined)
// are defined in the same block to keep them together.

// ---------------------------------------------------------------------------
// Walker — full RBasic dispatch
// ---------------------------------------------------------------------------

func (k *Kernel) walk(n NodeID, env *Frame) Value {
	// Tail-call optimization: a tail-position call — a closure body, a cond
	// branch, or a do-block's last expr — reassigns n/env and loops here
	// instead of recursing, so tail-recursive Form loops (gm-rep-loop,
	// gm-sep-loop, caps-get, find-loop, …) run in CONSTANT stack. This is the
	// "non-stack" shape: genuine data nesting still recurses; iteration does
	// not. Result-transparent — identical values to plain recursion, far less
	// stack (a long member/statement list no longer recurses N-deep), which is
	// what lets the strictest kernel parse the full thesis grammar files.
	for {
		if n.Level == LevelTrivial {
			return k.trivialValue(n)
		}
		// One map lookup per composite walk step. cat + kids read off the same
		// recipe row; Go's map returns Recipe by value, but Children is a slice
		// header pointing to the table's backing array — zero-copy access.
		r := k.recipeAt(n)
		cat, kids := r.Category, r.Children

		// Tracing hook: when k.Trace is set, record the arm dispatch. Pure
		// counter increment — no allocation, no IO. Per lc-native-kernel-binary.
		// Records (ty, inst) so typed-numeric distribution stays distinguishable.
		if k.Trace != nil {
			k.Trace.record(cat.Type, cat.Inst)
		}
		k.observeRecipeDispatch(cat)

		switch cat.Type {
		case RBasicMath:
			lv := k.walk(kids[0], env)
			rv := k.walk(kids[1], env)
			// Width promotion: if either operand is Float, the result is
			// Float (matches Python `int + float → float`, and IEEE 754
			// arithmetic on mixed inputs). Pure int/int stays on the
			// fast int path. Mirrors Rust kernel's RB_MATH dispatch.
			if lv.Kind == VFloat || rv.Kind == VFloat {
				l := lv.AsFloat()
				r := rv.AsFloat()
				switch cat.Inst {
				case RMathPlus:
					return Value{Kind: VFloat, Float: l + r}
				case RMathMinus:
					return Value{Kind: VFloat, Float: l - r}
				case RMathMultiply:
					return Value{Kind: VFloat, Float: l * r}
				case RMathDivide:
					return Value{Kind: VFloat, Float: l / r}
				case RMathModulo:
					return Value{Kind: VFloat, Float: l - math.Floor(l/r)*r}
				}
			}
			a := lv.Int
			b := rv.Int
			switch cat.Inst {
			case RMathPlus:
				return Value{Kind: VInt, Int: a + b}
			case RMathMinus:
				return Value{Kind: VInt, Int: a - b}
			case RMathMultiply:
				return Value{Kind: VInt, Int: a * b}
			case RMathDivide:
				return Value{Kind: VInt, Int: a / b}
			case RMathModulo:
				return Value{Kind: VInt, Int: a % b}
			}

		case RBasicCompare:
			lv := k.walk(kids[0], env)
			rv := k.walk(kids[1], env)
			// Same width-promotion rule as math: float on either side forces
			// an IEEE comparison. Pure int/int stays integer. Mirrors Rust.
			if lv.Kind == VFloat || rv.Kind == VFloat {
				l := lv.AsFloat()
				r := rv.AsFloat()
				switch cat.Inst {
				case RCompareEq:
					return Value{Kind: VBool, Bool: l == r}
				case RCompareNe:
					return Value{Kind: VBool, Bool: l != r}
				case RCompareLt:
					return Value{Kind: VBool, Bool: l < r}
				case RCompareLe:
					return Value{Kind: VBool, Bool: l <= r}
				case RCompareGt:
					return Value{Kind: VBool, Bool: l > r}
				case RCompareGe:
					return Value{Kind: VBool, Bool: l >= r}
				}
			}
			a := lv.Int
			b := rv.Int
			switch cat.Inst {
			case RCompareEq:
				return Value{Kind: VBool, Bool: a == b}
			case RCompareNe:
				return Value{Kind: VBool, Bool: a != b}
			case RCompareLt:
				return Value{Kind: VBool, Bool: a < b}
			case RCompareLe:
				return Value{Kind: VBool, Bool: a <= b}
			case RCompareGt:
				return Value{Kind: VBool, Bool: a > b}
			case RCompareGe:
				return Value{Kind: VBool, Bool: a >= b}
			}

		case RBasicLogic:
			switch cat.Inst {
			case RLogicAnd:
				if !k.walk(kids[0], env).Bool {
					return Value{Kind: VBool, Bool: false}
				}
				return Value{Kind: VBool, Bool: k.walk(kids[1], env).Bool}
			case RLogicOr:
				if k.walk(kids[0], env).Bool {
					return Value{Kind: VBool, Bool: true}
				}
				return Value{Kind: VBool, Bool: k.walk(kids[1], env).Bool}
			case RLogicNot:
				return Value{Kind: VBool, Bool: !k.walk(kids[0], env).Bool}
			}

		case RBasicCond:
			cond := k.walk(kids[0], env)
			if truthy(cond) {
				n = kids[1] // TCO: taken branch is in tail position
				continue
			}
			if cat.Inst == RCondIfThenElse && len(kids) >= 3 {
				n = kids[2] // TCO: else branch is in tail position
				continue
			}
			return Value{Kind: VNull}

		case RBasicBlock:
			if cat.Inst == RBlockLet {
				name := k.identID(kids[0])
				v := k.walk(kids[1], env)
				env.Bind(name, v)
				return v
			}
			if len(kids) == 0 {
				return Value{}
			}
			for i := 0; i < len(kids)-1; i++ {
				k.walk(kids[i], env)
			}
			n = kids[len(kids)-1] // TCO: a do/seq block's last expr is in tail position
			continue

		case RBasicMatch:
			if cat.Inst == RMatchSwitch {
				return k.walkMatchSwitch(n, kids, env)
			}
			return Value{Kind: VNodeID, Nid: n}

		case RBasicChoice:
			switch cat.Inst {
			case RChoiceFail:
				panic(choiceFailSignal{})
			case RChoiceStop:
				panic(choiceStopSignal{})
			case RChoiceChoose:
				for i, branch := range kids {
					if k.Trace != nil {
						k.Trace.ChoiceAttempts++
					}
					k.observeFrame("observe/go/choice/attempt", uint32(i+1), uint32(len(kids)), branch)
					value, ok, stopped := k.walkChoiceBranch(branch, env)
					if ok {
						if k.Trace != nil {
							k.Trace.ChoiceSuccesses++
						}
						if stopped {
							k.observeFrame("observe/go/choice/stop", uint32(i+1), uint32(len(kids)), branch)
						} else {
							k.observeFrame("observe/go/choice/success", uint32(i+1), uint32(len(kids)), branch)
						}
						return value
					}
					if k.Trace != nil {
						k.Trace.ChoiceFailures++
					}
					k.observeFrame("observe/go/choice/fail", uint32(i+1), uint32(len(kids)), branch)
				}
				panic(choiceFailSignal{})
			}
			return Value{Kind: VNull}

		case RBasicIdent:
			id := k.identID(n)
			if v, ok := env.Lookup(id); ok {
				return v
			}
			panic(fmt.Sprintf("walk: unbound identifier %q", k.nameStr(id)))

		case RBasicFnDef:
			name := k.identID(kids[0])
			paramKids := k.children(kids[1])
			params := make([]NameID, len(paramKids))
			for i, p := range paramKids {
				params[i] = NameID(p.Inst)
			}
			cl := &Closure{Name: name, Params: params, Body: kids[2], Env: env}
			env.Bind(name, Value{Kind: VClosure, Cl: cl})
			return Value{Kind: VClosure, Cl: cl}

		case RBasicFnCall:
			rawName := k.identID(kids[0])
			// JIT alias: if a Form function-name is JIT-registered, swap to
			// the aliased native-name before native lookup. Form recipes are
			// the canonical truth; `register_jit form-name native-name` opts
			// calls into a kernel-resident optimized native.
			name := rawName
			if aliased, ok := k.jitAliases[rawName]; ok {
				name = aliased
			}
			// Env-aware natives first — they need the caller env to splice
			// pre-built Recipes (walk_recipe_here, etc.). Checked before
			// plain natives so a name registered both ways prefers env-aware.
			if ne, ok := k.envNatives[name]; ok {
				if _, hasUserBinding := env.Lookup(name); !hasUserBinding {
					args := make([]Value, len(kids)-1)
					for i := 1; i < len(kids); i++ {
						args[i-1] = k.walk(kids[i], env)
					}
					if k.Trace != nil && ne.Category.Type != RBasicUndefined {
						k.Trace.record(ne.Category.Type, ne.Category.Inst)
					}
					if k.Trace != nil {
						k.Trace.recordNative(k.nameStr(ne.Name))
					}
					k.observeNamedDispatch("observe/go/native-dispatch", ne.Name)
					return ne.Fn(k, env, args)
				}
			}
			// Native takes priority unless user shadowed with a closure.
			if ne, ok := k.natives[name]; ok {
				if _, hasUserBinding := env.Lookup(name); !hasUserBinding {
					args := make([]Value, len(kids)-1)
					for i := 1; i < len(kids); i++ {
						args[i-1] = k.walk(kids[i], env)
					}
					if k.Trace != nil && ne.Category.Type != RBasicUndefined {
						k.Trace.record(ne.Category.Type, ne.Category.Inst)
					}
					if k.Trace != nil {
						k.Trace.recordNative(k.nameStr(ne.Name))
					}
					k.observeNamedDispatch("observe/go/native-dispatch", ne.Name)
					return ne.Fn(k, args)
				}
			}
			// Closure lookup uses the original function name so user code stays
			// canonical when no native or alias resolved above.
			v, ok := env.Lookup(rawName)
			if !ok {
				panic(fmt.Sprintf("walk: unbound function %q", k.nameStr(rawName)))
			}
			if v.Kind != VClosure {
				panic(fmt.Sprintf("walk: %q is not callable", k.nameStr(rawName)))
			}
			cl := v.Cl
			if len(kids)-1 != len(cl.Params) {
				panic(fmt.Sprintf("walk: %q wants %d args, got %d", k.nameStr(rawName), len(cl.Params), len(kids)-1))
			}
			argVals := make([]Value, len(cl.Params))
			for i := 1; i < len(kids); i++ {
				argVals[i-1] = k.walk(kids[i], env)
			}
			bodyKey := nodeIDKey(cl.Body)
			if _, ok := k.jitCompiledGoV[bodyKey]; ok {
				if k.Trace != nil {
					k.Trace.recordFn(k.nameStr(cl.Name))
					k.Trace.recordNative("jit-go-value-dispatch")
				}
				k.jitDispatchHits[cl.Body]++
				k.observeNamedDispatch("observe/go/function-dispatch", cl.Name)
				k.observeJIT("observe/go/jit/dispatch-hit", cl.Body, 4, uint32(len(argVals)))
				return k.applyClosureValue(cl, argVals)
			}
			if jc, ok := k.jitCompiledGo[bodyKey]; ok && jc != nil {
				allInt := true
				allNumeric := true
				hasFloat := false
				allJITValue := true
				intArgs := make([]int64, len(cl.Params))
				floatArgs := make([]float64, len(cl.Params))
				jitArgs := make([]jitabi.Value, len(cl.Params))
				for i, av := range argVals {
					if av.Kind != VInt {
						allInt = false
					}
					if jv, ok := valueToJIT(av); ok {
						jitArgs[i] = jv
					} else {
						allJITValue = false
					}
					switch av.Kind {
					case VInt:
						intArgs[i] = av.Int
						floatArgs[i] = float64(av.Int)
					case VFloat:
						hasFloat = true
						floatArgs[i] = av.Float
					default:
						allNumeric = false
					}
				}
				if allInt && jc.I64 != nil {
					if k.Trace != nil {
						k.Trace.recordFn(k.nameStr(cl.Name))
						k.Trace.recordNative("jit-go-dispatch")
					}
					k.jitDispatchHits[cl.Body]++
					k.observeNamedDispatch("observe/go/function-dispatch", cl.Name)
					k.observeJIT("observe/go/jit/dispatch-hit", cl.Body, 1, uint32(len(argVals)))
					return Value{Kind: VInt, Int: jc.I64(intArgs)}
				}
				if allNumeric && hasFloat && jc.F64 != nil {
					if k.Trace != nil {
						k.Trace.recordFn(k.nameStr(cl.Name))
						k.Trace.recordNative("jit-go-dispatch")
					}
					k.jitDispatchHits[cl.Body]++
					k.observeNamedDispatch("observe/go/function-dispatch", cl.Name)
					k.observeJIT("observe/go/jit/dispatch-hit", cl.Body, 2, uint32(len(argVals)))
					return Value{Kind: VFloat, Float: jc.F64(floatArgs)}
				}
				if allJITValue && jc.Value != nil {
					if k.Trace != nil {
						k.Trace.recordFn(k.nameStr(cl.Name))
						k.Trace.recordNative("jit-go-dispatch")
					}
					k.jitDispatchHits[cl.Body]++
					k.observeNamedDispatch("observe/go/function-dispatch", cl.Name)
					k.observeJIT("observe/go/jit/dispatch-hit", cl.Body, 3, uint32(len(argVals)))
					return valueFromJIT(jc.Value(jitArgs))
				}
				k.observeJIT("observe/go/jit/guard-miss", cl.Body, 1, uint32(len(argVals)))
			} else if !k.jitFailed[cl.Body] {
				const goJITHotThreshold uint32 = 2000
				hits := k.jitHits[cl.Body] + 1
				if hits >= goJITHotThreshold {
					if jc, err := jitCompileClosureGo(k, cl); err == nil {
						k.jitCompiledGo[bodyKey] = jc
						k.observeJIT("observe/go/jit/auto-compile-success", cl.Body, 1, 1)
					} else {
						k.jitFailed[cl.Body] = true
						k.jitFailedReason[cl.Body] = err.Error()
						k.observeJIT("observe/go/jit/auto-compile-fail", cl.Body, 1, 1)
					}
					delete(k.jitHits, cl.Body)
				} else {
					k.jitHits[cl.Body] = hits
				}
			}
			call := NewCallFrame(cl.Env, len(cl.Params))
			for i, p := range cl.Params {
				call.Bind(p, argVals[i])
			}
			if k.Trace != nil {
				k.Trace.recordFn(k.nameStr(cl.Name))
			}
			k.observeNamedDispatch("observe/go/function-dispatch", cl.Name)
			n = cl.Body // TCO: closure body is in tail position.
			env = call
			continue

		case RBasicList:
			out := make([]Value, len(kids))
			for i, c := range kids {
				out[i] = k.walk(c, env)
			}
			return Value{Kind: VList, List: out}
		}

		// Structural passthrough — categories the walker can't yet execute
		// (CHOICE_MATCH, CONSTRUCTOR, INDUCTIVE, QUOTIENT, ALIAS, BLANKET,
		// PROJECT, GENERATIVE, PROOF, INFERENCE, VECTOR, TILE, PARALLELIZE,
		// VECTORIZE, OBSERVER, TRANSMUTE, ...) intern fine and the trace
		// records their attribution. Walking returns the NodeID itself so
		// downstream structural reasoning continues. Sibling-parity with
		// the Rust + TS kernels.
		return Value{Kind: VNodeID, Nid: n}
	}
}

func (k *Kernel) walkChoiceBranch(branch NodeID, env *Frame) (value Value, ok bool, stopped bool) {
	defer func() {
		if r := recover(); r != nil {
			switch r.(type) {
			case choiceFailSignal:
				value = Value{Kind: VNull}
				ok = false
				stopped = false
			case choiceStopSignal:
				value = Value{Kind: VNull}
				ok = true
				stopped = true
			default:
				panic(r)
			}
		}
	}()
	return k.walk(branch, env), true, false
}

func (k *Kernel) switchTableFor(node NodeID, kids []NodeID) *switchTable {
	if table, ok := k.switchTables[node]; ok {
		return table
	}
	if len(kids) < 1 || (len(kids)-1)%2 != 0 {
		panic("match: SWITCH expects scrutinee plus pattern/body pairs")
	}
	table := &switchTable{cases: make(map[NodeID]NodeID)}
	for i := 1; i < len(kids); i += 2 {
		pattern := kids[i]
		body := kids[i+1]
		if k.isSwitchDefaultPattern(pattern) {
			table.defaultBody = body
			table.hasDefault = true
			continue
		}
		if pattern.Level == LevelTrivial {
			table.cases[pattern] = body
			continue
		}
		table.dynamicArms = append(table.dynamicArms, switchArm{pattern: pattern, body: body})
	}
	k.switchTables[node] = table
	return table
}

func (k *Kernel) isSwitchDefaultPattern(pattern NodeID) bool {
	if pattern.Level != LevelTrivial {
		cat := k.category(pattern)
		if cat.Type == RBasicIdent {
			return k.nameStr(k.identID(pattern)) == "_"
		}
	}
	return false
}

func (k *Kernel) switchKeyFromValue(v Value) (NodeID, bool) {
	switch v.Kind {
	case VNull:
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivNull, Inst: 0}, true
	case VInt:
		return k.internTrivialInt(v.Int), true
	case VFloat:
		return k.internTrivialFloat64(v.Float), true
	case VStr:
		return k.internString(v.Str), true
	case VBool:
		if v.Bool {
			return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivBool, Inst: 1}, true
		}
		return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivBool, Inst: 0}, true
	case VNodeID:
		return v.Nid, true
	default:
		return NodeID{}, false
	}
}

func valueEqual(a, b Value) bool {
	if a.Kind != b.Kind {
		return false
	}
	switch a.Kind {
	case VNull:
		return true
	case VInt:
		return a.Int == b.Int
	case VFloat:
		return a.Float == b.Float
	case VStr:
		return a.Str == b.Str
	case VBool:
		return a.Bool == b.Bool
	case VNodeID:
		return a.Nid == b.Nid
	case VList:
		if len(a.List) != len(b.List) {
			return false
		}
		for i := range a.List {
			if !valueEqual(a.List[i], b.List[i]) {
				return false
			}
		}
		return true
	default:
		return false
	}
}

func (k *Kernel) walkMatchSwitch(node NodeID, kids []NodeID, env *Frame) Value {
	if len(kids) < 1 || (len(kids)-1)%2 != 0 {
		panic("match: SWITCH expects scrutinee plus pattern/body pairs")
	}
	if k.Trace != nil {
		k.Trace.MatchLookups++
	}
	scrutinee := k.walk(kids[0], env)
	table := k.switchTableFor(node, kids)
	if key, ok := k.switchKeyFromValue(scrutinee); ok {
		if body, found := table.cases[key]; found {
			if k.Trace != nil {
				k.Trace.MatchHits++
			}
			k.observeFrame("observe/go/match/hit", key.Type, key.Inst, node, key, body)
			return k.walk(body, env)
		}
	}
	for _, arm := range table.dynamicArms {
		if valueEqual(k.walk(arm.pattern, env), scrutinee) {
			if k.Trace != nil {
				k.Trace.MatchHits++
			}
			k.observeFrame("observe/go/match/dynamic-hit", 1, uint32(len(table.dynamicArms)), node, arm.pattern, arm.body)
			return k.walk(arm.body, env)
		}
	}
	if table.hasDefault {
		if k.Trace != nil {
			k.Trace.MatchDefaults++
		}
		k.observeFrame("observe/go/match/default", 1, 1, node, table.defaultBody)
		return k.walk(table.defaultBody, env)
	}
	if k.Trace != nil {
		k.Trace.MatchMisses++
	}
	k.observeFrame("observe/go/match/miss", 1, uint32(len(kids)), node)
	panic(fmt.Sprintf("match: exhausted without a matching arm for %s", scrutinee.String()))
}

func truthy(v Value) bool {
	switch v.Kind {
	case VBool:
		return v.Bool
	case VInt:
		return v.Int != 0
	case VNull:
		return false
	}
	return true
}

// ---------------------------------------------------------------------------
// S-expression source adapter — text → recipe tree
// ---------------------------------------------------------------------------
//
// Syntax:
//   (verb arg arg ...)      — composite recipe
//   <int>                   — trivial INT
//   "string"                — trivial STRING
//   <ident>                 — identifier reference (RBasicIdent)
//   ; comment to end of line
//
// Verb mapping (recipe builders):
//   do, seq, let
//   if (2-arg or 3-arg)
//   add, sub, mul, div, mod
//   eq, ne, lt, le, gt, ge
//   and, or, not
//   defn (name params-list body)
//   <anything-else>         — FnCall to that name

// sexpToken — source-reader cell. Carries 1-based line/col so parse
// errors can point at the source. Without this, every paren imbalance
// surfaces as an unhelpful "index out of bounds" panic.
type sexpToken struct {
	kind  string // "LPAREN" | "RPAREN" | "INT" | "STRING" | "IDENT"
	value string
	line  int
	col   int
}

func tokenizeSexp(src string) []sexpToken {
	tokens := make([]sexpToken, 0, 64)
	line, col := 1, 1
	advance := func(n int) { col += n }
	newline := func() { line++; col = 1 }
	i := 0
	for i < len(src) {
		c := src[i]
		if c == '\n' {
			i++
			newline()
			continue
		}
		if c == ' ' || c == '\t' || c == '\r' {
			i++
			advance(1)
			continue
		}
		if c == ';' {
			for i < len(src) && src[i] != '\n' {
				i++
			}
			// Don't advance col; newline handler will reset on \n
			continue
		}
		startLine, startCol := line, col
		if c == '(' {
			tokens = append(tokens, sexpToken{"LPAREN", "(", startLine, startCol})
			i++
			advance(1)
			continue
		}
		if c == ')' {
			tokens = append(tokens, sexpToken{"RPAREN", ")", startLine, startCol})
			i++
			advance(1)
			continue
		}
		if c == '"' {
			i++
			advance(1)
			start := i
			for i < len(src) && src[i] != '"' {
				if src[i] == '\\' && i+1 < len(src) {
					i += 2
					advance(2)
					continue
				}
				if src[i] == '\n' {
					newline()
				} else {
					advance(1)
				}
				i++
			}
			tokens = append(tokens, sexpToken{"STRING", unescapeStr(src[start:i]), startLine, startCol})
			if i < len(src) {
				i++
				advance(1)
			}
			continue
		}
		if (c >= '0' && c <= '9') || (c == '-' && i+1 < len(src) && src[i+1] >= '0' && src[i+1] <= '9') {
			start := i
			if c == '-' {
				i++
			}
			for i < len(src) && src[i] >= '0' && src[i] <= '9' {
				i++
			}
			isFloat := false
			// Fractional part: `.` followed by at least one digit.
			if i < len(src) && src[i] == '.' && i+1 < len(src) && src[i+1] >= '0' && src[i+1] <= '9' {
				isFloat = true
				i++ // consume '.'
				for i < len(src) && src[i] >= '0' && src[i] <= '9' {
					i++
				}
			}
			// Exponent: e/E [+/-] one-or-more digits. Accepted on both
			// pure-int mantissa (1e5) and fractional mantissa (1.5e3),
			// matching the TS kernel reader's float regex.
			if i < len(src) && (src[i] == 'e' || src[i] == 'E') {
				j := i + 1
				if j < len(src) && (src[j] == '+' || src[j] == '-') {
					j++
				}
				if j < len(src) && src[j] >= '0' && src[j] <= '9' {
					isFloat = true
					i = j
					for i < len(src) && src[i] >= '0' && src[i] <= '9' {
						i++
					}
				}
			}
			if isFloat {
				tokens = append(tokens, sexpToken{"FLOAT", src[start:i], startLine, startCol})
			} else {
				tokens = append(tokens, sexpToken{"INT", src[start:i], startLine, startCol})
			}
			advance(i - start)
			continue
		}
		// Identifier — any non-whitespace, non-paren, non-quote
		start := i
		for i < len(src) && src[i] != ' ' && src[i] != '\t' && src[i] != '\n' &&
			src[i] != '\r' && src[i] != '(' && src[i] != ')' && src[i] != '"' && src[i] != ';' {
			i++
		}
		tokens = append(tokens, sexpToken{"IDENT", src[start:i], startLine, startCol})
		advance(i - start)
	}
	return tokens
}

func unescapeStr(s string) string {
	out := make([]byte, 0, len(s))
	for i := 0; i < len(s); i++ {
		if s[i] == '\\' && i+1 < len(s) {
			switch s[i+1] {
			case 'n':
				out = append(out, '\n')
			case 't':
				out = append(out, '\t')
			case 'r':
				out = append(out, '\r')
			case '\\':
				out = append(out, '\\')
			case '"':
				out = append(out, '"')
			default:
				out = append(out, s[i+1])
			}
			i++
			continue
		}
		out = append(out, s[i])
	}
	return string(out)
}

// readSexpr — parse the token stream starting at position i, return the
// recipe NodeID and the next position. Every error path includes line/col
// so paren imbalance points at the source instead of dying with "index
// out of bounds." The source adapter is foreign-syntax-by-necessity;
// its job is to fail informatively when humans miscount.
func (k *Kernel) readSexpr(toks []sexpToken, i int) (NodeID, int) {
	if i >= len(toks) {
		panic("parse error: unexpected end of input (expected an expression)")
	}
	t := toks[i]
	switch t.kind {
	case "INT":
		n, _ := strconv.ParseInt(t.value, 10, 64)
		return k.internTrivialInt(n), i + 1
	case "FLOAT":
		f, err := strconv.ParseFloat(t.value, 64)
		if err != nil {
			panic(fmt.Sprintf("parse error: bad float literal %q at line %d col %d: %v",
				t.value, t.line, t.col, err))
		}
		return k.internTrivialFloat64(f), i + 1
	case "STRING":
		return k.internString(t.value), i + 1
	case "IDENT":
		// Bool literals — true/false are reserved, become trivial values at parse
		// time. Parallel to int/string literals; lets Form predicates read
		// naturally without `(eq 0 0)` constructors.
		if t.value == "true" {
			return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivBool, Inst: 1}, i + 1
		}
		if t.value == "false" {
			return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivBool, Inst: 0}, i + 1
		}
		return k.intern(catIdent(), []NodeID{k.internString(t.value)}), i + 1
	case "RPAREN":
		panic(fmt.Sprintf("parse error at line %d col %d: unmatched `)` (no `(` to close)", t.line, t.col))
	case "LPAREN":
		openLine, openCol := t.line, t.col
		i++
		if i >= len(toks) {
			panic(fmt.Sprintf("parse error: unclosed `(` opened at line %d col %d (reached end of input)", openLine, openCol))
		}
		if toks[i].kind == "RPAREN" {
			return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivNull, Inst: 0}, i + 1
		}
		if toks[i].kind != "IDENT" {
			panic(fmt.Sprintf("parse error at line %d col %d: expected verb after `(` opened at line %d col %d, got %s %q",
				toks[i].line, toks[i].col, openLine, openCol, toks[i].kind, toks[i].value))
		}
		verb := toks[i].value
		i++
		args := []NodeID{}
		for {
			if i >= len(toks) {
				panic(fmt.Sprintf("parse error: unclosed `(` opened at line %d col %d in `(%s ...)` (reached end of input)",
					openLine, openCol, verb))
			}
			if toks[i].kind == "RPAREN" {
				i++
				break
			}
			arg, ni := k.readSexpr(toks, i)
			args = append(args, arg)
			i = ni
		}
		return k.buildVerb(verb, args), i
	}
	panic(fmt.Sprintf("parse error at line %d col %d: unexpected token %s %q", t.line, t.col, t.kind, t.value))
}

// buildVerb — map an S-expression verb to its recipe category + children.
// The single point where the source syntax meets the substrate vocabulary.
func (k *Kernel) buildVerb(verb string, args []NodeID) NodeID {
	switch verb {
	case "do":
		return k.intern(catBlock(RBlockDo), args)
	case "seq":
		return k.intern(catBlock(RBlockSequence), args)
	case "let":
		// (let <ident> <value>) — repackage the identifier wrapper as the
		// bare string trivial so the walker reads NameID directly from `inst`.
		nameID := k.identID(args[0])
		nameTrivial := NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivString, Inst: uint32(nameID)}
		return k.intern(catBlock(RBlockLet), []NodeID{nameTrivial, args[1]})
	case "if":
		if len(args) == 2 {
			return k.intern(catCond(RCondIfThen), args)
		}
		return k.intern(catCond(RCondIfThenElse), args)
	case "add":
		return k.intern(catMath(RMathPlus), args)
	case "sub":
		return k.intern(catMath(RMathMinus), args)
	case "mul":
		return k.intern(catMath(RMathMultiply), args)
	case "div":
		return k.intern(catMath(RMathDivide), args)
	case "mod":
		return k.intern(catMath(RMathModulo), args)
	case "eq":
		return k.intern(catCompare(RCompareEq), args)
	case "ne":
		return k.intern(catCompare(RCompareNe), args)
	case "lt":
		return k.intern(catCompare(RCompareLt), args)
	case "le":
		return k.intern(catCompare(RCompareLe), args)
	case "gt":
		return k.intern(catCompare(RCompareGt), args)
	case "ge":
		return k.intern(catCompare(RCompareGe), args)
	case "and":
		return k.intern(catLogic(RLogicAnd), args)
	case "or":
		return k.intern(catLogic(RLogicOr), args)
	case "not":
		return k.intern(catLogic(RLogicNot), args)
	case "match":
		return k.intern(catMatch(RMatchSwitch), args)
	case "choose":
		return k.intern(catChoice(RChoiceChoose), args)
	case "fail":
		return k.intern(catChoice(RChoiceFail), args)
	case "stop":
		return k.intern(catChoice(RChoiceStop), args)
	case "defn":
		// (defn <name> (<params>...) <body>) — names and params get repackaged
		// as bare string trivials so the walker reads NameID via `inst`.
		toTriv := func(id NameID) NodeID {
			return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivString, Inst: uint32(id)}
		}
		nameTrivial := toTriv(k.identID(args[0]))
		paramKids := k.children(args[1])
		pnames := make([]NodeID, len(paramKids))
		for i, p := range paramKids {
			pnames[i] = toTriv(k.identID(p))
		}
		paramsBlock := k.intern(catBlock(RBlockSequence), pnames)
		return k.intern(catFnDef(), []NodeID{nameTrivial, paramsBlock, args[2]})
	case "params":
		// Special: a params-list literal, returns a SEQUENCE of idents
		return k.intern(catBlock(RBlockSequence), args)
	default:
		// Default: a function call to `verb` with these args
		nameStr := k.internString(verb)
		all := append([]NodeID{nameStr}, args...)
		return k.intern(catFnCall(), all)
	}
}

// Category constructors
func catMath(inst uint32) NodeID    { return NodeID{1, LevelBasic, RBasicMath, inst} }
func catCompare(inst uint32) NodeID { return NodeID{1, LevelBasic, RBasicCompare, inst} }
func catLogic(inst uint32) NodeID   { return NodeID{1, LevelBasic, RBasicLogic, inst} }
func catCond(inst uint32) NodeID    { return NodeID{1, LevelBasic, RBasicCond, inst} }
func catBlock(inst uint32) NodeID   { return NodeID{1, LevelBasic, RBasicBlock, inst} }
func catMatch(inst uint32) NodeID   { return NodeID{1, LevelBasic, RBasicMatch, inst} }
func catChoice(inst uint32) NodeID  { return NodeID{1, LevelBasic, RBasicChoice, inst} }
func catIdent() NodeID              { return NodeID{1, LevelBasic, RBasicIdent, 1} }
func catFnDef() NodeID              { return NodeID{1, LevelBasic, RBasicFnDef, 1} }
func catFnCall() NodeID             { return NodeID{1, LevelBasic, RBasicFnCall, 1} }

// Native-attribution category constructors. Each names the Form-shape a
// native expresses; the walker records them in the trace when the native
// fires. Mirrors Rust kernel's cat_call / cat_witness / cat_access /
// cat_method / cat_list_nat / cat_undefined.
func catCall() NodeID      { return NodeID{1, LevelBasic, RBasicCall, 1} }
func catWitness() NodeID   { return NodeID{1, LevelBasic, RBasicWitness, 1} }
func catAccess() NodeID    { return NodeID{1, LevelBasic, RBasicAccess, 1} }
func catMethod() NodeID    { return NodeID{1, LevelBasic, RBasicMethod, 1} }
func catListNat() NodeID   { return NodeID{1, LevelBasic, RBasicList, 1} }
func catTransmute() NodeID { return NodeID{1, LevelBasic, RBasicTransmute, 1} }
func catFieldPrimitive(categoryType uint32) NodeID {
	return NodeID{1, LevelBasic, categoryType, 1}
}
func catField() NodeID     { return NodeID{1, LevelBasic, RBasicField, 1} }
func catDelta() NodeID     { return NodeID{1, LevelBasic, RBasicDelta, 1} }
func catReceipt() NodeID   { return NodeID{1, LevelBasic, RBasicReceipt, 1} }
func catResidual() NodeID  { return NodeID{1, LevelBasic, RBasicResidual, 1} }
func catUndefined() NodeID { return NodeID{1, LevelBasic, RBasicUndefined, 0} }

// ---------------------------------------------------------------------------
// Main — entry point
// ---------------------------------------------------------------------------

func readRootFromSource(k *Kernel, src string) NodeID {
	toks := tokenizeSexp(src)
	// Wrap multiple top-level forms in an implicit do-block. Counts
	// top-level expressions by paren depth — single expr passes through,
	// multiple get wrapped.
	wrapped := "(do " + src + ")"
	if len(toks) > 0 && toks[0].kind == "LPAREN" {
		depth := 0
		topLevelCount := 0
		for _, t := range toks {
			if t.kind == "LPAREN" {
				if depth == 0 {
					topLevelCount++
				}
				depth++
			} else if t.kind == "RPAREN" {
				depth--
			} else if depth == 0 {
				topLevelCount++
			}
		}
		if topLevelCount == 1 {
			wrapped = src
		}
	}
	toks = tokenizeSexp(wrapped)
	root, _ := k.readSexpr(toks, 0)
	return root
}

func kernelSourceExcerpt(src string, maxLen int) string {
	if len(src) <= maxLen {
		return src
	}
	return src[:maxLen]
}

func kernelSourceLineCount(src string) int {
	if src == "" {
		return 0
	}
	return strings.Count(src, "\n") + 1
}

func kernelModeFromArgs(args []string) string {
	if len(args) == 0 {
		return "startup"
	}
	switch args[0] {
	case "--expr":
		return "expr"
	case "--emit-binary":
		return "emit-binary"
	case "--binary":
		return "binary"
	case "--bench":
		return "bench"
	case "--numeric-bench":
		return "numeric-bench"
	case "trace":
		return "trace"
	case "serve":
		return "serve"
	default:
		return "source"
	}
}

func writeKernelCrashTrace(args []string, src string, recovered any) string {
	dir := filepath.Join(".cache", "form-kernel-go")
	if err := os.MkdirAll(dir, 0755); err != nil {
		dir = os.TempDir()
	}
	path := filepath.Join(
		dir,
		fmt.Sprintf("crash-%s-%d.json", time.Now().UTC().Format("20060102T150405Z"), os.Getpid()),
	)
	tailStart := len(src) - 2000
	if tailStart < 0 {
		tailStart = 0
	}
	report := map[string]any{
		"when_utc":          time.Now().UTC().Format(time.RFC3339Nano),
		"pid":               os.Getpid(),
		"mode":              kernelModeFromArgs(args),
		"args":              args,
		"panic":             fmt.Sprint(recovered),
		"source_bytes":      len(src),
		"source_line_count": kernelSourceLineCount(src),
		"source_head":       kernelSourceExcerpt(src, 2000),
		"source_tail":       src[tailStart:],
		"go_stack":          string(debug.Stack()),
	}
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return ""
	}
	if err := os.WriteFile(path, append(data, '\n'), 0644); err != nil {
		return ""
	}
	return path
}

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: form-kernel-go <file.fk> [more.fk ...] | --binary file.fkb | --emit-binary out.fkb file.fk... | --expr \"...\" | --bench | --numeric-bench | trace ... | serve --port 18080 <route-prelude.fk...>")
		os.Exit(2)
	}

	var src string

	// Catch parse-time and walk-time panics and convert them to clean error
	// output. The trace file keeps the host stack and source excerpt for
	// backtracking without making Form authors read a host runtime dump first.
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "form-kernel-go: %v\n", r)
			if tracePath := writeKernelCrashTrace(args, src, r); tracePath != "" {
				fmt.Fprintf(os.Stderr, "form-kernel-go: crash trace: %s\n", tracePath)
			}
			os.Exit(1)
		}
	}()

	if args[0] == "--bench" {
		runBench()
		return
	}

	if args[0] == "--numeric-bench" {
		runNumericBench()
		return
	}

	if args[0] == "trace" {
		os.Exit(cliTrace(args[1:]))
	}

	if args[0] == "serve" {
		os.Exit(cliServe(args[1:]))
	}

	if args[0] == "--binary" {
		if len(args) < 2 {
			fmt.Fprintln(os.Stderr, "--binary requires a path")
			os.Exit(2)
		}
		b, err := os.ReadFile(args[1])
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", args[1], err)
			os.Exit(1)
		}
		k := NewKernel()
		root, err := deserializeArtifact(k, b)
		if err != nil {
			fmt.Fprintf(os.Stderr, "form-kernel-go: %v\n", err)
			os.Exit(1)
		}
		k.activeRoots = []NodeID{root}
		env := NewFrame(nil)
		result := k.walk(root, env)
		k.substrateGC([]Value{{Kind: VNodeID, Nid: root}, result}, env)
		fmt.Println(result.String())
		return
	}

	if args[0] == "--emit-binary" {
		if len(args) < 3 {
			fmt.Fprintln(os.Stderr, "--emit-binary requires an output path and one or more .fk files")
			os.Exit(2)
		}
		var parts []string
		for _, path := range args[2:] {
			b, err := os.ReadFile(path)
			if err != nil {
				fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
				os.Exit(1)
			}
			parts = append(parts, string(b))
		}
		src = strings.Join(parts, "\n")
	} else if args[0] == "--expr" {
		if len(args) < 2 {
			fmt.Fprintln(os.Stderr, "--expr requires an argument")
			os.Exit(2)
		}
		src = args[1]
	} else {
		// Multiple files load sequentially into a shared top-level scope.
		// Concatenation works because the kernel wraps multi-form input in
		// an implicit do-block — definitions from earlier files become
		// visible to later ones.
		var parts []string
		for _, path := range args {
			b, err := os.ReadFile(path)
			if err != nil {
				fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
				os.Exit(1)
			}
			parts = append(parts, string(b))
		}
		src = strings.Join(parts, "\n")
	}

	k := NewKernel()
	root := readRootFromSource(k, src)
	if args[0] == "--emit-binary" {
		if err := os.WriteFile(args[1], serializeArtifact(k, root), 0644); err != nil {
			fmt.Fprintf(os.Stderr, "write %s: %v\n", args[1], err)
			os.Exit(1)
		}
		return
	}
	k.activeRoots = []NodeID{root}
	env := NewFrame(nil)
	result := k.walk(root, env)
	k.substrateGC([]Value{result}, env)
	fmt.Println(result.String())
}

// cliTrace — run with arm-dispatch tracing enabled. Emits a JSON report
// with the result, elapsed time, and the per-arm dispatch counts including
// native Blueprint attribution. Sibling-parity with the Rust kernel's
// trace subcommand.
func cliTrace(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: form-kernel-go trace [--expr \"...\" | <file.fk>]")
		return 2
	}
	var src string
	if args[0] == "--expr" {
		if len(args) < 2 {
			fmt.Fprintln(os.Stderr, "--expr requires an argument")
			return 2
		}
		src = args[1]
	} else {
		var parts []string
		for _, path := range args {
			b, err := os.ReadFile(path)
			if err != nil {
				fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
				return 1
			}
			parts = append(parts, string(b))
		}
		src = strings.Join(parts, "\n")
	}

	k := NewKernel()
	k.Trace = newTrace()
	toks := tokenizeSexp(src)
	wrapped := "(do " + src + ")"
	if len(toks) > 0 && toks[0].kind == "LPAREN" {
		depth := 0
		topLevelCount := 0
		for _, t := range toks {
			if t.kind == "LPAREN" {
				if depth == 0 {
					topLevelCount++
				}
				depth++
			} else if t.kind == "RPAREN" {
				depth--
			} else if depth == 0 {
				topLevelCount++
			}
		}
		if topLevelCount == 1 {
			wrapped = src
		}
	}
	toks = tokenizeSexp(wrapped)
	root, _ := k.readSexpr(toks, 0)
	k.activeRoots = []NodeID{root}
	env := NewFrame(nil)
	start := time.Now()
	result := k.walk(root, env)
	k.substrateGC([]Value{result}, env)
	elapsed := time.Since(start)

	report := map[string]interface{}{
		"result":             result.String(),
		"elapsed_us":         elapsed.Microseconds(),
		"elapsed_human":      elapsed.String(),
		"trace":              k.Trace.toJSON(),
		"framebuffer_counts": k.framebufferSourceCounts(),
		"framebuffer_events": k.framebufferEvents(),
	}
	out, _ := json.MarshalIndent(report, "", "  ")
	fmt.Println(string(out))
	return 0
}

// --- Native implementations — same recursive shape as the Form versions.
// `opaque` is an //go:noinline barrier; wrapping the recursive call's
// argument prevents Go from folding the whole computation when inputs
// are compile-time constants. Without it, pure functions get partially
// folded and the "native" column measures register loads, not work.

//go:noinline
func opaque(n int64) int64 { return n }

func nativeFib(n int64) int64 {
	if n <= 1 {
		return n
	}
	return nativeFib(opaque(n-1)) + nativeFib(opaque(n-2))
}

func nativeFact(n int64) int64 {
	if n <= 1 {
		return 1
	}
	return n * nativeFact(opaque(n-1))
}

func nativeSum(n, acc int64) int64 {
	if n == 0 {
		return acc
	}
	return nativeSum(opaque(n-1), opaque(acc+n))
}

func nativeAck(m, n int64) int64 {
	if m == 0 {
		return n + 1
	}
	if n == 0 {
		return nativeAck(opaque(m-1), 1)
	}
	return nativeAck(opaque(m-1), nativeAck(m, opaque(n-1)))
}

// runBench — three-column output: native compile, kernel walk, overhead.
func runBench() {
	cases := []struct {
		name        string
		src         string
		nativeIters int
		native      func() int64
	}{
		{"fib28",
			`(do (defn fib (n) (if (le n 1) n (add (fib (sub n 1)) (fib (sub n 2))))) (fib 28))`,
			100, func() int64 { return nativeFib(28) }},
		{"fact12",
			`(do (defn fact (n) (if (le n 1) 1 (mul n (fact (sub n 1))))) (fact 12))`,
			500000, func() int64 { return nativeFact(12) }},
		{"sum1000",
			`(do (defn sum (n acc) (if (eq n 0) acc (sum (sub n 1) (add acc n)))) (sum 1000 0))`,
			50000, func() int64 { return nativeSum(1000, 0) }},
		{"ackermann",
			`(do (defn ack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (ack (sub m 1) 1) (ack (sub m 1) (ack m (sub n 1)))))) (ack 3 6))`,
			100, func() int64 { return nativeAck(3, 6) }},
	}

	const kernelIters = 5

	fmt.Printf("%-12s %-12s %-14s %-14s %s\n", "workload", "result", "native", "kernel", "overhead")
	for _, c := range cases {
		// Native timing
		start := time.Now()
		var nativeResult int64
		for i := 0; i < c.nativeIters; i++ {
			nativeResult = c.native()
		}
		nativeDur := time.Since(start) / time.Duration(c.nativeIters)

		// Kernel timing — fresh kernel per case so intern table starts clean
		k := NewKernel()
		toks := tokenizeSexp(c.src)
		root, _ := k.readSexpr(toks, 0)
		env := NewFrame(nil)
		start = time.Now()
		var kernelResult Value
		for i := 0; i < kernelIters; i++ {
			kernelResult = k.walk(root, env)
		}
		kernelDur := time.Since(start) / kernelIters

		overhead := float64(kernelDur) / float64(nativeDur)
		fmt.Printf("%-12s %-12s %-14s %-14s %.0f×\n",
			c.name,
			kernelResult.String(),
			nativeDur,
			kernelDur,
			overhead,
		)
		_ = nativeResult // silence unused-write warning for the loop's last value
	}
}

// ---------------------------------------------------------------------------
// Form binary artifact format helpers
// ---------------------------------------------------------------------------
// Per-node serialization is tagged. Leaves store their local 4-tuple value.
// Composites store the full category node followed by children. That keeps
// temporary, unregistered blueprint/recipe categories scoped to the artifact
// shape instead of treating their context-local NodeID numbers as global.
// Sibling of the Rust/TS binary artifact helpers. Same byte layout.
const (
	formBinaryLeaf      uint32 = 0
	formBinaryComposite uint32 = 1
	// FLOAT64 carries its VALUE, not its index. A float64 trivial NodeID's
	// Inst is a per-kernel f64s-table index — meaningless in another kernel.
	// So a float node serializes as [formBinaryFloat64][8 bytes IEEE-754
	// little-endian] and each kernel re-interns the value on read (fresh
	// local index). The trivial float type tag (FLOAT64 = 7 three-way) never
	// rides the wire either: the value travels in bytes, not the index nor
	// the local type-tag, so the .fkb stays portable regardless of how each
	// kernel numbers its trivial types.
	formBinaryFloat64 uint32 = 2
	// INT64 carries its VALUE, not its index — the same reasoning as FLOAT64.
	// A TrivInt64 NodeID's Inst is a per-kernel i64s-table index, meaningless
	// in another kernel, so an int64 node serializes as [formBinaryInt64][8
	// bytes signed little-endian] and each kernel re-interns on read.
	formBinaryInt64 uint32 = 3
)

func pushU32(bytes []byte, v uint32) []byte {
	return append(bytes, byte(v>>24), byte(v>>16), byte(v>>8), byte(v))
}

func readU32(bytes []byte, pos int) (uint32, int) {
	v := (uint32(bytes[pos]) << 24) |
		(uint32(bytes[pos+1]) << 16) |
		(uint32(bytes[pos+2]) << 8) |
		uint32(bytes[pos+3])
	return v, pos + 4
}

// pushF64LE — append an IEEE-754 f64 as 8 little-endian bytes (the payload of
// a formBinaryFloat64 node). Sibling parity with Rust/TS little-endian writers.
func pushF64LE(bytes []byte, f float64) []byte {
	bits := math.Float64bits(f)
	return append(bytes,
		byte(bits), byte(bits>>8), byte(bits>>16), byte(bits>>24),
		byte(bits>>32), byte(bits>>40), byte(bits>>48), byte(bits>>56))
}

func readF64LE(bytes []byte, pos int) (float64, int) {
	bits := uint64(bytes[pos]) |
		uint64(bytes[pos+1])<<8 |
		uint64(bytes[pos+2])<<16 |
		uint64(bytes[pos+3])<<24 |
		uint64(bytes[pos+4])<<32 |
		uint64(bytes[pos+5])<<40 |
		uint64(bytes[pos+6])<<48 |
		uint64(bytes[pos+7])<<56
	return math.Float64frombits(bits), pos + 8
}

// pushI64LE / readI64LE — a signed int64 as 8 little-endian bytes (the payload
// of a formBinaryInt64 node). Sibling parity with Rust/TS little-endian writers.
func pushI64LE(bytes []byte, n int64) []byte {
	u := uint64(n)
	return append(bytes,
		byte(u), byte(u>>8), byte(u>>16), byte(u>>24),
		byte(u>>32), byte(u>>40), byte(u>>48), byte(u>>56))
}

func readI64LE(bytes []byte, pos int) (int64, int) {
	u := uint64(bytes[pos]) |
		uint64(bytes[pos+1])<<8 |
		uint64(bytes[pos+2])<<16 |
		uint64(bytes[pos+3])<<24 |
		uint64(bytes[pos+4])<<32 |
		uint64(bytes[pos+5])<<40 |
		uint64(bytes[pos+6])<<48 |
		uint64(bytes[pos+7])<<56
	return int64(u), pos + 8
}

func serializeNid(k *Kernel, nid NodeID, bytes []byte) []byte {
	if r, ok := k.byID[nid]; ok {
		bytes = pushU32(bytes, formBinaryComposite)
		bytes = serializeNid(k, r.Category, bytes)
		bytes = pushU32(bytes, uint32(len(r.Children)))
		for _, c := range r.Children {
			bytes = serializeNid(k, c, bytes)
		}
		return bytes
	}
	if nid.Level == LevelTrivial && nid.Type == TrivFloat64 {
		bytes = pushU32(bytes, formBinaryFloat64)
		bytes = pushF64LE(bytes, k.decodeFloat64(nid.Inst))
		return bytes
	}
	if nid.Level == LevelTrivial && nid.Type == TrivInt64 {
		bytes = pushU32(bytes, formBinaryInt64)
		bytes = pushI64LE(bytes, k.decodeInt64(nid.Inst))
		return bytes
	}
	bytes = pushU32(bytes, formBinaryLeaf)
	bytes = pushU32(bytes, nid.Pkg)
	bytes = pushU32(bytes, nid.Level)
	bytes = pushU32(bytes, nid.Type)
	bytes = pushU32(bytes, nid.Inst)
	return bytes
}

func deserializeNid(k *Kernel, bytes []byte, pos int, scope uint32) (NodeID, int) {
	tag, pos := readU32(bytes, pos)
	if tag == formBinaryFloat64 {
		var value float64
		value, pos = readF64LE(bytes, pos)
		return k.internTrivialFloat64(value), pos
	}
	if tag == formBinaryInt64 {
		var value int64
		value, pos = readI64LE(bytes, pos)
		return k.internTrivialInt(value), pos
	}
	if tag == formBinaryLeaf {
		var pkg, level, ty, inst uint32
		pkg, pos = readU32(bytes, pos)
		level, pos = readU32(bytes, pos)
		ty, pos = readU32(bytes, pos)
		inst, pos = readU32(bytes, pos)
		return k.remapImportedLeaf(scope, NodeID{Pkg: pkg, Level: level, Type: ty, Inst: inst}), pos
	}
	category, pos := deserializeNid(k, bytes, pos, scope)
	count, pos := readU32(bytes, pos)
	children := make([]NodeID, count)
	for i := uint32(0); i < count; i++ {
		var c NodeID
		c, pos = deserializeNid(k, bytes, pos, scope)
		children[i] = c
	}
	return k.intern(category, children), pos
}

func deserializeNidWithStringsV1(k *Kernel, bytes []byte, pos int, stringsTable []string, scope uint32) (NodeID, int) {
	var pkg, level, ty, inst, count uint32
	pkg, pos = readU32(bytes, pos)
	level, pos = readU32(bytes, pos)
	ty, pos = readU32(bytes, pos)
	inst, pos = readU32(bytes, pos)
	count, pos = readU32(bytes, pos)
	if count == 0 {
		if level == LevelTrivial && ty == TrivString {
			if int(inst) >= len(stringsTable) {
				panic(fmt.Sprintf("form binary: bad string index %d", inst))
			}
			return k.internString(stringsTable[inst]), pos
		}
		return k.remapImportedLeaf(scope, NodeID{Pkg: pkg, Level: level, Type: ty, Inst: inst}), pos
	}
	category := NodeID{Pkg: pkg, Level: level, Type: ty, Inst: inst}
	if level == LevelTrivial && ty == TrivString {
		if int(inst) >= len(stringsTable) {
			panic(fmt.Sprintf("form binary: bad string index %d", inst))
		}
		category = k.internString(stringsTable[inst])
	}
	children := make([]NodeID, count)
	for i := uint32(0); i < count; i++ {
		var c NodeID
		c, pos = deserializeNidWithStringsV1(k, bytes, pos, stringsTable, scope)
		children[i] = c
	}
	return k.intern(category, children), pos
}

var formBinaryMagicV1 = []byte("FORMBIN1")
var formBinaryMagic = []byte("FORMBIN2")

func serializeArtifact(k *Kernel, root NodeID) []byte {
	bytes := append([]byte{}, formBinaryMagic...)
	bytes = pushU32(bytes, uint32(len(k.strs)))
	for _, s := range k.strs {
		raw := []byte(s)
		bytes = pushU32(bytes, uint32(len(raw)))
		bytes = append(bytes, raw...)
	}
	return serializeNid(k, root, bytes)
}

func deserializeArtifact(k *Kernel, bytes []byte) (NodeID, error) {
	v1 := len(bytes) >= len(formBinaryMagicV1) && string(bytes[:len(formBinaryMagicV1)]) == string(formBinaryMagicV1)
	v2 := len(bytes) >= len(formBinaryMagic) && string(bytes[:len(formBinaryMagic)]) == string(formBinaryMagic)
	if !v1 && !v2 {
		return NodeID{}, fmt.Errorf("form binary: bad magic")
	}
	pos := len(formBinaryMagic)
	if v1 {
		pos = len(formBinaryMagicV1)
	}
	stringCount, pos := readU32(bytes, pos)
	stringsTable := make([]string, stringCount)
	for i := uint32(0); i < stringCount; i++ {
		var n uint32
		n, pos = readU32(bytes, pos)
		end := pos + int(n)
		if end > len(bytes) {
			return NodeID{}, fmt.Errorf("form binary: truncated string")
		}
		stringsTable[i] = string(bytes[pos:end])
		pos = end
	}
	var root NodeID
	var end int
	if v1 {
		scope := k.nextImportScope()
		root, end = deserializeNidWithStringsV1(k, bytes, pos, stringsTable, scope)
	} else {
		scope := k.nextImportScope()
		root, end = deserializeNidWithStrings(k, bytes, pos, stringsTable, scope)
	}
	if end != len(bytes) {
		return NodeID{}, fmt.Errorf("form binary: trailing bytes")
	}
	return root, nil
}

func deserializeNidWithStrings(k *Kernel, bytes []byte, pos int, stringsTable []string, scope uint32) (NodeID, int) {
	tag, pos := readU32(bytes, pos)
	if tag == formBinaryFloat64 {
		if pos+8 > len(bytes) {
			panic("form binary: truncated float64")
		}
		var value float64
		value, pos = readF64LE(bytes, pos)
		return k.internTrivialFloat64(value), pos
	}
	if tag == formBinaryInt64 {
		if pos+8 > len(bytes) {
			panic("form binary: truncated int64")
		}
		var value int64
		value, pos = readI64LE(bytes, pos)
		return k.internTrivialInt(value), pos
	}
	if tag == formBinaryLeaf {
		var pkg, level, ty, inst uint32
		pkg, pos = readU32(bytes, pos)
		level, pos = readU32(bytes, pos)
		ty, pos = readU32(bytes, pos)
		inst, pos = readU32(bytes, pos)
		if level == LevelTrivial && ty == TrivString {
			if int(inst) >= len(stringsTable) {
				panic(fmt.Sprintf("form binary: bad string index %d", inst))
			}
			return k.internString(stringsTable[inst]), pos
		}
		return k.remapImportedLeaf(scope, NodeID{Pkg: pkg, Level: level, Type: ty, Inst: inst}), pos
	}
	category, pos := deserializeNidWithStrings(k, bytes, pos, stringsTable, scope)
	count, pos := readU32(bytes, pos)
	children := make([]NodeID, count)
	for i := uint32(0); i < count; i++ {
		var c NodeID
		c, pos = deserializeNidWithStrings(k, bytes, pos, stringsTable, scope)
		children[i] = c
	}
	return k.intern(category, children), pos
}
