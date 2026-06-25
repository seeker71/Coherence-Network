#!/usr/bin/env bash
# regen_form_cli_bootstrap.sh — maintainer-only: refresh the pre-flattened
# form-cli table and emitted C carrier. Runtime `form-cli` stays fkwu-native;
# this is an explicit off-receipt bridge until the self-host flatten/emit path is
# warm everywhere.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
GB="$FORM/form-kernel-go/bin-go"
[[ -x "$GB" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
cd "$FORM"
export GO_BIN="$GB"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
FORM_CLI_SRCS=(
    form-stdlib/fourth-shim.fk form-stdlib/core.fk form-stdlib/line-grammar.fk
    form-stdlib/resource-port.fk form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk
    form-stdlib/form-native-resource-interfaces.fk form-stdlib/form-fs.fk
    form-stdlib/storage-port.fk form-stdlib/host-kernel-carrier.fk form-stdlib/fnri-standin.fk
    form-stdlib/fnri-receipt.fk form-stdlib/http-client.fk
    form-stdlib/voice-traits.fk form-stdlib/nearest-shape.fk
    form-stdlib/co-learning.fk form-stdlib/co-learning-stream.fk form-stdlib/mesh-dispatch.fk
    form-stdlib/surprise-salience.fk form-stdlib/host-sense-organ.fk form-stdlib/speech-organ.fk
    form-stdlib/native-host-instance.fk form-stdlib/text-tokenize.fk form-stdlib/rag-embed.fk
    form-stdlib/rag-index-codec.fk form-stdlib/rag-retrieve.fk form-stdlib/rag-ask.fk
    form-stdlib/form-cli-ask.fk form-stdlib/form-cli.fk form-stdlib/form-cli-repl.fk
)
mkdir -p form-stdlib/bootstrap
echo "regen: flatten bin-go (form-cli table)"
S=form-stdlib
MODS="(list (read_file \"$S/fourth-shim.fk\") (read_file \"$S/core.fk\") (read_file \"$S/resource-port.fk\") (read_file \"$S/bml-native-interface-package-import.fk\") (read_file \"$S/hati-os-targets.fk\") (read_file \"$S/form-native-resource-interfaces.fk\") (read_file \"$S/form-fs.fk\") (read_file \"$S/storage-port.fk\") (read_file \"$S/host-kernel-carrier.fk\") (read_file \"$S/fnri-standin.fk\") (read_file \"$S/fnri-receipt.fk\") (read_file \"$S/http-client.fk\") (read_file \"$S/line-grammar.fk\") (read_file \"$S/voice-traits.fk\") (read_file \"$S/nearest-shape.fk\") (read_file \"$S/co-learning.fk\") (read_file \"$S/co-learning-stream.fk\") (read_file \"$S/mesh-dispatch.fk\") (read_file \"$S/surprise-salience.fk\") (read_file \"$S/host-sense-organ.fk\") (read_file \"$S/speech-organ.fk\") (read_file \"$S/native-host-instance.fk\") (read_file \"$S/text-tokenize.fk\") (read_file \"$S/rag-embed.fk\") (read_file \"$S/rag-index-codec.fk\") (read_file \"$S/rag-retrieve.fk\") (read_file \"$S/rag-ask.fk\") (read_file \"$S/form-cli-ask.fk\") (read_file \"$S/form-cli.fk\"))"
BAND="(read_file \"$S/form-cli-repl.fk\")"
FLAT_CHAIN="form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk form-stdlib/fkc-table-serialize.fk form-stdlib/hati-os-kernel-emit.fk form-stdlib/form-parse.fk form-stdlib/form-flatten.fk"
echo "(fks-table-file (flt-band-sources-fns $MODS $BAND) (flt-band-sources-pool $MODS $BAND))" > /tmp/flatten.fk
"$GB" $FLAT_CHAIN /tmp/flatten.fk > form-stdlib/bootstrap/form-cli-table.txt
fourth_hash16 "${FORM_CLI_SRCS[@]}" > form-stdlib/bootstrap/form-cli.stamp
EMIT_CHAIN="form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk form-stdlib/host-io-fs-fkwu-emit.fk form-stdlib/fkc-table-serialize.fk form-stdlib/hati-os-kernel-emit.fk"
d="$(mktemp -d)"
printf '(fkc-emit-combined-repl "%s")\n' "$(cat form-stdlib/bootstrap/form-cli-table.txt)" > "$d/emit.fk"
"$GB" $EMIT_CHAIN "$d/emit.fk" > form-stdlib/bootstrap/form-cli-emitted.c
rm -rf "$d"
echo "regen: form-cli-emitted.c ($(wc -c < form-stdlib/bootstrap/form-cli-emitted.c | tr -d ' ') bytes) stamp=$(cat form-stdlib/bootstrap/form-cli.stamp)"
