#!/usr/bin/env bash
# form_cli_native.sh — the ONE generic front-door stager for the native form-cli.
#
# The form-cli LOGIC is Form (form/form-stdlib/form-cli.fk dispatches to the
# proven lane recipes). What this shell is — and ALL it is — is the thin carrier
# that turns an argv command into a kernel run of that ONE dispatch recipe. It
# replaces the bespoke per-command orchestration for every PURE-COMPUTE subcommand
# (eval / predict / score / judge / review-gap): no per-command script, no
# per-command argparse, no per-command stdout-parse — the routing is Form.
#
# WHY a carrier remains at all (named honestly): a high-level Form recipe reads its
# command via a passed STRING argument. The kernel's fk-buf (argv[3] -> fk_src,
# tag 17) is the low-level BMF cursor, not yet reachable from the defn grammar — so
# this stager stages the argv command as a string literal into the program it runs.
# When the kernel reads argv-as-strings natively at the high-grammar level, even
# this single stager composts.
#
# Usage:
#   form_cli_native.sh eval '(... a Form value expr ...)'
#       Compute a Form value through the eval lane. Zero tokens, no Python.
#       e.g.  form_cli_native.sh eval '(mul 17 23)'        -> 391
#
#   form_cli_native.sh <subcommand> --args '<lane arg exprs, space-separated>'
#       Route <subcommand> (predict|score|judge|review-gap) to its lane recipe
#       over the explicit Form args (the per-lane arg shapes are documented in
#       form/form-stdlib/form-cli.fk's fcli-dispatch). The stager wraps the args
#       in one (list ...), so pass the bare lane args, not an outer list.
#       e.g.  form_cli_native.sh judge --args '(list 80 40 90 55) 60'   -> 2
#             form_cli_native.sh review-gap --args '(list 80 40 90) (list 75 70 88) 10' -> 1
#
# Host-io-gated subcommands (ask/rag need HTTP POST; gaps/ingest need a
# directory-scan) keep their own carriers until those host-io ops land — see the
# header of form/form-stdlib/form-cli.fk.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
SUB="${1:-}"
[ -n "$SUB" ] || { echo 'usage: form_cli_native.sh <eval|predict|score|judge|review-gap> ...' >&2; exit 2; }
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

# build the lane args list (a Form expression). For eval the value IS the second
# arg; for the other lanes the caller passes --args '(<lane args>)'.
case "$SUB" in
    eval)
        VAL="${2:?eval needs a Form value expression}"
        ARGS="(list $VAL)"
        ;;
    predict|score|judge|review-gap)
        [ "${2:-}" = "--args" ] || { echo "$SUB needs --args '(<lane args>)'" >&2; exit 2; }
        ARGS="(list ${3:?--args needs a Form args list})"
        ;;
    *)
        echo "form_cli_native: '$SUB' is not a native pure-compute lane." >&2
        echo "  pure-compute lanes: eval predict score judge review-gap" >&2
        echo "  host-io-gated (own carriers): ask rag gaps ingest" >&2
        exit 2
        ;;
esac

# stage the command STRING + the lane args, run the ONE dispatch recipe.
# (The lane recipes use only kernel-native ops — add/sub/eq/nth/list + the string
# ops — so the BML-dialect core.fk prelude is not needed at the high-grammar run
# path here; the four-way band carries core.fk through the source-compiler.)
prog="$(mktemp)"; trap 'rm -f "$prog"' EXIT
printf '(print (fcli-dispatch "%s" %s))\n' "$SUB" "$ARGS" > "$prog"
# the printed verdict is the first line; the kernel echoes the top-level do-value
# (null) after it, so take the verdict line only.
"$GO" "$STD/form-cli-predict.fk" "$STD/form-cli-score.fk" \
      "$STD/form-cli-judge.fk" "$STD/form-cli-review-gap.fk" \
      "$STD/form-cli.fk" "$prog" | sed -n '1p'
