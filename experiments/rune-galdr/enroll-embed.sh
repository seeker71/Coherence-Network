#!/usr/bin/env bash
# enroll-embed.sh — enroll speaker voiceprints with the ECAPA oracle (the clear recognizer).
#
# For each speaker, take a PUBLIC voice clip, lift the voice off any music with Demucs
# (separate-galdr.sh), embed it with the ECAPA oracle (ecapa_embed.py), and write the 192-d
# embedding to a PRIVATE roster (~/.coherence-network/recordings/speakers-embed.json). The
# roster is biometric — never committed. Recognition uses form-stdlib/speaker-embed.fk.
#
#   enroll-embed.sh NAME=clip.wav [NAME=clip.wav ...]
#   enroll-embed.sh            # re-embed whatever is already in recordings/speakers/*.16k.wav
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$HOME/.coherence-network/demucs-venv/bin/python"
SPK="$HOME/.coherence-network/recordings/speakers"
SEP="$SPK/sep/htdemucs"
ROSTER="$HOME/.coherence-network/recordings/speakers-embed.json"
mkdir -p "$SPK"

names=()
if [[ $# -gt 0 ]]; then
  for arg in "$@"; do
    n="${arg%%=*}"; clip="${arg#*=}"
    sox "$clip" -c 1 -r 16000 "$SPK/$n.16k.wav" 2>/dev/null
    "$SCRIPT_DIR/separate-galdr.sh" "$SPK/$n.16k.wav" >/dev/null 2>&1 || true
    names+=("$n")
  done
else
  for w in "$SPK"/*.16k.wav; do [[ -f "$w" ]] && names+=("$(basename "$w" .16k.wav)"); done
fi

tmp="$(mktemp)"; echo "[" > "$tmp"; first=1
for n in "${names[@]}"; do
  v="$SEP/$n.16k/vocals.wav"; [[ -f "$v" ]] || v="$SPK/$n.16k.wav"
  emb="$("$VENV_PY" "$SCRIPT_DIR/ecapa_embed.py" "$v" 2>/dev/null)"
  [[ -z "$emb" ]] && { echo "  $n: embed failed" >&2; continue; }
  arr="$(echo "$emb" | tr ' ' ',')"
  [[ $first -eq 0 ]] && echo "," >> "$tmp"; first=0
  printf '["%s",[%s]]' "$n" "$arr" >> "$tmp"
  echo "  enrolled $n (192-d)" >&2
done
echo "]" >> "$tmp"; mv "$tmp" "$ROSTER"
echo "[enroll] roster → $ROSTER (PRIVATE, $(python3 -c "import json;print(len(json.load(open('$ROSTER'))))") speakers)" >&2
