#!/usr/bin/env bash
# file-io-bml-proof.sh — proves the BML file-I/O interface end-to-end on fkwu.
#
# The interface (form-stdlib/file-io.bml) is authored in BML high grammar — a
# generic class with block-bodied, recursive, higher-order methods and an async
# Task surface — and lowers onto fkwu's host-native streaming primitives
# (file_open/file_read/file_close = tags 127/128/129, plus the uncapped
# read_file / write_file_text). The buffered read_file used to slurp a file into
# a fixed 65536-byte kernel buffer: anything larger was silently TRUNCATED and
# copied twice (host buffer -> string pool). This proof drives a 256 KiB /
# 8192-line file through every door of the interface and asserts each works.
#
#   1 read-all  2 fold-chunks  4 fold-lines  8 read-lines
#  16 reader-handle object  32 read-all-async  64 read-lines-async  128 descriptor
#
# Expected witness: 255 (all eight doors).
#
# fkwu-native: file_open/file_read/file_close are fkwu host-io carriers; the Go,
# Rust, and TS kernels do not carry them, so this band is fkwu-only by design
# (an honest floor, not a divergence).
#
# Run from form/:  ./scripts/file-io-bml-proof.sh
set -euo pipefail
cd "$(dirname "$0")/.."

GO_DIR="form-kernel-go"
GO_BIN="$GO_DIR/bin-go"
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building Go emitter (bin-go)..." >&2
    (cd "$GO_DIR" && go build -o bin-go .)
fi

# build_fourth + fourth_flatten_expr live in the validate.sh fourth leg.
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh

if ! command -v clang >/dev/null 2>&1; then
    echo "SKIP: clang not available — fkwu cannot be built" >&2
    exit 0
fi

INTERFACE="form-stdlib/file-io.bml"
BAND="form-samples/file-io/bml-proof.fk"

# The BML source-compiler chain — same set validate.sh's prepare_sources uses to
# lower any `section [...]` file to plain Form.
compiler_chain=(
    form-stdlib/form-ontology-loader.fk
    form-stdlib/line-grammar.fk
    form-stdlib/bmf-core.fk
    form-stdlib/bmf-grammar.fk
    form-stdlib/bml.fk
    form-stdlib/bml-source.fk
    form-stdlib/source-compiler.fk
    form-stdlib/grammars/form-bml.fk
    form-stdlib/form-bml-lower.fk
)

d="$(mktemp -d "${TMPDIR:-/tmp}/fk-file-io-bml.XXXXXX")"
trap 'rm -rf "$d"' EXIT

# 1) lower the BML interface to plain Form recipes. The source-compiler strips
#    the BML's `//` doc-comment lines itself now (fsc-strip-bml-comments), so the
#    lowered Form is flattener-clean with no post-processing.
printf '(do (form-source-compile-file "%s" "%s"))\n' "$INTERFACE" "$d/file-io.fk" > "$d/compile.fk"
"$GO_BIN" "${compiler_chain[@]}" "$d/compile.fk" >/dev/null 2>"$d/compile.err" || {
    echo "FAIL: BML compile failed" >&2; sed -n '1,12p' "$d/compile.err" >&2; exit 1; }
if [[ ! -s "$d/file-io.fk" ]]; then
    echo "FAIL: BML compile produced no Form" >&2; sed -n '1,12p' "$d/compile.err" >&2; exit 1
fi

# 2) build fkwu
build_fourth
if ! fourth_available; then
    echo "FAIL: fkwu binary did not build" >&2
    exit 1
fi

# 3) flatten [lowered interface + band] into a node-table, run on fkwu
cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
fourth_flatten_expr fks "$d/file-io.fk" "$BAND" >> "$d/driver.fk"
"$GO_BIN" "$d/driver.fk" 2>"$d/flatten.err" > "$d/table.txt" || {
    echo "FAIL: flatten failed" >&2; sed -n '1,12p' "$d/flatten.err" >&2; exit 1; }
if [[ ! -s "$d/table.txt" ]]; then
    echo "FAIL: empty flattened table" >&2; sed -n '1,12p' "$d/flatten.err" >&2; exit 1
fi

out="$(TMPDIR="$d" "$FKWU" "$d/table.txt" 0 2>/dev/null | head -1)"
echo "  fkwu witness: $out (expected 255)"

# 4) the VERDICT is decided in Form, not by a bash `[[ "$out" == "255" ]]`.
#    file-io-shell.fk (the proof orchestration as a Form-shell cell) carries the
#    `255` constant and the test/echo gate; fio-verdict runs that gate on fkwu —
#    the decision executes on the 4th kernel. Bash only dispatches on the answer.
#    (go/clang/fkwu above are passthrough bootstrap — the honest floor; the
#    DECISION is native, the band file-io-shell crosses four-way at 255.)
verdict_modules=(
    form-stdlib/form-ontology-loader.fk form-stdlib/line-grammar.fk
    form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/grammar-loader.fk
    form-stdlib/shell-grammar.fk form-stdlib/voice-traits.fk form-stdlib/feature-vector.fk
    form-stdlib/nearest-shape.fk form-stdlib/voice-diarize.fk form-stdlib/shell-exec.fk
    form-stdlib/shell-lower.fk form-stdlib/file-io-shell.fk
)
printf '(do (fio-verdict-code "%s"))\n' "$out" > "$d/verdict.fk"
cat "${FOURTH_CHAIN[@]}" > "$d/verdict-driver.fk"
fourth_flatten_expr fks "${verdict_modules[@]}" "$d/verdict.fk" >> "$d/verdict-driver.fk"
"$GO_BIN" "$d/verdict-driver.fk" 2>"$d/verdict.err" > "$d/verdict-table.txt" || {
    echo "FAIL: verdict flatten failed" >&2; sed -n '1,12p' "$d/verdict.err" >&2; exit 1; }
verdict="$(TMPDIR="$d" "$FKWU" "$d/verdict-table.txt" 0 2>/dev/null | head -1)"
echo "  form-shell verdict (native test gate on fkwu): $verdict (1=PASS 0=FAIL)"

if [[ "$verdict" == "1" ]]; then
    echo "PASS: BML file-I/O interface — streaming, lines, handle object, async Task, generic descriptor"
    exit 0
fi
echo "FAIL: form-shell verdict $verdict (witness $out != 255)" >&2
exit 1
