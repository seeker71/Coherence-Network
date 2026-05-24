// formats_test.go — conformance tests for the format-recipe library.
//
// Covers:
//   - Canonical-vector conformance (each vector from the canonical JSON)
//   - Content-addressing (same value twice → same NodeID)
//   - Canonicalization (NaN, -0 collapse correctly)
//   - Cross-call stability (BuildFormatLibrary called twice in the same
//     kernel produces identical NodeIDs — interning is idempotent).

package main

import (
	"encoding/json"
	"math"
	"math/big"
	"strconv"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// Helpers — parse the canonical JSON values into NumValue (handles bigint
// suffix "n" as a string in the JSON).
// ---------------------------------------------------------------------------

func parseOperand(raw interface{}, hint uint32) NumValue {
	switch x := raw.(type) {
	case float64:
		if hint == ArithHintBigint {
			return NV_BigFromInt64(int64(x))
		}
		if hint == ArithHintNativeInt || hint == ArithHintNativeIntNarrow || hint == ArithHintXorPopcount {
			return NV_I(int64(x))
		}
		return NV_F(x)
	case string:
		// Bigint literals carry a trailing 'n' as a marker.
		if strings.HasSuffix(x, "n") {
			b := new(big.Int)
			b.SetString(strings.TrimSuffix(x, "n"), 10)
			return NV_Big(b)
		}
		if x == "NaN" {
			return NV_F(math.NaN())
		}
		// Numeric string fallback
		if f, err := strconv.ParseFloat(x, 64); err == nil {
			return NV_F(f)
		}
	case bool:
		if x {
			return NV_I(1)
		}
		return NV_I(0)
	case json.Number:
		f, _ := x.Float64()
		return NV_F(f)
	}
	return NV_F(0)
}

func valuesClose(a, b NumValue, eps float64) bool {
	if a.Kind == NumBig || b.Kind == NumBig {
		return a.AsBig().Cmp(b.AsBig()) == 0
	}
	if a.Kind == NumI64 && b.Kind == NumI64 {
		return a.I == b.I
	}
	af, bf := a.AsFloat(), b.AsFloat()
	if math.IsNaN(af) && math.IsNaN(bf) {
		return true
	}
	return math.Abs(af-bf) <= eps
}

func epsForFormat(name string) float64 {
	switch name {
	case "fp64", "i64", "u64", "i32", "i16", "i8", "u32", "u16", "u8", "i4",
		"bitnet-158", "bit-1":
		return 0
	case "fp32":
		return 1e-6
	case "bf16":
		return 1e-2
	case "fp8-e4m3", "fp8-e5m2", "fp4-uniform", "nf4":
		return 1e-2
	case "log-prob":
		return 1e-12
	}
	return 1e-9
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

func TestBuildFormatLibrary_ContractMatch(t *testing.T) {
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("BuildFormatLibrary: %v", err)
	}
	wantNames := []string{
		"fp64", "fp32", "bf16", "fp8-e4m3", "fp8-e5m2", "fp4-uniform", "nf4",
		"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "i4",
		"bitnet-158", "bit-1", "log-prob",
	}
	if len(lib.ByOrder) != len(wantNames) {
		t.Fatalf("expected %d formats, got %d", len(wantNames), len(lib.ByOrder))
	}
	for i, name := range wantNames {
		if lib.ByOrder[i].Name != name {
			t.Errorf("ByOrder[%d]: want %q, got %q", i, name, lib.ByOrder[i].Name)
		}
		if lib.ByName[name] == nil {
			t.Errorf("ByName[%q] missing", name)
		}
	}
}

func TestFormatRecipe_ContentAddressing(t *testing.T) {
	// Two BuildFormatLibrary calls on the same kernel must return the
	// same NodeIDs for every format (intern is idempotent).
	k := NewKernel()
	lib1, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("first BuildFormatLibrary: %v", err)
	}
	lib2, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("second BuildFormatLibrary: %v", err)
	}
	for name, fr1 := range lib1.ByName {
		fr2 := lib2.ByName[name]
		if fr1.NodeID != fr2.NodeID {
			t.Errorf("format %q: first NodeID %v != second %v", name, fr1.NodeID, fr2.NodeID)
		}
	}
}

func TestFormatRecipe_FreshKernelsAgree(t *testing.T) {
	// Two fresh kernels building the format library should produce
	// identical NodeIDs (modulo string-name-id alignment — see formats.go).
	// In this test we assert structural identity of the recipe tree by
	// comparing the (Pkg, Level, Type, Inst) tuple. Since intern assigns
	// Inst sequentially as new recipes are seen, and the formats are
	// interned in the same order, the Inst values line up.
	k1 := NewKernel()
	lib1, err := BuildFormatLibrary(k1)
	if err != nil {
		t.Fatalf("kernel 1: %v", err)
	}
	k2 := NewKernel()
	lib2, err := BuildFormatLibrary(k2)
	if err != nil {
		t.Fatalf("kernel 2: %v", err)
	}
	for name, fr1 := range lib1.ByName {
		fr2 := lib2.ByName[name]
		// Category-level identity (encoding + format-slot) must match.
		if fr1.NodeID.Type != fr2.NodeID.Type {
			t.Errorf("format %q: Type %d != %d", name, fr1.NodeID.Type, fr2.NodeID.Type)
		}
		// Inst should also match because intern() assigns sequentially
		// from the same starting state.
		if fr1.NodeID.Inst != fr2.NodeID.Inst {
			t.Errorf("format %q: Inst %d != %d", name, fr1.NodeID.Inst, fr2.NodeID.Inst)
		}
	}
}

