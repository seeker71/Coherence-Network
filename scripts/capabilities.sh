#!/usr/bin/env bash
# capabilities.sh — the runtime capability readout. Run this when you're about to reach for a
# Go/Rust kernel native, or wonder "can we do X natively?" — it answers from the body's own truth.
#
# THE RULE this readout exists to keep load-bearing:
#   fkwu (the emitted 4th kernel, C-bootstrapped) is the RUNTIME.
#   Go, Rust, TypeScript are PROOF WALKERS — they witness four-way agreement at validate.sh and
#   they NEVER gate a feature. A capability is a FORM RECIPE proven four-way; that is what ships.
#   A kernel native is swappable tissue (primitive-registry.fk), not a dependency: if it is broken
#   or missing on one arm (str_byte_at returned 0 on fkwu), do NOT patch a walker and do NOT block —
#   build the recipe over the minimal proven core (lc-one-engine), prove four-way, ship on fkwu.
#   bin-go is BOOTSTRAP (it runs the flattener/emitter); it is never the runtime.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT" || exit 1
MAN="form/fourth-arm-bands.txt"

N="$(grep -cE '^[a-z][a-z0-9-]* (fkc|fks) ' "$MAN" 2>/dev/null)"
echo "⟐ RUNTIME CAPABILITIES — Form recipes proven four-way (Go=Rust=TS=fkwu), the set that ships on fkwu"
echo "  ledger: $MAN   ·   $N capabilities proven on the 4th kernel"
echo
echo "  the kernels, by role (presence here ≠ requirement — walkers are witnesses, not deps):"
[ -x form/form-kernel-go/bin-go ] && echo "    Go    — PROOF WALKER (+ bootstrap: runs the flattener/emitter). built." || echo "    Go    — PROOF WALKER. not built (a feature does NOT need it)."
[ -x form/form-kernel-rust/target/release/form-kernel-rust ] && echo "    Rust  — PROOF WALKER. built." || echo "    Rust  — PROOF WALKER. not built (a feature does NOT need it)."
ls form/form-kernel-ts/dist/*.js >/dev/null 2>&1 && echo "    TS    — PROOF WALKER. built." || echo "    TS    — PROOF WALKER. not built (a feature does NOT need it)."
ls form/form-stdlib/.cache/fourth/fkwu-* >/dev/null 2>&1 && echo "    fkwu  — RUNTIME (C-bootstrap). built — this is what executes." || echo "    fkwu  — RUNTIME (C-bootstrap). not built — 'cd form && source scripts/fourth-arm.sh && build_fourth'."
echo

if [ "${1:-}" = "--families" ] || [ "${1:-}" = "-f" ]; then
  echo "  capability families (grep the ledger for the rest):"
  for fam in crypto:'sha256|hmac|pbkdf2|base64|hex|crc32|uuid' \
             postgres/db:'pg-|storage-port|sqlite|substrate-core' \
             native-codegen:'form-asm|form-lower|jit|champion|recipe-dylib|codesign' \
             net/http:'http|socket' string/bytes:'str-byte-at|tokenize|json|url-encode' \
             model/ml:'transformer|attention|whisper|mlp|gelu|adam|sgd'; do
    name="${fam%%:*}"; pat="${fam#*:}"
    c="$(grep -cE "^($pat)[a-z0-9-]* (fkc|fks) " "$MAN" 2>/dev/null)"
    printf "    %-16s %s\n" "$name" "$c proven"
  done
  echo
fi

echo "  standing walls — what fkwu does NOT yet carry (a band is out for ONE honest reason: a missing op"
echo "  FAMILY, never a divergence). These are the only honest 'not yet native' answers:"
sed -n '/^# The standing walls/,/^# Crossed walls/p' "$MAN" | grep -E '^#   [a-z]' | sed 's/^#  /   /' | head -8
echo
echo "  → building a feature: use a four-way recipe, or write one and prove it. NEVER block on a Go/Rust"
echo "    native and NEVER patch a walker to add a runtime op. Teaching: docs/vision-kb/concepts/lc-one-engine.md"
