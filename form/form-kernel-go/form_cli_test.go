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
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func sourceCompileForFlatten(t *testing.T, stdlib, dir, src string) string {
	t.Helper()
	data, err := os.ReadFile(src)
	if err != nil {
		t.Fatalf("read %s: %v", src, err)
	}
	if !strings.Contains(string(data), "section [") {
		return src
	}
	out := filepath.Join(dir, strings.TrimSuffix(filepath.Base(src), ".fk")+".compiled.fk")
	chain := []string{
		filepath.Join(stdlib, "form-ontology-loader.fk"),
		filepath.Join(stdlib, "line-grammar.fk"),
		filepath.Join(stdlib, "bmf-core.fk"),
		filepath.Join(stdlib, "bmf-grammar.fk"),
		filepath.Join(stdlib, "bml.fk"),
		filepath.Join(stdlib, "bml-source.fk"),
		filepath.Join(stdlib, "source-compiler.fk"),
		filepath.Join(stdlib, "grammars", "form-bml.fk"),
		filepath.Join(stdlib, "form-bml-lower.fk"),
	}
	driver := fmt.Sprintf("(do (form-source-compile-file %q %q))\n", src, out)
	runFormSource(t, readFiles(t, chain...)+"\n"+driver)
	if info, err := os.Stat(out); err != nil || info.Size() == 0 {
		t.Fatalf("source-compile %s -> %s failed: %v", src, out, err)
	}
	return out
}

func formCliModsExpr(t *testing.T, stdlib, dir string) string {
	t.Helper()
	paths := []string{
		filepath.Join(stdlib, "fourth-shim.fk"),
		sourceCompileForFlatten(t, stdlib, dir, filepath.Join(stdlib, "core.fk")),
		filepath.Join(stdlib, "resource-port.fk"),
		filepath.Join(stdlib, "bml-native-interface-package-import.fk"),
		filepath.Join(stdlib, "hati-os-targets.fk"),
		filepath.Join(stdlib, "form-native-resource-interfaces.fk"),
		filepath.Join(stdlib, "form-fs.fk"),
		filepath.Join(stdlib, "storage-port.fk"),
		filepath.Join(stdlib, "host-kernel-carrier.fk"),
		filepath.Join(stdlib, "fnri-standin.fk"),
		filepath.Join(stdlib, "fnri-receipt.fk"),
		sourceCompileForFlatten(t, stdlib, dir, filepath.Join(stdlib, "http-client.fk")),
		filepath.Join(stdlib, "line-grammar.fk"),
		filepath.Join(stdlib, "voice-traits.fk"),
		filepath.Join(stdlib, "nearest-shape.fk"),
		filepath.Join(stdlib, "co-learning.fk"),
		filepath.Join(stdlib, "co-learning-stream.fk"),
		filepath.Join(stdlib, "mesh-dispatch.fk"),
		filepath.Join(stdlib, "surprise-salience.fk"),
		filepath.Join(stdlib, "host-sense-organ.fk"),
		filepath.Join(stdlib, "speech-organ.fk"),
		filepath.Join(stdlib, "native-host-instance.fk"),
		filepath.Join(stdlib, "text-tokenize.fk"),
		filepath.Join(stdlib, "rag-embed.fk"),
		filepath.Join(stdlib, "rag-index-codec.fk"),
		filepath.Join(stdlib, "rag-retrieve.fk"),
		filepath.Join(stdlib, "rag-ask.fk"),
		sourceCompileForFlatten(t, stdlib, dir, filepath.Join(stdlib, "form-cli-ask.fk")),
		filepath.Join(stdlib, "form-cli.fk"),
	}
	parts := make([]string, 0, len(paths))
	for _, path := range paths {
		parts = append(parts, `(read_file "`+path+`")`)
	}
	return "(list " + strings.Join(parts, " ") + ")"
}

