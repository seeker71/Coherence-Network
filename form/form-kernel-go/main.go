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
	"hash/fnv"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// NodeID — the 4-tuple identity. Registered substrate ids use pkg=1.
// Runtime-interned composites use pkg=0 so temporary recipe ids cannot collide
// with registered/basic categories across an execution context boundary.
// Trivials encode their value in `Inst`.
type NodeID struct{ Pkg, Level, Type, Inst uint32 }

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
	RBasicMethod    uint32 = 27 // transform on a cell-like value
	RBasicTransmute uint32 = 76 // present value through Blueprint without changing identity
	// Kernel-demo additions (extending RBasic for self-hosting needs)
	RBasicFnDef  uint32 = 31
	RBasicFnCall uint32 = 32
	RBasicIdent  uint32 = 33
	RBasicList   uint32 = 34 // list-literal recipe

	TrivInt    uint32 = 1
	TrivString uint32 = 2
	TrivBool   uint32 = 3
	TrivNull   uint32 = 4
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
type NameID uint32

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
	case RBasicIdent:
		return "IDENT"
	case RBasicFnDef:
		return "FNDEF"
	case RBasicFnCall:
		return "FNCALL"
	case RBasicList:
		return "LIST"
	case RBasicWitness:
		return "WITNESS"
	case RBasicCall:
		return "CALL"
	case RBasicAccess:
		return "ACCESS"
	case RBasicMethod:
		return "METHOD"
	case RBasicTransmute:
		return "TRANSMUTE"
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
	}
}

// Kernel — the running substrate.
type Kernel struct {
	byHash  map[uint64]NodeID
	byID    map[NodeID]Recipe
	strs    []string
	strIdx  map[string]NameID
	next    uint32
	natives map[NameID]NativeEntry
	// SourceAttr — NodeID → (file_name_id, line, col). Populated by
	// intern_node_at; read by node_source. The satsang-load-bearing
	// surface: every cell's state traceable to the source line that
	// authored it. The practice of self-knowing.
	sourceAttr map[NodeID]sourceLoc
	importSeq  uint32
	// walkCache — JIT-vector memoization for pure recipes. Keyed by
	// recipe NodeID. Real JIT replaces this with compiled native code;
	// the architectural slot is the same: same NodeID = same result.
	walkCache       map[NodeID]Value
	walkCacheHits   uint64
	walkCacheMisses uint64
	activeRoots     []NodeID
	// Optional tracing — nil for hot-path runs, set for trace subcommand.
	// Per lc-native-kernel-binary's "tracing and observation pattern."
	Trace *Trace
}

type sourceLoc struct {
	FileID NameID
	Line   uint32
	Col    uint32
}

