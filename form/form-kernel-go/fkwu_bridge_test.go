// fkwu_bridge_test.go — proves the offload bridge end to end.
//
// The Go kernel emits + compiles fkwu in-process, then proves two things the
// offload path needs, both against the emitted fourth kernel:
//   - TestFkwuOffloadBridge: the carrier->fkwu->value loop on a real four-way
//     band (content-address) matches the in-process walker bit-for-bit.
//   - TestFkwuOffloadInput: the structured-input channel — a program that reads
//     fk_src via fk-buf (here fkcount, which counts the staged bytes) returns a
//     value that DEPENDS on the bundle the carrier passes (argv[3] -> fk_src).
//
// Skips when clang is absent (the toolchain that builds fkwu) — the repo's
// runs-or-skips-when-tools-missing pattern, so the proof runs where the
// toolchain lives and stays green everywhere else.
package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// runFormSource walks concatenated Form source in-process and returns the
// result value's raw string (the .Str for a string value, else .String()).
func runFormSource(t *testing.T, src string) (Value, string) {
	t.Helper()
	k := NewKernel()
	root := readRootFromSource(k, src)
	result := k.walk(root, NewFrame(nil))
	if result.Kind == VStr {
		return result, result.Str
	}
	return result, result.String()
}

func readFiles(t *testing.T, paths ...string) string {
	t.Helper()
	var b strings.Builder
	for _, p := range paths {
		data, err := os.ReadFile(p)
		if err != nil {
			t.Fatalf("read %s: %v", p, err)
		}
		b.Write(data)
		b.WriteByte('\n')
	}
	return b.String()
}

// emitChain returns the three sources whose walk emits fkwu and carries the
// hati-os program/flatten surface (fkc-emit-universal, fkc-table-file,
// fkcount-fns), skipping the test if any is missing.
func emitChain(t *testing.T, stdlib string) (minimal, hatiKernel, hatiEmit string) {
	t.Helper()
	mustExist := func(p string) string {
		if _, err := os.Stat(p); err != nil {
			t.Skipf("missing source %s: %v", p, err)
		}
		return p
	}
	return mustExist(filepath.Join(stdlib, "minimal-surface.fk")),
		mustExist(filepath.Join(stdlib, "hati-os-kernel.fk")),
		mustExist(filepath.Join(stdlib, "hati-os-kernel-emit.fk"))
}

// buildFkwu emits the universal fkwu C source in-process and compiles it,
// returning the binary path. Requires clang.
func buildFkwu(t *testing.T, clang, dir, minimal, hatiKernel, hatiEmit string) string {
	t.Helper()
	_, cSrc := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit)+"\n(fkc-emit-universal)\n")
	if len(strings.TrimSpace(cSrc)) < 1000 {
		t.Fatalf("fkwu emit produced suspiciously small C source (%d bytes)", len(cSrc))
	}
	cPath := filepath.Join(dir, "fkwu.c")
	if err := os.WriteFile(cPath, []byte(cSrc), 0o644); err != nil {
		t.Fatalf("write fkwu.c: %v", err)
	}
	fkwuBin := filepath.Join(dir, "fkwu")
	if out, err := exec.Command(clang, "-O2", "-o", fkwuBin, cPath).CombinedOutput(); err != nil {
		t.Fatalf("clang fkwu: %v\n%s", err, out)
	}
	return fkwuBin
}

func requireClang(t *testing.T) string {
	t.Helper()
	clang, err := exec.LookPath("clang")
	if err != nil {
		t.Skip("clang not available — fkwu proof skipped")
	}
	return clang
}

func TestFkwuOffloadBridge(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	shim := filepath.Join(stdlib, "fourth-shim.fk")
	band := filepath.Join(stdlib, "tests", "content-address-band.fk")

	dir := t.TempDir()
	fkwuBin := buildFkwu(t, clang, dir, minimal, hatiKernel, hatiEmit)

	// Flatten the band to a node-table in-process (fks: string-pool variant).
	flattenExpr := "(fks-table-file " +
		"(flt-band-sources-fns (list (read_file \"" + shim + "\")) (read_file \"" + band + "\")) " +
		"(flt-band-sources-pool (list (read_file \"" + shim + "\")) (read_file \"" + band + "\")))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
	if len(strings.TrimSpace(table)) < 100 {
		t.Fatalf("flatten produced suspiciously small table (%d bytes)", len(table))
	}
	tablePath := filepath.Join(dir, "band-table.txt")
	if err := os.WriteFile(tablePath, []byte(table), 0o644); err != nil {
		t.Fatalf("write table: %v", err)
	}

	// The in-process walker's verdict for the same band — the truth fkwu must match.
	_, walked := runFormSource(t, readFiles(t, minimal, shim, band))
	want := strings.TrimSpace(walked)

	got, err := FkwuEval(fkwuBin, tablePath, 0)
	if err != nil {
		t.Fatalf("FkwuEval: %v", err)
	}
	if got != want {
		t.Fatalf("offload mismatch: fkwu=%q walker=%q (a divergence — one kernel is wrong)", got, want)
	}
	if got == "" {
		t.Fatal("offload produced empty verdict")
	}
}

func TestFkwuOffloadInput(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hatiEmit := emitChain(t, stdlib)

	dir := t.TempDir()
	fkwuBin := buildFkwu(t, clang, dir, minimal, hatiKernel, hatiEmit)

	// fkcount: a program that reads the staged input (fk_src) via fk-buf and
	// returns its byte count — the minimal input-dependent fourth-kernel program.
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit)+"\n(fkc-table-file (fkcount-fns))\n")
	if len(strings.TrimSpace(table)) < 20 {
		t.Fatalf("fkcount flatten produced suspiciously small table (%d bytes)", len(table))
	}
	tablePath := filepath.Join(dir, "fkcount-table.txt")
	if err := os.WriteFile(tablePath, []byte(table), 0o644); err != nil {
		t.Fatalf("write table: %v", err)
	}

	// The value fkwu returns must DEPEND on the bundle the carrier passes.
	cases := []struct {
		input []byte
		want  string
	}{
		{[]byte(""), "0"},
		{[]byte("hello world"), "11"},
		{[]byte("abcdefghijklmnopqrstuvwxyz"), "26"},
	}
	for _, c := range cases {
		got, err := FkwuEvalWithInput(fkwuBin, tablePath, 0, c.input)
		if err != nil {
			t.Fatalf("FkwuEvalWithInput(%q): %v", c.input, err)
		}
		if got != c.want {
			t.Fatalf("fk_src input channel: input %d bytes -> fkwu=%q want=%q", len(c.input), got, c.want)
		}
	}
}
