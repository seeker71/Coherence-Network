// inductive.go — INDUCTIVE / CONSTRUCTOR / CHOICE arms: algebraic datatypes
// as substrate cells. Mirrors:
//
//   form/form-kernel-ts/src/inductive.ts   (TS reference)
//   api/app/services/substrate/inductive.py       (Python port)
//
// An inductive type is a substrate recipe whose category is RBasicInductive
// (slot 71). Its shape — defined here once, read everywhere by
// content-addressing — is:
//
//   INDUCTIVE[
//     type-name        : Triv.STRING        ; "Nat", "List", ...
//     type-params      : RBasicList         ; parametric types (T, E, ...)
//     ctor0..ctorN     : RBasicConstructor  ; the type's constructors
//   ]
//
// A constructor recipe is RBasicConstructor (slot 72) with children:
//
//   CONSTRUCTOR[
//     inductive-ref    : NodeID  ; the inductive type this ctor belongs to
//     ctor-name        : Triv.STRING
//     ctor-index       : Triv.INT
//     arg0..argN       : NodeID  ; type-recipes (definition) OR
//                              ; value-recipes (application)
//   ]
//
// Constructor *application* — value-shape — reuses the same RBasicConstructor
// recipe shape but with concrete value-recipes in place of arg-types.
// WalkConstructor materializes a CtorValue from one.
//
// A pattern-match is an RBasicChoiceMatch recipe (slot 35):
//
//   CHOICE_MATCH[
//     scrutinee        : NodeID,
//     arm0-ctor-name   : Triv.STRING,
//     arm0-body        : NodeID,
//     arm1-ctor-name   : Triv.STRING,
//     arm1-body        : NodeID,
//     ...
//   ]
//
// WalkChoice verifies every constructor declared on the scrutinee's
// inductive appears among the arms — non-total matches raise.
//
// Because the recipes are content-addressed, two inductives defined with
// identical (name, params, ctor-list) intern to the SAME NodeID. That's
// what the substrate's promise of structural equivalence buys us here.
//
// Cross-kernel: TS / Python / Go / Rust at slots 71 / 72 / 35 with builtin
// constructor names {zero, succ, nil, cons, none, some, ok, err, true,
// false} and inductive names {Nat, Bool, Option, Result, List}. A Form
// program that defines Nat in any kernel produces matching NodeIDs for
// Nat, zero, succ — content-addressing across kernels.
//
// Note on Value representation: rather than extend main.go's Value enum,
// the inductive arm uses its own CtorValue struct as the runtime carrier
// for constructor values. CtorValue.Args carries a heterogeneous slice
// (CtorValue for nested ctors, NodeID for trivials and other recipes).
// MatchValue / WalkChoice operate over this representation; main.go's
// kernel remains unmodified.

package main

import (
	"fmt"
)

// ---------------------------------------------------------------------------
// RBasic slot constants — part of the cross-kernel contract. Same numbers
// in TS (kernel.ts), Python (category.py), and Rust. Do NOT renumber.
// ---------------------------------------------------------------------------

const (
	// RBasicChoiceMatch — pattern-match arm with totality checking.
	// Slot 35 mirrors TS RBasic.CHOICE and Python BCategoryT.CHOICE_MATCH.
	RBasicChoiceMatch uint32 = 35

	// RBasicInductive — algebraic datatype definition. Slot 71.
	RBasicInductive uint32 = 71

	// RBasicConstructor — constructor (type-definition or value-application).
	// Slot 72.
	RBasicConstructor uint32 = 72

	// TrivConstructorTag — small-int tag used by the walker for ctor values.
	// Reserved at trivial-level slot 15 across all kernels.
	TrivConstructorTag uint32 = 15
)

// ---------------------------------------------------------------------------
// Structural descriptions handed to the kernel at intern time
// ---------------------------------------------------------------------------

// ConstructorDef — a constructor declaration on an inductive type.
type ConstructorDef struct {
	CtorName  string
	CtorIndex int
	// ArgTypes are NodeIDs of type-recipes. Self-reference uses the parent
	// inductive's type-name trivial as the sentinel (see MakeInductive).
	ArgTypes []NodeID
}