func TestFkwuFormCli(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	mainCli := filepath.Join(stdlib, "form-cli-main.fk")

	dir := t.TempDir()
	fkwuBin := buildFkwu(t, clang, dir, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit)

	// Flatten form-cli-main (preludes: shim + core + form-cli, band: the runtime
	// entry) to a string-pool node table — the fks path that carries strings.
	mods := formCliModsExpr(t, stdlib, dir)
	band := `(read_file "` + mainCli + `")`
	flattenExpr := "(fks-table-file " +
		"(flt-band-sources-fns " + mods + " " + band + ") " +
		"(flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
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
		{"version", "form-cli 0.3"},
		{"ping extra", "pong"},
		{"foobar", "form-cli: unknown verb 'foobar' — type 'help'"},
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
	// the self-description verbs return their pure strings (exact match lives in
	// the four-way band tests/form-cli-band.fk; here we confirm they reach fkwu).
	for _, c := range []struct{ cmd, sub string }{
		{"help", "synthesis-status"},
		{"about", "one self-contained native binary"},
		{"kernel", "fkwu, a universal walker"},
	} {
		got, err := FkwuEvalWithInput(fkwuBin, tablePath, 0, []byte(c.cmd))
		if err != nil {
			t.Fatalf("FkwuEvalWithInput(%q): %v", c.cmd, err)
		}
		if !strings.Contains(got, c.sub) {
			t.Fatalf("form-cli %q -> %q, missing %q", c.cmd, got, c.sub)
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
	minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	repl := filepath.Join(stdlib, "form-cli-repl.fk")

	dir := t.TempDir()
	// the REPL rides the effect-only entry (fkc-emit-repl): walk fk_fn[0] for
	// effect, no root-value print, no arm-profile dump — so stdout is exactly the
	// responses the loop emits via print_str.
	_, cSrc := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit)+"\n(fkc-emit-repl)\n")
	cPath := filepath.Join(dir, "fkwu-repl.c")
	if err := os.WriteFile(cPath, []byte(cSrc), 0o644); err != nil {
		t.Fatalf("write fkwu-repl.c: %v", err)
	}
	fkwuBin := filepath.Join(dir, "fkwu-repl")
	if out, err := exec.Command(clang, "-O2", "-o", fkwuBin, cPath).CombinedOutput(); err != nil {
		t.Fatalf("clang fkwu-repl: %v\n%s", err, out)
	}

	mods := formCliModsExpr(t, stdlib, dir)
	band := `(read_file "` + repl + `")`
	flattenExpr := "(fks-table-file " +
		"(flt-band-sources-fns " + mods + " " + band + ") " +
		"(flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
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
	got := run("ping\nversion\nquit\n")
	want := "pong\nform-cli 0.3\n"
	if got != want {
		t.Fatalf("repl transcript:\n got=%q\nwant=%q", got, want)
	}

	// EOF (closed stdin, no quit verb) also ends the loop cleanly — same output.
	if eof := run("ping\nversion\n"); eof != want {
		t.Fatalf("repl EOF transcript:\n got=%q\nwant=%q", eof, want)
	}

	// 'diagnose' surfaces the live framebuffer (fk_arms op-dispatch counts plus
	// the node/string/arena/value-stack/float high-water) back through kernel_stat
	// (tag 127) — a fkwu-only verb beside source/verify. The exact counts are a
	// live snapshot of this session, so assert the readout shape, not the numbers.
	if d := run("diagnose\nquit\n"); !strings.Contains(d, "fkwu live | ops=") || !strings.Contains(d, "nodes=") {
		t.Fatalf("repl diagnose: got=%q, want a live framebuffer readout", d)
	}

	// An unknown verb echoes it back; the verb is the line up to the first space.
	if u := run("wobble the cat\nquit\n"); u != "form-cli: unknown verb 'wobble' — type 'help'\n" {
		t.Fatalf("repl unknown-verb: got=%q", u)
	}

	// This repl binary has no baked genesis (built emit-only), so 'source' is
	// empty and 'verify' reports 0 bytes — the dispatch still works. The real
	// baked genesis is proven in TestFkwuFormCliCombined and build-form-cli.sh.
	if v := run("verify\nquit\n"); !strings.Contains(v, "coherent:") {
		t.Fatalf("repl verify: got=%q", v)
	}

	// Determinism: identical input yields byte-identical output.
	if run("ping\nversion\nquit\n") != run("ping\nversion\nquit\n") {
		t.Fatal("repl output not deterministic for identical input")
	}
}

