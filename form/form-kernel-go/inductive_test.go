// inductive_test.go — proof-of-shape tests for INDUCTIVE + CONSTRUCTOR
// + CHOICE arms. Mirrors:
//
//   form/form-kernel-ts/src/inductive.test.ts
//   api/tests/test_inductive.py
//
// Run with: go test ./form/form-kernel-go/...

package main

import (
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// Slot constants — part of the cross-kernel contract.
// ---------------------------------------------------------------------------

func TestRBasicSlots(t *testing.T) {
	if RBasicInductive != 71 {
		t.Errorf("RBasicInductive = %d, want 71", RBasicInductive)
	}
	if RBasicConstructor != 72 {
		t.Errorf("RBasicConstructor = %d, want 72", RBasicConstructor)
	}
	if RBasicChoiceMatch != 35 {
		t.Errorf("RBasicChoiceMatch = %d, want 35", RBasicChoiceMatch)
	}
	if TrivConstructorTag != 15 {
		t.Errorf("TrivConstructorTag = %d, want 15", TrivConstructorTag)
	}
}

// ---------------------------------------------------------------------------
// Nat — round-trip 0..5 through succ/zero.
// ---------------------------------------------------------------------------

func TestNatRoundTrip(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)

	for i := 0; i <= 5; i++ {
		nid := NatOf(k, inds, i)
		v := WalkValue(k, nid)
		got := NatToInt(v)
		if got != i {
			t.Errorf("NatToInt(NatOf(%d)) = %d, want %d", i, got, i)
		}
	}
}

func TestNatTwoIsCtorSucc(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	two := NatOf(k, inds, 2)
	v := WalkValue(k, two)
	cv, ok := AsCtor(v)
	if !ok {
		t.Fatalf("expected CtorValue, got %T", v)
	}
	if cv.CtorName != "succ" {
		t.Errorf("two.CtorName = %q, want %q", cv.CtorName, "succ")
	}
	if cv.CtorIndex != 1 {
		t.Errorf("two.CtorIndex = %d, want 1", cv.CtorIndex)
	}
}

// ---------------------------------------------------------------------------
// List — cons/nil and length.
// ---------------------------------------------------------------------------

func TestListLengthTwo(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	one := k.internTrivialInt(1)
	two := k.internTrivialInt(2)
	lst := ListCons(k, inds, one, ListCons(k, inds, two, ListNil(k, inds)))
	v := WalkValue(k, lst)
	if got := ListLength(v); got != 2 {
		t.Errorf("ListLength = %d, want 2", got)
	}
}

func TestListLengthEmpty(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	v := WalkValue(k, ListNil(k, inds))
	if got := ListLength(v); got != 0 {
		t.Errorf("ListLength(nil) = %d, want 0", got)
	}
}

// ---------------------------------------------------------------------------
// Option — MatchValue total / non-total.
// ---------------------------------------------------------------------------

func TestOptionMatchCoversSome(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	someFive := MakeConstructor(k, inds.Option, "some", []NodeID{k.internTrivialInt(5)})
	v := WalkValue(k, someFive)

	r := MatchValue(k, v, map[string]ArmHandler{
		"none": func(_ []IndValue) interface{} { return int64(-1) },
		"some": func(args []IndValue) interface{} {
			n, ok := AsInt(args[0])
			if !ok {
				return int64(-2)
			}
			return n
		},
	})
	if r.(int64) != 5 {
		t.Errorf("matched some(5) = %v, want 5", r)
	}
}

func TestOptionMatchCoversNone(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	none := MakeConstructor(k, inds.Option, "none", nil)
	v := WalkValue(k, none)

	r := MatchValue(k, v, map[string]ArmHandler{
		"none": func(_ []IndValue) interface{} { return int64(-1) },
		"some": func(_ []IndValue) interface{} { return int64(0) },
	})
	if r.(int64) != -1 {
		t.Errorf("matched none = %v, want -1", r)
	}
}

func TestOptionMatchMissingArmPanics(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	someFive := MakeConstructor(k, inds.Option, "some", []NodeID{k.internTrivialInt(5)})
	v := WalkValue(k, someFive)

	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic on non-total match")
		}
		msg, _ := r.(string)
		if !strings.Contains(msg, "none") {
			t.Errorf("panic message %q should mention 'none'", msg)
		}
	}()
	MatchValue(k, v, map[string]ArmHandler{
		"some": func(args []IndValue) interface{} { return args[0] },
	})
}

// ---------------------------------------------------------------------------
// CHOICE_MATCH recipe — walker totality check.
// ---------------------------------------------------------------------------