// InductiveType — in-memory handle for an inductive type. The recipe
// interned into the substrate is the source of truth; this struct is the
// caller's convenience.
type InductiveType struct {
	TypeName     string
	TypeParams   []NodeID
	Constructors []*ConstructorDef
	NodeID       NodeID
}

// IndValue — runtime value flowing through CHOICE arms. Either:
//   - a CtorValue (constructor application result), or
//   - a raw NodeID (trivial literal or other recipe value).
//
// Using an interface keeps the type-space tight: no boxing for trivials,
// no enum tag for the Go switch — the dispatch is type-assertion.
type IndValue interface {
	indValue()
}

// CtorValue — runtime tagged value: the result of walking a CONSTRUCTOR
// value-recipe. Inductive identifies the type; Args are the constructor's
// argument IndValues (already walked).
type CtorValue struct {
	Inductive NodeID
	CtorName  string
	CtorIndex int
	Args      []IndValue
}

func (*CtorValue) indValue() {}

// NodeValue — a thin wrapper around NodeID so it satisfies IndValue.
// Trivial literals and other recipe values flow through CHOICE / MatchValue
// as NodeValue rather than being boxed into a tagged Value.
type NodeValue struct{ Nid NodeID }

func (NodeValue) indValue() {}

// AsNode — extract the NodeID from a NodeValue. Returns ({},false) if `v`
// is a CtorValue or anything else.
func AsNode(v IndValue) (NodeID, bool) {
	if nv, ok := v.(NodeValue); ok {
		return nv.Nid, true
	}
	return NodeID{}, false
}

// AsCtor — extract the *CtorValue from a CtorValue. Returns (nil,false)
// if `v` is a NodeValue.
func AsCtor(v IndValue) (*CtorValue, bool) {
	if cv, ok := v.(*CtorValue); ok {
		return cv, true
	}
	return nil, false
}

// AsInt — read an int from a NodeValue wrapping a TrivInt NodeID.
// Returns (0,false) if `v` isn't a trivial int.
func AsInt(v IndValue) (int64, bool) {
	nv, ok := v.(NodeValue)
	if !ok {
		return 0, false
	}
	n := nv.Nid
	if n.Level != LevelTrivial || n.Type != TrivInt {
		return 0, false
	}
	return int64(int32(n.Inst)), true
}

// ArmHandler — callback for an arm in MatchValue. Receives the constructor's
// IndValue arguments; returns the arm's result (interface{} so any Go value
// flows).
type ArmHandler func(args []IndValue) interface{}

// ---------------------------------------------------------------------------
// Category-NodeID helpers
// ---------------------------------------------------------------------------

func catInductive() NodeID {
	return NodeID{Pkg: 1, Level: LevelBasic, Type: RBasicInductive, Inst: 1}
}

func catConstructor() NodeID {
	return NodeID{Pkg: 1, Level: LevelBasic, Type: RBasicConstructor, Inst: 1}
}

func catChoiceMatch() NodeID {
	return NodeID{Pkg: 1, Level: LevelBasic, Type: RBasicChoiceMatch, Inst: 1}
}

// catParamsList — params-list recipe category. Reuses main.go's RBasicList.
func catParamsList() NodeID {
	return NodeID{Pkg: 1, Level: LevelBasic, Type: RBasicList, Inst: 1}
}

// ---------------------------------------------------------------------------
// MakeInductive / MakeConstructor — intern recipes
// ---------------------------------------------------------------------------

// MakeInductive — intern an INDUCTIVE recipe. Returns the NodeID of the
// inductive type itself.
//
// Two-phase encoding: at definition time the constructor's `inductive-ref`
// slot is the type-name trivial (a self-ref sentinel — the inductive's
// NodeID isn't known until it's interned). At constructor *application*
// time MakeConstructor plugs in the real inductive NodeID.
//
// Because recipes are content-addressed, two inductives with identical
// (name, params, ctor-list) hash to the same NodeID.
func MakeInductive(
	k *Kernel,
	name string,
	params []NodeID,
	ctors []*ConstructorDef,
) NodeID {
	typeName := k.internString(name)
	paramsList := k.intern(catParamsList(), params)

	ctorDefs := make([]NodeID, 0, len(ctors))
	for _, c := range ctors {
		nameNid := k.internString(c.CtorName)
		indexNid := k.internTrivialInt(int64(c.CtorIndex))
		children := make([]NodeID, 0, 3+len(c.ArgTypes))
		children = append(children, typeName, nameNid, indexNid)
		children = append(children, c.ArgTypes...)
		ctorDefs = append(ctorDefs, k.intern(catConstructor(), children))
	}

	children := make([]NodeID, 0, 2+len(ctorDefs))
	children = append(children, typeName, paramsList)
	children = append(children, ctorDefs...)
	return k.intern(catInductive(), children)
}

