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
# engine 2495 + compiler 1110) and exceeds 30+ MINUTES — ~2-3x the source, >33x the time. That is an
# O(n^2) (or worse) in flt-*, so even warm-once is impractical for the heaviest bands here. The genuine
# fix is to profile flt-* (the Go kernel's -prof flag) and DE-QUADRATIC it — and that fix is
# OUTPUT-PRESERVING (identical table bytes, just faster), so it is far lower-risk than reachability-
# pruning and re-validates by byte-identity against the existing cached tables. THAT is the next pass.
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
