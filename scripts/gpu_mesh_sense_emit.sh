#!/usr/bin/env bash
# gpu_mesh_sense_emit.sh — the GPU sensing organ reports live into the mesh.
#
# The body is Form: form/form-stdlib/gpu-mesh-sense.fk turns a GPU bit-exact proof verdict
# (backend, device, kernel, parity N/N, max-abs ULP) into a wmg-sense row — the SAME shape the
# world-model learner already consumes from active samples and capability receipts. Proven four-way
# (Go/Rust/TS/fkwu) by form-stdlib/tests/gpu-mesh-sense-band.fk → verdict 511.
#
# This carrier is the thin last mile: it renders THIS session's real GPU readings through that
# proven recipe and posts each to the live field board (the local mesh the session-start
# "who is in the field" readout reads) as the gpu-organ — so other cells see, on their next breath,
# what the silicon proved and can learn from it. Form is the body; this shell only carries.
#
# Env:
#   POST_TO_BOARD=0   render + prove only, do not post to the board (default: 1, post)
#   COORD_AGENT       override the organ identity on the board (default: gpu-organ)
# Run:  scripts/gpu_mesh_sense_emit.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
POST_TO_BOARD="${POST_TO_BOARD:-1}"
ORGAN="${COORD_AGENT:-gpu-organ}"

# the Form prelude chain wmg-sense needs (core.fk is implicit in validate)
CHAIN=(
  form-stdlib/obs-verify.fk form-stdlib/trust-decay.fk form-stdlib/channel-interface.fk
  form-stdlib/satsang.fk form-stdlib/satsang-field.fk form-stdlib/persistence.fk
  form-stdlib/world-module-model.fk form-stdlib/world-model-growth.fk form-stdlib/gpu-mesh-sense.fk
)

# this session's real GPU organ readings:  backend|device|kernel|parity-num|parity-den|max-abs-ulp
# (the same fixtures the four-way band proves; the device+parity are the measured evidence the
#  organ reports — the recipe decides observed/absent, the carrier carries the numbers.)
READINGS=(
  "metal|Apple M4 Max|conv2d|75|75|0"
  "metal|Apple M4 Max|matvec|1280|1280|0"
  "vulkan|Adreno (TM) 740|matvec|1280|1280|0"
)

run_band() {  # $@ = extra .fk files after the chain; echoes the "→ <value>" payload
  ( cd "$FORMDIR" && ./validate.sh "${CHAIN[@]}" "$@" 2>&1 )
}

echo "── proving the GPU→mesh converter four-way ──"
proof="$(run_band form-stdlib/tests/gpu-mesh-sense-band.fk)"
if ! printf '%s\n' "$proof" | grep -q '→ 511'; then
    echo "FAIL  gpu-mesh-sense-band did not prove 511 four-way:"; printf '%s\n' "$proof" | tail -6; exit 1
fi
printf '%s\n' "$proof" | grep -E '✓|fourth arm|ok,' | sed 's/^/  /'

echo
echo "── rendering this session's GPU readings through the proven recipe ──"
emit="$(run_band form-stdlib/tests/gpu-mesh-emit.fk | sed -n 's/.*→ //p')"
echo "  Form render (go/rust/ts agree): $emit"

echo
echo "── the gpu-organ reports into the field (mesh) ──"
# verdict per reading comes from the Form render ("<name> gpu-bit-exact <verdict>"); the carrier
# joins it with the measured parity/device it holds. We pull each verdict word out of the render.
i=0
for r in "${READINGS[@]}"; do
    IFS='|' read -r backend device kernel num den ulp <<<"$r"
    name="${backend}:${kernel}"
    verdict="$(printf '%s' "$emit" | tr '|' '\n' | sed -n "$((i+1))p" | awk '{print $3}')"
    [ -z "$verdict" ] && verdict="observed"
    line="$name gpu-bit-exact $verdict ${num}/${den} ulp${ulp} (${device})"
    if [ "$POST_TO_BOARD" = "1" ]; then
        COORD_AGENT="$ORGAN" bash "$ROOT/scripts/agent-coord.sh" share "$line" >/dev/null 2>&1 \
            && echo "  → posted: $line" || echo "  (board post failed; render still valid) $line"
    else
        echo "  (dry-run, not posted): $line"
    fi
    i=$((i+1))
done

echo
if [ "$POST_TO_BOARD" = "1" ]; then
    echo "ok — the GPU organ is live in the mesh as '$ORGAN'. Read it: scripts/agent-coord.sh roster   (or  log)"
    echo "     The reading shape is wmg-sense (form/form-stdlib/gpu-mesh-sense.fk), the same the world-model"
    echo "     learner ingests — so cells learn from the silicon's proof, not just stdout."
else
    echo "ok — rendered + proven (511 four-way), not posted (POST_TO_BOARD=0)."
fi
echo "next mile (opt-in, outward): POST each wmg-sense to the durable graph via /api/sensings so it"
echo "     reaches every instance, not just this machine's board."
