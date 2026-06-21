#!/usr/bin/env bash
# mesh_dispatch.sh — run the body's mesh-dispatch decision on a message BODY.
#
# Carrier-last: the DECISION is form/form-stdlib/mesh-dispatch.fk (four-way proven,
# md-route / md-verdict / md-boundary). This thin marshaller only hands the message
# to the kernel and prints what the recipe decided — it holds NO dispatch logic.
# The message is passed through a file (read_file) so no quote-escaping is needed.
#
#   mesh_dispatch.sh "<message body>"   (or piped on stdin)
# Prints three lines:
#   <route: gold|ask>
#   <verdict: 1 clear | 0 fear | 2 none>
#   <boundary: the human's words for where the fear sat>
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) >/dev/null 2>&1

msg="${1:-$(cat)}"
mf="$(mktemp)"; df="$(mktemp)"
printf '%s' "$msg" > "$mf"
# read the message from the file (no literal-escaping); print the three decisions.
# mesh-dispatch's primitives are all kernel-native, so it runs standalone — no need
# for the BML core.fk prelude (which would need the source-compiler to load).
{
  printf '(do\n'
  printf '  (let m (read_file "%s"))\n' "$mf"
  printf '  (print (md-route m))\n'
  printf '  (print (md-verdict m))\n'
  printf '  (print (md-boundary m)))\n'
} > "$df"
"$GO" "$STD/mesh-dispatch.fk" "$df" 2>/dev/null | sed '/^null$/d'
rm -f "$mf" "$df"
