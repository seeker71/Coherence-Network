// numeric_bench.go — three-workload format-recipe arithmetic bench.
//
// Same shape as experiments/form-kernel-ts/src/numeric-bench.ts:
//   - fp64 sum         (arithmetic-hint = native-fp)
//   - fp8 sum          (arithmetic-hint = table-lookup-via-fp32, fp32 narrow)
//   - bitnet ternary   (arithmetic-hint = native-int)
//
// Each workload runs three paths:
//   1. Native Go arithmetic — reference, no dispatch
//   2. Pass 0  — generic dispatcher (applyArith) per op
//   3. Pass 1  — per-(format, op) cached closure from FormatTable
//
// The TS bench also has Pass 2 (recipe-driven full-function codegen via
// `new Function`). Go doesn't have an equivalent runtime-JIT story; the
// closest analogue would be writing source to a .go file, invoking the
// Go compiler, and dlopen-loading the result — outside the scope of
// "kernel reads format-recipes" for v0. The Pass 0/Pass 1 arc covers
// the architectural claim: format-recipe dispatch pays a constant
// overhead, and the cache closes most of the gap.

package main

import (
	"fmt"
	"os"
	"time"
)

// opaqueNumeric — //go:noinline barrier identical to the bench.ts
// `opaque` trick. Keeps Go's compiler from folding constant-input
// recursive calls and making "native" measure register loads.
//
//go:noinline
func opaqueNumeric(n int64) int64 { return n }

// ── Native references ───────────────────────────────────────────────────

func nativeFp64Sum(n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	return nativeFp64Sum(float64(opaqueNumeric(int64(n))-1), acc+n*0.5)
}

func nativeFp8Sum(n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	x := float64(float32(n * 0.0625))
	return nativeFp8Sum(float64(opaqueNumeric(int64(n))-1), float64(float32(acc+x)))
}

func nativeBitnetDot(n, acc int64) int64 {
	if n == 0 {
		return acc
	}
	t := ((n * 13) % 3) - 1
	return nativeBitnetDot(opaqueNumeric(n-1), opaqueNumeric(acc+t))
}

// ── Pass 0 — generic applyArith dispatcher ─────────────────────────────

func pass0Fp64Sum(fmt *FormatRecipe, n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	x := applyArith(fmt, ArithOpMul, NV_F(n), NV_F(0.5))
	acc2 := applyArith(fmt, ArithOpAdd, NV_F(acc), x)
	return pass0Fp64Sum(fmt, float64(opaqueNumeric(int64(n))-1), acc2.AsFloat())
}

func pass0Fp8Sum(fmt *FormatRecipe, n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	x := applyArith(fmt, ArithOpMul, NV_F(n), NV_F(0.0625))
	acc2 := applyArith(fmt, ArithOpAdd, NV_F(acc), x)
	return pass0Fp8Sum(fmt, float64(opaqueNumeric(int64(n))-1), acc2.AsFloat())
}

func pass0BitnetDot(fmt *FormatRecipe, n, acc int64) int64 {
	if n == 0 {
		return acc
	}
	t := ((n * 13) % 3) - 1
	acc2 := applyArith(fmt, ArithOpAdd, NV_I(acc), NV_I(t))
	return pass0BitnetDot(fmt, opaqueNumeric(n-1), acc2.AsInt64())
}

// ── Pass 1 — cached per-(format, op) closures ──────────────────────────

func pass1Fp64Sum(add, mul NumHandler, n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	x := mul(NV_F(n), NV_F(0.5))
	acc2 := add(NV_F(acc), x)
	return pass1Fp64Sum(add, mul, float64(opaqueNumeric(int64(n))-1), acc2.AsFloat())
}

func pass1Fp8Sum(add, mul NumHandler, n, acc float64) float64 {
	if n == 0 {
		return acc
	}
	x := mul(NV_F(n), NV_F(0.0625))
	acc2 := add(NV_F(acc), x)
	return pass1Fp8Sum(add, mul, float64(opaqueNumeric(int64(n))-1), acc2.AsFloat())
}