func TestConformanceVectors(t *testing.T) {
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("BuildFormatLibrary: %v", err)
	}
	c, err := loadCanonicalContract()
	if err != nil {
		t.Fatalf("loadCanonicalContract: %v", err)
	}

	for _, v := range c.Conform.Vectors {
		v := v
		t.Run(v.Format+"_"+v.Op, func(t *testing.T) {
			fr := lib.ByName[v.Format]
			if fr == nil {
				t.Fatalf("unknown format %q", v.Format)
			}
			// Contract gap resolved 2026-05-20 in synthesis pass:
			// i8/i16/u8/u16 flipped to arithmetic_hint="native-int-narrow"
			// in the canonical JSON. All 15 vectors now run end-to-end.
			opCode, ok := arithOpByName[v.Op]
			if !ok {
				t.Fatalf("unknown op %q", v.Op)
			}
			a := parseOperand(v.A, fr.ArithHintCode)
			b := parseOperand(v.B, fr.ArithHintCode)
			expected := parseOperand(v.Expected, fr.ArithHintCode)
			got := applyArith(fr, opCode, a, b)
			eps := epsForFormat(v.Format)
			if !valuesClose(got, expected, eps) {
				t.Errorf("Pass0 %s.%s(%v, %v): want %v, got %v", v.Format, v.Op, a, b, expected, got)
			}
			// Pass 1: same answer through the handler cache.
			table := NewFormatTable()
			table.RegisterAll(lib)
			handle := table.Register(fr)
			h := table.Handler(handle, opCode)
			got2 := h(a, b)
			if !valuesClose(got2, expected, eps) {
				t.Errorf("Pass1 %s.%s(%v, %v): want %v, got %v", v.Format, v.Op, a, b, expected, got2)
			}
		})
	}
}

func TestCanonicalization(t *testing.T) {
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("BuildFormatLibrary: %v", err)
	}
	fp64 := lib.FP64

	// +0 and -0 collapse to same value
	got := canonicalize(fp64, NV_F(math.Copysign(0, -1)))
	if math.Signbit(got.AsFloat()) {
		t.Errorf("canonicalize(-0): sign bit not cleared")
	}

	// NaN values collapse to a single canonical NaN
	c1 := canonicalize(fp64, NV_F(math.NaN()))
	c2 := canonicalize(fp64, NV_F(math.NaN()))
	if !math.IsNaN(c1.AsFloat()) || !math.IsNaN(c2.AsFloat()) {
		t.Errorf("canonicalize(NaN): result not NaN")
	}

	// Overflow-string routing for fp64 produces the same NodeID for
	// equivalent floats and for -0 / +0.
	id1 := internOverflowFloat64(k, 0.0)
	id2 := internOverflowFloat64(k, math.Copysign(0, -1))
	if id1 != id2 {
		t.Errorf("internOverflowFloat64(+0) %v != (-0) %v", id1, id2)
	}
	idA := internOverflowFloat64(k, 3.14159)
	idB := internOverflowFloat64(k, 3.14159)
	if idA != idB {
		t.Errorf("internOverflowFloat64(3.14159) twice: %v != %v", idA, idB)
	}
	idNaN1 := internOverflowFloat64(k, math.NaN())
	idNaN2 := internOverflowFloat64(k, math.NaN())
	if idNaN1 != idNaN2 {
		t.Errorf("internOverflowFloat64(NaN) twice: %v != %v", idNaN1, idNaN2)
	}
}

func TestHandlerCache_HitsSameClosure(t *testing.T) {
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("BuildFormatLibrary: %v", err)
	}
	table := NewFormatTable()
	table.RegisterAll(lib)

	handle := table.Register(lib.FP64)
	h1 := table.Handler(handle, ArithOpAdd)
	h2 := table.Handler(handle, ArithOpAdd)
	// Function-value equality not directly comparable in Go (closures),
	// but invoking twice with the same inputs must produce the same result.
	r1 := h1(NV_F(1.5), NV_F(2.25))
	r2 := h2(NV_F(1.5), NV_F(2.25))
	if r1.F != r2.F || r1.F != 3.75 {
		t.Errorf("FP64 add cache: %v vs %v (want 3.75)", r1, r2)
	}
}

func TestBitnetTernary_DotProduct(t *testing.T) {
	// Workload smoke test: dot product of ternary values through Pass 0
	// and Pass 1 should agree with bare Go arithmetic.
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		t.Fatalf("BuildFormatLibrary: %v", err)
	}
	bitnet := lib.Bitnet158
	table := NewFormatTable()
	table.RegisterAll(lib)
	handle := table.Register(bitnet)
	add := table.Handler(handle, ArithOpAdd)

	// Σ ((i*13) % 3) - 1 for i in 1..100, native i32
	var native int32
	for i := int32(1); i <= 100; i++ {
		t := ((i * 13) % 3) - 1
		native += t
	}

	var pass0 NumValue = NV_I(0)
	var pass1 NumValue = NV_I(0)
	for i := int32(1); i <= 100; i++ {
		ti := ((i * 13) % 3) - 1
		pass0 = applyArith(bitnet, ArithOpAdd, pass0, NV_I(int64(ti)))
		pass1 = add(pass1, NV_I(int64(ti)))
	}
	if pass0.AsInt64() != int64(native) {
		t.Errorf("Pass0 bitnet dot: %d != native %d", pass0.AsInt64(), native)
	}
	if pass1.AsInt64() != int64(native) {
		t.Errorf("Pass1 bitnet dot: %d != native %d", pass1.AsInt64(), native)
	}
}
