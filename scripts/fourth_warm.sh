#!/usr/bin/env bash
# fourth_warm.sh — container-safe router to the fkwu (fourth) kernel.
#
# WHY: proving a band four-way needs a pre-flattened fkwu table. Generating it is a Go tree-walk over
# the band's whole prelude chain — cheap for small bands, slow+memory-heavy for the source-compiler/
# grammar chains, and the full-suite path flattens 48 bands x 4 cores at once, which OOMs a constrained
# container. But the table is CONTENT-CACHED (.cache/fourth/t-<stem>-<hash>.txt): once generated it is
# reused. So this router warms tables ONE AT A TIME (serial, bounded memory) into the persistent cache,
# turning an all-at-once spike into a sequence that fits any container. After warming, the four-way
# proof reuses the cached table and runs fast:
#
#   scripts/fourth_warm.sh form-bml-cursor-full         # warm one band's table (persists)
#   scripts/fourth_warm.sh --all                        # warm every manifest band, serial + bounded
#   cd form && ./validate.sh <preludes> tests/<stem>-band.fk   # now reuses the warm table, four-way
#
# MEASURED, so the next session does not re-try a dead lever: the JIT is NOT what speeds the flatten.
# The Go kernel's self-JIT (FORM_JIT_HOT) crystallizes hot NUMERIC closures (tags 1-7,12); the flt-*
# flatten is string/list/parse work, the wrong op family. Tuning FORM_JIT_HOT over the cursor-parse
# flatten only moved 54s (default 2000) / 59s (off) / 73s (HOT=20, build overhead with no payoff), all
# byte-identical — no win. The real lever is REDUCING WORK: reachability-prune the flatten so a heavy
# band serializes only the source-compiler functions it actually reaches, not the whole module (a
# focused, output-preserving flatten change — the table shrinks, the band's verdict is unchanged).
# A truly native flatten would need the form-asm/JIT op coverage extended to string/list ops (the
# grow-form-asm-coverage effort), not the numeric self-JIT. Until either lands, this router is the
# container-safe door: warm the heavy table ONCE (serial, bounded), then every proof reuses it.
#
# SHARPER MEASUREMENT (the real root cause): the flatten is SUPER-LINEAR in chain size.
# cursor-parse (6 light srcs) flattens in 54s; cursor-full adds ~6300 lines (source-compiler 2712 +
# engine 2495 + compiler 1110) and exceeds 30+ MINUTES — ~2-3x the source, >33x the time. O(n^2) in flt-*.
#
# LOCALIZED (by inspection + measurement): the dominant quadratic is the STRING-POOL DEDUP. flt-sidx
# (form-flatten.fk) does a LINEAR SCAN of the pool per string literal to find/dedup its index =
# O(literals x pool); source-compiler has a huge pool, so it explodes. (A secondary O(n) factor —
# (eq (len X) 0) emptiness checks computing ListLength O(n) per step — looked tempting to swap for nil?,
# but DON'T: nil? is not a bare builtin and form-flatten is loaded in paths without it (build-form-cli),
# so that change broke windows-floor CI with unbound "nil?" and was reverted. The len==0 idiom is the
# universal one here.) The REAL de-quadratic is an O(1) pool lookup replacing flt-sidx's scan.
# CRUCIAL: this is NOT a recipe change. Pure Form cannot build an O(1) map — Form lists are cons-cells
# with no O(1) random access — and the kernel's _dict_* is itself linear (_dict_get scans, _dict_set
# copies the whole list: O(n)/O(n^2)). So the fix is a NATIVE O(1) HASH-MAP PRIMITIVE added to the three
# source-walker kernels (Go map / Rust HashMap / TS Map) — fkwu is NOT needed, table-gen runs on
# Go/Rust/TS — then flt-sidx's pool dedup uses it, keyed in first-occurrence order so index assignments
# (table bytes / verdicts) stay identical; validate by verdict-preservation on a diverse sample + CI's
# full gate. A focused MULTI-KERNEL native pass, not a quick recipe edit.
#
# ON THE NATIVE JIT (corrected): do NOT read "JIT can't help" as a law. Today the native JIT crystallizes
# NUMERIC closures and the flatten is string/list work — but that op-coverage gap is a TARGET, not a
# limit. The native JIT shall support EVERYTHING; extending its (and form-asm's) op coverage to string/
# list/node families is the same grow-the-native-emitter effort, and once it covers the flt-* families
# the whole flatten crystallizes native and the speed problem dissolves at the root. The hash-map
# primitive above is the nearer fix; growing the native JIT to cover all ops is the deeper one. Both are
# native-emitter growth, not Form-level workarounds — that is the north star, op family by op family.
set -uo pipefail
cd "$(dirname "$0")/../form" || exit 1

export GO_BIN="${GO_BIN:-$PWD/form-kernel-go/bin-go}"
[[ -x "$GO_BIN" ]] || ( cd form-kernel-go && go build -o bin-go . )

# shellcheck source=form/scripts/fourth-arm.sh
source scripts/fourth-arm.sh
mkdir -p "$FOURTH_DIR"

warm_one() {
    local stem="$1" t
    t="$(fourth_table "$stem" 2>/dev/null)"
    if [[ -n "$t" && -s "$t" ]]; then
        echo "  warmed  $stem  ->  $(basename "$t")  ($(wc -c < "$t") bytes)"
    else
        echo "  3-kernel  $stem  (no fourth table: unsupported op family, or not in manifest)"
    fi
}

if [[ "${1:-}" == "--all" ]]; then
    # serial: one band per flatten run keeps memory flat (overcomes the 48x4 cold-cache OOM)
    export FOURTH_PREPARE_ALL_BATCH_MAX=1
    awk '!/^#/ && NF>=3 {print $1}' "$FOURTH_MANIFEST" | while read -r stem; do warm_one "$stem"; done
elif [[ "$#" -ge 1 ]]; then
    for stem in "$@"; do warm_one "$stem"; done
else
    echo "usage: fourth_warm.sh <band-stem> [<band-stem> ...] | --all" >&2
    exit 2
fi
