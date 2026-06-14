// fkwu_bridge_test.go — proves the offload bridge end to end.
//
// The Go kernel emits + compiles fkwu in-process, flattens a real four-way band
// (content-address) to a node-table, hands the table to fkwu via FkwuEval, and
// confirms fkwu's value equals the in-process walker's. This is the carrier ->
// fkwu -> value loop the offload path needs, proven on a band already in the
// fourth-arm manifest.
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

func TestFkwuOffloadBridge(t *testing.T) {
	clang, err := exec.LookPath("clang")
	if err != nil {
		t.Skip("clang not available — fkwu offload bridge proof skipped")
	}

	stdlib := filepath.Join("..", "form-stdlib")
	mustExist := func(p string) string {
		if _, err := os.Stat(p); err != nil {
			t.Skipf("missing source %s: %v", p, err)
		}
		return p
	}
	minimal := mustExist(filepath.Join(stdlib, "minimal-surface.fk"))
	hatiKernel := mustExist(filepath.Join(stdlib, "hati-os-kernel.fk"))
	hatiEmit := mustExist(filepath.Join(stdlib, "hati-os-kernel-emit.fk"))
	formParse := mustExist(filepath.Join(stdlib, "form-parse.fk"))
	formFlatten := mustExist(filepath.Join(stdlib, "form-flatten.fk"))
	shim := mustExist(filepath.Join(stdlib, "fourth-shim.fk"))
	band := mustExist(filepath.Join(stdlib, "tests", "content-address-band.fk"))

	dir := t.TempDir()

	// 1. Emit the universal fkwu C source in-process, then compile it.
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

	// 2. Flatten the band to a node-table in-process (fks: string-pool variant).
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

	// 3. The in-process walker's verdict for the same band — the truth fkwu must match.
	_, walked := runFormSource(t, readFiles(t, minimal, shim, band))
	want := strings.TrimSpace(walked)

	// 4. Offload to fkwu and confirm the value matches the walker.
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
