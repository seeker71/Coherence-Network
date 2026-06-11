// jit_test.go — the typed i64 JIT ABI is built and carries recursion natively.
//
// Regression ground: the Value-ABI pre-filter (jitRecipeNeedsValueABI) once
// treated the recipe's structural name slots — an IDENT's name child, an
// FNCALL's static callee, a LET's binding name — as runtime string values.
// Every real body contains one of those, so every compile was forced onto
// the boxed Value-only ABI: jc.I64 stayed nil and recursive int workloads
// ran at walker speed (fib 38 ≈ 8s where the realized i64 native is ~0.13s).
// These tests pin both halves: the pre-filter classification and the actual
// i64 artifact + single-dispatch realization.

package main

import "testing"

func TestJITValueABIPreFilterSkipsNameSlots(t *testing.T) {
	k := NewKernel()
	root := readRootFromSource(k, `(do
  (defn fib (n) (if (lt n 2) n (add (fib (sub n 1)) (fib (sub n 2)))))
  (defn withlet (a) (do (let b (mul a 2)) (add a b)))
  (defn slen (s) (str_len s))
  0)`)
	env := NewFrame(nil)
	k.walk(root, env)

	body := func(name string) NodeID {
		v, ok := env.Lookup(k.internName(name))
		if !ok || v.Kind != VClosure {
			t.Fatalf("%s closure missing from top-level env", name)
		}
		return v.Cl.Body
	}
	if jitRecipeNeedsValueABI(k, body("fib")) {
		t.Fatal("pure-int recursive body classified as Value-only: name slots are structure, not string values")
	}
	if jitRecipeNeedsValueABI(k, body("withlet")) {
		t.Fatal("let-binding body classified as Value-only: the binding-name slot is structure")
	}
	if !jitRecipeNeedsValueABI(k, body("slen")) {
		t.Fatal("string-op body must keep the Value-only ABI")
	}
}

func TestIntJITTypedDispatchCarriesRecursion(t *testing.T) {
	// fib 14 walks 1219 calls — under the auto-compile hot threshold, so the
	// baseline stays a pure walk and jit_compile below does the only build.
	src := `
(defn fib (n) (if (lt n 2) n (add (fib (sub n 1)) (fib (sub n 2)))))
(do
  (let walked (fib 14))
  (let compiled (jit_compile "fib"))
  (let jitted (fib 14))
  (list walked compiled jitted))
`
	k := NewKernel()
	root := readRootFromSource(k, src)
	env := NewFrame(nil)
	result := k.walk(root, env)
	if result.Kind != VList || len(result.List) != 3 {
		t.Fatalf("want 3-list, got %v", result)
	}
	walked, compiled, jitted := result.List[0], result.List[1], result.List[2]
	if compiled.Kind != VInt || compiled.Int != 1 {
		t.Fatalf("jit_compile fib: want 1, got %v", compiled)
	}
	if walked.Kind != VInt || walked.Int != 377 || jitted.Kind != VInt || jitted.Int != 377 {
		t.Fatalf("fib 14: want 377 walked and jitted, got %v / %v", walked, jitted)
	}
	v, ok := env.Lookup(k.internName("fib"))
	if !ok || v.Kind != VClosure {
		t.Fatal("fib closure missing from top-level env")
	}
	jc := k.jitCompiledGo[nodeIDKey(v.Cl.Body)]
	if jc == nil || jc.I64 == nil {
		t.Fatal("typed i64 ABI missing — recursive int calls would run boxed at walker speed")
	}
	if hits := k.jitDispatchHits[v.Cl.Body]; hits != 1 {
		t.Fatalf("native must carry the whole recursion in one crossing: want 1 dispatch hit, got %d", hits)
	}
}

func TestIntJITModRecipeBuildsTypedABI(t *testing.T) {
	// mod has no f64 leg (Go lacks float %, and the walker's float mod is
	// floor-mod); the f64 refusal must skip that leg without poisoning the
	// combined plugin build, so i64 still carries the int shape natively.
	src := `
(defn collatzlen (n acc)
  (if (le n 1) acc
      (if (eq (mod n 2) 0)
          (collatzlen (div n 2) (add acc 1))
          (collatzlen (add (mul n 3) 1) (add acc 1)))))
(do
  (let compiled (jit_compile "collatzlen"))
  (list compiled (collatzlen 27 0)))
`
	k := NewKernel()
	root := readRootFromSource(k, src)
	env := NewFrame(nil)
	result := k.walk(root, env)
	if result.Kind != VList || len(result.List) != 2 {
		t.Fatalf("want 2-list, got %v", result)
	}
	compiled, jitted := result.List[0], result.List[1]
	if compiled.Kind != VInt || compiled.Int != 1 {
		t.Fatalf("jit_compile collatzlen: want 1, got %v", compiled)
	}
	if jitted.Kind != VInt || jitted.Int != 111 {
		t.Fatalf("collatzlen 27: want 111, got %v", jitted)
	}
	v, ok := env.Lookup(k.internName("collatzlen"))
	if !ok || v.Kind != VClosure {
		t.Fatal("collatzlen closure missing from top-level env")
	}
	jc := k.jitCompiledGo[nodeIDKey(v.Cl.Body)]
	if jc == nil || jc.I64 == nil {
		t.Fatal("typed i64 ABI missing for mod-using int recipe")
	}
	if jc.F64 != nil {
		t.Fatal("f64 leg must refuse float mod rather than emit invalid Go")
	}
}
