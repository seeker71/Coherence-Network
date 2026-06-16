#!/usr/bin/env bash
# form_coreutils_diff.sh — differential test of the zero-clang Form coreutils against
# the REAL system tools, over a battery of edge-case INPUTS derived from the actual
# GNU/POSIX source (docs/coherence-substrate/coreutils-edge-surface.md), not invented.
# The system tool is the behavioral oracle; we throw the hard inputs (empty, no
# trailing newline, NUL bytes, high-bit/UTF-8, >page-size lines, all-newlines) and
# confirm the Form binary matches byte-for-byte — or name the gap honestly.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fdiff.XXXXXX")"; trap 'rm -rf "$work"' EXIT
SDK="$(xcrun --show-sdk-path 2>/dev/null)"

# Build a Form tool: name + the fa-* instruction list -> a linked binary at $work/<name>.
build() {
    local name="$1" prog="$2"
    { sed '$ d' "$FORM/form-stdlib/form-asm.fk"
      sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
      printf '%s\n' \
        '(defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))' \
        '(defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))' \
        '(defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))' \
        "(print (str_concat \"MACHO \" (hxb (mo-object $prog))))" '0)'
    } > "$work/$name.fk"
    (cd "$FORM" && "$GO" "$work/$name.fk" 2>/dev/null) | grep '^MACHO ' | sed 's/^MACHO //' | xxd -r -p > "$work/$name.o"
    ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/$name" "$work/$name.o" 2>/dev/null
}

CAT='(fa-image (list (fa-sub-x-imm 31 31 16)
  (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
  (fa-cmp-x 0 0) (fa-bcond 13 8)
  (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
  (fa-b-off -14) (fa-movz 0 0) (fa-add-x-imm 31 31 16) (fa-ret)))'
TR='(fa-image (list (fa-sub-x-imm 31 31 16)
  (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
  (fa-cmp-x 0 0) (fa-bcond 13 14)
  (fa-ldrb 8 31 0) (fa-sub 9 8 65) (fa-add 10 8 32) (fa-cmp 9 25) (fa-csel 8 10 8 9) (fa-strb 8 31 0)
  (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
  (fa-b-off -20) (fa-movz 0 0) (fa-add-x-imm 31 31 16) (fa-ret)))'

build cat "$CAT"; build tr "$TR"

# the edge-case input battery (derived from the source surface, not invented)
mk() { case "$1" in
  empty)      : > "$work/in";;
  no_nl)      printf 'abc XYZ' > "$work/in";;
  only_nls)   printf '\n\n\n' > "$work/in";;
  nul)        printf 'A\000B\000C\n' > "$work/in";;
  highbit)    printf 'caf\303\251 ZURICH \342\230\203\n' > "$work/in";;   # UTF-8: café, snowman
  longline)   { head -c 9000 /dev/zero | tr '\0' 'A'; printf '\n'; } > "$work/in";;
  mixed)      printf 'Hello, World!\nLine TWO\n123 abcABC\n' > "$work/in";;
esac; }

pass=0; total=0
run() { # tool  form-bin  system-cmd...
  local label="$1" bin="$2"; shift 2
  for c in empty no_nl only_nls nul highbit longline mixed; do
    mk "$c"
    "$bin" < "$work/in" > "$work/f.out" 2>/dev/null
    "$@" < "$work/in" > "$work/s.out" 2>/dev/null
    total=$((total+1))
    if cmp -s "$work/f.out" "$work/s.out"; then pass=$((pass+1)); printf "  ok   %-4s %-9s (%s bytes)\n" "$label" "$c" "$(wc -c <"$work/f.out"|tr -d ' ')"
    else printf "  DIFF %-4s %-9s  form=%sB system=%sB\n" "$label" "$c" "$(wc -c <"$work/f.out"|tr -d ' ')" "$(wc -c <"$work/s.out"|tr -d ' ')"; fi
  done
}

echo "── Form coreutils vs system tools, over edge-case inputs from the real source ──"
echo "  cat (Form) vs /bin/cat:"
run cat "$work/cat" /bin/cat
echo "  tr (Form, A-Z a-z) vs /usr/bin/tr A-Z a-z:"
run tr "$work/tr" /usr/bin/tr 'A-Z' 'a-z'
echo
echo "  $pass/$total edge inputs match byte-for-byte across the implemented operations"
echo
echo "  NOT YET COVERED (named gaps from the source surface — see coreutils-edge-surface.md):"
echo "    tr  : -d -s -c -t, [:classes:], [=equiv=], [c*n] repeats, octal/\\ escapes, ranges other than A-Z"
echo "    cat : -n -b -s -A -E -T -v, file args, '-'=stdin, missing-file error + exit code"
echo "    bash: the whole POSIX shell (lexer, parser, expansions, builtins, control flow) — a separate arc"
[[ "$pass" -eq "$total" ]]