func TestChoiceMatchRejectsMissingArm(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	some5 := MakeConstructor(k, inds.Option, "some", []NodeID{k.internTrivialInt(5)})
	// Arm body: a bare expression returning int 99.
	body := k.internTrivialInt(99)
	choice := MakeChoice(k, some5, []ChoiceArm{{Name: "some", Body: body}})

	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic on non-total CHOICE")
		}
		msg, _ := r.(string)
		if !strings.Contains(msg, "none") {
			t.Errorf("panic message %q should mention missing 'none'", msg)
		}
	}()
	WalkChoice(k, choice)
}

func TestChoiceMatchTotalDispatch(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	some5 := MakeConstructor(k, inds.Option, "some", []NodeID{k.internTrivialInt(5)})
	body99 := k.internTrivialInt(99)
	body0 := k.internTrivialInt(0)
	choice := MakeChoice(k, some5, []ChoiceArm{
		{Name: "some", Body: body99},
		{Name: "none", Body: body0},
	})
	v := WalkChoice(k, choice)
	nid, ok := AsNode(v)
	if !ok {
		t.Fatalf("expected NodeValue, got %T", v)
	}
	if nid.Level != LevelTrivial || nid.Type != TrivInt || int32(nid.Inst) != 99 {
		t.Errorf("CHOICE returned %v, want trivial int 99", nid)
	}
}

// ---------------------------------------------------------------------------
// Custom inductive — Color := red | green | blue, content-addressed.
// ---------------------------------------------------------------------------

func makeColor(k *Kernel) NodeID {
	return MakeInductive(k, "Color", nil, []*ConstructorDef{
		{CtorName: "red", CtorIndex: 0},
		{CtorName: "green", CtorIndex: 1},
		{CtorName: "blue", CtorIndex: 2},
	})
}

func TestColorConstructorNames(t *testing.T) {
	k := NewKernel()
	color := makeColor(k)
	got := ConstructorNames(k, color)
	want := []string{"red", "green", "blue"}
	if len(got) != len(want) {
		t.Fatalf("ConstructorNames len = %d, want %d", len(got), len(want))
	}
	for i, n := range want {
		if got[i] != n {
			t.Errorf("ConstructorNames[%d] = %q, want %q", i, got[i], n)
		}
	}
}

func TestColorIsTotal(t *testing.T) {
	k := NewKernel()
	color := makeColor(k)
	if !IsTotal(k, color, []string{"red", "green", "blue"}) {
		t.Errorf("IsTotal should be true with all 3 covered")
	}
	if IsTotal(k, color, []string{"red", "green"}) {
		t.Errorf("IsTotal should be false missing blue")
	}
	missing := MissingArms(k, color, []string{"red", "green"})
	if len(missing) != 1 || missing[0] != "blue" {
		t.Errorf("MissingArms = %v, want [blue]", missing)
	}
}

func TestColorStructuralEquivalence(t *testing.T) {
	// Two structurally-identical Color definitions intern to the same NodeID.
	k := NewKernel()
	c1 := makeColor(k)
	c2 := makeColor(k)
	if c1 != c2 {
		t.Errorf("structurally identical Color → same NodeID; got %v vs %v", c1, c2)
	}

	// Even across separate kernels, the contained recipe shape — name,
	// params, ctor list — produces matching cell-content. NodeID instance
	// numbers differ across kernels (per-kernel intern counters), but the
	// SAME kernel always recovers the same NodeID for the same definition.
	k2 := NewKernel()
	c3 := makeColor(k2)
	// On a fresh kernel the inst counter resets — c3 should equal c1 only
	// if the intern sequence matches. Both kernels intern "Color" first
	// (via internString) and the same ctor names; the inst values track
	// because the per-string and per-recipe ordering is the same.
	if c3.Type != c1.Type {
		t.Errorf("Color from separate kernel has wrong slot: %v vs %v", c3, c1)
	}
}

// ---------------------------------------------------------------------------
// Custom inductive with arguments — Pair Nat Nat (for QUOTIENT composition).
// ---------------------------------------------------------------------------

// makePair — Pair := mkPair Nat Nat. The two Nat-typed args express how
// integers are constructed as (Nat × Nat) — the pair-carrier of the
// QUOTIENT-defined Z := (Nat × Nat) / equiv. The QUOTIENT module (when
// composed) wraps this Pair with the integer-from-nat-pair equivalence
// recipe; INDUCTIVE supplies the carrier shape.
func makePair(k *Kernel, inds BuiltinInductives) NodeID {
	return MakeInductive(k, "Pair", nil, []*ConstructorDef{
		{CtorName: "mkPair", CtorIndex: 0, ArgTypes: []NodeID{inds.Nat, inds.Nat}},
	})
}