func NewKernel() *Kernel {
	k := &Kernel{
		byHash:     make(map[uint64]NodeID),
		byID:       make(map[NodeID]Recipe),
		strIdx:     make(map[string]NameID),
		sourceAttr: make(map[NodeID]sourceLoc),
		importSeq:  1,
		walkCache:  make(map[NodeID]Value),
		next:       1,
		natives:    make(map[NameID]NativeEntry),
	}
	k.registerNatives()
	return k
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
	return NodeID{Pkg: 1, Level: LevelTrivial, Type: TrivInt, Inst: uint32(int32(n))}
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
	for cur := frame; cur != nil; cur = cur.parent {
		if liveFrames[cur] {
			return
		}
		liveFrames[cur] = true
		for _, binding := range cur.bindings {
			liveStrings[binding.name] = true
			k.markValue(binding.val, liveNodes, liveStrings, liveFrames)
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
	case RBasicMath, RBasicCompare, RBasicLogic, RBasicCond, RBasicList:
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
	case TrivString:
		return Value{Kind: VStr, Str: k.strs[n.Inst]}
	case TrivBool:
		return Value{Kind: VBool, Bool: n.Inst != 0}
	case TrivNull:
		return Value{Kind: VNull}
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

type ValueKind int

const (
	VNull ValueKind = iota
	VInt
	VStr
	VBool
	VList
	VClosure
	// VNodeID — Form code holds substrate NodeIDs as values once the
	// substrate-write natives expose them. Adding this variant is the
	// foundational step that lets Form construct recipes, not just walk
	// them. Without it, templates (Breath 2) literally cannot exist.
	VNodeID
)

// Value — runtime tagged union. List and Closure carry pointers; the rest
// are inline. Kept as a flat struct so the walker's hot path is allocation-
// free for ints and bools.
type Value struct {
	Kind ValueKind
	Int  int64
	Str  string
	Bool bool
	List []Value
	Cl   *Closure
	Nid  NodeID
}

func (v Value) String() string {
	switch v.Kind {
	case VNull:
		return "null"
	case VInt:
		return strconv.FormatInt(v.Int, 10)
	case VStr:
		return v.Str
	case VBool:
		if v.Bool {
			return "true"
		}
		return "false"
	case VList:
		parts := make([]string, len(v.List))
		for i, x := range v.List {
			parts[i] = x.String()
		}
		return "[" + strings.Join(parts, ", ") + "]"
	case VClosure:
		return "<closure #" + strconv.FormatUint(uint64(v.Cl.Name), 10) + ">"
	case VNodeID:
		// Canonical substrate notation: @pkg.level.type.instance
		return fmt.Sprintf("@%d.%d.%d.%d", v.Nid.Pkg, v.Nid.Level, v.Nid.Type, v.Nid.Inst)
	}
	return "?"
}

type Closure struct {
	Name   NameID // display only — runtime lookup uses Params/Body/Env
	Params []NameID
	Body   NodeID
	Env    *Frame
}

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

// Frame — scope primitive. Bindings as a small ordered slice; the common
// case (function call with 1-3 args) beats a hash map at this size and
// keeps the data layout cache-friendly. Linear scan is the right shape
// for n < ~16.
type Frame struct {
	parent   *Frame
	bindings []binding
}

type binding struct {
	name NameID
	val  Value
}

func NewFrame(parent *Frame) *Frame { return &Frame{parent: parent} }

// NewCallFrame — pre-sized for a function call with `arity` params.
// Avoids append-grow during parameter binding in the hot recursion path.
func NewCallFrame(parent *Frame, arity int) *Frame {
	return &Frame{parent: parent, bindings: make([]binding, 0, arity)}
}

func (f *Frame) Bind(name NameID, v Value) {
	for i := range f.bindings {
		if f.bindings[i].name == name {
			f.bindings[i].val = v
			return
		}
	}
	f.bindings = append(f.bindings, binding{name, v})
}

func (f *Frame) Lookup(name NameID) (Value, bool) {
	for cur := f; cur != nil; cur = cur.parent {
		for i := range cur.bindings {
			if cur.bindings[i].name == name {
				return cur.bindings[i].val, true
			}
		}
	}
	return Value{}, false
}

// ---------------------------------------------------------------------------
// Native functions — what Form-on-top reaches for at the leaves
// ---------------------------------------------------------------------------

type NativeFn func(k *Kernel, args []Value) Value

// registerNative — central registration point. The string name is
// interned once into a NameID; runtime dispatch is u32-keyed. Each
// native carries the Form category it expresses (Blueprint attribution).
func (k *Kernel) registerNative(name string, category NodeID, fn NativeFn) {
	id := k.internName(name)
	k.natives[id] = NativeEntry{Name: id, Category: category, Fn: fn}
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
		return Value{Kind: VStr, Str: args[0].Str[args[1].Int:args[2].Int]}
	})
	k.registerNative("char_at", catAccess(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: string(args[0].Str[args[1].Int])}
	})
	k.registerNative("str_concat", catMethod(), func(_ *Kernel, args []Value) Value {
		return Value{Kind: VStr, Str: args[0].Str + args[1].Str}
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
		}
		return Value{Kind: VStr, Str: strconv.FormatInt(v.Int, 10)}
	})
	k.registerNative("str_to_int", catMethod(), func(_ *Kernel, args []Value) Value {
		n, _ := strconv.ParseInt(args[0].Str, 10, 64)
		return Value{Kind: VInt, Int: n}
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
			return Value{Kind: VInt, Int: int64(len(args[0].List))}
		case VStr:
			return Value{Kind: VInt, Int: int64(len(args[0].Str))}
		}
		return Value{Kind: VInt, Int: 0}
	})
	// `nth` composted 2026-05-22 — sibling-parity with Rust kernel.
	// Re-author in core.fk as needed: (defn nth (xs n) (if (eq n 0) (head xs) (nth (tail xs) (sub n 1))))
	k.registerNative("empty", catListNat(), func(_ *Kernel, _ []Value) Value {
		return Value{Kind: VList, List: []Value{}}
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
		n := args[0].Int
		if n < 0 {
			n = -n
		}
		return Value{Kind: VInt, Int: n}
	})
	// Polymorphic `+` for Python: int+int=add, str+str=concat,
	// list+list=concat. Sibling-parity with Rust + TS kernels.
	k.registerNative("_plus", catMethod(), func(_ *Kernel, args []Value) Value {
		a, b := args[0], args[1]
		if a.Kind == VInt && b.Kind == VInt {
			return Value{Kind: VInt, Int: a.Int + b.Int}
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
	// File I/O
	k.registerNative("read_file", catCall(), func(_ *Kernel, args []Value) Value {
		b, err := os.ReadFile(args[0].Str)
		if err != nil {
			return Value{Kind: VNull}
		}
		return Value{Kind: VStr, Str: string(b)}
	})
	// Byte-level host file read — returns a list of ints (0-255), one per byte.
	k.registerNative("read_file_bytes", catCall(), func(_ *Kernel, args []Value) Value {
		b, err := os.ReadFile(args[0].Str)
		if err != nil {
			return Value{Kind: VNull}
		}
		out := make([]Value, len(b))
		for i, by := range b {
			out[i] = Value{Kind: VInt, Int: int64(by)}
		}
		return Value{Kind: VList, List: out}
	})
	k.registerNative("file_size", catCall(), func(_ *Kernel, args []Value) Value {
		info, err := os.Stat(args[0].Str)
		if err != nil {
			return Value{Kind: VInt, Int: -1}
		}
		return Value{Kind: VInt, Int: info.Size()}
	})
	k.registerNative("file_byte_at", catCall(), func(_ *Kernel, args []Value) Value {
		if args[1].Int < 0 {
			return Value{Kind: VInt, Int: -1}
		}
		f, err := os.Open(args[0].Str)
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
		f, err := os.Open(args[0].Str)
		if err != nil {
			return Value{Kind: VStr, Str: ""}
		}
		defer f.Close()
		buf := make([]byte, length)
		n, _ := f.ReadAt(buf, offset)
		return Value{Kind: VStr, Str: string(buf[:n])}
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
	k.registerNative("intern_trivial_int", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internTrivialInt(args[0].Int)}
	})
	k.registerNative("intern_trivial_string", catWitness(), func(k *Kernel, args []Value) Value {
		return Value{Kind: VNodeID, Nid: k.internString(args[0].Str)}
	})
	k.registerNative("intern_node", catWitness(), func(k *Kernel, args []Value) Value {
		cat := args[0].Nid
		kids := make([]NodeID, len(args[1].List))
		for i, c := range args[1].List {
			kids[i] = c.Nid
		}
		return Value{Kind: VNodeID, Nid: k.intern(cat, kids)}
	})
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
	// node_eq — compare two NodeIDs structurally. Sibling to Rust's node_eq.
	// Form code (emit-engine.fk lookup-template) uses this for category
	// dispatch — the kernel's `eq` (RCMP_EQ) coerces operands via as_int,
	// which panics on NodeIDs; node_eq closes that gap.
	k.registerNative("node_eq", catCompare(RCompareEq), func(k *Kernel, args []Value) Value {
		return Value{Kind: VBool, Bool: args[0].Nid == args[1].Nid}
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
		out := make([]Value, 0, len(k.sourceAttr))
		for nid := range k.sourceAttr {
			out = append(out, Value{Kind: VNodeID, Nid: nid})
		}
		return Value{Kind: VList, List: out}
	})
	// framebuffer-clear — reset the framebuffer for bounded windows.
	k.registerNative("framebuffer-clear", catWitness(), func(k *Kernel, _ []Value) Value {
		k.sourceAttr = make(map[NodeID]sourceLoc)
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
	k.registerNative("walk_recipe", catWitness(), func(k *Kernel, args []Value) Value {
		env := NewFrame(nil)
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
			for i, root := range roots {
				if cache {
					if cached, ok := k.walkCache[root]; ok {
						k.walkCacheHits++
						out[i] = cached
						continue
					}
					k.walkCacheMisses++
				}
				out[i] = k.walk(root, NewFrame(nil))
				if cache {
					k.walkCache[root] = out[i]
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
		for i, root := range roots {
			if cached, ok := k.walkCache[root]; ok {
				k.walkCacheHits++
				out[i] = cached
			} else {
				k.walkCacheMisses++
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

	switch cat.Type {
	case RBasicMath:
		a := k.walk(kids[0], env).Int
		b := k.walk(kids[1], env).Int
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
		a := k.walk(kids[0], env).Int
		b := k.walk(kids[1], env).Int
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
			return k.walk(kids[1], env)
		}
		if cat.Inst == RCondIfThenElse && len(kids) >= 3 {
			return k.walk(kids[2], env)
		}
		return Value{Kind: VNull}

	case RBasicBlock:
		if cat.Inst == RBlockLet {
			name := k.identID(kids[0])
			v := k.walk(kids[1], env)
			env.Bind(name, v)
			return v
		}
		var last Value
		for _, c := range kids {
			last = k.walk(c, env)
		}
		return last

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
		name := k.identID(kids[0])
		// Native takes priority unless user shadowed with a closure
		if ne, ok := k.natives[name]; ok {
			if _, hasUserBinding := env.Lookup(name); !hasUserBinding {
				args := make([]Value, len(kids)-1)
				for i := 1; i < len(kids); i++ {
					args[i-1] = k.walk(kids[i], env)
				}
				// Native Blueprint attribution — record the Form category
				// the native expresses alongside the FNCALL arm already
				// recorded above. The kernel knows itself even when the
				// call leaves Form-land.
				if k.Trace != nil && ne.Category.Type != RBasicUndefined {
					k.Trace.record(ne.Category.Type, ne.Category.Inst)
				}
				if k.Trace != nil {
					k.Trace.recordNative(k.nameStr(ne.Name))
				}
				return ne.Fn(k, args)
			}
		}
		v, ok := env.Lookup(name)
		if !ok {
			panic(fmt.Sprintf("walk: unbound function %q", k.nameStr(name)))
		}
		if v.Kind != VClosure {
			panic(fmt.Sprintf("walk: %q is not callable", k.nameStr(name)))
		}
		cl := v.Cl
		if len(kids)-1 != len(cl.Params) {
			panic(fmt.Sprintf("walk: %q wants %d args, got %d", k.nameStr(name), len(cl.Params), len(kids)-1))
		}
		call := NewCallFrame(cl.Env, len(cl.Params))
		for i, p := range cl.Params {
			call.Bind(p, k.walk(kids[i+1], env))
		}
		if k.Trace != nil {
			k.Trace.recordFn(k.nameStr(cl.Name))
		}
		return k.walk(cl.Body, call)

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
			tokens = append(tokens, sexpToken{"INT", src[start:i], startLine, startCol})
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

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: form-kernel-go <file.fk> [more.fk ...] | --binary file.fkb | --emit-binary out.fkb file.fk... | --expr \"...\" | --bench | --numeric-bench | trace ...")
		os.Exit(2)
	}

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

	var src string
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

	// Catch parse-time panics and convert to clean error output. Without
	// this, Go's default runtime panic also dumps the kernel's internal
	// stack — useful for kernel devs, noise for Form authors.
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "form-kernel-go: %v\n", r)
			os.Exit(1)
		}
	}()

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
		b, err := os.ReadFile(args[0])
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", args[0], err)
			return 1
		}
		src = string(b)
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
		"result":        result.String(),
		"elapsed_us":    elapsed.Microseconds(),
		"elapsed_human": elapsed.String(),
		"trace":         k.Trace.toJSON(),
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
	bytes = pushU32(bytes, formBinaryLeaf)
	bytes = pushU32(bytes, nid.Pkg)
	bytes = pushU32(bytes, nid.Level)
	bytes = pushU32(bytes, nid.Type)
	bytes = pushU32(bytes, nid.Inst)
	return bytes
}

func deserializeNid(k *Kernel, bytes []byte, pos int, scope uint32) (NodeID, int) {
	tag, pos := readU32(bytes, pos)
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