// MakeConstructor — apply a constructor to value-recipe arguments,
// producing a value-recipe NodeID. The first child is the inductive
// type's NodeID so the walker / totality checker can find the type
// without a symbol table.
func MakeConstructor(
	k *Kernel,
	inductive NodeID,
	ctorName string,
	args []NodeID,
) NodeID {
	idx := ConstructorIndex(k, inductive, ctorName)
	if idx < 0 {
		panic(fmt.Sprintf(
			"MakeConstructor: %q is not a constructor of inductive %v",
			ctorName, inductive,
		))
	}
	nameNid := k.internString(ctorName)
	indexNid := k.internTrivialInt(int64(idx))
	children := make([]NodeID, 0, 3+len(args))
	children = append(children, inductive, nameNid, indexNid)
	children = append(children, args...)
	return k.intern(catConstructor(), children)
}

// ---------------------------------------------------------------------------
// Inductive introspection — by-name / by-index lookups via the interned recipe
// ---------------------------------------------------------------------------

// ConstructorIndex — look up a constructor's index on an inductive by
// name. Returns -1 if absent.
func ConstructorIndex(k *Kernel, inductive NodeID, ctorName string) int {
	if !isInductive(k, inductive) {
		return -1
	}
	kids := k.children(inductive)
	// children: [type-name, params-list, ctor0, ctor1, ...]
	for i := 2; i < len(kids); i++ {
		ctorKids := k.children(kids[i])
		if len(ctorKids) < 3 {
			continue
		}
		nameNid := ctorKids[1]
		idxNid := ctorKids[2]
		if nameNid.Level != LevelTrivial || nameNid.Type != TrivString {
			continue
		}
		if k.strs[nameNid.Inst] != ctorName {
			continue
		}
		if idxNid.Level != LevelTrivial || idxNid.Type != TrivInt {
			continue
		}
		return int(int32(idxNid.Inst))
	}
	return -1
}

// ConstructorNames — every constructor name declared on an inductive, in
// declaration order.
func ConstructorNames(k *Kernel, inductive NodeID) []string {
	if !isInductive(k, inductive) {
		return nil
	}
	kids := k.children(inductive)
	out := make([]string, 0, len(kids)-2)
	for i := 2; i < len(kids); i++ {
		ctorKids := k.children(kids[i])
		if len(ctorKids) < 2 {
			continue
		}
		nameNid := ctorKids[1]
		if nameNid.Level == LevelTrivial && nameNid.Type == TrivString {
			out = append(out, k.strs[nameNid.Inst])
		}
	}
	return out
}

// IsTotal — true iff every constructor declared on `inductive` appears in
// `armNames`. CHOICE walkers run this on every match.
func IsTotal(k *Kernel, inductive NodeID, armNames []string) bool {
	declared := ConstructorNames(k, inductive)
	set := make(map[string]struct{}, len(armNames))
	for _, n := range armNames {
		set[n] = struct{}{}
	}
	for _, d := range declared {
		if _, ok := set[d]; !ok {
			return false
		}
	}
	return true
}

// MissingArms — constructors declared on `inductive` not covered by
// `armNames`. Empty result iff the match is total.
func MissingArms(k *Kernel, inductive NodeID, armNames []string) []string {
	declared := ConstructorNames(k, inductive)
	set := make(map[string]struct{}, len(armNames))
	for _, n := range armNames {
		set[n] = struct{}{}
	}
	out := make([]string, 0)
	for _, d := range declared {
		if _, ok := set[d]; !ok {
			out = append(out, d)
		}
	}
	return out
}

// isInductive — true iff `n` is the NodeID of an INDUCTIVE recipe in `k`.
func isInductive(k *Kernel, n NodeID) bool {
	r, ok := k.byID[n]
	if !ok {
		return false
	}
	return r.Category.Type == RBasicInductive
}