func TestPairCarrierForQuotient(t *testing.T) {
	// Compose with QUOTIENT: Z := (Nat × Nat) / equiv.
	//
	// This proof-of-shape demonstrates the carrier side of the composition:
	// the inductive `Pair Nat Nat` is what the QUOTIENT recipe wraps. With
	// quotient.go in the same module the full QUOTIENT cell would project
	// (a,b) → canonical-form and content-address equivalent pairs to the
	// same NodeID — the integers Z drop out as the substrate cells.
	//
	// We verify the carrier here: mkPair(3, 1) and mkPair(5, 3) are
	// structurally distinct (different Nat args), as Z-canonicalization
	// has not yet been applied. Once QUOTIENT runs canonicalize they
	// would collapse to a single representative pair.
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	pairType := makePair(k, inds)

	p31 := MakeConstructor(k, pairType, "mkPair", []NodeID{
		NatOf(k, inds, 3),
		NatOf(k, inds, 1),
	})
	p53 := MakeConstructor(k, pairType, "mkPair", []NodeID{
		NatOf(k, inds, 5),
		NatOf(k, inds, 3),
	})

	if p31 == p53 {
		t.Errorf("uncanonicalized (3,1) and (5,3) should be distinct cells; got %v", p31)
	}

	// Reading the components back through walk:
	v31 := WalkConstructor(k, p31)
	if v31.CtorName != "mkPair" {
		t.Errorf("p31.CtorName = %q, want mkPair", v31.CtorName)
	}
	if len(v31.Args) != 2 {
		t.Fatalf("p31 has %d args, want 2", len(v31.Args))
	}
	a, _ := AsCtor(v31.Args[0])
	b, _ := AsCtor(v31.Args[1])
	if NatToInt(a) != 3 {
		t.Errorf("p31.Args[0] = %d, want 3", NatToInt(a))
	}
	if NatToInt(b) != 1 {
		t.Errorf("p31.Args[1] = %d, want 1", NatToInt(b))
	}

	// Idempotent: building the same pair twice returns the same NodeID
	// (content-addressing) — the contract QUOTIENT relies on.
	p31_again := MakeConstructor(k, pairType, "mkPair", []NodeID{
		NatOf(k, inds, 3),
		NatOf(k, inds, 1),
	})
	if p31 != p31_again {
		t.Errorf("identical mkPair(3,1) should intern to same NodeID; got %v vs %v", p31, p31_again)
	}
}

// ---------------------------------------------------------------------------
// Built-in inductives are content-addressed within a kernel.
// ---------------------------------------------------------------------------

func TestBuiltinInductivesIdempotent(t *testing.T) {
	k := NewKernel()
	m1 := InstallBuiltinInductives(k)
	m2 := InstallBuiltinInductives(k)
	for name := range m1 {
		if m1[name].NodeID != m2[name].NodeID {
			t.Errorf("re-install of %s changed NodeID: %v vs %v",
				name, m1[name].NodeID, m2[name].NodeID)
		}
	}
}

func TestBuiltinInductivesAllPresent(t *testing.T) {
	k := NewKernel()
	m := InstallBuiltinInductives(k)
	for _, name := range []string{"Nat", "Bool", "Option", "Result", "List"} {
		if _, ok := m[name]; !ok {
			t.Errorf("missing built-in inductive: %s", name)
		}
	}
}

func TestNatHasZeroAndSucc(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	names := ConstructorNames(k, inds.Nat)
	want := []string{"zero", "succ"}
	if len(names) != len(want) {
		t.Fatalf("Nat ctors = %v, want %v", names, want)
	}
	for i, n := range want {
		if names[i] != n {
			t.Errorf("Nat ctor %d = %q, want %q", i, names[i], n)
		}
	}
}

func TestResultCtorIndices(t *testing.T) {
	k := NewKernel()
	inds := InstallBuiltinInductivesTyped(k)
	if got := ConstructorIndex(k, inds.Result, "ok"); got != 0 {
		t.Errorf("Result.ok index = %d, want 0", got)
	}
	if got := ConstructorIndex(k, inds.Result, "err"); got != 1 {
		t.Errorf("Result.err index = %d, want 1", got)
	}
	if got := ConstructorIndex(k, inds.Result, "missing"); got != -1 {
		t.Errorf("Result.missing index = %d, want -1", got)
	}
}
