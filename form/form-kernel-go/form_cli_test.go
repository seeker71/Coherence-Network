// form_cli_test.go — the native form-cli runs on the emitted walker (fkwu).
//
// Proof that the headless form-cli front door is real and DETERMINISTIC: the
// command arrives staged in fk_src (fkwu's argv[3], the input_byte channel),
// form-cli-main.fk reads it byte-by-byte and dispatches via fc-respond (the
// four-way-proven brain), and fkwu prints the response string natively through
// fk_pv_root/fk_psv. Output is a pure function of input — fixed command in,
// fixed response out — so it is testable by staging bytes and reading stdout.
// This is the same fks-table flatten + FkwuEvalWithInput path the bridge proof
// uses; the reliable harness, not the standalone bash flatten.
package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestFkwuFormCli(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	shim := filepath.Join(stdlib, "fourth-shim.fk")
	core := filepath.Join(stdlib, "core.fk")
	cli := filepath.Join(stdlib, "form-cli.fk")
	mainCli := filepath.Join(stdlib, "form-cli-main.fk")

	dir := t.TempDir()
	fkwuBin := buildFkwu(t, clang, dir, minimal, hatiKernel, hatiEmit)

	// Flatten form-cli-main (preludes: shim + core + form-cli, band: the runtime
	// entry) to a string-pool node table — the fks path that carries strings.
	mods := `(list (read_file "` + shim + `") (read_file "` + core + `") (read_file "` + cli + `"))`
	band := `(read_file "` + mainCli + `")`
	flattenExpr := "(fks-table-file " +
		"(flt-band-sources-fns " + mods + " " + band + ") " +
		"(flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
	if len(strings.TrimSpace(table)) < 100 {
		t.Fatalf("form-cli flatten produced suspiciously small table (%d bytes)", len(table))
	}
	tablePath := filepath.Join(dir, "form-cli-table.txt")
	if err := os.WriteFile(tablePath, []byte(table), 0o644); err != nil {
		t.Fatalf("write table: %v", err)
	}

	// The dispatch is deterministic: each staged command yields exactly one
	// response. fc-read stops at NUL/newline, so the verb routing is what fkwu
	// proves end-to-end against the staged fk_src bytes.
	cases := []struct {
		cmd  string
		want string
	}{
		{"ping", "pong"},
		{"help", "form-cli (native/fkwu): ping | help | version | <verb> ..."},
		{"version", "form-cli native 0.1 - running on the emitted walker (fkwu)"},
		{"ping extra", "pong"},
		{"foobar", "form-cli: unknown verb foobar"},
	}
	for _, c := range cases {
		got, err := FkwuEvalWithInput(fkwuBin, tablePath, 0, []byte(c.cmd))
		if err != nil {
			t.Fatalf("FkwuEvalWithInput(%q): %v", c.cmd, err)
		}
		if got != c.want {
			t.Fatalf("form-cli on fkwu: cmd %q -> fkwu=%q want=%q", c.cmd, got, c.want)
		}
	}
}
