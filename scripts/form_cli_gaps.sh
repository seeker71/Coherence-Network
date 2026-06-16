#!/usr/bin/env bash
# form_cli_gaps.sh — the catalog of what is OPEN, walked from the live body.
#
# Gathers the three lanes of openness and renders them through the Form gaps
# recipe (form-cli-gaps.fk) — the ladder logic (rung, next move, offline-closable,
# stage-before-flight) is Form; this shell is a thin carrier that gathers facts
# and formats. The headline numbers (open / offline-closable / stage-before-flight
# / flight-ready) are computed by the recipe, not here.
#
#   open IDEA       — an idea slug no spec references        → author a spec
#   open SPEC       — a non-draft spec with no test/proof    → write a band
#   open CAPABILITY — an oracle-catalog teacher lane, placed  → climb the ladder
#                     on the ladder by its (trust, state)
#
# Usage: scripts/form_cli_gaps.sh            # full catalog
#        scripts/form_cli_gaps.sh --stage    # only the stage-before-flight items
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
ONLY_STAGE=0; [[ "${1:-}" == "--stage" ]] && ONLY_STAGE=1
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

# ── gather lane 1: open ideas (idea slugs no spec references) ────────────────
ideas_tmp="$(mktemp)"; specideas_tmp="$(mktemp)"; trap 'rm -f "$ideas_tmp" "$specideas_tmp"' EXIT
find "$ROOT/ideas" -maxdepth 1 -name '*.md' 2>/dev/null | while IFS= read -r f; do
    b="$(basename "$f" .md)"; case "$b" in INDEX|TEMPLATE|MANIFEST|README) ;; *) echo "$b";; esac
done | sort > "$ideas_tmp"
grep -hE '^\s*idea_id\s*:' "$ROOT"/specs/*.md 2>/dev/null | sed -E 's/.*idea_id\s*:\s*//; s/["'"'"']//g; s/[[:space:]]*$//' | sort -u > "$specideas_tmp"
OPEN_IDEAS="$(comm -23 "$ideas_tmp" "$specideas_tmp")"

