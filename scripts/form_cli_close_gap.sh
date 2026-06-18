#!/usr/bin/env bash
# form_cli_close_gap.sh — close a Form recipe gap OFFLINE with a local oracle.
#
# The offline self-improvement loop, made concrete: name a gap (a recipe the
# body does not yet have), let a LOCAL coder oracle draft it in the Form .fk
# dialect, VALIDATE the draft on the kernel against a known assertion, and ledger
# the crossing through the Form membrane recipe. No network is touched — the
# oracle is a local model, the validator is the local kernel.
#
# This is the gap half of the membrane: a crossing where native-avail=0 (no
# native recipe yet). A validated draft turns the gap into a candidate recipe;
# the crossing is recorded local-oracle, outcome success, so the flywheel can
# later retire even this oracle once the class is covered.
#
# Usage:
#   form_cli_close_gap.sh "<gap-name>" "<recipe-spec>" "<assert-expr>" "<expected>" [oracle]
# Example:
#   form_cli_close_gap.sh triangular \
#     "(tri n) returns the nth triangular number n*(n+1)/2" \
#     "(tri 5)" 15 "ollama run coder"
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT/form/form-kernel-go"; GO="$GO_DIR/bin-go"
STD="$ROOT/form/form-stdlib"
GAP="${1:?gap-name}"; SPEC="${2:?recipe-spec}"; ASSERT="${3:?assert-expr}"; EXPECT="${4:?expected}"
ORACLE="${5:-ollama run coder}"
# optional 6th arg: space-separated stdlib basenames preluded BEFORE the draft, so a
# recipe that composes existing cells (e.g. form-asm primitives for a lowering step)
# validates against them instead of failing on unbound symbols. The lever steps all
# need this — they build on form-asm/form-lower.
PRELUDE="${6:-}"
[[ -x "$GO" ]] || ( cd "$GO_DIR" && go build -o bin-go . ) 2>/dev/null

echo "── close gap: $GAP (oracle: $ORACLE, offline) ──"

# 1. Build the coder prompt — constrain hard to the Lisp .fk dialect ----------
prompt="$(cat <<EOF
You write Form recipes in the Lisp .fk dialect for a content-addressed kernel.
Dialect: (defn name (args) body). Calls are prefix: (add a b) (sub a b)
(mul a b) (div a b) (eq a b) (lt a b) (gt a b) (if c then else) (let x v)
(do e1 e2 ...) (list ...) (nth l i) (head l) (tail l) (len l) (print x).
There are NO infix operators, NO semicolons, NO 'def', NO 'return'. Integers only.

EXAMPLE — a recipe (sq n) = n*n:
;;;BEGIN
(defn sq (n) (mul n n))
;;;END

You MAY call functions already defined in these preludes (do not redefine them): ${PRELUDE:-none}

TASK: write a recipe for: $SPEC
Output ONLY the recipe between ;;;BEGIN and ;;;END markers. No prose.
EOF
)"

