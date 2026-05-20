// quotient_test.go — mirrors the assertions in TS quotient.test.ts and
// Rust quotient.rs#[cfg(test)]. Cross-kernel identity: same inputs into
// any kernel's quotient arm produce the same equivalence answers.

package main

import "testing"

// placeholderCarrier — a distinct NodeID to stand in as the carrier
// slot of a QUOTIENT recipe. The carrier's content doesn't drive
// canonicalization in any of the built-in equivalences; it's a
// structural placeholder.
func placeholderCarrier(k *Kernel) NodeID {
	category := NodeID{
		Pkg:   1,
		Level: LevelBasic,
		Type:  RBasicList,
		Inst:  0,
	}
	return k.intern(category, nil)
}

func TestRBasicQuotientIsSlot70(t *testing.T) {
	if RBasicQuotient != 70 {
		t.Fatalf("RBasicQuotient = %d, want 70", RBasicQuotient)
	}
	if RBasicEquivalence != 71 {
		t.Fatalf("RBasicEquivalence = %d, want 71", RBasicEquivalence)
	}
}

func TestIntegerFromNatPairSharesNodeID(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lib.EquivIntegerFromNatPair.NodeID)

	v31 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(3), k.internTrivialInt(1)})
	v53 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(5), k.internTrivialInt(3)})
	v97 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(9), k.internTrivialInt(7)})

	if v31 != v53 {
		t.Errorf("(3,1) ≡ (5,3) [both +2]: %v != %v", v31, v53)
	}
	if v31 != v97 {
		t.Errorf("(3,1) ≡ (9,7) [transitivity]: %v != %v", v31, v97)
	}

	// Negative integers
	vn13 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(1), k.internTrivialInt(3)})
	vn24 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(2), k.internTrivialInt(4)})
	if vn13 != vn24 {
		t.Errorf("(1,3) ≡ (2,4) [both -2]: %v != %v", vn13, vn24)
	}
	if v31 == vn13 {
		t.Errorf("+2 == -2 should not collide: %v", v31)
	}
	if !QuotientEqual(k, v31, v53) {
		t.Errorf("QuotientEqual((3,1),(5,3)) should hold")
	}
}

func TestRationalFromIntPairCanonicalizes(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lib.EquivRationalFromIntPair.NodeID)

	v24 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(2), k.internTrivialInt(4)})
	v12 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(1), k.internTrivialInt(2)})
	v36 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(3), k.internTrivialInt(6)})
	vNeg2Pos4 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(-2), k.internTrivialInt(4)})
	vPos2Neg4 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(2), k.internTrivialInt(-4)})

	if v24 != v12 {
		t.Errorf("2/4 ≡ 1/2: %v != %v", v24, v12)
	}
	if v36 != v12 {
		t.Errorf("3/6 ≡ 1/2 (reduce): %v != %v", v36, v12)
	}
	if vNeg2Pos4 != vPos2Neg4 {
		t.Errorf("-2/4 ≡ 2/-4 (sign normalization): %v != %v", vNeg2Pos4, vPos2Neg4)
	}
	if v12 == vNeg2Pos4 {
		t.Errorf("1/2 ≠ -1/2 but they share a NodeID: %v", v12)
	}
}

func TestCommutativePairSwaps(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lib.EquivCommutativePair.NodeID)

	a := k.internTrivialInt(7)
	b := k.internTrivialInt(42)
	c := k.internTrivialInt(99)

	vab := InternQuotientValue(k, q, []NodeID{a, b})
	vba := InternQuotientValue(k, q, []NodeID{b, a})
	if vab != vba {
		t.Errorf("(7,42) ≡ (42,7): %v != %v", vab, vba)
	}
	vac := InternQuotientValue(k, q, []NodeID{a, c})
	if vab == vac {
		t.Errorf("(7,42) != (7,99) but they collide: %v", vab)
	}
}

func TestCanonicalRoundTripShape(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lib.EquivIntegerFromNatPair.NodeID)

	v := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(7), k.internTrivialInt(2)})
	canon := CanonicalForm(k, v)
	kids := k.children(canon)
	if len(kids) != 3 {
		t.Fatalf("[quotient, canon-a, canon-b]: got %d children", len(kids))
	}
	ca, ok := readIntTrivial(kids[1])
	if !ok {
		t.Fatalf("canon-a not int trivial")
	}
	cb, ok := readIntTrivial(kids[2])
	if !ok {
		t.Fatalf("canon-b not int trivial")
	}
	if ca != 5 {
		t.Errorf("canon-a = %d, want 5", ca)
	}
	if cb != 0 {
		t.Errorf("canon-b = %d, want 0", cb)
	}
	// Re-intern from canonical children lands at same NodeID
	v2 := InternQuotientValue(k, q, []NodeID{kids[1], kids[2]})
	if v != v2 {
		t.Errorf("canonical re-intern not idempotent: %v != %v", v, v2)
	}
}

