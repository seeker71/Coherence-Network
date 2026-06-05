// jit_value_test.go — the Value-typed JIT returns the walker's answer.
//
// Proves the general unlock: a recipe with a STRING argument and three native
// calls (str_len, char_at, ord) plus self-recursion compiles to a native Go
// plugin (jit_compile_value) and evaluates to the exact value the walker
// produces. This is the shape the int64 JIT refuses (non-int args → fallback);
// here it runs native. The verdict is 5 only when the compile actually
// happened (compiled == 1) AND every walked/jitted/edge answer matches — so a
// silent fallback to the walker fails the test rather than passing quietly.

package main

import "testing"

func TestValueJITMatchesWalker(t *testing.T) {
	// The plugin imports form-kernel-go/core via a replace directive; point
	// it at this package's own source tree (cwd during `go test`).
	t.Setenv("FORM_KERNEL_SRC", ".")

	src := `
(defn sumcp (s i acc)
  (if (ge i (str_len s))
      acc
      (sumcp s (add i 1) (add acc (ord (char_at s i))))))
(do
  (let walked (sumcp "ABC" 0 0))
  (let compiled (jit_compile_value "sumcp"))
  (let jitted (sumcp "ABC" 0 0))
  (let edge_empty (sumcp "" 0 0))
  (let edge_one (sumcp "z" 0 0))
  (add (if (eq walked 198) 1 0)
    (add (if (eq compiled 1) 1 0)
      (add (if (eq jitted 198) 1 0)
        (add (if (eq edge_empty 0) 1 0)
             (if (eq edge_one 122) 1 0))))))
`
	k := NewKernel()
	root := readRootFromSource(k, src)
	env := NewFrame(nil)
	result := k.walk(root, env)
	if result.Kind != VInt || result.Int != 5 {
		t.Fatalf("value-JIT band: want VInt 5 (compile happened + all answers match), got %v", result)
	}
}