// TestFkwuFormCliCombined proves the north star: a single self-contained native
// binary. The form-cli program is flattened once and BAKED into the emitted C
// (fkc-emit-combined-repl) as the fk_prog literal, so the compiled executable IS
// form-cli — it runs DIRECTLY with no table-file argument, no Go, no clang, no C
// source, nothing at runtime but the binary and stdin. Build-time uses the
// bootstrap (flatten) + clang (compile) once; runtime is pure native.
func TestFkwuFormCliCombined(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	repl := filepath.Join(stdlib, "form-cli-repl.fk")

	dir := t.TempDir()

	// 1. flatten form-cli-repl into its program table (build-time, on the bootstrap).
	mods := formCliModsExpr(t, stdlib, dir)
	band := `(read_file "` + repl + `")`
	flattenExpr := "(fks-table-file (flt-band-sources-fns " + mods + " " + band + ") (flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
	table = strings.TrimSpace(table)
	if len(table) < 100 {
		t.Fatalf("flatten produced suspiciously small table (%d bytes)", len(table))
	}

	// 2. emit the COMBINED walker with the table baked in (fk_prog).
	_, cSrc := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit)+"\n(fkc-emit-combined-repl \""+table+"\")\n")
	if !strings.Contains(cSrc, "fk_prog") {
		t.Fatalf("combined emit missing the baked program literal")
	}

	// Bake a genesis blob (build-form-cli.sh appends the real Form source; here a
	// recognizable marker proves self_source reads the baked bytes end to end via
	// the weak fk_genesis symbol). Appended as a byte array — no escaping.
	genesis := ";;;; ==== FILE: form-stdlib/form-cli.fk ====\n(self-describing form-cli source marker)\n"
	var gb strings.Builder
	gb.WriteString(cSrc)
	gb.WriteString("\nconst unsigned char fk_genesis[] = {")
	for i := 0; i < len(genesis); i++ {
		if i > 0 {
			gb.WriteByte(',')
		}
		gb.WriteString(strconv.Itoa(int(genesis[i])))
	}
	fmt.Fprintf(&gb, "}; const long long fk_genesis_len = %d;\n", len(genesis))
	cSrc = gb.String()

	cPath := filepath.Join(dir, "form-cli.c")
	if err := os.WriteFile(cPath, []byte(cSrc), 0o644); err != nil {
		t.Fatalf("write form-cli.c: %v", err)
	}

	// 3. compile once → the standalone binary.
	binPath := filepath.Join(dir, "form-cli")
	if out, err := exec.Command(clang, "-O2", "-o", binPath, cPath).CombinedOutput(); err != nil {
		t.Fatalf("clang form-cli: %v\n%s", err, out)
	}

	// 4. run it DIRECTLY — NO arguments (no table file), only stdin. The program
	// is inside the binary. This is the whole point: nothing else is present.
	run := func(in string) string {
		cmd := exec.Command(binPath)
		cmd.Stdin = strings.NewReader(in)
		out, err := cmd.Output()
		if err != nil {
			t.Fatalf("form-cli run (input %q): %v", in, err)
		}
		return string(out)
	}
	want := "pong\nform-cli 0.3\n"
	if got := run("ping\nversion\nquit\n"); got != want {
		t.Fatalf("combined form-cli transcript:\n got=%q\nwant=%q", got, want)
	}
	// EOF (no quit) ends cleanly too.
	if eof := run("ping\nversion\n"); eof != want {
		t.Fatalf("combined form-cli EOF transcript:\n got=%q\nwant=%q", eof, want)
	}
	// the binary inspects its OWN running kernel: 'diagnose' reads the live
	// framebuffer (op-dispatch counts + substrate high-water) through kernel_stat
	// (tag 127). A live snapshot, so assert the readout shape, not the numbers.
	if d := run("diagnose\nquit\n"); !strings.Contains(d, "fkwu live | ops=") || !strings.Contains(d, "nodes=") {
		t.Fatalf("combined diagnose: got=%q, want a live framebuffer readout", d)
	}
	// the binary expresses its OWN baked source (self_source reads fk_genesis).
	if src := run("source\nquit\n"); src != genesis+"\n" {
		t.Fatalf("combined source:\n got=%q\nwant=%q", src, genesis)
	}
	// and verifies it carries that source (length reported from the baked bytes).
	if v := run("verify\nquit\n"); !strings.Contains(v, "coherent:") || !strings.Contains(v, fmt.Sprintf("%d bytes", len(genesis))) {
		t.Fatalf("combined verify: got=%q", v)
	}
}

