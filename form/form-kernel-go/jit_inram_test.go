//go:build darwin && arm64 && cgo

// jit_inram_test.go — the in-RAM JIT path proven end to end IN ONE PROCESS:
// the Form emitter (lo-compile-fn, four-way in tests/inram-leaf-emit-band.fk)
// produces the arm64 leaf image, and the host executor (jit_leaf_inram, MAP_JIT)
// runs it as int64 f(int64). No `go build`, no plugin .so — emit and exec meet
// on one byte image, the same image the four-way band checksums.

package main

import (
	"fmt"
	"path/filepath"
	"testing"
)

// loInRAM lowers f(n)=n*3+7 with lo-compile-fn, then runs the emitted image
// in-RAM with arg via the jit_leaf_inram native, returning the kernel result.
func loInRAM(t *testing.T, preludes string, arg int64) Value {
	t.Helper()
	// f(n) = n*3 + 7 as an op-tagged prog (1=LIT 2=ARG 3=ADD 5=MUL),
	// children are indices: 0 LIT7 · 1 ARG · 2 LIT3 · 3 MUL(ARG,LIT3) ·
	// 4 ADD(MUL,LIT7), root=4 — the exact shape the four-way band emits.
	src := preludes + fmt.Sprintf(`
(do
  (let prog (list (list 1 7) (list 2) (list 1 3) (list 5 1 2) (list 3 3 0)))
  (let img (lo-compile-fn prog 4))
  (jit_leaf_inram img %d))`, arg)
	k := NewKernel()
	root := readRootFromSource(k, src)
	return k.walk(root, NewFrame(nil))
}

func TestInRAMLeafRunsFormEmittedArm64(t *testing.T) {
	stdlib := filepath.Join("..", "form-stdlib")
	preludes := readFiles(t,
		filepath.Join(stdlib, "form-asm.fk"),
		filepath.Join(stdlib, "form-lower.fk"),
	)
	// f(n) = n*3 + 7 across a spread that exercises the immediate, the
	// register multiply, and zero — every input the walker would also answer.
	for _, tc := range []struct{ arg, want int64 }{
		{5, 22}, {0, 7}, {10, 37}, {100, 307}, {7, 28},
	} {
		got := loInRAM(t, preludes, tc.arg)
		if got.Kind != VInt {
			t.Fatalf("f(%d): want VInt, got kind %v (%v)", tc.arg, got.Kind, got)
		}
		if got.Int != tc.want {
			t.Fatalf("in-RAM f(%d) = %d, want %d (n*3+7) — emitter/executor disagree",
				tc.arg, got.Int, tc.want)
		}
	}
}

// TestInRAMLeafRefusesBadImage — the native answers null (never panics or
// segfaults) for malformed input, so a non-leaf or out-of-range image leaves
// the caller on the fallback path rather than crashing the kernel.
func TestInRAMLeafRefusesBadImage(t *testing.T) {
	k := NewKernel()
	// empty list, a byte out of 0..255, and a wrong arg kind all refuse.
	cases := []string{
		`(jit_leaf_inram (list) 5)`,
		`(jit_leaf_inram (list 999) 5)`,
		`(jit_leaf_inram (list 1 2 3) "x")`,
	}
	for _, src := range cases {
		got := k.walk(readRootFromSource(k, src), NewFrame(nil))
		if got.Kind != VNull {
			t.Fatalf("%s: want null refusal, got %v", src, got)
		}
	}
}