# ── gather lane 2: open specs (non-draft, no test: and no proof:) ────────────
OPEN_SPECS=""
for f in "$ROOT"/specs/*.md; do
    b="$(basename "$f" .md)"; case "$b" in INDEX|TEMPLATE|MANIFEST) continue;; esac
    fm="$(awk 'NR==1&&/^---/{f=1;next} /^---/{if(f)exit} f' "$f")"
    printf '%s\n' "$fm" | grep -qiE '^\s*status\s*:\s*draft' && continue
    printf '%s\n' "$fm" | grep -qE '^\s*(test|proof)\s*:' || OPEN_SPECS="$OPEN_SPECS $b"
done

# ── gather lane 3: open capabilities — ASK the recipe, not the source ────────
# evaluate oracle-catalog's oc-catalog on the kernel and emit (lane|trust|state)
# per real teacher row. The recipe maps (trust,state) onto the ladder rung.
captmp="$(mktemp)"; trap 'rm -f "$ideas_tmp" "$specideas_tmp" "$captmp"' EXIT
{ cat "$STD/oracle-catalog.fk"
  echo '(defn gaps-cap-row (xs) (if (eq (len xs) 0) 0 (do (print (str_concat (oc-lane (head xs)) (str_concat "|" (str_concat (oc-trust (head xs)) (str_concat "|" (oc-state (head xs))))))) (gaps-cap-row (tail xs)))))'
  echo '(gaps-cap-row (oc-catalog))'
} > "$captmp"
CAP_ROWS="$("$GO" "$captmp" 2>/dev/null | grep '|')"

# ── build the Form program: the recipe classifies + tallies everything ──────
prog="$(mktemp)"; out="$(mktemp)"; trap 'rm -f "$ideas_tmp" "$specideas_tmp" "$captmp" "$prog" "$out"' EXIT
{
    cat "$STD/form-cli-gaps.fk"
    echo '(defn gaps-emit (x) (print (str_concat "ITEM|" (str_concat (gaps-i-kind x) (str_concat "|" (str_concat (gaps-i-id x) (str_concat "|" (str_concat (gaps-i-rung x) (str_concat "|" (str_concat (gaps-i-next x) (str_concat "|" (str_concat (int_to_str (gaps-i-offline? x)) (str_concat "|" (int_to_str (gaps-i-stage? x)))))))))))))))'
    echo '(defn gaps-emit-all (xs) (if (eq (len xs) 0) 0 (do (gaps-emit (head xs)) (gaps-emit-all (tail xs)))))'
    printf '(let items (list'
    while IFS= read -r s; do [[ -n "$s" ]] && printf ' (gaps-item "idea" "%s" (gaps-rung-no-spec))' "$s"; done <<< "$OPEN_IDEAS"
    for s in $OPEN_SPECS; do printf ' (gaps-item "spec" "%s" (gaps-rung-no-proof))' "$s"; done
    while IFS='|' read -r lane trust state; do
        [[ -z "$lane" ]] && continue
        printf ' (gaps-item "capability" "%s" (gaps-rung-from-oracle "%s" "%s"))' "$lane" "$trust" "$state"
    done <<< "$CAP_ROWS"
    printf '))\n'
    echo '(gaps-emit-all items)'
    echo '(let cat (gaps-catalog items))'
    echo '(print "TALLY")'
    echo '(print (gaps-cat-open-count cat))'
    echo '(print (gaps-cat-idea-count cat))'
    echo '(print (gaps-cat-spec-count cat))'
    echo '(print (gaps-cat-capability-count cat))'
    echo '(print (gaps-cat-offline-count cat))'
    echo '(print (gaps-cat-stage-count cat))'
    echo '(print (gaps-cat-flight-ready? cat))'
} > "$prog"
"$GO" "$prog" 2>"${GAPS_DEBUG:-/dev/null}" > "$out"
[[ -n "${GAPS_DEBUG:-}" ]] && cp "$prog" "$GAPS_DEBUG.prog"

# ── render ──────────────────────────────────────────────────────────────────
echo "── the open-gap catalog (walked from the body) ──"
render_lane() {
    local want="$1" title="$2" shown=0
    while IFS='|' read -r tag kind id rung next offline stage; do
        [[ "$tag" != "ITEM" || "$kind" != "$want" ]] && continue
        [[ "$ONLY_STAGE" -eq 1 && "$stage" != "1" ]] && continue
        if [[ "$shown" -eq 0 ]]; then printf "\n%s\n" "$title"; shown=1; fi
        local flag="offline-ok"; [[ "$stage" == "1" ]] && flag="⚑ STAGE BEFORE FLIGHT"
        printf "  %-26s [%-12s] → %-32s %s\n" "$id" "$rung" "$next" "$flag"
    done < "$out"
}
render_lane idea       "open IDEAS (no form spec):"
render_lane spec       "open SPECS (no validation):"
render_lane capability "open CAPABILITIES (model leans on an oracle):"

TVALS="$(awk '/^TALLY$/{f=1;next} f{v=$0;gsub(/[[:space:]]/,"",v);if(v!=""){print v;n++}} n>=7{exit}' "$out" | paste -sd' ' -)"
read -r T_OPEN T_IDEA T_SPEC T_CAP T_OFF T_STAGE T_FLIGHT <<< "$TVALS"
echo
echo "── tally ──"
printf "  open total         %s   (ideas %s · specs %s · capabilities %s)\n" "$T_OPEN" "$T_IDEA" "$T_SPEC" "$T_CAP"
printf "  offline-closable   %s   (workable air-gapped, right now)\n" "$T_OFF"
printf "  stage before flight %s   (need the network FIRST — stage these before you lose it)\n" "$T_STAGE"
if [[ "${T_FLIGHT:-0}" == "1" ]]; then
    echo "  flight-ready       yes — every open gap can be worked offline."
else
    echo "  flight-ready       NO  — stage the ⚑ items above before the network goes dark."
fi