# 2-4. Draft + validate, ITERATIVELY. Local models over-reason (wrap a simple body
# in let/do/nth); on a failed Go-validate we feed the kernel error + the failed
# draft back and tighten the ask, retrying up to FORM_CLI_CLOSE_TRIES times. No
# remote oracle — the same LOCAL model converges with feedback. host-exec only.
DRAFTS="$STD/drafts"; mkdir -p "$DRAFTS"
pf="$(mktemp)"; raw="$(mktemp)"; val="$(mktemp)"; draft="$DRAFTS/${GAP}.fk"
trap 'rm -f "$pf" "$raw" "$val"' EXIT
OUTCOME="fail"; GOT=""; COST=0; feedback=""; tries="${FORM_CLI_CLOSE_TRIES:-3}"
for attempt in $(seq 1 "$tries"); do
    { printf '%s' "$prompt"; [ -n "$feedback" ] && printf '\n\n%s' "$feedback"; } > "$pf"
    a0=$(date +%s)
    # `ollama run` streams through a TUI that rewraps long lines with cursor-control
    # escapes (ESC[2D ESC[K), corrupting a draft mid-token — and stripping the escapes
    # leaves the overwritten fragment. The HTTP API (/api/generate) returns CLEAN text.
    # Use it for ollama; run any other oracle (claude -p, …) as a command.
    case "$ORACLE" in
      "ollama run "*)
        jq -Rs --arg m "${ORACLE#ollama run }" '{model:$m,prompt:.,stream:false}' < "$pf" \
          | curl -sS --max-time 600 http://localhost:11434/api/generate -d @- 2>/dev/null \
          | jq -r '.response // ""' > "$raw" ;;
      *)
        COLUMNS=100000 $ORACLE < "$pf" 2>/dev/null | LC_ALL=C sed $'s/\x1b\\[[0-9;]*[A-Za-z]//g' > "$raw" ;;
    esac
    a1=$(date +%s); COST=$((COST + a1 - a0))
    awk '/;;;BEGIN/{f=1;next} /;;;END/{f=0} f' "$raw" > "$draft"
    [[ -s "$draft" ]] || awk '/```/{f=!f;next} f' "$raw" > "$draft"
    [[ -s "$draft" ]] || grep -E '^\(defn ' "$raw" > "$draft"
    echo "[1] attempt $attempt: drafted $(grep -c . "$draft" 2>/dev/null | tr -d ' ') line(s)"
    sed 's/^/     /' "$draft"
    { for p in $PRELUDE; do cat "$STD/$p" 2>/dev/null; done; cat "$draft"; echo "(print $ASSERT)"; } > "$val"
    GOT="$("$GO" "$val" 2>/dev/null | tr -d '[:space:]')"
    case "$GOT" in
        ${EXPECT}*) OUTCOME="success"; echo "[2] kernel validated: $ASSERT = $GOT (expected $EXPECT) ✓"; break ;;
        *) echo "[2] attempt $attempt rejected: $ASSERT = '$GOT' (expected $EXPECT) ✗"
           feedback="Your previous attempt was:
$(cat "$draft")
It FAILED on the kernel: $ASSERT gave '$GOT' but must equal $EXPECT. Output ONLY the single (defn ...) the task names, its body exactly the expression given — NO let, NO do, NO nth, NO extra arguments to the recipes you call." ;;
    esac
done

# 5. Ledger the crossing through the Form membrane recipe ----------------------
# native-avail=0 (this was a gap); surface=local-oracle; the note is the gap.
led="$(mktemp)"; trap 'rm -f "$pf" "$raw" "$val" "$led"' EXIT
# core.fk is BML (needs the source-compiler) and cannot be raw-cat;
# core-native.fk is the native-dialect prelude that gives nil? for raw kernel eval.
{ cat "$STD/core-native.fk"
  cat "$STD/tool-channel.fk" "$STD/choice-receipt.fk" "$STD/form-cli-membrane.fk"
  echo "(let cx (fcm-crossing \"close-gap:$GAP\" \"cap.recipe.synthesis\" (fcm-surface-local-oracle) 0 \"gap: $GAP — drafted by local coder oracle\" \"$OUTCOME\" 85 $COST))"
  echo '(print (fcm-x-gap? cx))'
  echo '(print (fcm-crossing-valid? cx "form-cli" "form_cli_close_gap" 20260616))'
} > "$led"
L_GAP=""; L_VALID=""; i=0
while IFS= read -r line; do
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [[ -z "$line" || "$line" == "null" ]] && continue
    case $i in 0) L_GAP="$line";; 1) L_VALID="$line";; esac; i=$((i+1))
done < <("$GO" "$led" 2>/dev/null)
echo "[3] ledger crossing: surface=local-oracle gap=$L_GAP receipt-valid=$L_VALID outcome=$OUTCOME"

# 6. Capture the turn as a training sample (success AND fail both teach) ------
if [[ -x "$ROOT/scripts/form_cli_capture.sh" ]]; then
    bash "$ROOT/scripts/form_cli_capture.sh" --gap \
        "close gap $GAP: $SPEC" \
        "draft a Form recipe with a local coder oracle; the kernel validates it against $ASSERT" \
        "$(cat "$draft" 2>/dev/null | head -c 800)" \
        "$OUTCOME" "$(printf '%s' "$ORACLE" | sed 's/.* //')" 2>/dev/null | sed 's/^/   capture: /'
fi

# 7. Verdict ------------------------------------------------------------------
if [[ "$OUTCOME" == "success" ]]; then
    echo "── gap '$GAP' CLOSED offline → draft kept at form/form-stdlib/drafts/${GAP}.fk"
    echo "   next: name an assertion band and add to the manifest to make it four-way."
    exit 0
else
    echo "── gap '$GAP' NOT closed this pass (draft kept for inspection). Re-run or refine the spec."
    exit 1
fi