// ---------------------------------------------------------------------------
// Walkers — value-recipe → runtime IndValue
// ---------------------------------------------------------------------------

// WalkValue — walk an arbitrary value-recipe into an IndValue.
//
//   - Trivials: returned as NodeValue (the raw NodeID carries the value).
//   - CONSTRUCTOR recipes: walked to a *CtorValue with all args recursed.
//   - CHOICE_MATCH recipes: dispatched and the matched arm body walked.
//   - Other recipes: returned as NodeValue (their NodeID is the result —
//     this module does not interpret BLOCK / MATH / etc. The full kernel
//     walker is in main.go; the inductive arm composes with it via the
//     CHOICE arm body returning a recipe NodeID).
func WalkValue(k *Kernel, node NodeID) IndValue {
	if node.Level == LevelTrivial {
		return NodeValue{Nid: node}
	}
	r := k.recipeAt(node)
	switch r.Category.Type {
	case RBasicConstructor:
		return WalkConstructor(k, node)
	case RBasicChoiceMatch:
		return WalkChoice(k, node)
	default:
		return NodeValue{Nid: node}
	}
}

// WalkConstructor — materialize a CONSTRUCTOR value-recipe into a
// *CtorValue. Recipe shape:
// `CONSTRUCTOR[inductive-ref, ctor-name, ctor-index, arg0, ...]`.
func WalkConstructor(k *Kernel, node NodeID) *CtorValue {
	kids := k.children(node)
	if len(kids) < 3 {
		panic("WalkConstructor: need 3+ children (inductive-ref, name, index)")
	}
	inductive := kids[0]
	nameNid := kids[1]
	idxNid := kids[2]
	if nameNid.Level != LevelTrivial || nameNid.Type != TrivString {
		panic("WalkConstructor: name must be a string trivial")
	}
	if idxNid.Level != LevelTrivial || idxNid.Type != TrivInt {
		panic("WalkConstructor: index must be an int trivial")
	}
	args := make([]IndValue, 0, len(kids)-3)
	for _, c := range kids[3:] {
		args = append(args, WalkValue(k, c))
	}
	return &CtorValue{
		Inductive: inductive,
		CtorName:  k.strs[nameNid.Inst],
		CtorIndex: int(int32(idxNid.Inst)),
		Args:      args,
	}
}

// MakeChoice — intern a CHOICE_MATCH recipe.
//
// `arms` is an ordered list of (ctor-name, body-recipe) pairs. The recipe
// is checked for totality at walk time, not intern time — non-total
// matches are valid substrate cells that raise when walked.
func MakeChoice(k *Kernel, scrutinee NodeID, arms []ChoiceArm) NodeID {
	children := make([]NodeID, 0, 1+2*len(arms))
	children = append(children, scrutinee)
	for _, arm := range arms {
		children = append(children, k.internString(arm.Name), arm.Body)
	}
	return k.intern(catChoiceMatch(), children)
}

// ChoiceArm — one arm of a CHOICE_MATCH recipe.
type ChoiceArm struct {
	Name string
	Body NodeID
}

// WalkChoice — walk a CHOICE_MATCH recipe. Verifies every constructor on
// the scrutinee's inductive appears as an arm; returns the matched arm's
// body (walked).
func WalkChoice(k *Kernel, node NodeID) IndValue {
	kids := k.children(node)
	if len(kids) < 1 {
		panic("WalkChoice: need scrutinee")
	}
	if (len(kids)-1)%2 != 0 {
		panic("WalkChoice: arms must be (name, body) pairs")
	}
	scrutVal := WalkValue(k, kids[0])
	scrut, ok := AsCtor(scrutVal)
	if !ok {
		panic(fmt.Sprintf(
			"WalkChoice: scrutinee must be a ctor value (got %T)", scrutVal,
		))
	}
	armNames := make([]string, 0, (len(kids)-1)/2)
	armBodies := make([]NodeID, 0, (len(kids)-1)/2)
	for i := 1; i < len(kids); i += 2 {
		nameNid := kids[i]
		if nameNid.Level != LevelTrivial || nameNid.Type != TrivString {
			panic("WalkChoice: arm name must be a string trivial")
		}
		armNames = append(armNames, k.strs[nameNid.Inst])
		armBodies = append(armBodies, kids[i+1])
	}

	declared := ConstructorNames(k, scrut.Inductive)
	if len(declared) > 0 {
		missing := MissingArms(k, scrut.Inductive, armNames)
		if len(missing) > 0 {
			label := "constructor"
			if len(missing) > 1 {
				label = "constructors"
			}
			panic(fmt.Sprintf(
				"choice: non-total — missing %s: %v", label, missing,
			))
		}
	}

	for i, name := range armNames {
		if name == scrut.CtorName {
			return WalkValue(k, armBodies[i])
		}
	}
	panic(fmt.Sprintf(
		"choice: no arm matches constructor %q", scrut.CtorName,
	))
}