func pass1BitnetDot(add NumHandler, n, acc int64) int64 {
	if n == 0 {
		return acc
	}
	t := ((n * 13) % 3) - 1
	acc2 := add(NV_I(acc), NV_I(t))
	return pass1BitnetDot(add, opaqueNumeric(n-1), acc2.AsInt64())
}

// ── Driver ──────────────────────────────────────────────────────────────

type benchRow struct {
	name             string
	native, p0, p1   time.Duration
}

func timeNs(iters int, fn func()) time.Duration {
	start := time.Now()
	for i := 0; i < iters; i++ {
		fn()
	}
	return time.Since(start) / time.Duration(iters)
}

func runRow(
	name string,
	native func(), nativeIters int,
	pass0 func(), pass0Iters int,
	pass1 func(), pass1Iters int,
) benchRow {
	// Warmup
	native()
	pass0()
	pass1()
	return benchRow{
		name:   name,
		native: timeNs(nativeIters, native),
		p0:     timeNs(pass0Iters, pass0),
		p1:     timeNs(pass1Iters, pass1),
	}
}

func formatDur(d time.Duration) string {
	switch {
	case d < time.Microsecond:
		return fmt.Sprintf("%d ns", d.Nanoseconds())
	case d < time.Millisecond:
		return fmt.Sprintf("%.2f µs", float64(d.Nanoseconds())/1000.0)
	case d < time.Second:
		return fmt.Sprintf("%.2f ms", float64(d.Nanoseconds())/1_000_000.0)
	}
	return fmt.Sprintf("%.2f s", d.Seconds())
}

// runNumericBench — fp64 / fp8 / bitnet × native / Pass 0 / Pass 1.
//
// Output mirrors the TS bench's column layout (minus Pass 2). Runs each
// inner loop multiple times so variance is averaged into the reported µs.
func runNumericBench() {
	k := NewKernel()
	lib, err := BuildFormatLibrary(k)
	if err != nil {
		fmt.Fprintf(os.Stderr, "BuildFormatLibrary: %v\n", err)
		return
	}
	table := NewFormatTable()
	table.RegisterAll(lib)

	fp64 := lib.FP64
	fp8 := lib.FP8E4M3
	bitnet := lib.Bitnet158

	fp64Add := table.Handler(table.Register(fp64), ArithOpAdd)
	fp64Mul := table.Handler(table.Register(fp64), ArithOpMul)
	fp8Add := table.Handler(table.Register(fp8), ArithOpAdd)
	fp8Mul := table.Handler(table.Register(fp8), ArithOpMul)
	bitnetAdd := table.Handler(table.Register(bitnet), ArithOpAdd)

	const N = 1000

	rowFp64 := runRow("fp64",
		func() { nativeFp64Sum(N, 0) }, 50000,
		func() { pass0Fp64Sum(fp64, N, 0) }, 1000,
		func() { pass1Fp64Sum(fp64Add, fp64Mul, N, 0) }, 50000,
	)
	rowFp8 := runRow("fp8",
		func() { nativeFp8Sum(N, 0) }, 50000,
		func() { pass0Fp8Sum(fp8, N, 0) }, 1000,
		func() { pass1Fp8Sum(fp8Add, fp8Mul, N, 0) }, 50000,
	)
	rowBitnet := runRow("bitnet",
		func() { nativeBitnetDot(N, 0) }, 50000,
		func() { pass0BitnetDot(bitnet, N, 0) }, 1000,
		func() { pass1BitnetDot(bitnetAdd, N, 0) }, 50000,
	)

	rows := []benchRow{rowFp64, rowFp8, rowBitnet}

	fmt.Printf("%-10s %-12s %-14s %-9s %-14s %s\n",
		"format", "native", "pass0(naïve)", "p0-over", "pass1(cached)", "p1-over")
	for _, r := range rows {
		p0Over := float64(r.p0.Nanoseconds()) / float64(r.native.Nanoseconds())
		p1Over := float64(r.p1.Nanoseconds()) / float64(r.native.Nanoseconds())
		fmt.Printf("%-10s %-12s %-14s %-9s %-14s %.2f×\n",
			r.name,
			formatDur(r.native),
			formatDur(r.p0),
			fmt.Sprintf("%.2f×", p0Over),
			formatDur(r.p1),
			p1Over,
		)
	}
}
