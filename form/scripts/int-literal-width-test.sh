#!/usr/bin/env bash
#
# int-literal-width-test.sh — prove integers wider than int32 compute CORRECTLY
# (not merely identically) across all three kernels, on both the parse and the
# arithmetic paths.
#
# Two traps in the same family, both invisible to plain agreement:
#   parse   — 3596153792 (0xD65F03C0, bit 31 set) packed into the 32-bit `inst`
#             slot read back as -698813504, so (div ... 16777216) = -41 not 214,
#             and all three kernels agreed on the wrong answer.
#   compute — TS's bare-int fold wrapped RESULTS at int32 (Math.imul / `| 0`),
#             so (mul 100000 100000) = 1410065408 vs Go/Rust's 10000000000.
#
# This gate runs the band on each kernel and asserts the verdict is exactly 9
# (every check in tests/int-literal-width-band.fk holds). Agreement on a wrong
# number is a FAIL here.
#
# Exit 0 on the expected verdict (9) from all three kernels, 1 otherwise.
set -euo pipefail

FORMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FORMDIR"

# The band uses only kernel primitives (div/mod/eq/add/if/let/do), so it runs
# standalone — no stdlib prelude, no source-compilation. validate.sh's
# auto-discovery additionally exercises it with core.fk prepended.
BAND="form-stdlib/tests/int-literal-width-band.fk"
EXPECT=9

GO_BIN="form-kernel-go/bin-go"
RS_BIN="form-kernel-rust/target/release/form-kernel-rust"
TS_MAIN="form-kernel-ts/src/main.ts"

if [[ ! -x "$GO_BIN" ]]; then (cd form-kernel-go && go build -o bin-go .); fi
if [[ ! -x "$RS_BIN" ]]; then (cd form-kernel-rust && cargo build --release --quiet); fi

run_ts() {
  local loader="$FORMDIR/form-kernel-ts/node_modules/tsx/dist/loader.mjs"
  if [[ -x "form-kernel-ts/node_modules/.bin/tsx" ]]; then
    node --import "$loader" "$TS_MAIN" "$@"
  else
    npx --yes tsx "$TS_MAIN" "$@"
  fi
}

go_out="$($GO_BIN $BAND 2>&1 | tail -1)"
rs_out="$($RS_BIN $BAND 2>&1 | tail -1)"
ts_out="$(run_ts $BAND 2>&1 | tail -1)"

echo "go=$go_out  rust=$rs_out  typescript=$ts_out  (expect $EXPECT)"

if [[ "$go_out" == "$EXPECT" && "$rs_out" == "$EXPECT" && "$ts_out" == "$EXPECT" ]]; then
  echo "int literal width: PASS — literals > 2^31 compute correctly on Go/Rust/TS."
  exit 0
else
  echo "int literal width: FAIL — expected $EXPECT from every kernel (a smaller" >&2
  echo "  verdict means a kernel is still truncating wide literals or results" >&2
  echo "  to int32)." >&2
  exit 1
fi