// MatchValue — exhaustive runtime pattern match. The imperative
// entry-point used by tests and kernel-internal helpers; in surface
// Form, CHOICE_MATCH recipes carry the arms structurally (walked by
// WalkChoice above).
//
// `arms` is a map of ctor-name → ArmHandler. Returns the matched arm's
// result. Panics on non-totality or if no arm matches.
func MatchValue(
	k *Kernel,
	value IndValue,
	arms map[string]ArmHandler,
) interface{} {
	cv, ok := AsCtor(value)
	if !ok {
		panic(fmt.Sprintf(
			"MatchValue: expected ctor value, got %T", value,
		))
	}
	armNames := make([]string, 0, len(arms))
	for n := range arms {
		armNames = append(armNames, n)
	}
	if !IsTotal(k, cv.Inductive, armNames) {
		missing := MissingArms(k, cv.Inductive, armNames)
		panic(fmt.Sprintf(
			"MatchValue: non-total — missing: %v", missing,
		))
	}
	handler, ok := arms[cv.CtorName]
	if !ok {
		panic(fmt.Sprintf(
			"MatchValue: no arm matched %q", cv.CtorName,
		))
	}
	return handler(cv.Args)
}

// ---------------------------------------------------------------------------
// Built-in inductive types — interned as substrate cells. These exist so
// the rest of the body has a stable Nat / Bool / Option / Result / List
// to reach for; downstream code does not redefine its own.
// ---------------------------------------------------------------------------

// BuiltinInductives — the standard library of inductive types every body
// has. Returned by InstallBuiltinInductives.
type BuiltinInductives struct {
	Nat    NodeID
	Bool   NodeID
	Option NodeID
	Result NodeID
	List   NodeID
	// Parametric type-variable placeholders — bare string trivials carrying
	// the parameter name (T, E). Richer parametricity lands later; the
	// proof-of-shape uses bare strings.
	T NodeID
	E NodeID
}

// InstallBuiltinInductives — install the standard library of inductives.
// Idempotent — repeated calls on the same kernel return the same NodeIDs
// through content-addressing.
//
// The map returned keys built-in names to their NodeIDs; callers that
// want strongly-typed access can use the BuiltinInductives accessor.
func InstallBuiltinInductives(k *Kernel) map[string]*InductiveType {
	T := k.internString("T")
	E := k.internString("E")

	// Nat ::= zero | succ Nat
	// Self-reference: the `succ` constructor's arg type is Nat itself —
	// we use the type-name trivial as the sentinel (the inductive's NodeID
	// isn't known until intern completes).
	natSelf := k.internString("Nat")
	natID := MakeInductive(k, "Nat", nil, []*ConstructorDef{
		{CtorName: "zero", CtorIndex: 0},
		{CtorName: "succ", CtorIndex: 1, ArgTypes: []NodeID{natSelf}},
	})

	// Bool ::= false | true
	boolID := MakeInductive(k, "Bool", nil, []*ConstructorDef{
		{CtorName: "false", CtorIndex: 0},
		{CtorName: "true", CtorIndex: 1},
	})

	// Option[T] ::= none | some T
	optionID := MakeInductive(k, "Option", []NodeID{T}, []*ConstructorDef{
		{CtorName: "none", CtorIndex: 0},
		{CtorName: "some", CtorIndex: 1, ArgTypes: []NodeID{T}},
	})

	// Result[T, E] ::= ok T | err E
	resultID := MakeInductive(k, "Result", []NodeID{T, E}, []*ConstructorDef{
		{CtorName: "ok", CtorIndex: 0, ArgTypes: []NodeID{T}},
		{CtorName: "err", CtorIndex: 1, ArgTypes: []NodeID{E}},
	})

	// List[T] ::= nil | cons T (List T)
	listSelf := k.internString("List")
	listID := MakeInductive(k, "List", []NodeID{T}, []*ConstructorDef{
		{CtorName: "nil", CtorIndex: 0},
		{CtorName: "cons", CtorIndex: 1, ArgTypes: []NodeID{T, listSelf}},
	})

	return map[string]*InductiveType{
		"Nat":    {TypeName: "Nat", NodeID: natID},
		"Bool":   {TypeName: "Bool", NodeID: boolID},
		"Option": {TypeName: "Option", NodeID: optionID, TypeParams: []NodeID{T}},
		"Result": {TypeName: "Result", NodeID: resultID, TypeParams: []NodeID{T, E}},
		"List":   {TypeName: "List", NodeID: listID, TypeParams: []NodeID{T}},
	}
}

