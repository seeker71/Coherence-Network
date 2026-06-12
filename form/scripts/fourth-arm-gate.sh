#!/usr/bin/env bash
# fourth-arm-gate.sh — four-way gate for manifest rows: each named band runs
# through validate.sh (its declared preludes, suite-mode shape) and must
# answer "0 divergent" WITH the fourth leg firing. Usage:
#   scripts/fourth-arm-gate.sh stem [stem ...]
set -u
cd "$(dirname "$0")/.."

gate_one() {
    local stem="$1" band="form-stdlib/tests/$stem-band.fk" pres out
    pres="$(grep -E '^; preludes:' "$band" 2>/dev/null | head -1 | sed 's/^; preludes://')"
    if [[ -z "$pres" ]]; then
        pres="form-stdlib/core.fk"
        [[ -f "form-stdlib/$stem.fk" ]] && pres="$pres form-stdlib/$stem.fk"
    fi
    # shellcheck disable=SC2086
    out="$(./validate.sh $pres "$band" 2>&1)"
    if echo "$out" | grep -q "0 divergent" && echo "$out" | grep -q "fourth arm: 1"; then
        echo "PASS-4WAY  $stem"
    elif echo "$out" | grep -q "0 divergent"; then
        echo "NO-FOURTH  $stem"
    else
        echo "DIVERGENT  $stem"
        echo "$out" | grep -A5 '✗' | head -8
    fi
}

for stem in "$@"; do
    gate_one "$stem" &
    # bash 3.2 (macOS) has no `wait -n`; a short poll throttles the fan-out
    while [[ "$(jobs -r | wc -l)" -ge 4 ]]; do sleep 1; done
done
wait
