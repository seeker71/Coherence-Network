//go:build darwin && arm64 && cgo

// jit_dylib_test.go — the recipe-as-dylib path proven end to end, zero clang:
// the Form emitter (form-macho's mo-object-sym, four-way in
// tests/recipe-dylib-band.fk) produces a Mach-O .o carrying only the lo-compile
// recipe and exporting _recipe; `ld -dylib` links+signs it into a tiny
// dlopen-able binary; the kernel's dylib_call native loads it and calls the
// recipe. Emitter (Form) and loader (host dlopen) meet on one object file.

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// emitRecipeObject runs form-macho over the lo-compile recipe (f(n)=n*3+7) and
// returns the Mach-O .o byte image exporting _recipe.
func emitRecipeObject(t *testing.T) []byte {
	t.Helper()
	stdlib := filepath.Join("..", "form-stdlib")
	preludes := readFiles(t,
		filepath.Join(stdlib, "form-asm.fk"),
		filepath.Join(stdlib, "form-lower.fk"),
		filepath.Join(stdlib, "form-macho.fk"),
	)
	// _recipe = 95 114 101 99 105 112 101
	src := preludes + `
(do
  (let prog (list (list 1 7) (list 2) (list 1 3) (list 5 1 2) (list 3 3 0)))
  (let code (lo-compile-fn prog 4))
  (mo-object-sym code (list 95 114 101 99 105 112 101)))`
	k := NewKernel()
	res := k.walk(readRootFromSource(k, src), NewFrame(nil))
	if res.Kind != VList {
		t.Fatalf("mo-object-sym did not return a byte list (kind %v)", res.Kind)
	}
	out := make([]byte, len(res.List))
	for i, b := range res.List {
		if b.Kind != VInt || b.Int < 0 || b.Int > 255 {
			t.Fatalf("object byte %d not a 0..255 int: %v", i, b)
		}
		out[i] = byte(b.Int)
	}
	return out
}

func TestRecipeDylibLoadsAndCalls(t *testing.T) {
	ld, err := exec.LookPath("ld")
	if err != nil {
		t.Skip("ld not available — recipe-dylib link step needs the system linker")
	}
	sdkOut, err := exec.Command("xcrun", "--sdk", "macosx", "--show-sdk-path").Output()
	if err != nil {
		t.Skip("macOS SDK not available")
	}
	sdk := strings.TrimSpace(string(sdkOut))

	obj := emitRecipeObject(t)
	dir := t.TempDir()
	oPath := filepath.Join(dir, "recipe.o")
	if err := os.WriteFile(oPath, obj, 0o644); err != nil {
		t.Fatal(err)
	}
	dylibPath := filepath.Join(dir, "librecipe.dylib")

	// ld -dylib links the Form .o into a dlopen-able dylib and ad-hoc signs it
	// (the macOS arm64 signing requirement) — no clang, the same linker the
	// executable floor already uses.
	cmd := exec.Command(ld, "-dylib", "-arch", "arm64",
		"-platform_version", "macos", "11.0", "11.0",
		"-o", dylibPath, oPath,
		"-lSystem", "-L", filepath.Join(sdk, "usr/lib"), "-syslibroot", sdk)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("ld -dylib failed: %v\n%s", err, out)
	}

	// Call the recipe through the kernel's dylib_call native: emit (Form) ->
	// ld -dylib -> dlopen+dlsym+call (host). f(n) = n*3 + 7.
	for _, tc := range []struct{ arg, want int64 }{{5, 22}, {0, 7}, {10, 37}, {100, 307}} {
		src := fmt.Sprintf(`(dylib_call "%s" "recipe" %d)`, dylibPath, tc.arg)
		k := NewKernel()
		got := k.walk(readRootFromSource(k, src), NewFrame(nil))
		if got.Kind != VInt || got.Int != tc.want {
			t.Fatalf("dylib_call recipe(%d) = %v, want %d (n*3+7)", tc.arg, got, tc.want)
		}
	}
}

// TestDylibCallRefusesMissing — a missing library or symbol answers null (never
// crashes), so the caller stays on the fallback path.
func TestDylibCallRefusesMissing(t *testing.T) {
	k := NewKernel()
	for _, src := range []string{
		`(dylib_call "/nonexistent/path.dylib" "recipe" 5)`,
		`(dylib_call "/usr/lib/libSystem.B.dylib" "no_such_symbol_xyz" 5)`,
	} {
		got := k.walk(readRootFromSource(k, src), NewFrame(nil))
		if got.Kind != VNull {
			t.Fatalf("%s: want null refusal, got %v", src, got)
		}
	}
}
