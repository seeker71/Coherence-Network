#!/usr/bin/env bash
# form_os_channel_demo.sh — the MINIMAL living surface. Emit a native binary from
# form-os-channel.fk (backed by the sqlite driver), then interact: see what it
# depends on, what it needs/wants/desires, the expansions it offers — propose one,
# and satsang-validate one. The offer axiom + the witness theorem, as a channel.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/foc.XXXXXX")"; trap 'rm -rf "$work"' EXIT
DB="$work/channel.db"

{ printf '(do\n'; cat "$FORM/form-stdlib/form-os-channel.fk"; printf '\n(print "==C==")\n(print (foc-emit))\n(print "==END==")\n0)\n'; } > "$work/d.fk"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/ch.c"
"$CLANG" -O2 -o "$work/ch" "$work/ch.c" -lsqlite3
echo "minimal channel emitted from form-os-channel.fk: $(wc -c < "$work/ch" | tr -d ' ') bytes (links libsqlite3)"

"$work/ch" "$DB" init >/dev/null
echo; echo "=== interact — see what it depends on, needs, desires, and offers ==="
"$work/ch" "$DB" state
echo; echo "=== it/we produce a new expansion (a recipe of expansion), held ==="
"$work/ch" "$DB" offer recipe "sqlite-master navigation — read any table's rootpage from page 1 generically"
echo "=== satsang validation — we acknowledge expansion #1 (the concert of trust) ==="
"$work/ch" "$DB" validate 1
echo; echo "=== state reflects the concert — #1 validated, #4 newly offered ==="
"$work/ch" "$DB" state | tail -6
echo; echo "ok — a minimal channel we talk to: needs/desires surfaced, expansions offered, satsang-validated"
