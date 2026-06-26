#!/usr/bin/env bash
# regen_standard_lane_binaries.sh — maintainer-only: refresh fkwu + form-cli
# platform bootstrap binaries. Runtime and standard-lane receipt stay fkwu-native;
# this script is the explicit off-receipt carrier while form-macho closes the last
# platform binary generation gap.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
cd "$FORM"
export GO_BIN="$FORM/form-kernel-go/bin-go"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
command -v clang >/dev/null 2>&1 || { echo "maintainer regen requires clang to refresh platform bootstrap binaries; runtime/standard lane does not" >&2; exit 1; }

slug="$(fourth_platform_slug)"
mkdir -p form-stdlib/bootstrap

FORM_STANDARD_LANE=0 build_fourth
stamp="$(fourth_fkwu_cache_stamp)"
out="$FOURTH_DIR/fkwu-$stamp"
[[ -x "$out" ]] || { echo "fkwu build failed" >&2; exit 1; }
cp "$out" "form-stdlib/bootstrap/fkwu-${slug}"
printf '%s\n' "$stamp" > "form-stdlib/bootstrap/fkwu-${slug}.stamp"
echo "regen: fkwu-${slug} ($(wc -c < "form-stdlib/bootstrap/fkwu-${slug}" | tr -d ' ') bytes) stamp=$stamp"

FORM_CLI_SRCS=(
    form-stdlib/fourth-shim.fk form-stdlib/core.fk form-stdlib/line-grammar.fk
    form-stdlib/str-byte-at.fk form-stdlib/sha256.fk form-stdlib/hex.fk
    form-stdlib/resource-port.fk form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk
    form-stdlib/form-native-resource-interfaces.fk form-stdlib/form-fs.fk
    form-stdlib/storage-port.fk form-stdlib/host-kernel-carrier.fk
    form-stdlib/fnri-standin.fk form-stdlib/fnri-receipt.fk
    form-stdlib/http-client.fk
    form-stdlib/voice-traits.fk form-stdlib/nearest-shape.fk
    form-stdlib/co-learning.fk form-stdlib/co-learning-stream.fk
    form-stdlib/mesh-dispatch.fk form-stdlib/surprise-salience.fk form-stdlib/host-sense-organ.fk
    form-stdlib/speech-organ.fk form-stdlib/native-host-instance.fk
    form-stdlib/text-tokenize.fk form-stdlib/rag-embed.fk
    form-stdlib/rag-index-codec.fk form-stdlib/rag-retrieve.fk
    form-stdlib/rag-ask.fk form-stdlib/form-cli-ask.fk form-stdlib/form-cli.fk
    form-stdlib/form-cli-gguf-cell.fk
    form-stdlib/form-cli-repl.fk
)
want_cli="$(fourth_hash16 "${FORM_CLI_SRCS[@]}")"
FORM_STANDARD_LANE=0 ./build-form-cli.sh
[[ -x form-cli ]] || { echo "form-cli build failed" >&2; exit 1; }
cp form-cli "form-stdlib/bootstrap/form-cli-${slug}"
printf '%s\n' "$want_cli" > "form-stdlib/bootstrap/form-cli-${slug}.stamp"
echo "regen: form-cli-${slug} ($(wc -c < "form-stdlib/bootstrap/form-cli-${slug}" | tr -d ' ') bytes) stamp=$want_cli"
