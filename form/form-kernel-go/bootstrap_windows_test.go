//go:build windows

// bootstrap_windows_test.go - minimal Windows host exe over swappable Form DLLs.
//
// The exe is not the destination; it is the smallest replaceable host surface.
// It loads a DLL entrypoint and calls it. The DLLs in this test are emitted from
// Form PE/COFF objects, linked with lld-link/link, then swapped behind the same
// exported symbol.

package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func windowsCCompiler(t *testing.T) string {
	t.Helper()
	for _, name := range []string{"gcc", "clang"} {
		if p, err := exec.LookPath(name); err == nil {
			return p
		}
	}
	for _, p := range []string{
		filepath.Join(`C:\TDM-GCC-64\bin`, "gcc.exe"),
		filepath.Join(`C:\Program Files\LLVM\bin`, "clang.exe"),
	} {
		if fileExists(p) {
			return p
		}
	}
	t.Skip("gcc/clang not available - Windows bootstrap host exe needs a C compiler carrier")
	return ""
}

func buildWindowsBootstrapHost(t *testing.T, dir string) string {
	t.Helper()
	src := filepath.Join("..", "native", "windows", "bootstrap", "form_bootstrap_host.c")
	exe := filepath.Join(dir, "form-bootstrap-host.exe")
	cmd := exec.Command(windowsCCompiler(t), src, "-O2", "-o", exe)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("Windows bootstrap host compile failed: %v\n%s", err, out)
	}
	return exe
}

func runBootstrapHost(t *testing.T, exe, dll, sym string, arg int64) int64 {
	t.Helper()
	cmd := exec.Command(exe, dll, sym, strconv.FormatInt(arg, 10))
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("bootstrap host call failed: %v\n%s", err, out)
	}
	got, err := strconv.ParseInt(strings.TrimSpace(string(out)), 10, 64)
	if err != nil {
		t.Fatalf("bootstrap host returned non-i64 output %q: %v", out, err)
	}
	return got
}

func TestWindowsBootstrapHostExeLoadsAndSwapsFormDLLs(t *testing.T) {
	linker := windowsLinker(t)
	dir := t.TempDir()
	exe := buildWindowsBootstrapHost(t, dir)
	dllA := linkWindowsRecipeDLL(t, linker, dir, "bootstrap_recipe_a", emitWindowsRecipeObject(t, "WindowsX64RecipeEmitter_code_mul3_add7"))
	dllB := linkWindowsRecipeDLL(t, linker, dir, "bootstrap_recipe_b", emitWindowsRecipeObject(t, "WindowsX64RecipeEmitter_code_mul5_add1"))

	for _, tc := range []struct {
		dll  string
		arg  int64
		want int64
	}{
		{dllA, 5, 22},
		{dllA, 100, 307},
		{dllB, 5, 26},
		{dllB, 10, 51},
		{dllA, 5, 22},
	} {
		if got := runBootstrapHost(t, exe, tc.dll, "recipe", tc.arg); got != tc.want {
			t.Fatalf("bootstrap host recipe(%d) = %d, want %d", tc.arg, got, tc.want)
		}
	}

	cmd := exec.Command(exe)
	cmd.Env = append(os.Environ(),
		"FORM_BOOTSTRAP_DLL="+filepath.FromSlash(dllB),
		"FORM_BOOTSTRAP_SYMBOL=recipe",
		"FORM_BOOTSTRAP_ARG=7",
	)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("bootstrap host env call failed: %v\n%s", err, out)
	}
	if strings.TrimSpace(string(out)) != "36" {
		t.Fatalf("bootstrap host env call = %q, want 36", out)
	}
}