// InstallBuiltinInductivesTyped — the same install as the map version, but
// returns a BuiltinInductives struct for callers that want named fields.
func InstallBuiltinInductivesTyped(k *Kernel) BuiltinInductives {
	m := InstallBuiltinInductives(k)
	return BuiltinInductives{
		Nat:    m["Nat"].NodeID,
		Bool:   m["Bool"].NodeID,
		Option: m["Option"].NodeID,
		Result: m["Result"].NodeID,
		List:   m["List"].NodeID,
		T:      k.internString("T"),
		E:      k.internString("E"),
	}
}

// ---------------------------------------------------------------------------
// Convenience builders — common value-recipes
// ---------------------------------------------------------------------------

// NatZero — value-recipe NodeID for `zero`.
func NatZero(k *Kernel, inds BuiltinInductives) NodeID {
	return MakeConstructor(k, inds.Nat, "zero", nil)
}

// NatSucc — value-recipe NodeID for `succ prev`.
func NatSucc(k *Kernel, inds BuiltinInductives, prev NodeID) NodeID {
	return MakeConstructor(k, inds.Nat, "succ", []NodeID{prev})
}

// NatOf — value-recipe NodeID for the Peano numeral of `n`.
func NatOf(k *Kernel, inds BuiltinInductives, n int) NodeID {
	if n < 0 {
		panic("NatOf: negative")
	}
	out := NatZero(k, inds)
	for i := 0; i < n; i++ {
		out = NatSucc(k, inds, out)
	}
	return out
}

// ListNil — value-recipe NodeID for `nil`.
func ListNil(k *Kernel, inds BuiltinInductives) NodeID {
	return MakeConstructor(k, inds.List, "nil", nil)
}

// ListCons — value-recipe NodeID for `cons head tail`.
func ListCons(k *Kernel, inds BuiltinInductives, head, tail NodeID) NodeID {
	return MakeConstructor(k, inds.List, "cons", []NodeID{head, tail})
}

// ---------------------------------------------------------------------------
// Decoders — IndValue → Go primitive
// ---------------------------------------------------------------------------

// NatToInt — walk a Nat ctor-value into a Go int. Used by tests.
func NatToInt(v IndValue) int {
	n := 0
	cur := v
	for {
		cv, ok := AsCtor(cur)
		if !ok || cv.CtorName != "succ" {
			break
		}
		n++
		if len(cv.Args) == 0 {
			panic("NatToInt: succ with no args")
		}
		cur = cv.Args[0]
	}
	cv, ok := AsCtor(cur)
	if !ok || cv.CtorName != "zero" {
		panic("NatToInt: not a Nat")
	}
	return n
}

// ListLength — count cons cells in a List ctor-value.
func ListLength(v IndValue) int {
	n := 0
	cur := v
	for {
		cv, ok := AsCtor(cur)
		if !ok || cv.CtorName != "cons" {
			break
		}
		n++
		if len(cv.Args) < 2 {
			panic("ListLength: cons with insufficient args")
		}
		cur = cv.Args[1]
	}
	cv, ok := AsCtor(cur)
	if !ok || cv.CtorName != "nil" {
		panic("ListLength: not a List")
	}
	return n
}
