#!/usr/bin/env bash
# satsang voice — start the local door into the circle. Everything stays on this Mac.
set -euo pipefail
cd "$(dirname "$0")"

# 1. ensure the local LLM daemon is up (offerings need it; the transcript flows without it)
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "  starting ollama daemon…"
  (ollama serve >/tmp/satsang-ollama.log 2>&1 &) ; sleep 2
fi
MODEL="${SATSANG_OLLAMA_MODEL:-qwen2.5:7b}"
if ! ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
  echo "  the offering model '$MODEL' isn't pulled yet."
  echo "  pull it once (a few GB):   ollama pull $MODEL"
  echo "  …starting anyway — you'll get the live transcript now, offerings once it's pulled."
fi

# 2. compile the native on-device sound classifier if needed (names animals, music, …)
[ -x ./sound_classify ] || { echo "  compiling sound classifier…"; swiftc -O sound_classify.swift -o sound_classify; }

# 3. run (the venv holds mlx-whisper; everything else is stdlib + ffmpeg + the native binary)
echo "  open  http://localhost:${SATSANG_PORT:-8777}  in your browser"
exec .venv/bin/python satsang_voice.py
