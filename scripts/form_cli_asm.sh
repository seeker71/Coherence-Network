#!/usr/bin/env bash
# form_cli_asm.sh — interrogate LLVM offline: how does clang lower / optimize this?
#
# clang IS LLVM. Without the source and without the network, the binary still
# answers every lowering question — feed it C, read what it emits at each stage:
#   (default)  arm64 asm at -O2 — LLVM's actual lowering + optimizations
#   --ir       the LLVM IR (the SSA optimization substrate)
#   --opt      -O0 vs -O2 asm, side by side — what the optimizer DID (the path)
#   --x86      x86_64 asm — target-specific lowering, same source
#   --passes   per-pass IR via opt -print-after-all (brew llvm) — the full pipeline
# This is the clang-compiler teacher lane (oracle-catalog.fk): form-lower drafts a
# lowering, compares its bytes to clang's here (the conviction gate, fa-conviction),
# and learns LLVM's answer — all offline. Thin host-tool carrier; clang is the oracle.
#
# Usage: form_cli_asm.sh "<C snippet or function>" [--ir|--opt|--x86|--passes]
set -u
SNIP="${1:-}"; [ -n "$SNIP" ] || { echo 'usage: form_cli_asm.sh "<C snippet>" [--ir|--opt|--x86|--passes]' >&2; exit 2; }
MODE="${2:-}"
CLANG="${CLANG:-clang}"
LLVM="$(brew --prefix llvm 2>/dev/null)/bin"

emit(){ printf '%s\n' "$SNIP" | "$CLANG" -x c "$@" -o - - 2>/dev/null; }

case "$MODE" in
  --ir)
    echo "── LLVM IR (-O2) — the optimization substrate ──"
    emit -S -emit-llvm -O2 | grep -vE '^[[:space:]]*$|^source_filename|^target ' ;;
  --x86)
    echo "── x86_64 asm (-O2) — target-specific lowering ──"
    emit -S -O2 -arch x86_64 | grep -vE '^[[:space:]]*[.;]|^[[:space:]]*$|cfi' ;;
  --opt)
    echo "── -O0 (literal) ──";  emit -S -O0 -arch arm64 | grep -vE '^[[:space:]]*[.;]|^[[:space:]]*$|cfi' | head -20
    echo "── -O2 (optimized) — the delta IS what the optimizer did ──"
    emit -S -O2 -arch arm64 | grep -vE '^[[:space:]]*[.;]|^[[:space:]]*$|cfi' | head -20 ;;
  --passes)
    if [ -x "$LLVM/opt" ]; then
      echo "── per-pass IR (opt -print-after-all) — the optimization pipeline ──"
      printf '%s\n' "$SNIP" | "$CLANG" -x c -S -emit-llvm -O0 -o - - 2>/dev/null \
        | "$LLVM/opt" -O2 -print-after-all -S 2>&1 | grep -E '^\*\*\*|define|%[0-9]| = ' | head -60
    else echo "brew llvm 'opt' not found — install: brew install llvm"; fi ;;
  *)
    echo "── arm64 asm (-O2) — LLVM's actual lowering ──"
    emit -S -O2 -arch arm64 | grep -vE '^[[:space:]]*[.;]|^[[:space:]]*$|cfi' ;;
esac
