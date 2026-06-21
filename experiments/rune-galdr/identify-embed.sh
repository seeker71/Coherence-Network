#!/usr/bin/env bash
# identify-embed.sh — clear speaker recognition: ECAPA oracle + Form recognizer.
#
# Slide over a (separated) voice; for each window the ECAPA oracle (ecapa_embed.py) emits a
# 192-d embedding, and the Form body (speaker-embed.fk: se-name / se-confident? over the
# enrolled roster) decides who it is — or "unknown" below the floor/margin. The roster is
# PRIVATE biometric data (~/.coherence-network/recordings/speakers-embed.json); the
# who-spoke-when timeline is PRIVATE — held in awareness, never committed.
#
#   identify-embed.sh VOICE.wav START DUR HOP N [FLOOR MARGIN]
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM="$(cd "$SCRIPT_DIR/../.." && pwd)/form"
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
VENV_PY="$HOME/.coherence-network/demucs-venv/bin/python"
ROSTER_JSON="$HOME/.coherence-network/recordings/speakers-embed.json"
[[ -x "$KERNEL" ]] || { echo "FAIL kernel not built (run validate.sh on speaker-embed)"; exit 1; }
[[ -f "$ROSTER_JSON" ]] || { echo "FAIL no roster — run enroll-embed.sh first"; exit 1; }
V="${1:?voice wav}"; START="${2:-0}"; DUR="${3:-3}"; HOP="${4:-30}"; N="${5:-20}"
FLOOR="${6:-250000}"; MARGIN="${7:-60000}"   # cosine×1e6 space: floor 0.25, margin 0.06

# Form roster literal from the private JSON
ROSTER="$(python3 -c "import json;r=json.load(open('$ROSTER_JSON'));print('(list '+' '.join('(list \"%s\" (list %s))'%(n,' '.join(map(str,v))) for n,v in r)+')')")"
echo "[identify] $(basename "$V")  ${START}s→$(python3 -c "print(int($START+$N*$HOP))")s  roster=$(python3 -c "import json;print(len(json.load(open('$ROSTER_JSON'))))")  (PRIVATE)"

i=0
"$VENV_PY" "$SCRIPT_DIR/ecapa_embed.py" "$V" "$START" "$DUR" "$HOP" "$N" 2>/dev/null | while IFS= read -r emb; do
  t=$(python3 -c "print(int($START+$i*$HOP))")
  drv="$(mktemp /tmp/spk.XXXX.fk)"
  printf '(do (print (se-name (list %s) %s)) (print (se-confident? (list %s) %s %s %s)) (print (se-sim (list %s) %s)))\n' \
    "$emb" "$ROSTER" "$emb" "$ROSTER" "$FLOOR" "$MARGIN" "$emb" "$ROSTER" > "$drv"
  out="$(cd "$FORM" && "$KERNEL" form-stdlib/speaker-embed.fk "$drv" 2>/dev/null | grep -vE '^\(|null' )"
  rm -f "$drv"
  name="$(echo "$out" | sed -n '1p')"; conf="$(echo "$out" | sed -n '2p')"; sim="$(echo "$out" | sed -n '3p')"
  who="$name"; [[ "$conf" != "1" ]] && who="unknown"
  printf "  %d:%02d  %-9s  cos=%.2f\n" $((t/60)) $((t%60)) "$who" "$(python3 -c "print(${sim:-0}/1e6)")"
  i=$((i+1))
done