func TestEquivalenceCellsAreContentAddressed(t *testing.T) {
	k := NewKernel()
	a := BuildQuotientLibrary(k)
	b := BuildQuotientLibrary(k)
	if a.EquivIntegerFromNatPair.NodeID != b.EquivIntegerFromNatPair.NodeID {
		t.Errorf("same kernel + bootstrap should yield identical equivalence-cell NodeID")
	}
	resolved, ok := ResolveEquivalence(k, a.EquivIntegerFromNatPair.NodeID)
	if !ok {
		t.Fatalf("ResolveEquivalence failed for known cell")
	}
	if resolved.EquivalenceName != "integer-from-nat-pair" {
		t.Errorf("name = %q, want integer-from-nat-pair", resolved.EquivalenceName)
	}
	if resolved.Decidability != uint32(DecidableCheap) {
		t.Errorf("decidability = %d, want %d", resolved.Decidability, DecidableCheap)
	}
}

func TestQuotientRecipesAreContentAddressed(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q1 := MakeQuotientRecipe(k, carrier, lib.EquivIntegerFromNatPair.NodeID)
	q2 := MakeQuotientRecipe(k, carrier, lib.EquivIntegerFromNatPair.NodeID)
	if q1 != q2 {
		t.Errorf("same (carrier, equiv) should yield same QUOTIENT NodeID: %v != %v", q1, q2)
	}
}

func TestDecidabilityPolicyRoutesStrategy(t *testing.T) {
	k := NewKernel()
	RegisterHandler("test-heavy-g", func(_ *Kernel, raw []NodeID) []NodeID {
		out := make([]NodeID, len(raw))
		copy(out, raw)
		return out
	})
	RegisterHandler("test-undec-g", func(_ *Kernel, raw []NodeID) []NodeID {
		out := make([]NodeID, len(raw))
		copy(out, raw)
		return out
	})

	heavy := MakeEquivalence(k, "test-heavy-g", DecidableHeavy, "test-heavy-g")
	undec := MakeEquivalence(k, "test-undec-g", Undecidable, "test-undec-g")

	if heavy.Strategy != uint32(StrategyLazy) {
		t.Errorf("heavy strategy = %d, want Lazy (%d)", heavy.Strategy, StrategyLazy)
	}
	if undec.Strategy != uint32(StrategyLazy) {
		t.Errorf("undec strategy = %d, want Lazy (%d)", undec.Strategy, StrategyLazy)
	}
	if undec.IsDecidable {
		t.Errorf("undec.IsDecidable should be false")
	}
}

func TestLazyStrategyMergesOnDemand(t *testing.T) {
	k := NewKernel()
	RegisterHandler("lazy-int-g", func(kk *Kernel, raw []NodeID) []NodeID {
		av, ok := readIntTrivial(raw[0])
		if !ok {
			panic("lazy-int-g: bad child 0")
		}
		bv, ok := readIntTrivial(raw[1])
		if !ok {
			panic("lazy-int-g: bad child 1")
		}
		return []NodeID{kk.internTrivialInt(av - bv), kk.internTrivialInt(0)}
	})
	lazyEq := MakeEquivalence(k, "lazy-int-g", DecidableHeavy, "lazy-int-g")
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lazyEq.NodeID)

	v31 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(3), k.internTrivialInt(1)})
	v53 := InternQuotientValue(k, q, []NodeID{k.internTrivialInt(5), k.internTrivialInt(3)})

	// Lazy: raw NodeIDs differ pre-canonicalization
	if v31 == v53 {
		t.Errorf("lazy raw NodeIDs should differ pre-canonicalization: %v", v31)
	}
	c31 := CanonicalForm(k, v31)
	c53 := CanonicalForm(k, v53)
	if c31 != c53 {
		t.Errorf("CanonicalForm should merge: %v != %v", c31, c53)
	}
	if !QuotientEqual(k, v31, v53) {
		t.Errorf("QuotientEqual should hold across strategies")
	}
}

func TestQuotientPartsInspection(t *testing.T) {
	k := NewKernel()
	lib := BuildQuotientLibrary(k)
	carrier := placeholderCarrier(k)
	q := MakeQuotientRecipe(k, carrier, lib.EquivCommutativePair.NodeID)

	c, e, err := QuotientParts(k, q)
	if err != nil {
		t.Fatalf("QuotientParts: %v", err)
	}
	if c != carrier {
		t.Errorf("carrier mismatch: %v != %v", c, carrier)
	}
	if e != lib.EquivCommutativePair.NodeID {
		t.Errorf("equiv mismatch: %v != %v", e, lib.EquivCommutativePair.NodeID)
	}
}

func TestHandlerRegistryIsQueryable(t *testing.T) {
	k := NewKernel()
	_ = BuildQuotientLibrary(k)
	if !HasHandler("integer-from-nat-pair") {
		t.Errorf("HasHandler(integer-from-nat-pair) should be true")
	}
	if HasHandler("does-not-exist-handler-name-g") {
		t.Errorf("unknown handler should not register as present")
	}
	fn, ok := GetHandler("integer-from-nat-pair")
	if !ok || fn == nil {
		t.Errorf("GetHandler should return the registered fn")
	}
}
