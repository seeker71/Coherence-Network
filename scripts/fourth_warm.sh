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
# This is the bridge to the north star the flatten itself points at: the flt-* flatten is a Form recipe,
# so fkwu's self-JIT (jit-lower / champion-challenger) crystallizing it to native is what makes the
# table-gen fast enough to not need warming at all — the body growing its own proof speed. Until then,
# this router is the container-safe door to the sovereign kernel.
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