// TestFkwuLocaleUtf8 locks the locale capability: fkwu must print ANY UTF-8
// byte-exact, not just ASCII. The string pool serializes raw bytes (str_byte_at
// in fks-lit-sp), so a baked multi-script string round-trips through the table
// and prints identically. This is the regression guard for the multibyte print
// path — the bug that the earlier ASCII-only responses worked around.
func TestFkwuLocaleUtf8(t *testing.T) {
	clang := requireClang(t)
	stdlib := filepath.Join("..", "form-stdlib")
	minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit := emitChain(t, stdlib)
	formParse := filepath.Join(stdlib, "form-parse.fk")
	formFlatten := filepath.Join(stdlib, "form-flatten.fk")
	shim := filepath.Join(stdlib, "fourth-shim.fk")
	core := filepath.Join(stdlib, "core.fk")

	dir := t.TempDir()
	fkwuBin := buildFkwu(t, clang, dir, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit)

	// a band whose root is a multi-script string: CJK, Arabic, Devanagari, emoji,
	// em-dash. If any continuation byte is dropped/corrupted, this mismatches.
	// build the string with str_concat — the shape real responses use (a bare
	// SLIT root isn't flagged string-valued by fk_str_root_depth, a separate gap);
	// this exercises the byte-serialization fix across two multibyte literals.
	want := "中文 العربية हिन्दी 😀—ok"
	bandPath := filepath.Join(dir, "locale-band.fk")
	if err := os.WriteFile(bandPath, []byte("; locale\n(str_concat \"中文 العربية हिन्दी 😀\" \"—ok\")\n"), 0o644); err != nil {
		t.Fatalf("write band: %v", err)
	}
	mods := `(list (read_file "` + shim + `") (read_file "` + core + `"))`
	band := `(read_file "` + bandPath + `")`
	flattenExpr := "(fks-table-file (flt-band-sources-fns " + mods + " " + band + ") (flt-band-sources-pool " + mods + " " + band + "))"
	_, table := runFormSource(t, readFiles(t, minimal, hatiKernel, hostIOFs, fkcSerialize, hatiEmit, formParse, formFlatten)+"\n"+flattenExpr+"\n")
	tablePath := filepath.Join(dir, "locale-table.txt")
	if err := os.WriteFile(tablePath, []byte(table), 0o644); err != nil {
		t.Fatalf("write table: %v", err)
	}

	got, err := FkwuEval(fkwuBin, tablePath, 0)
	if err != nil {
		t.Fatalf("FkwuEval: %v", err)
	}
	if got != want {
		t.Fatalf("fkwu locale print:\n got=%q (% x)\nwant=%q (% x)", got, []byte(got), want, []byte(want))
	}
}
