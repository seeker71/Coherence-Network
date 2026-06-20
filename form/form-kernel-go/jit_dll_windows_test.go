//go:build windows

// jit_dll_windows_test.go - Windows recipe-as-DLL path.
//
// The Form emitter creates a PE/COFF x64 object carrying only a recipe symbol.
// lld-link links that object into a DLL, and the kernel's dylib_call native
// loads/calls it through LoadLibrary/GetProcAddress. Two DLLs with the same
// exported symbol prove the runtime can swap the loaded recipe implementation.

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func windowsLinker(t *testing.T) string {
	t.Helper()
	if p, err := exec.LookPath("lld-link"); err == nil {
		return p
	}
	if p := filepath.Join(`C:\Program Files\LLVM\bin`, "lld-link.exe"); fileExists(p) {
		return p
	}
	if p, err := exec.LookPath("link"); err == nil {
		return p
	}
	t.Skip("lld-link/link not available - Windows recipe DLL link step needs a host linker carrier")
	return ""
}

func fileExists(path string) bool {
	st, err := os.Stat(path)
	return err == nil && !st.IsDir()
}

func emitWindowsRecipeObject(t *testing.T, fn string) []byte {
	t.Helper()
	stdlib := filepath.Join("..", "form-stdlib")
	preludes := readFiles(t,
		filepath.Join(stdlib, "form-pe-coff.fk"),
	)
	src := fmt.Sprintf(`%s
(do
  (pe-recipe-object (%s)))`, preludes, fn)
	k := NewKernel()
	res := k.walk(readRootFromSource(k, src), NewFrame(nil))
	if res.Kind != VList {
		t.Fatalf("pe-recipe-object did not return a byte list (kind %v)", res.Kind)
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

func linkWindowsRecipeDLL(t *testing.T, linker, dir, name string, obj []byte) string {
	t.Helper()
	oPath := filepath.Join(dir, name+".obj")
	dllPath := filepath.Join(dir, name+".dll")
	if err := os.WriteFile(oPath, obj, 0o644); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command(linker,
		"/dll",
		"/noentry",
		"/machine:x64",
		"/export:recipe",
		"/out:"+dllPath,
		oPath,
	)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("Windows recipe DLL link failed: %v\n%s", err, out)
	}
	return filepath.ToSlash(dllPath)
}

func callRecipeDLL(t *testing.T, dllPath string, arg int64) Value {
	t.Helper()
	src := fmt.Sprintf(`(dylib_call "%s" "recipe" %d)`, strings.ReplaceAll(dllPath, `"`, `\"`), arg)
	k := NewKernel()
	return k.walk(readRootFromSource(k, src), NewFrame(nil))
}

func TestWindowsRecipeDLLLoadsCallsAndSwaps(t *testing.T) {
	linker := windowsLinker(t)
	dir := t.TempDir()

	dllA := linkWindowsRecipeDLL(t, linker, dir, "recipe_a", emitWindowsRecipeObject(t, "pe-x64-recipe-mul3-add7-code"))
	dllB := linkWindowsRecipeDLL(t, linker, dir, "recipe_b", emitWindowsRecipeObject(t, "pe-x64-recipe-mul5-add1-code"))

	for _, tc := range []struct {
		dll  string
		arg  int64
		want int64
	}{
		{dllA, 0, 7},
		{dllA, 5, 22},
		{dllA, 100, 307},
		{dllB, 5, 26},
		{dllB, 10, 51},
		{dllA, 5, 22},
	} {
		got := callRecipeDLL(t, tc.dll, tc.arg)
		if got.Kind != VInt || got.Int != tc.want {
			t.Fatalf("dylib_call %s recipe(%d) = %v, want %d", tc.dll, tc.arg, got, tc.want)
		}
	}
}

func TestWindowsDylibCallRefusesMissing(t *testing.T) {
	k := NewKernel()
	for _, src := range []string{
		`(dylib_call "C:/no/such/recipe.dll" "recipe" 5)`,
		`(dylib_call "C:/Windows/System32/kernel32.dll" "no_such_symbol_xyz" 5)`,
	} {
		got := k.walk(readRootFromSource(k, src), NewFrame(nil))
		if got.Kind != VNull {
			t.Fatalf("%s: want null refusal, got %v", src, got)
		}
	}
}
