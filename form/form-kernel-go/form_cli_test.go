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
	"os/exec"
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

// TestFkwuFormCliRepl proves the INTERACTIVE TTY surface: form-cli-repl.fk loops
// over real fd 0 (read_line, tag 114), dispatches via fc-respond, and writes each
// response with print_str (tag 115). A REPL is deterministic — output is a pure
// function of the stdin bytes — so a fixed piped transcript yields a fixed
// response stream, asserted here. isatty (tag 116) keeps a piped session clean
// (no prompt). This is the fkwu-native interactive door, the twin of the headless
// fk_src door above; both call the same four-way-proven dispatch.
func TestFkwuFormCliRepl(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	shim := filepath.Join(stdlib, "fourth-shim.fk")
	core := filepath.Join(stdlib, "core.fk")
	cli := filepath.Join(stdlib, "form-cli.fk")
	repl := filepath.Join(stdlib, "form-cli-repl.fk")

	dir := t.TempDir()
	// the REPL rides the effect-only entry (fkc-emit-repl): walk fk_fn[0] for
	// effect, no root-value print, no arm-profile dump — so stdout is exactly the
	// responses the loop emits via print_str.
	_, cSrc := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit)+"\n(fkc-emit-repl)\n")
	cPath := filepath.Join(dir, "fkwu-repl.c")
	if err := os.WriteFile(cPath, []byte(cSrc), 0o644); err != nil {
		t.Fatalf("write fkwu-repl.c: %v", err)
	}
	fkwuBin := filepath.Join(dir, "fkwu-repl")
	if out, err := exec.Command(clang, "-O2", "-o", fkwuBin, cPath).CombinedOutput(); err != nil {
		t.Fatalf("clang fkwu-repl: %v\n%s", err, out)
	}

	mods := `(list (read_file "` + shim + `") (read_file "` + core + `") (read_file "` + cli + `"))`
	band := `(read_file "` + repl + `")`
	flattenExpr := "(fks-table-file " +
		"(flt-band-sources-fns " + mods + " " + band + ") " +
		"(flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
	if len(strings.TrimSpace(table)) < 100 {
		t.Fatalf("repl flatten produced suspiciously small table (%d bytes)", len(table))
	}
	tablePath := filepath.Join(dir, "form-cli-repl-table.txt")
	if err := os.WriteFile(tablePath, []byte(table), 0o644); err != nil {
		t.Fatalf("write table: %v", err)
	}

	// Pipe a fixed transcript into the REPL's real stdin (fd 0). The walker reads
	// argv[1]=table from a file, so stdin stays whole for read_line.
	run := func(in string) string {
		cmd := exec.Command(fkwuBin, tablePath)
		cmd.Stdin = strings.NewReader(in)
		out, err := cmd.Output()
		if err != nil {
			t.Fatalf("repl run (input %q): %v", in, err)
		}
		return string(out)
	}

	// quit ends the loop; each line before it produces exactly one response line,
	// in input order, and nothing else (effect-only entry — no root/arm dump).
	got := run("ping\nhelp\nversion\nquit\n")
	want := "pong\n" +
		"form-cli (native/fkwu): ping | help | version | <verb> ...\n" +
		"form-cli native 0.1 - running on the emitted walker (fkwu)\n"
	if got != want {
		t.Fatalf("repl transcript:\n got=%q\nwant=%q", got, want)
	}

	// EOF (closed stdin, no quit verb) also ends the loop cleanly — same output.
	if eof := run("ping\nhelp\nversion\n"); eof != want {
		t.Fatalf("repl EOF transcript:\n got=%q\nwant=%q", eof, want)
	}

	// An unknown verb echoes it back; the verb is the line up to the first space.
	if u := run("wobble the cat\nquit\n"); u != "form-cli: unknown verb wobble\n" {
		t.Fatalf("repl unknown-verb: got=%q", u)
	}

	// Determinism: identical input yields byte-identical output.
	if run("ping\nhelp\nquit\n") != run("ping\nhelp\nquit\n") {
		t.Fatal("repl output not deterministic for identical input")
	}
}
