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

import (
	"os"
	"strings"
	"testing"
	"time"
)

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

func TestJITNestedDefnLift(t *testing.T) {
	// A capture-free nested defn lifts as a plan-level sibling helper; a
	// nested defn reading an outer local keeps the documented
	// closures-over-outer refusal. Both bodies still walk to the same answer.
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	src := `
(defn outer (n) (do (defn inner (x) (mul x x)) (add (inner n) 1)))
(defn capouter (n) (do (defn capinner (x) (add x n)) (capinner 3)))
(do
  (let compiled (jit_compile "outer"))
  (let refused (jit_compile "capouter"))
  (list compiled refused (outer 5) (capouter 5)))
`
	k := NewKernel()
	root := readRootFromSource(k, src)
	env := NewFrame(nil)
	result := k.walk(root, env)
	if result.Kind != VList || len(result.List) != 4 {
		t.Fatalf("want 4-list, got %v", result)
	}
	compiled, refused, lifted, walked := result.List[0], result.List[1], result.List[2], result.List[3]
	if compiled.Kind != VInt || compiled.Int != 1 {
		t.Fatalf("jit_compile outer: capture-free nested defn must compile, got %v", compiled)
	}
	if refused.Kind != VInt || refused.Int != 0 {
		t.Fatalf("jit_compile capouter: capturing nested defn must refuse, got %v", refused)
	}
	if lifted.Kind != VInt || lifted.Int != 26 {
		t.Fatalf("outer 5 through the lifted helper: want 26, got %v", lifted)
	}
	if walked.Kind != VInt || walked.Int != 8 {
		t.Fatalf("capouter 5 on the walker: want 8, got %v", walked)
	}
	v, ok := env.Lookup(k.internName("outer"))
	if !ok || v.Kind != VClosure {
		t.Fatal("outer closure missing from top-level env")
	}
	jc := k.jitCompiledGo[nodeIDKey(v.Cl.Body)]
	if jc == nil || jc.I64 == nil {
		t.Fatal("typed i64 ABI missing for the nested-defn body")
	}
	cv, ok := env.Lookup(k.internName("capouter"))
	if !ok || cv.Kind != VClosure {
		t.Fatal("capouter closure missing from top-level env")
	}
	if reason := k.jitFailedReason[cv.Cl.Body]; !strings.Contains(reason, "captures outer local") {
		t.Fatalf("capturing nested defn must refuse with the closures-over-outer message, got %q", reason)
	}
}

func TestJITDiskCacheSkipsRebuild(t *testing.T) {
	// Same program, fresh kernel: the second compile must take the
	// plugin.Open path off the durable artifact without invoking go build.
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	src := `
(defn triple (n) (mul n 3))
(do (let compiled (jit_compile "triple")) (list compiled (triple 7)))
`
	run := func(k *Kernel) *Frame {
		root := readRootFromSource(k, src)
		env := NewFrame(nil)
		result := k.walk(root, env)
		if result.Kind != VList || len(result.List) != 2 {
			t.Fatalf("want 2-list, got %v", result)
		}
		if result.List[0].Int != 1 || result.List[1].Int != 21 {
			t.Fatalf("want compiled=1 triple(7)=21, got %v / %v", result.List[0], result.List[1])
		}
		return env
	}
	k1 := NewKernel()
	env1 := run(k1)
	v, ok := env1.Lookup(k1.internName("triple"))
	if !ok || v.Kind != VClosure {
		t.Fatal("triple closure missing from top-level env")
	}
	em, err := jitEmitClosureGo(k1, v.Cl)
	if err != nil {
		t.Fatalf("emit: %v", err)
	}
	so := jitPluginCachePath(em.cacheKey)
	if so == "" {
		t.Fatal("durable cache path unavailable")
	}
	if _, err := os.Stat(so); err != nil {
		t.Fatalf("artifact missing from disk cache after compile: %v", err)
	}
	before := jitGoBuildCount.Load()
	run(NewKernel())
	if after := jitGoBuildCount.Load(); after != before {
		t.Fatalf("warm cache key must not invoke go build: count %d -> %d", before, after)
	}
}

func TestJITAsyncHotThresholdBuild(t *testing.T) {
	// The hot crossing answers interpreted immediately; the build runs on a
	// goroutine, lands in the async zone, and a later call adopts + dispatches
	// the native artifact.
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	src := `
(defn hotsum (i acc) (if (le i 0) acc (hotsum (sub i 1) (add acc i))))
(hotsum 2500 0)
`
	k := NewKernel()
	root := readRootFromSource(k, src)
	env := NewFrame(nil)
	result := k.walk(root, env)
	if result.Kind != VInt || result.Int != 3126250 {
		t.Fatalf("crossing call must answer interpreted: want 3126250, got %v", result)
	}
	v, ok := env.Lookup(k.internName("hotsum"))
	if !ok || v.Kind != VClosure {
		t.Fatal("hotsum closure missing from top-level env")
	}
	bodyKey := nodeIDKey(v.Cl.Body)
	deadline := time.Now().Add(180 * time.Second)
	for k.jitCompiledGo[bodyKey] == nil {
		k.jitAsyncMu.Lock()
		_, landed := k.jitAsyncLanded[bodyKey]
		k.jitAsyncMu.Unlock()
		if landed {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("async build never landed")
		}
		time.Sleep(25 * time.Millisecond)
	}
	callRoot := readRootFromSource(k, "(hotsum 3 0)")
	first := k.walk(callRoot, env)  // adopts the landed artifact
	second := k.walk(callRoot, env) // dispatches the native
	if first.Int != 6 || second.Int != 6 {
		t.Fatalf("hotsum 3: want 6 before and after the swap, got %v / %v", first, second)
	}
	if k.jitFailed[v.Cl.Body] {
		t.Fatalf("async build marked failed: %s", k.jitFailedReason[v.Cl.Body])
	}
	jc := k.jitCompiledGo[bodyKey]
	if jc == nil || jc.I64 == nil {
		t.Fatal("typed i64 artifact not adopted after the async build landed")
	}
	if k.jitDispatchHits[v.Cl.Body] == 0 {
		t.Fatal("no native dispatch after adoption")
	}
}
