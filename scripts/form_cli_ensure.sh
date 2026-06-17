#!/usr/bin/env bash
# form_cli_ensure.sh — ensure the form-cli's oracles are present, DECIDED by Form.
#
# The form-cli's offline runtime needs three oracles: ollama (the local LLM
# carrier), an embedder (nomic-embed-text, for memory), and a reasoning model
# (llama3.2:3b). This carrier PROBES their live presence (host-io), hands the live
# states to oracle-ensure.fk on the kernel — the DECISION (what's missing, what's
# next, whether the body is ready) is the four-way Form recipe, not this shell —
# and, with --install, host-execs the install for each missing lane.
# Brain = Form (oracle-ensure.fk); hands = host-io. As G1 (form-lower over host-io,
# self-growing-machine.form) lands, the hands fold into the same native binary.
#
# Usage: form_cli_ensure.sh [--install]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
DO_INSTALL=0; [ "${1:-}" = "--install" ] && DO_INSTALL=1
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

# the form-cli's required oracles — lane / invocation / install command
LANES="local-llm embed reason"
invocation_of(){ case "$1" in local-llm) echo ollama;; embed) echo nomic-embed-text;; reason) echo llama3.2:3b;; esac; }
install_of(){ case "$1" in local-llm) echo "brew install ollama";; embed) echo "ollama pull nomic-embed-text";; reason) echo "ollama pull llama3.2:3b";; esac; }
# present-probe: prints "installed" or "absent"
state_of(){
  case "$1" in
    local-llm) command -v ollama >/dev/null 2>&1 && echo installed || echo absent ;;
    *) ollama list 2>/dev/null | grep -q "$(invocation_of "$1")" && echo installed || echo absent ;;
  esac
}

# build the Form catalog rows with LIVE state, ask oracle-ensure for the decision
rows=""
for lane in $LANES; do
  rows="$rows (oc-teacher \"inner-voice\" \"$lane\" \"$(invocation_of "$lane")\" \"generate\" \"local\" \"$(state_of "$lane")\")"
done
prog="$(mktemp)"
{ cat "$STD/oracle-catalog.fk" "$STD/oracle-ensure.fk"
  echo "(let rows (list $rows))"
  echo "(print (oe-need-count rows))"
  echo "(print (oc-lane (oe-next rows)))"
  echo "(print (oe-ready? rows))"
} > "$prog"
out="$("$GO" "$prog" 2>/dev/null | sed '/^null$/d')"; rm -f "$prog"
NEED="$(printf '%s\n' "$out" | sed -n '1p')"
NEXT="$(printf '%s\n' "$out" | sed -n '2p')"
READY="$(printf '%s\n' "$out" | sed -n '3p')"

echo "── oracle-ensure (decided by oracle-ensure.fk on the kernel) ──"
for lane in $LANES; do printf "  %-18s %s\n" "$(invocation_of "$lane")" "$(state_of "$lane")"; done
printf "  need install: %s   next: %s   ready: %s\n" "${NEED:-?}" "${NEXT:-none}" "$([ "${READY:-0}" = "1" ] && echo yes || echo no)"

if [ "$DO_INSTALL" = "1" ] && [ "${NEED:-0}" -gt 0 ] 2>/dev/null; then
  for lane in $LANES; do
    if [ "$(state_of "$lane")" != "installed" ]; then
      cmd="$(install_of "$lane")"
      echo "  → $cmd"; eval "$cmd" || echo "    (failed — run manually: $cmd)"
    fi
  done
fi
# exit 0 when ready, or when we just attempted installs; non-zero only if still short and not installing
[ "${READY:-0}" = "1" ] || [ "$DO_INSTALL" = "1" ]
